#!/bin/sh
# Repository-safe regression checks for Stage09 N2 native service assets.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
renderer="$script_dir/render-nginx-config.sh"
verifier="$script_dir/verify-native-service-assets.sh"
tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT HUP INT TERM

fail() {
    printf '%s\n' "$1: FAIL" >&2
    exit 1
}

assert_contains() {
    assertion_name=$1
    expected=$2
    actual_file=$3
    grep -Fqx "$expected" "$actual_file" || fail "$assertion_name"
    printf '%s\n' "$assertion_name: PASS"
}

assert_exact_sse_location_contains() {
    assertion_name=$1
    expected=$2
    rendered_file=$3
    location_file="$tmpdir/sse-location"

    awk '
        $0 == "    location = /api/stage08/assistant/query-stream {" {
            in_location = 1
            found = 1
        }
        in_location {
            print
        }
        in_location && $0 == "    }" {
            exit
        }
        END {
            if (!found) {
                exit 1
            }
        }
    ' "$rendered_file" > "$location_file" || fail "$assertion_name-location"

    grep -Fqx "$expected" "$location_file" || fail "$assertion_name"
    printf '%s\n' "$assertion_name: PASS"
}

assert_rejected_without_value_leak() {
    assertion_name=$1
    rejected_value=$2
    status=0
    output=$(STAGE09_P1_NGINX_BIND_ADDRESS="$rejected_value" \
        STAGE09_P1_NGINX_INTERNAL_PORT=18090 \
        STAGE09_P1_CADDY_SOURCE_CIDR=127.0.0.1/32 \
        sh "$renderer" 2>&1) || status=$?
    [ "$status" -ne 0 ] || fail "$assertion_name"
    case "$output" in
        *"$rejected_value"*) fail "$assertion_name" ;;
    esac
    [ "$output" = 'nginx-render: fail' ] || fail "$assertion_name"
    printf '%s\n' "$assertion_name: PASS"
}

copy_asset_fixture() {
    fixture_root=$1
    mkdir -p "$fixture_root/scripts" "$fixture_root/systemd" "$fixture_root/nginx"
    cp "$verifier" "$fixture_root/scripts/verify-native-service-assets.sh"
    cp "$script_dir"/../systemd/stage09-p1-*.service "$fixture_root/systemd/"
    cp "$script_dir"/../nginx/stage09-p1.conf.template "$fixture_root/nginx/"
}

assert_fixture_verifier_rejects() {
    assertion_name=$1
    fixture_root=$2
    status=0
    output=$(sh "$fixture_root/scripts/verify-native-service-assets.sh" 2>&1) || status=$?
    [ "$status" -ne 0 ] || fail "$assertion_name"
    [ "$output" = 'native-service-assets: fail' ] || fail "$assertion_name"
    printf '%s\n' "$assertion_name: PASS"
}

sh -n "$renderer"
sh -n "$verifier"
sh -n "$0"
printf '%s\n' 'shell-syntax: PASS'

# POSIX shell negates bracket classes with !, not ^. Keep the CIDR input
# guard portable because the production renderer runs under Ubuntu dash.
grep -Fq '*[!0-9./]*' "$renderer" || fail 'portable-cidr-character-class'
printf '%s\n' 'portable-cidr-character-class: PASS'

STAGE09_P1_NGINX_BIND_ADDRESS=127.0.0.1 \
STAGE09_P1_NGINX_INTERNAL_PORT=18090 \
STAGE09_P1_CADDY_SOURCE_CIDR=127.0.0.1/32 \
    sh "$renderer" > "$tmpdir/stage09-p1.conf"
assert_contains 'safe-render-listen' '    listen 127.0.0.1:18090;' "$tmpdir/stage09-p1.conf"
assert_contains 'safe-render-caddy-allow' '    allow 127.0.0.1/32;' "$tmpdir/stage09-p1.conf"
assert_contains 'safe-render-static-root' '    root /var/www/stage09-p1/current;' "$tmpdir/stage09-p1.conf"
assert_contains 'safe-render-body-limit' '    client_max_body_size 16m;' "$tmpdir/stage09-p1.conf"
awk '
    /^    client_max_body_size 16m;$/ { body_limit = NR }
    /^    location / && !first_location { first_location = NR }
    END { exit !(body_limit && first_location && body_limit < first_location) }
