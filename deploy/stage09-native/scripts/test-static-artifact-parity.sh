#!/bin/sh
# Isolated contract checks for the read-only Stage09 source/venv/static verifier.
set -eu

fail() { printf '%s\n' "static-parity-test: fail: $1" >&2; exit 1; }
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || fail script-directory
verifier="$script_dir/verify-static-artifact-parity.sh"
[ -f "$verifier" ] || fail missing-verifier
sh -n "$verifier" || fail verifier-syntax

fixture_root=$(mktemp -d "${TMPDIR:-/tmp}/stage09-static-parity.XXXXXX") || fail fixture-create
cleanup() { rm -rf "$fixture_root"; }
trap cleanup EXIT HUP INT TERM

artifact_id=stage09-p1-fixture
source_base="$fixture_root/opt/stage09-p1/releases"
venv_base="$fixture_root/opt/stage09-p1/venv"
static_base="$fixture_root/var/www/stage09-p1"
source_root="$source_base/$artifact_id"
venv_root="$venv_base/$artifact_id"
static_root="$static_base/$artifact_id"
fixture_verifier="$fixture_root/verify-static-artifact-parity.sh"

sed \
    -e "s|source_base=/opt/stage09-p1/releases|source_base=$source_base|" \
    -e "s|venv_base=/opt/stage09-p1/venv|venv_base=$venv_base|" \
    -e "s|static_base=/var/www/stage09-p1|static_base=$static_base|" \
    "$verifier" > "$fixture_verifier" || fail fixture-verifier
chmod 700 "$fixture_verifier" || fail fixture-verifier-mode

mkdir -p "$source_root/mini-app/dist" "$venv_root/bin" "$static_root/assets" || fail fixture-tree
printf '%s\n' '<!doctype html><title>handoff</title>' > "$source_root/mini-app/dist/browser-handoff.html" || fail source-handoff
printf '%s\n' '#!/bin/sh' 'exit 0' > "$venv_root/bin/python" || fail venv-python
chmod 700 "$venv_root/bin/python" || fail venv-python-mode
cp "$venv_root/bin/python" "$venv_root/bin/python3" || fail venv-python3
printf '%s\n' "#!$venv_root/bin/python3" 'exit 0' > "$venv_root/bin/uvicorn" || fail venv-uvicorn
printf '%s\n' "#!$venv_root/bin/python3" 'exit 0' > "$venv_root/bin/alembic" || fail venv-alembic
chmod 700 "$venv_root/bin/uvicorn" "$venv_root/bin/alembic" || fail venv-entrypoint-mode
printf '%s\n' '<!doctype html><link href="/assets/app.css"><script type="module" src="/assets/app.js"></script>' > "$static_root/index.html" || fail static-index
printf '%s\n' '<!doctype html><title>handoff</title>' > "$static_root/browser-handoff.html" || fail static-handoff
printf '%s\n' 'console.log("fixture")' > "$static_root/assets/app.js" || fail static-js
printf '%s\n' '.fixture { color: #1677ff; }' > "$static_root/assets/app.css" || fail static-css
printf '%s\n' "$artifact_id" > "$static_root/.stage09-static-artifact-id" || fail static-id

write_manifest() {
    (
        cd "$static_root" || exit 1
        find . -type f ! -name static-manifest.sha256 -print | LC_ALL=C sort | while IFS= read -r file; do
            relative_file=${file#./}
            hash=$(sha256sum "$relative_file" | awk '{print $1}') || exit 1
            printf '%s  %s\n' "$hash" "$relative_file"
        done
    ) > "$static_root/static-manifest.sha256"
}

write_manifest || fail static-manifest
pass_output=$(sh "$fixture_verifier" "$artifact_id" 2>&1) || fail valid-candidate
[ "$pass_output" = "static-parity: pass
artifact-id: $artifact_id" ] || fail valid-output

printf '%s\n' '#!/opt/stage09-p1/venv/stage09-p1-old/bin/python' 'exit 0' > "$venv_root/bin/uvicorn" || fail stale-venv-shebang-write
stale_shebang_output=$(sh "$fixture_verifier" "$artifact_id" 2>&1) && fail stale-venv-shebang-accepted
[ "$stale_shebang_output" = 'static-parity: fail
artifact-id: unavailable' ] || fail stale-venv-shebang-output
printf '%s\n' "#!$venv_root/bin/python3" 'exit 0' > "$venv_root/bin/uvicorn" || fail venv-uvicorn-restore

printf '%s\n' 'stage09-p1-wrong' > "$static_root/.stage09-static-artifact-id" || fail wrong-id-write
wrong_id_output=$(sh "$fixture_verifier" "$artifact_id" 2>&1) && fail mismatched-id-accepted
[ "$wrong_id_output" = 'static-parity: fail
artifact-id: unavailable' ] || fail mismatched-id-output
printf '%s\n' "$artifact_id" > "$static_root/.stage09-static-artifact-id" || fail right-id-write
write_manifest || fail right-id-manifest

rm -f "$static_root/assets/app.js" || fail asset-remove
missing_asset_output=$(sh "$fixture_verifier" "$artifact_id" 2>&1) && fail missing-referenced-asset-accepted
[ "$missing_asset_output" = 'static-parity: fail
artifact-id: unavailable' ] || fail missing-referenced-asset-output
printf '%s\n' 'console.log("fixture")' > "$static_root/assets/app.js" || fail asset-restore
write_manifest || fail restored-asset-manifest

printf '%s\n' 'console.log("mutated")' >> "$static_root/assets/app.js" || fail hash-mutation
hash_drift_output=$(sh "$fixture_verifier" "$artifact_id" 2>&1) && fail hash-drift-accepted
[ "$hash_drift_output" = 'static-parity: fail
artifact-id: unavailable' ] || fail hash-drift-output
write_manifest || fail restored-hash-manifest

printf '%s\n' 'not-a-manifest' > "$static_root/static-manifest.sha256" || fail malformed-manifest-write
malformed_output=$(sh "$fixture_verifier" "$artifact_id" 2>&1) && fail malformed-manifest-accepted
[ "$malformed_output" = 'static-parity: fail
artifact-id: unavailable' ] || fail malformed-manifest-output
write_manifest || fail restored-valid-manifest

link_root="$static_base/stage09-p1-linked"
ln -s "$static_root" "$link_root" 2>/dev/null || true
if [ -L "$link_root" ]; then
    linked_output=$(sh "$fixture_verifier" stage09-p1-linked 2>&1) && fail static-link-accepted
    [ "$linked_output" = 'static-parity: fail
artifact-id: unavailable' ] || fail static-link-output
fi

trap - EXIT HUP INT TERM
cleanup
printf '%s\n' 'static-parity-test: PASS'
