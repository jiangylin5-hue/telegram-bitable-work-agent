#!/bin/sh
# Repository-only contract tests for the Stage09 public-ingress assets.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
renderer="$script_dir/render-caddy-stage09-host.sh"
activator="$script_dir/activate-public-ingress.sh"
tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT HUP INT TERM

fail() {
    printf '%s\n' "public-ingress-assets: FAIL $1" >&2
    exit 1
}

[ -f "$renderer" ] || fail renderer-missing

assert_rendered_host() {
    rendered=$(
        STAGE09_P1_PUBLIC_HOSTNAME=agent.example.com \
        STAGE09_P1_CADDY_UPSTREAM_HOST=172.20.0.1 \
        STAGE09_P1_CADDY_UPSTREAM_PORT=18090 \
        sh "$renderer"
    ) || fail renderer-valid-input

    expected='# stage09-managed: agent.example.com
agent.example.com {
    reverse_proxy 172.20.0.1:18090
}'
    [ "$rendered" = "$expected" ] || fail renderer-output
}

assert_rejected_input() {
    hostname=$1
    upstream=$2
    port=$3
    output_file="$tmpdir/output"
    status=0
    STAGE09_P1_PUBLIC_HOSTNAME="$hostname" \
    STAGE09_P1_CADDY_UPSTREAM_HOST="$upstream" \
    STAGE09_P1_CADDY_UPSTREAM_PORT="$port" \
    sh "$renderer" >"$output_file" 2>/dev/null || status=$?
    [ "$status" -ne 0 ] || fail rejected-input-accepted
    [ ! -s "$output_file" ] || fail rejected-input-emitted-output
}

assert_rendered_host
assert_rejected_input localhost 172.20.0.1 18090
assert_rejected_input '*.example.com' 172.20.0.1 18090
assert_rejected_input 'agent example.com' 172.20.0.1 18090
assert_rejected_input 'agent.example.com/health' 172.20.0.1 18090
assert_rejected_input 8.8.8.8 172.20.0.1 18090
assert_rejected_input stage03.example.com 172.20.0.1 18090
assert_rejected_input stage07.example.com 172.20.0.1 18090
assert_rejected_input agent.example.com 8.8.8.8 18090
assert_rejected_input agent.example.com 127.0.0.1 18090
assert_rejected_input agent.example.com 172.20.0.1 443

assert_activator_contract() {
    [ -f "$activator" ] || fail activator-missing

    grep -Fq 'docker ps --format' "$activator" || fail activator-does-not-discover-caddy
    grep -Fq '/etc/caddy/Caddyfile' "$activator" || fail activator-does-not-locate-caddyfile
    grep -Fq 'docker exec "$caddy_id" cat /etc/caddy/Caddyfile > "$caddy_backup"' "$activator" || fail activator-does-not-read-live-caddyfile
    grep -Fq 'caddy validate --config - --adapter caddyfile' "$activator" || fail activator-does-not-validate-live-caddyfile
    grep -Fq 'caddy reload --config - --adapter caddyfile' "$activator" || fail activator-does-not-reload-live-caddyfile
    grep -Fq 'STAGE09_P1_CADDY_SOURCE_CIDR' "$activator" || fail activator-does-not-restrict-bridge
    grep -Fq 'nginx -t' "$activator" || fail activator-does-not-validate-nginx
    grep -Fq 'getent ahostsv4' "$activator" || fail activator-does-not-check-dns
    grep -Fq 'https://$hostname/health' "$activator" || fail activator-does-not-check-public-health
    grep -Fq 'until curl --fail --silent --show-error --max-time 15 "https://$hostname/health"' "$activator" || fail activator-does-not-wait-for-tls
    grep -Fq '[ "$attempt" -ge 12 ]' "$activator" || fail activator-does-not-bound-tls-wait
    grep -Fq 'rollback' "$activator" || fail activator-does-not-provide-rollback
    grep -Fq '[ "$status" -eq 0 ] && exit 0' "$activator" || fail activator-rolls-back-success

    if grep -Eq '(^|[;&|[:space:]])docker[[:space:]]+(stop|rm|restart)' "$activator"; then
        fail activator-manages-legacy-container-lifecycle
    fi
    if grep -Eq '(^|[;&|[:space:]])docker[[:space:]]+compose' "$activator"; then
        fail activator-uses-compose
    fi
    if grep -Fq '0.0.0.0' "$activator"; then
        fail activator-allows-public-bridge
    fi
    if grep -Fq 'host.docker.internal' "$activator"; then
        fail activator-uses-host-docker-internal
    fi
    if grep -Fq "*'|true')" "$activator"; then
        fail activator-requires-container-writable-mount
    fi
    if grep -Fq '>> "$caddyfile_host_path"' "$activator"; then
        fail activator-mutates-host-caddyfile
    fi
    if grep -Fq 'cp "$caddy_backup" "$caddyfile_host_path"' "$activator"; then
        fail activator-restores-host-caddyfile
    fi
}

assert_activator_contract

printf '%s\n' 'public-ingress-assets: PASS'
