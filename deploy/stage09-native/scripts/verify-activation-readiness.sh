#!/bin/sh
# Fail-closed, bounded readiness verifier for a Stage09 release activation.
# It is intentionally read-only: callers perform switching and rollback.
set -eu

PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH

max_retry_attempts=20
interval_seconds=2
total_deadline_seconds=40
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

seconds_remaining() {
    current_epoch=$(date +%s 2>/dev/null) || return 1
    case "$current_epoch" in
        ''|*[!0-9]*) return 1 ;;
    esac
    remaining=$((deadline_epoch - current_epoch))
    [ "$remaining" -gt 0 ] || return 1
    printf '%s\n' "$remaining"
}

bounded_command() {
    remaining=$(seconds_remaining) || return 1
    timeout "$remaining" "$@" >/dev/null 2>&1 || return 1
    seconds_remaining >/dev/null
}

http_status_is() {
    expected_status=$1
    target_url=$2
    remaining=$(seconds_remaining) || return 1
    curl_timeout=$remaining
    [ "$curl_timeout" -le 5 ] || curl_timeout=5
    actual_status=$(timeout "$curl_timeout" curl \
        --silent --show-error --output /dev/null --write-out '%{http_code}' \
        --connect-timeout "$curl_timeout" --max-time "$curl_timeout" \
        "$target_url" 2>/dev/null) || return 1
    seconds_remaining >/dev/null || return 1
    [ "$actual_status" = "$expected_status" ]
}

services_active() {
    for unit in \
        stage09-p1-api \
        stage09-p1-worker \
        stage09-p1-outbox-bridge \
        stage09-p1-redis \
        nginx
    do
        bounded_command systemctl is-active --quiet "$unit" || return 1
    done
}

core_ready() {
    services_active || return 1
    http_status_is 200 "$loopback_health_url" || return 1
    http_status_is 200 "$https_base/health"
}

listener_row_owned_only_by_nginx() {
    printf '%s\n' "$1" | awk '
        {
            remaining = $0
            found = 0
            while (match(remaining, /"[^"]+"/)) {
                owner = substr(remaining, RSTART + 1, RLENGTH - 2)
                if (owner != "nginx") exit 1
                found = 1
                remaining = substr(remaining, RSTART + RLENGTH)
            }
            exit found ? 0 : 1
        }
    ' >/dev/null
}

listeners_and_data_boundary_safe() {
    remaining=$(seconds_remaining) || return 1
    listener_rows=$(timeout "$remaining" ss -ltnp 2>/dev/null) || return 1
    seconds_remaining >/dev/null || return 1
    nginx_http=0
    nginx_https=0

    while IFS= read -r listener_row; do
        case "$listener_row" in
            *':80 '*)
                listener_row_owned_only_by_nginx "$listener_row" || return 1
                nginx_http=1
                ;;
        esac
        case "$listener_row" in
            *':443 '*)
                listener_row_owned_only_by_nginx "$listener_row" || return 1
                nginx_https=1
                ;;
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
for utility in awk curl date sleep ss systemctl timeout; do
    command -v "$utility" >/dev/null 2>&1 || fail
done

hostname=${STAGE09_P1_READINESS_HOSTNAME:-}
acme_probe_path=${STAGE09_P1_READINESS_ACME_PATH:-}
is_hostname "$hostname" || fail
is_acme_probe_path "$acme_probe_path" || fail

start_epoch=$(date +%s 2>/dev/null) || fail
case "$start_epoch" in
    ''|*[!0-9]*) fail ;;
esac
deadline_epoch=$((start_epoch + total_deadline_seconds))
https_base="https://$hostname"
http_base="http://$hostname"

retry_attempt=0
while :; do
    if core_ready; then
        post_ready_checks && {
            printf '%s\n' 'readiness-gate: pass'
            exit 0
        }
        fail
    fi

    [ "$retry_attempt" -lt "$max_retry_attempts" ] || break
    remaining=$(seconds_remaining) || break
    [ "$remaining" -gt "$interval_seconds" ] || break
    sleep "$interval_seconds" || fail
    seconds_remaining >/dev/null || break
    retry_attempt=$((retry_attempt + 1))
done

fail
