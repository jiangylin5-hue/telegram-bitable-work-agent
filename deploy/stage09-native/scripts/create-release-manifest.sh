#!/bin/sh
# Atomically write a deterministic SHA-256 manifest for a sealed release.
set -eu

fail() {
    printf '%s\n' 'release-manifest: fail' >&2
    printf '%s\n' 'artifact-id: unavailable' >&2
    printf '%s\n' 'manifest-sha256: unavailable' >&2
    exit 1
}

release_root=${1:-}
artifact_id=${2:-}
output_file=${3:-}
[ "$#" -eq 3 ] || fail
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || fail
sh "$script_dir/verify-release-layout.sh" "$release_root" "$artifact_id" >/dev/null 2>&1 || fail

case "$output_file" in "$release_root"|"$release_root"/*) fail ;; esac
[ -n "$output_file" ] && [ ! -L "$output_file" ] || fail
output_dir=$(dirname -- "$output_file") || fail
[ -d "$output_dir" ] && [ ! -L "$output_dir" ] || fail

for utility in sha256sum find sort sed awk mktemp mv rm; do
    command -v "$utility" >/dev/null 2>&1 || fail
done

umask 077
temp_path=$(mktemp "$output_dir/.stage09-manifest.XXXXXX") || fail
cleanup() { rm -f "$temp_path"; }
trap cleanup EXIT HUP INT TERM
(
    cd "$release_root" || exit 1
    LC_ALL=C find . -type f -print | sed 's|^./||' | LC_ALL=C sort | while IFS= read -r relative_path; do
        [ -n "$relative_path" ] || exit 1
        checksum=$(sha256sum "$relative_path" | awk '{print $1}') || exit 1
        printf '%s  %s\n' "$checksum" "$relative_path"
    done
) > "$temp_path" || fail
[ -s "$temp_path" ] || fail
manifest_sha256=$(sha256sum "$temp_path" | awk '{print $1}') || fail
printf '%s\n' "$manifest_sha256" | grep -Eq '^[0-9a-f]{64}$' || fail
mv -f "$temp_path" "$output_file" || fail
trap - EXIT HUP INT TERM

printf '%s\n' 'release-manifest: pass'
printf '%s\n' "artifact-id: $artifact_id"
printf '%s\n' "manifest-sha256: $manifest_sha256"
