#!/bin/sh
# Repository-only contract tests for the Stage09 native public Nginx renderer.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
renderer="$script_dir/render-native-public-nginx.sh"

fail() {
    printf '%s\n' "$1: FAIL" >&2
    exit 1
}

assert_contains() {
    label=$1
    expected=$2
    actual=$3
    printf '%s\n' "$actual" | grep -Fqx "$expected" || fail "$label"
}

assert_failure() {
    label=$1
    shift
    output=$("$@" 2>&1) && fail "$label"
    [ "$output" = 'native-public-nginx: fail' ] || fail "$label"
}

http_output=$(STAGE09_P1_PUBLIC_HOSTNAME=stage07.jiangtest1.online \
    STAGE09_P1_PUBLIC_MODE=http \
    sh "$renderer") || fail http-render
assert_contains http-listen '    listen 80;' "$http_output"
assert_contains http-server-name '    server_name stage07.jiangtest1.online;' "$http_output"
assert_contains http-acme '        root /var/www/stage09-p1/acme;' "$http_output"
printf '%s\n' 'http-render: PASS'

https_output=$(STAGE09_P1_PUBLIC_HOSTNAME=stage07.jiangtest1.online \
    STAGE09_P1_PUBLIC_MODE=https \
    STAGE09_P1_CERTIFICATE_PATH=/etc/letsencrypt/live/stage07.jiangtest1.online/fullchain.pem \
    STAGE09_P1_CERTIFICATE_KEY_PATH=/etc/letsencrypt/live/stage07.jiangtest1.online/privkey.pem \
    sh "$renderer") || fail https-render
assert_contains https-listen '    listen 443 ssl http2;' "$https_output"
assert_contains api-loopback '        proxy_pass http://127.0.0.1:18080;' "$https_output"
printf '%s\n' 'https-render: PASS'

assert_failure invalid-hostname env \
    STAGE09_P1_PUBLIC_HOSTNAME='bad;server_name injected' \
    STAGE09_P1_PUBLIC_MODE=http \
    sh "$renderer"
printf '%s\n' 'invalid-hostname: PASS'

assert_failure empty-hostname env \
    STAGE09_P1_PUBLIC_HOSTNAME= \
    STAGE09_P1_PUBLIC_MODE=http \
    sh "$renderer"
printf '%s\n' 'empty-hostname: PASS'

assert_failure forbidden-marker env \
    STAGE09_P1_PUBLIC_HOSTNAME=stage03.jiangtest1.online \
    STAGE09_P1_PUBLIC_MODE=http \
    sh "$renderer"
printf '%s\n' 'forbidden-marker: PASS'

assert_failure missing-keypair env \
    STAGE09_P1_PUBLIC_HOSTNAME=stage07.jiangtest1.online \
    STAGE09_P1_PUBLIC_MODE=https \
    sh "$renderer"
printf '%s\n' 'missing-keypair: PASS'

if command -v nginx >/dev/null 2>&1; then
    fixture_dir=$(mktemp -d "${TMPDIR:-/tmp}/stage09-native-nginx.XXXXXX") || fail nginx-fixture
    cleanup() { rm -rf "$fixture_dir"; }
    trap cleanup EXIT HUP INT TERM
    {
        printf '%s\n' 'events {}'
        printf '%s\n' 'http {'
        printf '%s\n' "$http_output"
        printf '%s\n' '}'
    } > "$fixture_dir/nginx.conf" || fail nginx-fixture
    nginx -t -c "$fixture_dir/nginx.conf" -p "$fixture_dir" >/dev/null 2>&1 || fail nginx-config-syntax
    trap - EXIT HUP INT TERM
    cleanup
    printf '%s\n' 'nginx-config-syntax: PASS'
else
    printf '%s\n' 'nginx-config-syntax: SKIPPED'
fi
