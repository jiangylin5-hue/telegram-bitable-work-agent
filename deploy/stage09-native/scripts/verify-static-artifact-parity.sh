#!/bin/sh
# Read-only verifier for one Stage09 source/venv/static candidate identity.
set -eu

source_base=/opt/stage09-p1/releases
venv_base=/opt/stage09-p1/venv
static_base=/var/www/stage09-p1

fail() {
    printf '%s\n' 'static-parity: fail' >&2
    printf '%s\n' 'artifact-id: unavailable' >&2
    exit 1
}

artifact_id=${1:-}
[ "$#" -eq 1 ] || fail
for utility in awk cat cmp find grep mktemp realpath rm sed sha256sum sort; do
    command -v "$utility" >/dev/null 2>&1 || fail
done
printf '%s\n' "$artifact_id" | grep -Eq '^stage09-p1-[a-z0-9][a-z0-9._-]*$' || fail
case "$artifact_id" in *latest*) fail ;; esac

source_root="$source_base/$artifact_id"
venv_root="$venv_base/$artifact_id"
static_root="$static_base/$artifact_id"

require_candidate_directory() {
    candidate=$1
    expected=$2
    [ "$candidate" = "$expected" ] || return 1
    [ -d "$candidate" ] && [ ! -L "$candidate" ] || return 1
    [ "$(realpath "$candidate")" = "$candidate" ] || return 1
    [ -z "$(find "$candidate" -type l -print -quit)" ]
}

require_candidate_directory "$source_root" "$source_base/$artifact_id" || fail
require_candidate_directory "$venv_root" "$venv_base/$artifact_id" || fail
require_candidate_directory "$static_root" "$static_base/$artifact_id" || fail

source_handoff="$source_root/mini-app/dist/browser-handoff.html"
venv_python="$venv_root/bin/python"
static_index="$static_root/index.html"
static_handoff="$static_root/browser-handoff.html"
static_marker="$static_root/.stage09-static-artifact-id"
static_manifest="$static_root/static-manifest.sha256"

for required in "$source_handoff" "$static_index" "$static_handoff" "$static_marker" "$static_manifest"; do
    [ -f "$required" ] && [ ! -L "$required" ] || fail
done
[ -x "$venv_python" ] || fail
for entrypoint in uvicorn alembic; do
    candidate="$venv_root/bin/$entrypoint"
    [ -f "$candidate" ] && [ ! -L "$candidate" ] && [ -x "$candidate" ] || fail
    entrypoint_python=$(sed -n '1p' "$candidate") || fail
    entrypoint_python=${entrypoint_python#\#!}
    case "$entrypoint_python" in
        "$venv_root/bin/python"|"$venv_root/bin/python3"|"$venv_root/bin/python3.12") ;;
        *) fail ;;
    esac
    [ -f "$entrypoint_python" ] && [ ! -L "$entrypoint_python" ] && [ -x "$entrypoint_python" ] || fail
done
[ "$(cat "$static_marker")" = "$artifact_id" ] || fail

fixture_dir=$(mktemp -d "${TMPDIR:-/tmp}/stage09-static-parity.XXXXXX") || fail
cleanup() { rm -rf "$fixture_dir"; }
trap cleanup EXIT HUP INT TERM
manifest_paths="$fixture_dir/manifest-paths"
actual_paths="$fixture_dir/actual-paths"

awk '
    {
        if (NF != 2 || $1 !~ /^[0-9a-f]{64}$/ || $2 !~ /^[A-Za-z0-9._/-]+$/) exit 1
        if ($2 == "static-manifest.sha256" || $2 ~ /^\// || $2 ~ /(^|\/)\.\.($|\/)/ || $2 ~ /\/\//) exit 1
        print $2
    }
' "$static_manifest" > "$manifest_paths" || fail
[ -s "$manifest_paths" ] || fail
LC_ALL=C sort -u "$manifest_paths" > "$fixture_dir/manifest-sorted" || fail
cmp -s "$manifest_paths" "$fixture_dir/manifest-sorted" || fail

(
    cd "$static_root" || exit 1
    find . -type f ! -name static-manifest.sha256 -print | sed 's|^./||' | LC_ALL=C sort
) > "$actual_paths" || fail
cmp -s "$manifest_paths" "$actual_paths" || fail

while IFS=' ' read -r expected_hash relative_path; do
    [ -n "$expected_hash" ] && [ -n "$relative_path" ] || fail
    candidate="$static_root/$relative_path"
    [ -f "$candidate" ] && [ ! -L "$candidate" ] || fail
    actual_hash=$(sha256sum "$candidate" | awk '{print $1}') || fail
    [ "$actual_hash" = "$expected_hash" ] || fail
done < "$static_manifest"

grep -oE '(src|href)="/assets/[A-Za-z0-9._/-]+"' "$static_index" \
    | sed -e 's/^[^\"]*"//' -e 's/"$//' \
    | LC_ALL=C sort -u \
    | while IFS= read -r asset_path; do
        [ -n "$asset_path" ] || continue
        case "$asset_path" in /assets/*) ;; *) exit 1 ;; esac
        relative_asset=${asset_path#/}
        [ -f "$static_root/$relative_asset" ] && [ ! -L "$static_root/$relative_asset" ] || exit 1
    done || fail

trap - EXIT HUP INT TERM
cleanup
printf '%s\n' 'static-parity: pass'
printf '%s\n' "artifact-id: $artifact_id"
