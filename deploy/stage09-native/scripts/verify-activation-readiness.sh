#!/bin/sh
# Fail-closed, bounded readiness verifier for a Stage09 release activation.
# It is intentionally read-only: callers perform switching and rollback.
set -eu

PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH

max_attempts=20
interval_seconds=2
loopback_health_url=http://127.0.0.1:18080/health

fail() {
    printf '%s\n' 'readiness-gate: fail' >&2
    exit 1
}

is_hostname() {
    candidate=$1
    [ -n "$candidate" ] && [ "${#candidate}" -le 253 ] || return 1
    case "$candidate" in
        .*|*..*|*.|*[!a-z0-9.-]*|*-) return 1 ;;
        *.*) ;;
        *) return 1 ;;
    esac

    previous_ifs=$IFS
    IFS=.
    set -- $candidate
    IFS=$previous_ifs
    for label in "$@"; do
        [ -n "$label" ] && [ "${#label}" -le 63 ] || return 1
        case "$label" in
            -*|*-) return 1 ;;
        esac
    done
}

is_acme_probe_path() {
    candidate=$1
    case "$candidate" in
        /.well-known/acme-challenge/*) ;;
        *) return 1 ;;
    esac
    case "$candidate" in
        *..*|*'//'|*[!A-Za-z0-9._/-]*) return 1 ;;
    esac
    suffix=${candidate#/.well-known/acme-challenge/}
    [ -n "$suffix" ] && [ "$suffix" = "${suffix#*/}" ]
}

http_status_is() {
    expected_status=$1
    target_url=$2
    actual_status=$(curl --silent --show-error --output /dev/null \
        --write-out '%{http_code}' --max-time 5 "$target_url" 2>/dev/null) || return 1
    [ "$actual_status" = "$expected_status" ]
}

services_active() {
    systemctl is-active --quiet \
        stage09-p1-api \
        stage09-p1-worker \
        stage09-p1-outbox-bridge \
        stage09-p1-redis \
        nginx >/dev/null 2>&1
}

core_ready() {
    services_active || return 1
    http_status_is 200 "$loopback_health_url" || return 1
    http_status_is 200 "$https_base/health"
}

listeners_and_data_boundary_safe() {
    listener_rows=$(ss -ltnp 2>/dev/null) || return 1
    nginx_http=0
    nginx_https=0

    while IFS= read -r listener_row; do
        case "$listener_row" in
            *':80 '*nginx*) nginx_http=1 ;;
        esac
        case "$listener_row" in
            *':443 '*nginx*) nginx_https=1 ;;
        esac
        case "$listener_row" in
            *':5432 '*)
                case "$listener_row" in
                    *'127.0.0.1:5432 '*|*'[::1]:5432 '*|*'::1:5432 '*) : ;;
                    *) return 1 ;;
                esac
                ;;
        esac
        case "$listener_row" in
            *':6379 '*) return 1 ;;
        esac
    done <<EOF
$listener_rows
EOF

    [ "$nginx_http" -eq 1 ] && [ "$nginx_https" -eq 1 ]
}

post_ready_checks() {
    http_status_is 200 "$https_base/" || return 1
    http_status_is 200 "$https_base/index.html" || return 1
    http_status_is 308 "$http_base/" || return 1
    http_status_is 200 "$http_base$acme_probe_path" || return 1
    listeners_and_data_boundary_safe
}

[ "$#" -eq 1 ] && [ "$1" = '--verify' ] || fail
for utility in systemctl curl ss sleep; do
    command -v "$utility" >/dev/null 2>&1 || fail
done

hostname=${STAGE09_P1_READINESS_HOSTNAME:-}
acme_probe_path=${STAGE09_P1_READINESS_ACME_PATH:-}
is_hostname "$hostname" || fail
is_acme_probe_path "$acme_probe_path" || fail

https_base="https://$hostname"
http_base="http://$hostname"

attempt=1
while [ "$attempt" -le "$max_attempts" ]; do
    if core_ready; then
        post_ready_checks && {
            printf '%s\n' 'readiness-gate: pass'
            exit 0
        }
        fail
    fi

    if [ "$attempt" -eq "$max_attempts" ]; then
        break
    fi
    sleep "$interval_seconds" >/dev/null 2>&1 || fail
    attempt=$((attempt + 1))
done

fail