' "$tmpdir/stage09-p1.conf" || fail 'safe-render-body-limit-order'
printf '%s\n' 'safe-render-body-limit-order: PASS'
assert_contains 'safe-render-api-loopback' '        proxy_pass http://127.0.0.1:18080;' "$tmpdir/stage09-p1.conf"
assert_exact_sse_location_contains 'sse-proxy-http-version' '        proxy_http_version 1.1;' "$tmpdir/stage09-p1.conf"
assert_exact_sse_location_contains 'sse-proxy-buffering' '        proxy_buffering off;' "$tmpdir/stage09-p1.conf"
assert_exact_sse_location_contains 'sse-proxy-cache' '        proxy_cache off;' "$tmpdir/stage09-p1.conf"
assert_exact_sse_location_contains 'sse-proxy-read-timeout' '        proxy_read_timeout 90s;' "$tmpdir/stage09-p1.conf"
assert_exact_sse_location_contains 'sse-x-accel-buffering' '        add_header X-Accel-Buffering no always;' "$tmpdir/stage09-p1.conf"
assert_exact_sse_location_contains 'sse-proxy-pass-preserved' '        proxy_pass http://127.0.0.1:18080;' "$tmpdir/stage09-p1.conf"
assert_exact_sse_location_contains 'sse-forward-host-preserved' '        proxy_set_header Host $host;' "$tmpdir/stage09-p1.conf"
assert_exact_sse_location_contains 'sse-forward-real-ip-preserved' '        proxy_set_header X-Real-IP $remote_addr;' "$tmpdir/stage09-p1.conf"
assert_exact_sse_location_contains 'sse-forward-for-preserved' '        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;' "$tmpdir/stage09-p1.conf"
assert_exact_sse_location_contains 'sse-forward-proto-preserved' '        proxy_set_header X-Forwarded-Proto $scheme;' "$tmpdir/stage09-p1.conf"

if command -v nginx >/dev/null 2>&1; then
    cat > "$tmpdir/nginx.conf" <<EOF
pid "$tmpdir/nginx.pid";
error_log "$tmpdir/error.log";
events {}
http {
    access_log "$tmpdir/access.log";
    include "$tmpdir/stage09-p1.conf";
}
EOF
    nginx -t -p "$tmpdir" -c "$tmpdir/nginx.conf" >/dev/null 2>&1 || fail 'nginx-config-syntax'
    printf '%s\n' 'nginx-config-syntax: PASS'
else
    printf '%s\n' 'nginx-config-syntax: SKIPPED'
fi

assert_rejected_without_value_leak 'public-bind' '0.0.0.0'
assert_rejected_without_value_leak 'stage03-marker' 'stage03-fixture'

status=0
output=$(STAGE09_P1_NGINX_BIND_ADDRESS=127.0.0.1 \
    STAGE09_P1_NGINX_INTERNAL_PORT=18090 \
    STAGE09_P1_CADDY_SOURCE_CIDR=0.0.0.0/0 \
    sh "$renderer" 2>&1) || status=$?
[ "$status" -ne 0 ] || fail 'public-cidr'
[ "$output" = 'nginx-render: fail' ] || fail 'public-cidr'
printf '%s\n' 'public-cidr: PASS'

status=0
output=$(STAGE09_P1_NGINX_BIND_ADDRESS=127.0.0.1 \
    STAGE09_P1_NGINX_INTERNAL_PORT=80 \
    STAGE09_P1_CADDY_SOURCE_CIDR=127.0.0.1/32 \
    sh "$renderer" 2>&1) || status=$?
[ "$status" -ne 0 ] || fail 'privileged-port'
[ "$output" = 'nginx-render: fail' ] || fail 'privileged-port'
printf '%s\n' 'privileged-port: PASS'

status=0
output=$(STAGE09_P1_NGINX_BIND_ADDRESS=127.0.0.1 \
    STAGE09_P1_NGINX_INTERNAL_PORT=443 \
    STAGE09_P1_CADDY_SOURCE_CIDR=127.0.0.1/32 \
    sh "$renderer" 2>&1) || status=$?
[ "$status" -ne 0 ] || fail 'https-port'
[ "$output" = 'nginx-render: fail' ] || fail 'https-port'
printf '%s\n' 'https-port: PASS'

