#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
verify="$root/scripts/verify-native-data-core-assets.sh"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

cp -R "$root/deploy" "$root/postgresql" "$root/redis" "$root/systemd" "$tmp/"

assert_rejected() {
  label=$1
  secret=$2
  if output=$("$verify" "$tmp" 2>&1); then
    printf '%s\n' "test failed: $label was accepted" >&2
    exit 1
  fi
  case "$output" in
    *"$secret"*) printf '%s\n' "test failed: $label leaked a value" >&2; exit 1 ;;
  esac
}

"$verify" "$tmp" >/dev/null

secret='STAGE09_TEST_SECRET_VALUE'
printf '%s\n' "host stage09_p1 stage09_p1 0.0.0.0/0 scram-sha-256 # $secret" >> "$tmp/postgresql/stage09-p1-hba.conf.fragment"
assert_rejected 'public hba rule' "$secret"
sed -i '$d' "$tmp/postgresql/stage09-p1-hba.conf.fragment"

printf '%s\n' 'port 6379' >> "$tmp/redis/redis-stage09-p1.conf"
assert_rejected 'redis TCP port' "$secret"
sed -i '$d' "$tmp/redis/redis-stage09-p1.conf"

sed -i '/\\if :{?stage09_p1_database_password}/d' "$tmp/deploy/stage09-native/postgresql/stage09-p1-bootstrap.sql"
assert_rejected 'empty password guard' "$secret"
cp "$root/deploy/stage09-native/postgresql/stage09-p1-bootstrap.sql" "$tmp/deploy/stage09-native/postgresql/stage09-p1-bootstrap.sql"

printf '%s\n' 'NoNewPrivileges=no' >> "$tmp/systemd/stage09-p1-redis.service"
assert_rejected 'unsafe systemd override' "$secret"

printf '%s\n' 'native data-core asset tests: PASS'
