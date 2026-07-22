#!/bin/sh
# Static, repository-safe contract check for the N4A release validators.
set -eu

fail() { printf '%s\n' 'release-assets: fail' >&2; exit 1; }
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || fail
layout="$script_dir/verify-release-layout.sh"
manifest="$script_dir/create-release-manifest.sh"
migration="$script_dir/verify-fixed-migration-offline.sh"
test_script="$script_dir/test-release-assets.sh"

for script in "$layout" "$manifest" "$migration" "$test_script" "$0"; do sh -n "$script" || fail; done
grep -Fq 'release_base=/opt/stage09-p1/releases' "$layout" || fail
grep -Fq 'static-assets: external-p1-b-required' "$layout" || fail
grep -Fq "find \"\$release_root\" -type l" "$layout" || fail
grep -Fq 'realpath "$release_root"' "$layout" || fail
for required_path in \
    backend/alembic.ini \
    backend/alembic/versions/20260720_0032_stage08_knowledge_indexing.py \
    deploy/stage09-native/runtime/runtime.env.example \
    deploy/stage09-native/nginx/stage09-p1.conf.template \
    deploy/stage09-native/postgresql/stage09-p1-bootstrap.sql \
    deploy/stage09-native/postgresql/stage09-p1-hba.conf.fragment \
    deploy/stage09-native/redis/redis-stage09-p1.conf \
    deploy/stage09-native/systemd/stage09-p1-api.service \
    deploy/stage09-native/systemd/stage09-p1-worker.service \
    deploy/stage09-native/systemd/stage09-p1-outbox-bridge.service \
    deploy/stage09-native/systemd/stage09-p1-redis.service \
    deploy/stage09-native/systemd/stage09-p1-migrate.service \
    deploy/stage09-native/scripts/validate-runtime-presence.sh \
    deploy/stage09-native/scripts/verify-native-isolation.sh \
    deploy/stage09-native/scripts/verify-native-service-assets.sh \
    deploy/stage09-native/scripts/verify-native-data-assets.sh \
    deploy/stage09-native/scripts/verify-release-layout.sh \
    deploy/stage09-native/scripts/create-release-manifest.sh \
    deploy/stage09-native/scripts/verify-fixed-migration-offline.sh \
    deploy/stage09-native/scripts/verify-release-assets.sh \
    deploy/stage09-native/scripts/inspect-native-host-readiness.sh
do
    grep -Fq "$required_path" "$layout" || fail
done
grep -Fq -- "-name '.env'" "$layout" || fail
grep -Fq -- "-name 'runtime.env'" "$layout" || fail
grep -Fq -- "-name '.git'" "$layout" || fail
grep -Fq -- "-name 'node_modules'" "$layout" || fail
grep -Fq -- "-name 'secrets'" "$layout" || fail
grep -Fq 'LC_ALL=C sort' "$manifest" || fail
grep -Fq 'sha256sum' "$manifest" || fail
grep -Fq 'mv -f "$temp_path" "$output_file"' "$manifest" || fail
grep -Fqx "offline_database_url='postgresql+psycopg://stage09_p1:offline-placeholder@127.0.0.1:5432/stage09_p1'" "$migration" || fail
[ "$(grep -Fc 'env -u DATABASE_URL "DATABASE_URL=$offline_database_url"' "$migration")" -eq 2 ] || fail
grep -Fq 'venv_root="/opt/stage09-p1/venv/$artifact_id"' "$migration" || fail
grep -Fq 'python_bin="$venv_root/bin/python"' "$migration" || fail
grep -Fq 'resolved_python=$(realpath "$python_bin") || fail' "$migration" || fail
grep -Fq '"$venv_root"/*|/usr/bin/python3|/usr/bin/python3.12' "$migration" || fail
grep -Fq 'for utility in env grep mktemp mv realpath rm; do' "$migration" || fail
if grep -Fq '[ ! -L "$python_bin" ]' "$migration"; then fail; fi
if grep -Fq 'python_bin="$resolved_python"' "$migration"; then fail; fi
if grep -Eq 'runtime\.env|source[[:space:]]|ads_agent' "$migration"; then fail; fi
grep -Fq 'cmp -s "$manifest_one" "$manifest_two"' "$test_script" || fail
grep -Fq 'fixture-secret-value' "$test_script" || fail
grep -Fq 'expected_executable=' "$test_script" || fail
grep -Fq '[ "$0" = "$expected_executable" ] || exit 94' "$test_script" || fail
grep -Fq 'fake-python-link-target' "$test_script" || fail
grep -Fq 'heads-fixed-stage09-offline-url' "$test_script" || fail
grep -Fq 'upgrade-fixed-stage09-offline-url' "$test_script" || fail
grep -Fq 'migration-external-python-symlink-accepted' "$test_script" || fail
grep -Fq 'migration-external-python-symlink-output-created' "$test_script" || fail
grep -Fq 'missing-critical-unit-layout-accepted' "$test_script" || fail
grep -Fq 'missing-critical-unit-manifest-accepted' "$test_script" || fail
grep -Fq 'stage09-p1-api.service' "$test_script" || fail
if grep -Eq 'cat[[:space:]]*>|<<' "$test_script"; then fail; fi
printf '%s\n' 'release-assets: pass'
