#!/bin/sh
# Repository-safe regression checks for the Stage09 runtime preflight scripts.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
validator="$script_dir/validate-runtime-presence.sh"
tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT HUP INT TERM

write_fixture() {
    fixture_path=$1
    database_url=$2
    redis_url=$3
    extra_line=${4:-}
    printf '%s\n' \
        'APP_ENV=staging' \
        'POSTGRES_USER=stage09_p1' \
        'POSTGRES_PASSWORD=fixture-postgres-password' \
        'POSTGRES_DB=stage09_p1' \
        "DATABASE_URL=$database_url" \
        "REDIS_URL=$redis_url" \
        'TELEGRAM_WEBHOOK_SECRET=fixture-webhook-nonce' \
        'STAGE09_P1_ARTIFACT_ID=stage09-p1-20260722-fixture' \
        'STAGE09_P1_RELEASE_DIR=/opt/stage09-p1/releases/stage09-p1-20260722-fixture' \
        'STAGE09_P1_NGINX_INTERNAL_PORT=18090' \
        'TELEGRAM_SEND_MODE=dry_run' \
        'LLM_ENABLED=false' \
        'AGENT_WORKFLOW_MODE=fake' \
        'PROVIDER_MODE=disabled' \
        'AGENT_SAVE_FULL_PROMPT=false' \
        'AGENT_SAVE_FULL_RESPONSE=false' \
        'TELEGRAM_ALLOWED_CHAT_IDS=' \
        'TELEGRAM_ALLOWED_USER_IDS=' \
        'TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS=' \
        'STAGE06_NOTIFICATION_ALLOWED_CHAT_IDS=' > "$fixture_path"
    if [ -n "$extra_line" ]; then
        printf '%s\n' "$extra_line" >> "$fixture_path"
    fi
}

assert_pass() {
    assertion_name=$1
    fixture_path=$2
    if sh "$validator" "$fixture_path" >/dev/null 2>&1; then
        printf '%s\n' "$assertion_name: PASS"
        return 0
    fi
    printf '%s\n' "$assertion_name: FAIL" >&2
    exit 1
}

assert_rejected_without_value_leak() {
    assertion_name=$1
    fixture_path=$2
    status=0
    output=$(sh "$validator" "$fixture_path" 2>&1) || status=$?
    if [ "$status" -eq 0 ]; then
        printf '%s\n' "$assertion_name: FAIL" >&2
        exit 1
    fi
    case "$output" in
        *fixture-postgres-password*|*fixture-webhook-nonce*|*198.51.100.42*|*stage03-fixture*|*stage07-fixture*)
            printf '%s\n' "$assertion_name: FAIL" >&2
            exit 1
            ;;
    esac
    printf '%s\n' "$assertion_name: PASS"
}

loopback_db='postgresql+psycopg://stage09_p1:fixture-postgres-password@127.0.0.1:5432/stage09_p1'
socket_redis='unix:///run/stage09-p1/redis.sock?db=0'
unix_db='postgresql+psycopg://stage09_p1:fixture-postgres-password@/stage09_p1?host=/var/run/postgresql'

write_fixture "$tmpdir/loopback.env" "$loopback_db" "$socket_redis"
assert_pass 'canonical-postgres-loopback-and-redis-socket' "$tmpdir/loopback.env"

write_fixture "$tmpdir/unix.env" "$unix_db" "$socket_redis"
assert_pass 'canonical-unix-sockets' "$tmpdir/unix.env"

write_fixture "$tmpdir/query-host.env" "${loopback_db}?host=198.51.100.42" "$socket_redis"
assert_rejected_without_value_leak 'query-host-override' "$tmpdir/query-host.env"

write_fixture "$tmpdir/encoded-host.env" "${loopback_db}%3Fhost%3D198.51.100.42" "$socket_redis"
assert_rejected_without_value_leak 'encoded-host-override' "$tmpdir/encoded-host.env"

write_fixture "$tmpdir/public-host.env" "$loopback_db" 'redis://198.51.100.42:6379/0'
assert_rejected_without_value_leak 'public-host' "$tmpdir/public-host.env"

write_fixture "$tmpdir/legacy-socket.env" "$loopback_db" 'unix:///run/redis-stage09-p1/redis.sock?db=0'
assert_rejected_without_value_leak 'legacy-redis-socket' "$tmpdir/legacy-socket.env"

write_fixture "$tmpdir/stage03.env" "$loopback_db" "$socket_redis" 'DEPLOYMENT_NOTE=stage03-fixture'
assert_rejected_without_value_leak 'stage03-marker' "$tmpdir/stage03.env"

write_fixture "$tmpdir/stage07.env" "$loopback_db" "$socket_redis" 'DEPLOYMENT_NOTE=stage07-fixture'
assert_rejected_without_value_leak 'stage07-marker' "$tmpdir/stage07.env"

write_fixture "$tmpdir/allowlist.env" "$loopback_db" "$socket_redis" 'TELEGRAM_ALLOWED_CHAT_IDS=fixture-allowlist'
assert_rejected_without_value_leak 'nonempty-allowlist' "$tmpdir/allowlist.env"

write_fixture "$tmpdir/unsafe-mode.env" "$loopback_db" "$socket_redis"
sed -i 's/^TELEGRAM_SEND_MODE=dry_run$/TELEGRAM_SEND_MODE=unsafe-mode/' "$tmpdir/unsafe-mode.env"
assert_rejected_without_value_leak 'unsafe-mode' "$tmpdir/unsafe-mode.env"

printf '%s\n' 'runtime-preflight: PASS'