copy_asset_fixture "$tmpdir/duplicate-user"
printf '%s\n' 'User=stage09-p1' >> "$tmpdir/duplicate-user/systemd/stage09-p1-api.service"
assert_fixture_verifier_rejects 'duplicate-user-directive' "$tmpdir/duplicate-user"

copy_asset_fixture "$tmpdir/extra-stage03"
printf '%s\n' '# stage03-docker-fixture' >> "$tmpdir/extra-stage03/systemd/stage09-p1-worker.service"
assert_fixture_verifier_rejects 'extra-stage03-marker' "$tmpdir/extra-stage03"

copy_asset_fixture "$tmpdir/api-stage03"
printf '%s\n' '# stage03-code-compatibility-is-not-allowed-here' >> "$tmpdir/api-stage03/systemd/stage09-p1-api.service"
assert_fixture_verifier_rejects 'api-stage03-marker' "$tmpdir/api-stage03"

copy_asset_fixture "$tmpdir/empty-security-reset"
printf '%s\n' 'NoNewPrivileges=' >> "$tmpdir/empty-security-reset/systemd/stage09-p1-api.service"
assert_fixture_verifier_rejects 'empty-security-reset' "$tmpdir/empty-security-reset"

copy_asset_fixture "$tmpdir/optional-preflight"
sed -i 's|^ExecStartPre=|ExecStartPre=-|' "$tmpdir/optional-preflight/systemd/stage09-p1-api.service"
assert_fixture_verifier_rejects 'optional-preflight' "$tmpdir/optional-preflight"

copy_asset_fixture "$tmpdir/spaced-no-new-privileges"
printf '%s\n' 'NoNewPrivileges = false' >> "$tmpdir/spaced-no-new-privileges/systemd/stage09-p1-api.service"
assert_fixture_verifier_rejects 'spaced-no-new-privileges' "$tmpdir/spaced-no-new-privileges"

copy_asset_fixture "$tmpdir/spaced-environment-file"
printf '%s\n' 'EnvironmentFile =' >> "$tmpdir/spaced-environment-file/systemd/stage09-p1-api.service"
assert_fixture_verifier_rejects 'spaced-environment-file' "$tmpdir/spaced-environment-file"

copy_asset_fixture "$tmpdir/spaced-preflight"
printf '%s\n' 'ExecStartPre = /bin/false' >> "$tmpdir/spaced-preflight/systemd/stage09-p1-api.service"
assert_fixture_verifier_rejects 'spaced-preflight' "$tmpdir/spaced-preflight"

copy_asset_fixture "$tmpdir/spaced-exec-start"
printf '%s\n' 'ExecStart = /bin/false' >> "$tmpdir/spaced-exec-start/systemd/stage09-p1-api.service"
assert_fixture_verifier_rejects 'spaced-exec-start' "$tmpdir/spaced-exec-start"

copy_asset_fixture "$tmpdir/spaced-root-user"
printf '%s\n' 'User = root' >> "$tmpdir/spaced-root-user/systemd/stage09-p1-api.service"
assert_fixture_verifier_rejects 'spaced-root-user' "$tmpdir/spaced-root-user"

sh "$verifier"
printf '%s\n' 'native-service-assets: PASS'

grep -Fqx 'ExecStart=/opt/stage09-p1/current-venv/bin/python -m app.workers.agent_event_outbox_runtime' \
    "$script_dir/../systemd/stage09-p1-agent-outbox-publisher.service" || fail 'stage10-publisher-unit'
grep -Fqx 'ExecStart=/opt/stage09-p1/current-venv/bin/python -m app.workers.agent_specialist_runtime' \
    "$script_dir/../systemd/stage09-p1-agent-tabular-worker.service" || fail 'stage10-worker-unit'
grep -Fq 'location ~ ^/api/stage10/agent-runs/' \
    "$script_dir/../nginx/stage09-p1.conf.template" || fail 'stage10-internal-sse-location'
grep -Fq 'location ~ ^/api/stage10/agent-runs/' \
    "$script_dir/../nginx/stage09-p1-public-https.conf.template" || fail 'stage10-public-sse-location'
printf '%s\n' 'stage10-native-assets: PASS'
