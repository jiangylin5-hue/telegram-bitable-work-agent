#!/bin/sh
# Render the single Stage09 Caddy host block. This script only renders text;
# activation, validation, reload and rollback live in activate-public-ingress.sh.
set -eu

fail() {
    printf '%s\n' 'stage09 public Caddy renderer: invalid configuration' >&2
    exit 1
}

has_forbidden_marker() {
    printf '%s\n' "$1" | grep -Eqi 'stage03|stage07|docker|compose|container|placeholder'
}

is_ipv4() {
    value=$1
    old_ifs=$IFS
    IFS=.
    set -- $value
    IFS=$old_ifs
    [ "$#" -eq 4 ] || return 1

    for octet in "$@"; do
        case $octet in
            ''|*[!0-9]*) return 1 ;;
        esac
        [ "$octet" -ge 0 ] 2>/dev/null && [ "$octet" -le 255 ] 2>/dev/null || return 1
    done
}

is_private_ipv4() {
    value=$1
    is_ipv4 "$value" || return 1
    case $value in
        10.*|192.168.*) return 0 ;;
        172.*)
            second=$(printf '%s\n' "$value" | cut -d. -f2)
            [ "$second" -ge 16 ] 2>/dev/null && [ "$second" -le 31 ] 2>/dev/null
            return
            ;;
        *) return 1 ;;
    esac
}

is_hostname() {
    value=$1
    [ "${#value}" -le 253 ] || return 1
    case $value in
        *.*) ;;
        *) return 1 ;;
    esac
    printf '%s\n' "$value" | grep -Eq '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$'
}

hostname=${STAGE09_P1_PUBLIC_HOSTNAME:-}
upstream_host=${STAGE09_P1_CADDY_UPSTREAM_HOST:-}
upstream_port=${STAGE09_P1_CADDY_UPSTREAM_PORT:-}

[ -n "$hostname" ] || fail
[ -n "$upstream_host" ] || fail
[ "$upstream_port" = '18090' ] || fail
has_forbidden_marker "$hostname" && fail
has_forbidden_marker "$upstream_host" && fail
is_hostname "$hostname" || fail
is_ipv4 "$hostname" && fail
is_private_ipv4 "$upstream_host" || fail

printf '%s\n' \
    "# stage09-managed: $hostname" \
    "$hostname {" \
    "    reverse_proxy $upstream_host:$upstream_port" \
    '}'
