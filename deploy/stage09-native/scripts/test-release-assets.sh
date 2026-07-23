#!/bin/sh
# Repository-only fixtures for the sealed Stage09 release asset validators.
# The copied scripts below are intentionally retargeted only inside mktemp;
# production scripts retain their fixed /opt Stage09 paths.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
layout="$script_dir/verify-release-layout.sh"
manifest="$script_dir/create-release-manifest.sh"
migration="$script_dir/verify-fixed-migration-offline.sh"

fail() {
    printf '%s\n' "$1: FAIL" >&2
    exit 1
}

for script in "$layout" "$manifest" "$migration" "$0"; do
    sh -n "$script" || fail shell-syntax
done

for script in "$script_dir"/*.sh; do
    if grep -q "$(printf '\r')" "$script"; then
        fail shell-script-crlf
    fi
done
grep -Fq '[ -f "$script" ] && [ -x "$script" ] || fail' "$layout" || fail release-script-exec-contract

grep -Fq 'release_base=/opt/stage09-p1/releases' "$layout" || fail fixed-release-root
grep -Fq 'static-assets: external-p1-b-required' "$layout" || fail external-static-assets
grep -Fq "find \"\$release_root\" -type l" "$layout" || fail symlink-rejection
grep -Fq 'realpath "$release_root"' "$layout" || fail canonical-release-root
grep -Fq 'backend/alembic/versions/20260720_0032_stage08_knowledge_indexing.py' "$layout" || fail required-migration
grep -Fq 'deploy/stage09-native/runtime/runtime.env.example' "$layout" || fail required-runtime-example
grep -Fq 'deploy/stage09-native/nginx/stage09-p1.conf.template' "$layout" || fail required-nginx-template
grep -Fq 'deploy/stage09-native/nginx/stage09-p1-public-http.conf.template' "$layout" || fail required-public-http-template
grep -Fq 'deploy/stage09-native/nginx/stage09-p1-public-https.conf.template' "$layout" || fail required-public-https-template
grep -Fq 'deploy/stage09-native/postgresql/stage09-p1-bootstrap.sql' "$layout" || fail required-postgres-bootstrap
grep -Fq 'deploy/stage09-native/redis/redis-stage09-p1.conf' "$layout" || fail required-redis-config
grep -Fq 'deploy/stage09-native/systemd/stage09-p1-api.service' "$layout" || fail required-api-unit
grep -Fq 'deploy/stage09-native/systemd/stage09-p1-migrate.service' "$layout" || fail required-migrate-unit
grep -Fq 'deploy/stage09-native/scripts/inspect-native-host-readiness.sh' "$layout" || fail required-host-readiness
grep -Fq 'deploy/stage09-native/scripts/render-caddy-stage09-host.sh' "$layout" || fail required-caddy-renderer
grep -Fq 'deploy/stage09-native/scripts/activate-public-ingress.sh' "$layout" || fail required-public-ingress-activator
grep -Fq 'deploy/stage09-native/scripts/test-public-ingress-assets.sh' "$layout" || fail required-public-ingress-test
grep -Fq 'deploy/stage09-native/scripts/render-native-public-nginx.sh' "$layout" || fail required-native-public-renderer
grep -Fq 'deploy/stage09-native/scripts/test-native-public-ingress-assets.sh' "$layout" || fail required-native-public-ingress-test
grep -Fq "offline_database_url='postgresql+psycopg://stage09_p1:offline-placeholder@127.0.0.1:5432/stage09_p1'" "$migration" || fail fixed-offline-database-url
grep -Fq 'env -u DATABASE_URL "DATABASE_URL=$offline_database_url"' "$migration" || fail explicit-offline-database-url
if grep -Eq 'runtime\.env|source[[:space:]]|ads_agent' "$migration"; then fail migration-secret-or-history; fi
grep -Fq 'venv_root="/opt/stage09-p1/venv/$artifact_id"' "$migration" || fail fixed-python-root
grep -Fq 'python_bin="$venv_root/bin/python"' "$migration" || fail fixed-python
grep -Fq 'resolved_python=$(realpath "$python_bin") || fail' "$migration" || fail resolved-python
grep -Fq '"$venv_root"/*|/usr/bin/python3|/usr/bin/python3.12' "$migration" || fail allowed-python-targets
if grep -Fq '[ ! -L "$python_bin" ]' "$migration"; then fail migration-python-symlink-rejected; fi

bad_output=$(sh "$layout" /tmp/not-stage09 stage09-p1-fixture 2>&1) && fail invalid-release-root
[ "$bad_output" = 'release-layout: fail
artifact-id: unavailable' ] || fail invalid-release-root-output

bad_id_output=$(sh "$layout" /opt/stage09-p1/releases/stage09-p1-fixture 'bad/id' 2>&1) && fail invalid-artifact-id
[ "$bad_id_output" = 'release-layout: fail
artifact-id: unavailable' ] || fail invalid-artifact-id-output

fixture_root=$(mktemp -d "${TMPDIR:-/tmp}/stage09-release-assets.XXXXXX") || fail fixture-create
cleanup() { rm -rf "$fixture_root"; }
trap cleanup EXIT HUP INT TERM

fixture_scripts="$fixture_root/scripts"
fixture_release_base="$fixture_root/opt/stage09-p1/releases"
artifact_id=stage09-p1-fixture
release_root="$fixture_release_base/$artifact_id"
fixture_venv="$fixture_root/opt/stage09-p1/venv"
fixture_system_python="$fixture_root/usr/bin/python3"
fixture_realpath_bin="$fixture_root/fake-bin"
realpath_system=$(command -v realpath) || fail fixture-realpath-command
mkdir -p \
    "$fixture_scripts" \
    "$release_root" \
    "$fixture_venv/$artifact_id/bin" \
    "$fixture_realpath_bin" \
    "$(dirname -- "$fixture_system_python")" || fail fixture-tree

copy_with_fixed_release_base() {
    sed "s|release_base=/opt/stage09-p1/releases|release_base=$fixture_release_base|" "$1" > "$2" || fail fixture-copy
    chmod 700 "$2" || fail fixture-copy-mode
}

copy_with_fixed_release_base "$layout" "$fixture_scripts/verify-release-layout.sh"
copy_with_fixed_release_base "$manifest" "$fixture_scripts/create-release-manifest.sh"
copy_with_fixed_release_base "$migration" "$fixture_scripts/verify-fixed-migration-offline.sh"
# Retarget the fixed production system-python allowlist only in this isolated
# fixture, so the test can exercise the same resolved-target contract without
# relying on a Python installation supplied by the developer machine.
sed \
    -e "s|/opt/stage09-p1/venv|$fixture_venv|g" \
    -e "s|/usr/bin/python3.12|$fixture_system_python|g" \
    -e "s|/usr/bin/python3|$fixture_system_python|g" \
    "$fixture_scripts/verify-fixed-migration-offline.sh" > "$fixture_scripts/.migration.tmp" || fail fixture-migration-copy
mv -f "$fixture_scripts/.migration.tmp" "$fixture_scripts/verify-fixed-migration-offline.sh" || fail fixture-migration-copy
chmod 700 "$fixture_scripts/verify-fixed-migration-offline.sh" || fail fixture-migration-copy-mode

# Populate every current allowlisted P1-B requirement. The fixture contents
# are inert: this suite proves release completeness and sealing, not target
# host service behaviour.
for required_fixture_path in \
    backend/alembic.ini \
    backend/alembic/versions/20260720_0032_stage08_knowledge_indexing.py \
    deploy/stage09-native/runtime/runtime.env.example \
    deploy/stage09-native/nginx/stage09-p1.conf.template \
    deploy/stage09-native/nginx/stage09-p1-public-http.conf.template \
    deploy/stage09-native/nginx/stage09-p1-public-https.conf.template \
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
    deploy/stage09-native/scripts/inspect-native-host-readiness.sh \
    deploy/stage09-native/scripts/render-caddy-stage09-host.sh \
    deploy/stage09-native/scripts/activate-public-ingress.sh \
    deploy/stage09-native/scripts/test-public-ingress-assets.sh \
    deploy/stage09-native/scripts/render-native-public-nginx.sh \
    deploy/stage09-native/scripts/test-native-public-ingress-assets.sh
do
    fixture_asset="$release_root/$required_fixture_path"
    mkdir -p "$(dirname -- "$fixture_asset")" || fail fixture-asset-directory
    printf '%s\n' '# fixed Stage09 release fixture asset' > "$fixture_asset" || fail fixture-asset
    case "$required_fixture_path" in
        deploy/stage09-native/scripts/*.sh)
            chmod 700 "$fixture_asset" || fail fixture-script-mode
            ;;
    esac
done

crlf_probe="$release_root/deploy/stage09-native/scripts/activate-public-ingress.sh"
printf '\r\n' >> "$crlf_probe" || fail crlf-probe-write
crlf_output=$(sh "$fixture_scripts/verify-release-layout.sh" "$release_root" "$artifact_id" 2>&1) && fail crlf-shell-script-accepted
[ "$crlf_output" = 'release-layout: fail
artifact-id: unavailable' ] || fail crlf-shell-script-output
tr -d '\r' < "$crlf_probe" > "$fixture_scripts/.crlf-cleaned" || fail crlf-probe-clean
mv -f "$fixture_scripts/.crlf-cleaned" "$crlf_probe" || fail crlf-probe-clean
chmod 700 "$crlf_probe" || fail crlf-probe-clean-mode

crlf_unit_probe="$release_root/deploy/stage09-native/systemd/stage09-p1-api.service"
printf '\r\n' >> "$crlf_unit_probe" || fail crlf-unit-probe-write
crlf_unit_output=$(sh "$fixture_scripts/verify-release-layout.sh" "$release_root" "$artifact_id" 2>&1) && fail crlf-unit-accepted
[ "$crlf_unit_output" = 'release-layout: fail
artifact-id: unavailable' ] || fail crlf-unit-output
tr -d '\r' < "$crlf_unit_probe" > "$fixture_scripts/.crlf-unit-cleaned" || fail crlf-unit-probe-clean
mv -f "$fixture_scripts/.crlf-unit-cleaned" "$crlf_unit_probe" || fail crlf-unit-probe-clean

clean_layout_output=$(sh "$fixture_scripts/verify-release-layout.sh" "$release_root" "$artifact_id" 2>&1) || fail clean-layout
[ "$clean_layout_output" = "release-layout: pass
artifact-id: $artifact_id
static-assets: external-p1-b-required" ] || fail clean-layout-output

manifest_one="$fixture_root/manifest-one.sha256"
manifest_two="$fixture_root/manifest-two.sha256"
manifest_one_output=$(sh "$fixture_scripts/create-release-manifest.sh" "$release_root" "$artifact_id" "$manifest_one" 2>&1) || fail manifest-first
manifest_two_output=$(sh "$fixture_scripts/create-release-manifest.sh" "$release_root" "$artifact_id" "$manifest_two" 2>&1) || fail manifest-second
[ "$manifest_one_output" = "$manifest_two_output" ] || fail manifest-output-nondeterministic
cmp -s "$manifest_one" "$manifest_two" || fail manifest-bytes-nondeterministic
[ -s "$manifest_one" ] || fail manifest-empty
awk '
    {
        hash = substr($0, 1, 64)
        separator = substr($0, 65, 2)
        relative_path = substr($0, 67)
        if (length(hash) != 64 || hash !~ /^[0-9a-f]+$/ || separator != "  " || relative_path == "" || relative_path ~ /^\//) exit 1
    }
' "$manifest_one" || fail manifest-not-hash-only-relative
if grep -Fq "$fixture_root" "$manifest_one"; then fail manifest-absolute-path; fi

printf '%s\n' 'fixture-secret-value' > "$release_root/.env" || fail private-env-fixture
private_output=$(sh "$fixture_scripts/verify-release-layout.sh" "$release_root" "$artifact_id" 2>&1) && fail private-env-accepted
[ "$private_output" = 'release-layout: fail
artifact-id: unavailable' ] || fail private-env-output
case "$private_output" in *fixture-secret-value*) fail private-env-leak ;; esac
rm -f "$release_root/.env" || fail private-env-cleanup

# The repository ships one documented backend example. It is not a runtime
# secret and must remain admissible, while every other .env-style file stays
# forbidden by the sealed-release gate.
printf '%s\n' '# documented environment example' > "$release_root/backend/.env.example" || fail example-env-fixture
example_env_output=$(sh "$fixture_scripts/verify-release-layout.sh" "$release_root" "$artifact_id" 2>&1) || fail example-env-accepted
[ "$example_env_output" = "release-layout: pass
artifact-id: $artifact_id
static-assets: external-p1-b-required" ] || fail example-env-output
rm -f "$release_root/backend/.env.example" || fail example-env-cleanup

fake_marker="$fixture_root/fake-alembic.marker"
{
    printf '%s\n' '#!/bin/sh'
    printf '%s\n' 'set -eu'
    printf '%s\n' "expected='postgresql+psycopg://stage09_p1:offline-placeholder@127.0.0.1:5432/stage09_p1'"
    printf '%s\n' "expected_executable='$fixture_venv/$artifact_id/bin/python'"
    printf '%s\n' '[ "$0" = "$expected_executable" ] || exit 94'
    printf '%s\n' '[ "${DATABASE_URL-}" = "$expected" ] || exit 91'
    printf '%s\n' 'case "${DATABASE_URL-}" in *fixture-secret-value*|*ads_agent*) exit 92 ;; esac'
    printf '%s\n' 'marker=${FAKE_ALEMBIC_MARKER:?}'
    printf '%s\n' 'if [ "$#" -eq 3 ] && [ "$1" = '\''-m'\'' ] && [ "$2" = '\''alembic'\'' ] && [ "$3" = '\''heads'\'' ]; then'
    printf '%s\n' '    printf '\''%s\n'\'' '\''heads-fixed-stage09-offline-url'\'' >> "$marker"'
    printf '%s\n' '    printf '\''%s\n'\'' '\''20260720_0032 (head)'\'''
    printf '%s\n' 'elif [ "$#" -eq 5 ] && [ "$1" = '\''-m'\'' ] && [ "$2" = '\''alembic'\'' ] && [ "$3" = '\''upgrade'\'' ] && [ "$4" = '\''20260720_0032'\'' ] && [ "$5" = '\''--sql'\'' ]; then'
    printf '%s\n' '    printf '\''%s\n'\'' '\''upgrade-fixed-stage09-offline-url'\'' >> "$marker"'
    printf '%s\n' '    printf '\''%s\n'\'' '\''-- Stage09 fixed offline migration SQL'\'''
    printf '%s\n' '    printf '\''%s\n'\'' '\''-- 20260720_0032'\'''
    printf '%s\n' 'else'
    printf '%s\n' '    exit 93'
    printf '%s\n' 'fi'
} > "$fixture_system_python" || fail fake-python-write
chmod 700 "$fixture_system_python" || fail fake-python-mode
ln -s "$fixture_system_python" "$fixture_venv/$artifact_id/bin/python" || fail fake-python-link
# Git for Windows can materialize the fixture link as a copied file.  Retarget
# only this fixture's realpath so the contract still proves the POSIX target
# deploy will have: resolve validation must permit the system interpreter,
# while execution must retain the venv entrypoint path.
fixture_realpath="$fixture_realpath_bin/realpath"
{
    printf '%s\n' '#!/bin/sh'
    printf '%s\n' "if [ \"\$#\" -eq 1 ] && [ \"\$1\" = '$fixture_venv/$artifact_id/bin/python' ]; then"
    printf '%s\n' "    printf '%s\\n' '$fixture_system_python'"
    printf '%s\n' '    exit 0'
    printf '%s\n' 'fi'
    printf '%s\n' "exec '$realpath_system' \"\$@\""
} > "$fixture_realpath" || fail fixture-realpath-write
chmod 700 "$fixture_realpath" || fail fixture-realpath-mode
[ "$(PATH="$fixture_realpath_bin:$PATH" realpath "$fixture_venv/$artifact_id/bin/python")" = "$(realpath "$fixture_system_python")" ] || fail fake-python-link-target

migration_sql="$fixture_root/fixed-migration.sql"
migration_output=$(FAKE_ALEMBIC_MARKER="$fake_marker" DATABASE_URL='fixture-secret-value' PATH="$fixture_realpath_bin:$PATH" sh "$fixture_scripts/verify-fixed-migration-offline.sh" "$release_root" "$artifact_id" "$migration_sql" 2>&1) || fail migration-fixture
[ "$migration_output" = "migration-offline: pass
artifact-id: $artifact_id
migration-verified: true" ] || fail migration-output
case "$migration_output" in *fixture-secret-value*|*ads_agent*) fail migration-output-leak ;; esac
[ -f "$migration_sql" ] && grep -Fq '20260720_0032' "$migration_sql" || fail migration-sql
[ "$(cat "$fake_marker")" = 'heads-fixed-stage09-offline-url
upgrade-fixed-stage09-offline-url' ] || fail migration-fixed-url-or-command

external_python="$fixture_root/external/python3"
mkdir -p "$(dirname -- "$external_python")" || fail external-python-directory
cp "$fixture_system_python" "$external_python" || fail external-python-copy
chmod 700 "$external_python" || fail external-python-mode
rm -f "$fixture_venv/$artifact_id/bin/python" || fail external-python-unlink
ln -s "$external_python" "$fixture_venv/$artifact_id/bin/python" || fail external-python-link
if [ -L "$fixture_venv/$artifact_id/bin/python" ]; then
    external_sql="$fixture_root/external-migration.sql"
    external_output=$(FAKE_ALEMBIC_MARKER="$fake_marker" sh "$fixture_scripts/verify-fixed-migration-offline.sh" "$release_root" "$artifact_id" "$external_sql" 2>&1) && fail migration-external-python-symlink-accepted
    [ "$external_output" = 'migration-offline: fail
artifact-id: unavailable
migration-verified: false' ] || fail migration-external-python-symlink-output
    [ ! -e "$external_sql" ] || fail migration-external-python-symlink-output-created
    case "$external_output" in *fixture-secret-value*|*ads_agent*|*"$fixture_root"*) fail migration-external-python-symlink-leak ;; esac
fi

# A sealed release must reject a missing critical service unit before the
# manifest writer can create output. Both failures remain generic so neither
# fixture paths nor fixture contents can surface in diagnostics.
critical_unit="$release_root/deploy/stage09-native/systemd/stage09-p1-api.service"
rm -f "$critical_unit" || fail critical-unit-remove
missing_unit_layout_output=$(sh "$fixture_scripts/verify-release-layout.sh" "$release_root" "$artifact_id" 2>&1) && fail missing-critical-unit-layout-accepted
[ "$missing_unit_layout_output" = 'release-layout: fail
artifact-id: unavailable' ] || fail missing-critical-unit-layout-output
case "$missing_unit_layout_output" in *"$fixture_root"*|*fixture-secret-value*) fail missing-critical-unit-layout-leak ;; esac

missing_unit_manifest="$fixture_root/missing-critical-unit.sha256"
missing_unit_manifest_output=$(sh "$fixture_scripts/create-release-manifest.sh" "$release_root" "$artifact_id" "$missing_unit_manifest" 2>&1) && fail missing-critical-unit-manifest-accepted
[ "$missing_unit_manifest_output" = 'release-manifest: fail
artifact-id: unavailable
manifest-sha256: unavailable' ] || fail missing-critical-unit-manifest-output
[ ! -e "$missing_unit_manifest" ] || fail missing-critical-unit-manifest-created
case "$missing_unit_manifest_output" in *"$fixture_root"*|*fixture-secret-value*) fail missing-critical-unit-manifest-leak ;; esac

trap - EXIT HUP INT TERM
cleanup
printf '%s\n' 'release-assets: PASS'
