#!/bin/sh
# Render only the approved Alembic revision without loading runtime settings.
# Alembic --sql must receive a fixed Stage09-only dialect URL, never a target
# runtime URL or a config-module fallback.  The placeholder is not a secret.
set -eu

target_revision=20260720_0032
offline_database_url='postgresql+psycopg://stage09_p1:offline-placeholder@127.0.0.1:5432/stage09_p1'

fail() {
    printf '%s\n' 'migration-offline: fail' >&2
    printf '%s\n' 'artifact-id: unavailable' >&2
    printf '%s\n' 'migration-verified: false' >&2
    exit 1
}

release_root=${1:-}
artifact_id=${2:-}
output_file=${3:-}
[ "$#" -eq 3 ] || fail
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || fail
sh "$script_dir/verify-release-layout.sh" "$release_root" "$artifact_id" >/dev/null 2>&1 || fail

for utility in env grep mktemp mv realpath rm; do
    command -v "$utility" >/dev/null 2>&1 || fail
done

case "$output_file" in "$release_root"|"$release_root"/*) fail ;; esac
output_dir=$(dirname -- "$output_file") || fail
[ -d "$output_dir" ] && [ ! -L "$output_dir" ] && [ ! -L "$output_file" ] || fail
venv_root="/opt/stage09-p1/venv/$artifact_id"
python_bin="$venv_root/bin/python"
[ -f "$python_bin" ] && [ -x "$python_bin" ] || fail
resolved_python=$(realpath "$python_bin") || fail
[ -f "$resolved_python" ] && [ -x "$resolved_python" ] && [ ! -L "$resolved_python" ] || fail
case "$resolved_python" in
    "$venv_root"/*|/usr/bin/python3|/usr/bin/python3.12) ;;
    *) fail ;;
esac
umask 077
temp_dir=$(mktemp -d "$output_dir/.stage09-offline.XXXXXX") || fail
cleanup() { rm -rf "$temp_dir"; }
trap cleanup EXIT HUP INT TERM

(
    cd "$release_root/backend" || exit 1
    env -u DATABASE_URL "DATABASE_URL=$offline_database_url" PYTHONPATH="$release_root/backend" "$python_bin" -m alembic heads
) > "$temp_dir/heads" 2>&1 || fail
[ "$(grep -Ecx "$target_revision \(head\)" "$temp_dir/heads" || true)" -eq 1 ] || fail
(
    cd "$release_root/backend" || exit 1
    env -u DATABASE_URL "DATABASE_URL=$offline_database_url" PYTHONPATH="$release_root/backend" "$python_bin" -m alembic upgrade "$target_revision" --sql
) > "$temp_dir/output.sql" 2>&1 || fail
grep -Fq "$target_revision" "$temp_dir/output.sql" || fail
mv -f "$temp_dir/output.sql" "$output_file" || fail
trap - EXIT HUP INT TERM
rm -rf "$temp_dir"

printf '%s\n' 'migration-offline: pass'
printf '%s\n' "artifact-id: $artifact_id"
printf '%s\n' 'migration-verified: true'
