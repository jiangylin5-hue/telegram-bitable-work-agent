#!/bin/sh
# Render the Stage09 P1 internal-only Nginx template without exposing inputs.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
template="$script_dir/../nginx/stage09-p1.conf.template"

fail() {
    printf '%s\n' 'nginx-render: fail' >&2
    exit 1
}

has_forbidden_marker() {
    printf '%s\n' "$1" | grep -Eqi 'stage03|stage07|docker|compose|container|placeholder|\{\{|\}\}'
}

is_ipv4() {
    printf '%s\n' "$1" | awk -F. '
        BEGIN { valid = 1 }
        NF != 4 { valid = 0 }
        {
            for (part_index = 1; part_index <= 4; part_index++) {
                if ($part_index !~ /^[0-9]+$/ || $part_index < 0 || $part_index > 255) {
                    valid = 0
                }
            }
        }
        END { exit valid ? 0 : 1 }
    '
}

private_prefix_minimum() {
    printf '%s\n' "$1" | awk -F. '
        $1 == 10 || $1 == 127 { print 8; exit 0 }
        $1 == 172 && $2 >= 16 && $2 <= 31 { print 12; exit 0 }
        $1 == 192 && $2 == 168 { print 16; exit 0 }
        { exit 1 }
    '
}

is_private_or_loopback_address() {
    is_ipv4 "$1" || return 1
    private_prefix_minimum "$1" >/dev/null
}

is_nonpublic_cidr() {
    value=$1
    case "$value" in
        */*/*|/*|*/|*[!0-9./]*) return 1 ;;
    esac
    address=${value%/*}
    prefix=${value#*/}
    is_ipv4 "$address" || return 1
    case "$prefix" in
        ''|*[!0-9]*) return 1 ;;
    esac
    [ "$prefix" -ge 1 ] && [ "$prefix" -le 32 ] || return 1
    minimum=$(private_prefix_minimum "$address") || return 1
    [ "$prefix" -ge "$minimum" ]
}

is_unprivileged_port() {
    case "$1" in
        ''|*[!0-9]*) return 1 ;;
    esac
    [ "$1" -ge 1024 ] && [ "$1" -le 65535 ]
}

[ -r "$template" ] || fail
bind_address=${STAGE09_P1_NGINX_BIND_ADDRESS:-}
internal_port=${STAGE09_P1_NGINX_INTERNAL_PORT:-}
caddy_source_cidr=${STAGE09_P1_CADDY_SOURCE_CIDR:-}

[ -n "$bind_address" ] && [ -n "$internal_port" ] && [ -n "$caddy_source_cidr" ] || fail
has_forbidden_marker "$bind_address" && fail
has_forbidden_marker "$internal_port" && fail
has_forbidden_marker "$caddy_source_cidr" && fail
is_private_or_loopback_address "$bind_address" || fail
is_unprivileged_port "$internal_port" || fail
is_nonpublic_cidr "$caddy_source_cidr" || fail

grep -Fq '{{STAGE09_P1_NGINX_BIND_ADDRESS}}' "$template" || fail
grep -Fq '{{STAGE09_P1_NGINX_INTERNAL_PORT}}' "$template" || fail
grep -Fq '{{STAGE09_P1_CADDY_SOURCE_CIDR}}' "$template" || fail
if grep -Eqi 'stage03|stage07|docker|compose|container|placeholder' "$template"; then
    fail
fi

rendered=$(sed \
    -e "s|{{STAGE09_P1_NGINX_BIND_ADDRESS}}|$bind_address|g" \
    -e "s|{{STAGE09_P1_NGINX_INTERNAL_PORT}}|$internal_port|g" \
    -e "s|{{STAGE09_P1_CADDY_SOURCE_CIDR}}|$caddy_source_cidr|g" \
    "$template") || fail
printf '%s\n' "$rendered" | grep -Fq '{{' && fail
printf '%s\n' "$rendered"
