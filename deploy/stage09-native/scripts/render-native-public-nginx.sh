#!/bin/sh
# Render one public Nginx server block from fixed, release-sealed templates.
set -eu

fail() {
    printf '%s\n' 'native-public-nginx: fail' >&2
    exit 1
}

has_line_break() {
    candidate=$1
    line_feed=$(printf '\nx')
    line_feed=${line_feed%x}
    carriage_return=$(printf '\r')
    case "$candidate" in
        *"$line_feed"*|*"$carriage_return"*) return 0 ;;
        *) return 1 ;;
    esac
}

is_hostname() {
    candidate=$1
    [ -n "$candidate" ] && [ "${#candidate}" -le 253 ] || return 1
    has_line_break "$candidate" && return 1
    printf '%s\n' "$candidate" | grep -Eq '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$'
}

has_forbidden_marker() {
    case "$1" in
        *stage03*|*docker*|*caddy*) return 0 ;;
        *) return 1 ;;
    esac
}

is_file_path() {
    candidate=$1
    has_line_break "$candidate" && return 1
    case "$candidate" in
        /*) ;;
        *) return 1 ;;
    esac
    case "$candidate" in
        *..*|*'//'*) return 1 ;;
    esac
    printf '%s\n' "$candidate" | grep -Eq '^/[A-Za-z0-9._/-]+$'
}

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || fail
asset_root=$(CDPATH= cd -- "$script_dir/.." && pwd) || fail
hostname=${STAGE09_P1_PUBLIC_HOSTNAME:-}
mode=${STAGE09_P1_PUBLIC_MODE:-}

is_hostname "$hostname" || fail
has_forbidden_marker "$hostname" && fail

case "$mode" in
    http)
        template="$asset_root/nginx/stage09-p1-public-http.conf.template"
        certificate_path=
        certificate_key_path=
        ;;
    https)
        template="$asset_root/nginx/stage09-p1-public-https.conf.template"
        certificate_path=${STAGE09_P1_CERTIFICATE_PATH:-}
        certificate_key_path=${STAGE09_P1_CERTIFICATE_KEY_PATH:-}
        is_file_path "$certificate_path" || fail
        is_file_path "$certificate_key_path" || fail
        ;;
    *) fail ;;
esac

[ -r "$template" ] || fail
sed \
    -e "s|{{STAGE09_P1_PUBLIC_HOSTNAME}}|$hostname|g" \
    -e "s|{{STAGE09_P1_CERTIFICATE_PATH}}|$certificate_path|g" \
    -e "s|{{STAGE09_P1_CERTIFICATE_KEY_PATH}}|$certificate_key_path|g" \
    "$template" || fail
