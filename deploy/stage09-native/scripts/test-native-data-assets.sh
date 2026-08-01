#!/bin/sh
# Repository-safe regression checks for Stage09 N3 native data assets.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
asset_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
verifier="$script_dir/verify-native-data-assets.sh"
tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT HUP INT TERM

fail() {
    printf '%s\n' "$1: FAIL" >&2
    exit 1
}

grep -Fqx 'ExecStart=/opt/stage09-p1/current-venv/bin/alembic upgrade 20260730_0039' "$asset_root/systemd/stage09-p1-migrate.service" || fail migration-stage12-runtime-target

copy_assets() {
    destination=$1
    mkdir -p "$destination"
    cp -R "$asset_root/postgresql" "$asset_root/redis" "$asset_root/systemd" "$asset_root/scripts" "$destination/"
}

assert_verifier_passes() {
    assertion_name=$1
    fixture_root=$2
    status=0
    output=$(sh "$fixture_root/scripts/verify-native-data-assets.sh" 2>&1) || status=$?
    [ "$status" -eq 0 ] || fail "$assertion_name"
    [ "$output" = 'native-data-assets: pass' ] || fail "$assertion_name"
    printf '%s\n' "$assertion_name: PASS"
}

assert_verifier_rejects() {
    assertion_name=$1
    fixture_root=$2
    status=0
    output=$(sh "$fixture_root/scripts/verify-native-data-assets.sh" 2>&1) || status=$?
    [ "$status" -ne 0 ] || fail "$assertion_name"
    case "$output" in
        *n3-test-secret*|*198.51.100.10*|*stage03-fixture*) fail "$assertion_name" ;;
    esac
    [ "$output" = 'native-data-assets: fail' ] || fail "$assertion_name"
    printf '%s\n' "$assertion_name: PASS"
}

sh -n "$verifier"
sh -n "$0"
printf '%s\n' 'shell-syntax: PASS'

copy_assets "$tmpdir/safe"
assert_verifier_passes 'static-assets' "$tmpdir/safe"

copy_assets "$tmpdir/missing-password-guard"
sed -i 's/\\if :{?stage09_p1_database_password}/\\if false/' "$tmpdir/missing-password-guard/postgresql/stage09-p1-bootstrap.sql"
assert_verifier_rejects 'missing-password-guard' "$tmpdir/missing-password-guard"

copy_assets "$tmpdir/empty-password-guard"
sed -i 's/\\if :stage09_p1_password_present/\\if false/' "$tmpdir/empty-password-guard/postgresql/stage09-p1-bootstrap.sql"
assert_verifier_rejects 'empty-password-guard' "$tmpdir/empty-password-guard"

copy_assets "$tmpdir/unsafe-password-exit"
sed -i '0,/\\quit 1/{s/\\quit 1/\\quit 0/}' "$tmpdir/unsafe-password-exit/postgresql/stage09-p1-bootstrap.sql"
assert_verifier_rejects 'unsafe-password-exit' "$tmpdir/unsafe-password-exit"

copy_assets "$tmpdir/public-hba"
printf '%s\n' 'host stage09_p1 stage09_p1 198.51.100.10/32 scram-sha-256' >> "$tmpdir/public-hba/postgresql/stage09-p1-hba.conf.fragment"
assert_verifier_rejects 'public-hba' "$tmpdir/public-hba"

copy_assets "$tmpdir/socket-mismatch"
sed -i 's|^unixsocket /run/stage09-p1/redis.sock$|unixsocket /run/stage09-p1/not-the-p1-socket.sock|' "$tmpdir/socket-mismatch/redis/redis-stage09-p1.conf"
assert_verifier_rejects 'socket-mismatch' "$tmpdir/socket-mismatch"

copy_assets "$tmpdir/unsafe-redis-port"
printf '%s\n' 'port 6379' >> "$tmpdir/unsafe-redis-port/redis/redis-stage09-p1.conf"
assert_verifier_rejects 'unsafe-redis-port' "$tmpdir/unsafe-redis-port"

copy_assets "$tmpdir/redis-app-user"
sed -i 's/^User=stage09-redis$/User=stage09-p1/' "$tmpdir/redis-app-user/systemd/stage09-p1-redis.service"
assert_verifier_rejects 'redis-app-user' "$tmpdir/redis-app-user"

copy_assets "$tmpdir/redis-runtime-env"
printf '%s\n' 'EnvironmentFile=/etc/stage09-p1/runtime.env' >> "$tmpdir/redis-runtime-env/systemd/stage09-p1-redis.service"
assert_verifier_rejects 'redis-runtime-env' "$tmpdir/redis-runtime-env"

copy_assets "$tmpdir/redis-app-preflight"
printf '%s\n' 'ExecStartPre=/bin/false' >> "$tmpdir/redis-app-preflight/systemd/stage09-p1-redis.service"
assert_verifier_rejects 'redis-app-preflight' "$tmpdir/redis-app-preflight"

copy_assets "$tmpdir/redis-whitespace-override"
printf '%s\n' 'Group = stage09-redis-socket' >> "$tmpdir/redis-whitespace-override/systemd/stage09-p1-redis.service"
assert_verifier_rejects 'redis-whitespace-override' "$tmpdir/redis-whitespace-override"

copy_assets "$tmpdir/redis-empty-reset"
printf '%s\n' 'UMask=' >> "$tmpdir/redis-empty-reset/systemd/stage09-p1-redis.service"
assert_verifier_rejects 'redis-empty-reset' "$tmpdir/redis-empty-reset"

copy_assets "$tmpdir/migration-head"
sed -i 's/upgrade 20260730_0039/upgrade head/' "$tmpdir/migration-head/systemd/stage09-p1-migrate.service"
assert_verifier_rejects 'migration-head' "$tmpdir/migration-head"

copy_assets "$tmpdir/stage03"
printf '%s\n' '# stage03-fixture' >> "$tmpdir/stage03/postgresql/stage09-p1-hba.conf.fragment"
assert_verifier_rejects 'stage03-marker' "$tmpdir/stage03"

printf '%s\n' 'psql-live-validation: SKIPPED (repository-only)'
printf '%s\n' 'redis-live-validation: SKIPPED (repository-only)'
printf '%s\n' 'systemd-live-validation: SKIPPED (repository-only)'
printf '%s\n' 'native-data-assets: PASS'
