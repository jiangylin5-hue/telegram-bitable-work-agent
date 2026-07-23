#!/bin/sh
# Repository-only lifecycle fixture for the legacy Stage03 retirement tool.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
script="$script_dir/retire-legacy-stage03-docker.sh"

fail() {
    printf '%s: FAIL\n' "$1" >&2
    exit 1
}

[ -x "$script" ] || fail retire-script-missing
sh -n "$script" || fail shell-syntax
grep -Fqx 'project_name=telegram-bitable-stage03' "$script" || fail fixed-project
grep -Fqx 'PATH=/usr/sbin:/usr/bin:/sbin:/bin' "$script" || fail fixed-path-missing
grep -Fqx 'required_owner_uid=0' "$script" || fail fixed-root-owner-missing
grep -Fq 'RETIRE_LEGACY_TEST_' "$script" && fail production-test-mode-present
grep -Fq '[ ! -L "$archive_root" ]' "$script" || fail archive-root-symlink-guard-missing
grep -Fq 'secure_archive_directory' "$script" || fail archive-directory-metadata-check-missing
grep -Fq 'secure_archive_file' "$script" || fail archive-file-metadata-check-missing
grep -Fq 'python3 -m json.tool' "$script" || fail caddy-json-validation-missing
grep -Fq 'load_ready_archive' "$script" || fail ready-archive-loader-missing
grep -Fq 'write_ready_marker' "$script" || fail ready-marker-writer-missing
grep -Fq 'pg_restore -l' "$script" || fail postgres-restore-verification-missing
grep -Fq 'all_images=$(docker images' "$script" || fail image-enumeration-status-capture-missing
grep -Eq 'docker images.*[[:space:]]\|[[:space:]]*$' "$script" && fail image-enumeration-pipefail-bypass
grep -Fq 'custom_image_bytes_before' "$script" || fail image-byte-semantics-missing
grep -Fq 'released_bytes' "$script" && fail released-bytes-ambiguous
grep -Fq 'docker system prune' "$script" && fail global-prune-forbidden
if grep -Fq '{{json' "$script"; then fail docker-inspect-json-forbidden; fi
root_check_line=$(grep -n -F '[ "$(id -u)" -eq "$required_owner_uid" ] || fail' "$script" | cut -d: -f1) || fail root-check-missing
mode_case_line=$(grep -n -F 'case "${1:-}" in' "$script" | cut -d: -f1) || fail mode-case-missing
[ "$root_check_line" -lt "$mode_case_line" ] || fail root-check-too-late

fixture_root=$(mktemp -d "${TMPDIR:-/tmp}/stage09-retire-fixture.XXXXXX") || fail fixture-create
cleanup() { rm -rf "$fixture_root"; }
trap cleanup EXIT HUP INT TERM
fixture_bin="$fixture_root/bin"
fixture_log="$fixture_root/docker.log"
fixture_compose="$fixture_root/compose"
real_stat=$(command -v stat) || fail real-stat-missing
attacker_bin="$fixture_root/attacker-bin"
attacker_log="$fixture_root/attacker.log"
mkdir -p "$fixture_bin" "$attacker_bin" "$fixture_compose" "$fixture_root/nginx" "$fixture_root/links" || fail fixture-tree
printf '%s\n' 'fixture-compose' > "$fixture_compose/compose.yml" || fail fixture-compose
printf '%s\n' 'fixture-nginx' > "$fixture_root/nginx/stage09-p1.conf" || fail fixture-nginx
mkdir -p "$fixture_root/releases/source" "$fixture_root/releases/venv" "$fixture_root/releases/static" || fail fixture-targets
ln -s "$fixture_root/releases/source" "$fixture_root/links/source-current" || fail fixture-source-link
ln -s "$fixture_root/releases/venv" "$fixture_root/links/venv-current" || fail fixture-venv-link
ln -s "$fixture_root/releases/static" "$fixture_root/links/static-current" || fail fixture-static-link

fake_docker="$fixture_bin/docker"
{
    printf '%s\n' '#!/bin/sh'
    printf '%s\n' 'set -eu'
    printf '%s\n' 'printf "%s\n" "$*" >> "${FAKE_DOCKER_LOG:?}"'
    printf '%s\n' 'command=$1'
    printf '%s\n' 'shift'
    printf '%s\n' 'case "$command" in'
    printf '%s\n' 'ps)'
    printf '%s\n' '    service='
    printf '%s\n' '    project_scoped=0'
    printf '%s\n' '    for value in "$@"; do case "$value" in label=com.docker.compose.project=telegram-bitable-stage03) project_scoped=1 ;; label=com.docker.compose.service=*) service=${value##*=} ;; esac; done'
    printf '%s\n' '    [ "$project_scoped" -eq 1 ] || { printf "%s\n" foreign-container; exit 0; }'
    printf '%s\n' '    case "$service" in postgres) printf "%s\n" postgres-id ;; redis) printf "%s\n" redis-id ;; caddy) printf "%s\n" caddy-id ;; *) printf "%s\n" api-id postgres-id redis-id caddy-id; [ "${FAKE_LIVE_MISMATCH:-0}" = 1 ] && printf "%s\n" drift-id; : ;; esac'
    printf '%s\n' '    ;;'
    printf '%s\n' 'network) case "${1:-}" in ls) case "$*" in *label=com.docker.compose.project=telegram-bitable-stage03*) printf "%s\n" stage03-net ;; *) printf "%s\n" foreign-net ;; esac ;; inspect) case "$*" in *Created*) printf "%s\n" 2026-07-23T00:00:00Z ;; *) printf "%s\n" 0 ;; esac ;; rm) [ "${2:-}" = stage03-net ] || exit 8; if [ "${FAKE_FAIL_NETWORK_RM:-0}" = 1 ]; then exit 9; fi ;; esac ;;'
    printf '%s\n' 'volume) case "${1:-}" in ls) case "$*" in *label=com.docker.compose.project=telegram-bitable-stage03*) printf "%s\n" stage03-volume ;; *) printf "%s\n" foreign-volume ;; esac ;; inspect) case "$*" in *CreatedAt*) printf "%s\n" 2026-07-23T00:00:00Z ;; *Mountpoint*) printf "%s\n" "${FAKE_VOLUME_PATH:?}" ;; *) printf "%s\n" 0 ;; esac ;; rm) [ "${2:-}" = stage03-volume ] || exit 8; if [ "${FAKE_FAIL_VOLUME_RM:-0}" = 1 ]; then exit 9; fi ;; esac ;;'
    printf '%s\n' 'images) [ "${FAKE_FAIL_IMAGES:-0}" = 1 ] && exit 9; printf "%s\n" telegram-bitable-stage03-api:test telegram-bitable-stage030-foreign:test caddy:2-alpine redis:7-alpine pgvector/pgvector:pg16 ;;'
    printf '%s\n' 'inspect) case "$*" in *working_dir*) printf "%s\n" "${FAKE_COMPOSE_DIR:?}" ;; *SizeRootFs*) printf "%s\n" 1 ;; *Created*) printf "%s\n" 2026-07-23T00:00:00Z ;; *) printf "%s\n" fixture-resource ;; esac ;;'
    printf '%s\n' 'exec) case "$*" in *pg_dump*) printf "%s" PGDMPfixture ;; *redis-cli*) if [ "${FAKE_BAD_REDIS_HEADER:-0}" = 1 ]; then printf "%s" WRONG0009fixture; else printf "%s" REDIS0009fixture; fi ;; *Caddyfile*) [ "${FAKE_CADDY_EXEC_FAIL:-0}" = 1 ] && exit 9; printf "%s\n" fixture-caddy ;; *wget*) if [ "${FAKE_BAD_CADDY_JSON:-0}" = 1 ]; then printf "%s\n" not-json; else printf "%s\n" "{\"apps\":{}}"; fi ;; esac ;;'
    printf '%s\n' 'image) case "${1:-}" in inspect) case "$*" in *Created*) printf "%s\n" 2026-07-23T00:00:00Z ;; *) printf "%s\n" 42 ;; esac ;; rm) if [ "${FAKE_FAIL_IMAGE_RM:-0}" = 1 ]; then exit 9; fi ;; esac ;;'
    printf '%s\n' 'rm) if [ "${FAKE_FAIL_CONTAINER_RM:-0}" = 1 ]; then exit 9; fi ;;'
    printf '%s\n' 'esac'
} > "$fake_docker" || fail fake-docker-write
chmod 700 "$fake_docker" || fail fake-docker-mode

fake_pg_restore="$fixture_bin/pg_restore"
{
    printf '%s\n' '#!/bin/sh'
    printf '%s\n' 'set -eu'
    printf '%s\n' '[ "${FAKE_PG_RESTORE_FAIL:-0}" = 1 ] && exit 9'
    printf '%s\n' 'grep -Fq PGDMPfixture "${2:?}"'
} > "$fake_pg_restore" || fail fake-pg-restore-write
chmod 700 "$fake_pg_restore" || fail fake-pg-restore-mode

fake_readlink="$fixture_bin/readlink"
{
    printf '%s\n' '#!/bin/sh'
    printf '%s\n' 'set -eu'
    printf '%s\n' 'case "${1##*/}" in'
    printf '%s\n' 'source-current) printf "%s\n" /opt/stage09-p1/releases/stage09-p1-fixture ;;'
    printf '%s\n' 'venv-current) printf "%s\n" /opt/stage09-p1/venv/stage09-p1-fixture ;;'
    printf '%s\n' 'static-current) printf "%s\n" /var/www/stage09-p1/stage09-p1-fixture ;;'
    printf '%s\n' '*) exit 9 ;;'
    printf '%s\n' 'esac'
} > "$fake_readlink" || fail fake-readlink-write
chmod 700 "$fake_readlink" || fail fake-readlink-mode

fake_python="$fixture_bin/python3"
{
    printf '%s\n' '#!/bin/sh'
    printf '%s\n' 'set -eu'
    printf '%s\n' '[ "$#" -eq 3 ] && [ "$1" = -m ] && [ "$2" = json.tool ] || exit 9'
    printf '%s\n' 'grep -Fqx '\''{"apps":{}}'\'' "$3"'
} > "$fake_python" || fail fake-python-write
chmod 700 "$fake_python" || fail fake-python-mode

fake_stat="$fixture_bin/stat"
{
    printf '%s\n' '#!/bin/sh'
    printf '%s\n' 'set -eu'
    printf '%s\n' 'last='
    printf '%s\n' 'for argument in "$@"; do last=$argument; done'
    printf '%s\n' 'case "${FAKE_INSECURE_ARCHIVE:-0}:$last" in'
    printf '%s\n' '    1:*/state) owner=$("${REAL_STAT:?}" -c %u -- "$last"); printf "%s:%s\n" "$owner" 644 ;;'
    printf '%s\n' '    *) exec "${REAL_STAT:?}" "$@" ;;'
    printf '%s\n' 'esac'
} > "$fake_stat" || fail fake-stat-write
chmod 700 "$fake_stat" || fail fake-stat-mode

{
    printf '%s\n' '#!/bin/sh'
    printf '%s\n' 'printf "%s\n" caller-id >> "${ATTACKER_LOG:?}"'
    printf '%s\n' 'printf "%s\n" 0'
} > "$attacker_bin/id" || fail attacker-id-write
chmod 700 "$attacker_bin/id" || fail attacker-id-mode
{
    printf '%s\n' '#!/bin/sh'
    printf '%s\n' 'printf "%s\n" caller-docker >> "${ATTACKER_LOG:?}"'
    printf '%s\n' 'exit 99'
} > "$attacker_bin/docker" || fail attacker-docker-write
chmod 700 "$attacker_bin/docker" || fail attacker-docker-mode

if [ "$(id -u)" -ne 0 ]; then
    : > "$attacker_log" || fail attacker-log
    root_gate_output=$(
        RETIRE_LEGACY_TEST_MODE=repository-fixture \
        RETIRE_LEGACY_TEST_ROOT="$fixture_root" \
        RETIRE_LEGACY_TEST_BIN="$attacker_bin" \
        ATTACKER_LOG="$attacker_log" \
        PATH="$attacker_bin:$PATH" \
        "$script" archive 2>&1
    ) && fail production-root-gate-bypassed
    [ "$root_gate_output" = 'status=failed' ] || fail production-root-gate-receipt
    [ ! -s "$attacker_log" ] || fail production-caller-path-used
fi

fixture_script="$fixture_root/retire-legacy-stage03-docker-fixture.sh"
fixture_uid=$(id -u) || fail fixture-uid
sed \
    -e "s|^PATH=/usr/sbin:/usr/bin:/sbin:/bin$|PATH=$fixture_bin:/usr/sbin:/usr/bin:/sbin:/bin|" \
    -e "s|^required_owner_uid=0$|required_owner_uid=$fixture_uid|" \
    -e "s|^archive_root=/var/backups/stage09-p1/legacy-stage03$|archive_root=$fixture_root/archives|" \
    -e "s|^nginx_config=/etc/nginx/sites-available/stage09-p1.conf$|nginx_config=$fixture_root/nginx/stage09-p1.conf|" \
    -e "s|^source_link=/opt/stage09-p1/current$|source_link=$fixture_root/links/source-current|" \
    -e "s|^venv_link=/opt/stage09-p1/current-venv$|venv_link=$fixture_root/links/venv-current|" \
    -e "s|^static_link=/var/www/stage09-p1/current$|static_link=$fixture_root/links/static-current|" \
    -e 's|\[ -L "$link_path" \]|[ -e "$link_path" ]|' \
    "$script" > "$fixture_script" || fail fixture-script-copy
chmod 700 "$fixture_script" || fail fixture-script-mode
sh -n "$fixture_script" || fail fixture-script-syntax

run_tool() {
    FAKE_DOCKER_LOG="$fixture_log" \
    FAKE_COMPOSE_DIR="$fixture_compose" \
    FAKE_VOLUME_PATH="$fixture_root/releases/source" \
    FAKE_SECRET=fixture-secret-value \
    REAL_STAT="$real_stat" \
    "$fixture_script" "$@"
}

assert_no_runtime_delete() {
    if grep -Eq '^(rm|stop|container rm|network rm|volume rm|image rm)( |$)' "$fixture_log"; then
        fail "$1"
    fi
}

failed_receipt='status=failed
archive_manifest=unavailable
custom_image_bytes_before=0
container_deleted_count=0
network_deleted_count=0
volume_deleted_count=0
image_deleted_count=0'

assert_failed_retire_receipt() {
    receipt_file=$1
    failure_name=$2
    receipt_output=$(< "$receipt_file")
    [ "$receipt_output" = "$failed_receipt" ] || fail "$failure_name"
    case "$receipt_output" in
        *"$fixture_root"*|*fixture-secret-value*|*FAKE_SECRET*|*api-id*|*stage03-net*|*stage03-volume*)
            fail "$failure_name-leak"
            ;;
    esac
}

: > "$fixture_log" || fail fixture-log
archive_output=$(run_tool archive 2>&1) || fail archive-run
case "$archive_output" in *'status=archived'*'archive_manifest=ready'*'custom_image_bytes_before=0'*) : ;; *) fail archive-receipt ;; esac
case "$archive_output" in *"$fixture_root"*|*fixture-secret-value*|*FAKE_SECRET*) fail archive-receipt-leak ;; esac
assert_no_runtime_delete archive-mutated-runtime
[ -f "$fixture_root/archives/ready" ] || fail archive-ready-marker
archive_name=$(tr -d '\r\n' < "$fixture_root/archives/ready") || fail archive-ready-read
archive_dir="$fixture_root/archives/$archive_name"
for artifact in compose.yml Caddyfile caddy-runtime.json postgres.dump redis.rdb inventory.tsv nginx-stage09-p1.conf stage09-source.target stage09-venv.target stage09-static.target state manifest.sha256; do
    [ -s "$archive_dir/$artifact" ] || fail "archive-artifact-$artifact"
done
manifest_entries=$(wc -l < "$archive_dir/manifest.sha256") || fail archive-manifest-count
[ "$manifest_entries" -eq 11 ] || fail archive-manifest-coverage
for artifact in compose.yml Caddyfile caddy-runtime.json postgres.dump redis.rdb inventory.tsv nginx-stage09-p1.conf stage09-source.target stage09-venv.target stage09-static.target state; do
    awk -v artifact="$artifact" '$2 == artifact { count += 1 } END { exit count == 1 ? 0 : 1 }' "$archive_dir/manifest.sha256" ||
        fail "archive-manifest-$artifact"
done
awk -F '\t' '
    NR == 1 {
        if ($0 != "type\tname\tsize_bytes\tobserved_at\tsha256") exit 1
        next
    }
    NF != 5 || $1 !~ /^(container|network|volume|image)$/ || $2 == "" ||
        $3 !~ /^[0-9]+$/ || $4 == "" || $5 !~ /^[0-9a-f]{64}$/ { exit 1 }
    END { if (NR != 8) exit 1 }
' "$archive_dir/inventory.tsv" || fail archive-inventory-shape

: > "$fixture_log" || fail fixture-log-reset
retire_output=$(FAKE_CADDY_EXEC_FAIL=1 run_tool retire 2>&1) || fail retire-run
case "$retire_output" in *'status=retired'*'custom_image_bytes_before=42'*'container_deleted_count=4'*'volume_deleted_count=1'*) : ;; *) fail retire-receipt ;; esac
case "$retire_output" in *"$fixture_root"*|*fixture-secret-value*|*FAKE_SECRET*|*api-id*|*stage03-net*|*stage03-volume*) fail retire-receipt-leak ;; esac
if grep -Fq 'exec caddy-id' "$fixture_log"; then fail retire-reused-caddy-exec; fi
grep -Fq 'label=com.docker.compose.project=telegram-bitable-stage03' "$fixture_log" || fail retire-project-filter
grep -Fq 'network ls --filter label=com.docker.compose.project=telegram-bitable-stage03' "$fixture_log" || fail retire-network-project-filter
grep -Fq 'network rm stage03-net' "$fixture_log" || fail retire-network-labelled-target
grep -Fq 'volume ls --filter label=com.docker.compose.project=telegram-bitable-stage03' "$fixture_log" || fail retire-volume-project-filter
grep -Fq 'volume rm stage03-volume' "$fixture_log" || fail retire-volume-labelled-target
grep -Fq 'image rm telegram-bitable-stage03-api:test' "$fixture_log" || fail retire-custom-image
if grep -Eq '(network rm foreign|volume rm foreign|image rm .*(stage030-foreign|caddy|redis|pgvector))' "$fixture_log"; then fail retire-foreign-resource; fi

rm -rf "$fixture_root/archives" || fail reset-archives
: > "$fixture_log" || fail fixture-log-reset
if FAKE_PG_RESTORE_FAIL=1 run_tool archive > "$fixture_root/archive-fail.receipt" 2>&1; then fail archive-verification-accepted; fi
[ ! -e "$fixture_root/archives/ready" ] || fail failed-archive-ready-marker
[ -z "$(find "$fixture_root/archives" -mindepth 1 -maxdepth 1 -type d -print -quit)" ] || fail failed-archive-directory-retained
if run_tool retire > "$fixture_root/retire-without-ready.receipt" 2>&1; then fail retire-without-ready-accepted; fi
assert_failed_retire_receipt "$fixture_root/retire-without-ready.receipt" missing-ready-receipt
assert_no_runtime_delete missing-ready-deleted-runtime

rm -rf "$fixture_root/archives" || fail reset-archives
: > "$fixture_log" || fail fixture-log-reset
if FAKE_BAD_REDIS_HEADER=1 run_tool archive > "$fixture_root/redis-header-fail.receipt" 2>&1; then fail redis-header-accepted; fi
[ ! -e "$fixture_root/archives/ready" ] || fail redis-header-ready-marker
assert_no_runtime_delete redis-header-deleted-runtime

rm -rf "$fixture_root/archives" || fail reset-archives
: > "$fixture_log" || fail fixture-log-reset
run_tool archive > "$fixture_root/archive-ambiguous.receipt" 2>&1 || fail ambiguous-archive-run
printf '%s\n' ambiguous > "$fixture_root/archives/ready.extra" || fail ambiguous-marker-create
if run_tool retire > "$fixture_root/ambiguous.receipt" 2>&1; then fail ambiguous-ready-accepted; fi
assert_failed_retire_receipt "$fixture_root/ambiguous.receipt" ambiguous-ready-receipt
assert_no_runtime_delete ambiguous-ready-deleted-runtime
rm -f "$fixture_root/archives/ready.extra" || fail ambiguous-marker-clean
ambiguous_archive_name=$(tr -d '\r\n' < "$fixture_root/archives/ready") || fail ambiguous-ready-read
rm -f "$fixture_root/archives/$ambiguous_archive_name/inventory.tsv" || fail incomplete-archive-create
if run_tool retire > "$fixture_root/incomplete.receipt" 2>&1; then fail incomplete-archive-accepted; fi
assert_failed_retire_receipt "$fixture_root/incomplete.receipt" incomplete-archive-receipt
assert_no_runtime_delete incomplete-archive-deleted-runtime

rm -rf "$fixture_root/archives" || fail reset-archives
: > "$fixture_log" || fail fixture-log-reset
run_tool archive > "$fixture_root/archive-corrupt.receipt" 2>&1 || fail corrupt-archive-run
corrupt_archive_name=$(tr -d '\r\n' < "$fixture_root/archives/ready") || fail corrupt-ready-read
printf '%s\n' corrupt >> "$fixture_root/archives/$corrupt_archive_name/state" || fail corrupt-archive-create
if run_tool retire > "$fixture_root/corrupt.receipt" 2>&1; then fail corrupt-archive-accepted; fi
assert_failed_retire_receipt "$fixture_root/corrupt.receipt" corrupt-archive-receipt
assert_no_runtime_delete corrupt-archive-deleted-runtime

rm -rf "$fixture_root/archives" || fail reset-archives
: > "$fixture_log" || fail fixture-log-reset
if FAKE_BAD_CADDY_JSON=1 run_tool archive > "$fixture_root/caddy-json-fail.receipt" 2>&1; then fail caddy-json-accepted; fi
[ ! -e "$fixture_root/archives/ready" ] || fail caddy-json-ready-marker
assert_no_runtime_delete caddy-json-deleted-runtime

rm -rf "$fixture_root/archives" || fail reset-archives
: > "$fixture_log" || fail fixture-log-reset
if FAKE_FAIL_IMAGES=1 run_tool archive > "$fixture_root/image-enumeration-archive.receipt" 2>&1; then fail image-enumeration-archive-accepted; fi
[ ! -e "$fixture_root/archives/ready" ] || fail image-enumeration-archive-ready
assert_no_runtime_delete image-enumeration-archive-deleted-runtime

rm -rf "$fixture_root/archives" || fail reset-archives
: > "$fixture_log" || fail fixture-log-reset
run_tool archive > "$fixture_root/archive-image-enumeration-retire.receipt" 2>&1 || fail image-enumeration-retire-archive
: > "$fixture_log" || fail fixture-log-reset
if FAKE_FAIL_IMAGES=1 run_tool retire > "$fixture_root/image-enumeration-retire.receipt" 2>&1; then fail image-enumeration-retire-accepted; fi
assert_failed_retire_receipt "$fixture_root/image-enumeration-retire.receipt" image-enumeration-retire-receipt
assert_no_runtime_delete image-enumeration-retire-deleted-runtime

rm -rf "$fixture_root/archives" || fail reset-archives
: > "$fixture_log" || fail fixture-log-reset
run_tool archive > "$fixture_root/archive-live-mismatch.receipt" 2>&1 || fail live-mismatch-archive
: > "$fixture_log" || fail fixture-log-reset
if FAKE_LIVE_MISMATCH=1 run_tool retire > "$fixture_root/live-mismatch.receipt" 2>&1; then fail live-mismatch-accepted; fi
assert_failed_retire_receipt "$fixture_root/live-mismatch.receipt" live-mismatch-receipt
assert_no_runtime_delete live-mismatch-deleted-runtime

rm -rf "$fixture_root/archives" || fail reset-archives
: > "$fixture_log" || fail fixture-log-reset
run_tool archive > "$fixture_root/archive-permission.receipt" 2>&1 || fail permission-archive
: > "$fixture_log" || fail fixture-log-reset
if FAKE_INSECURE_ARCHIVE=1 run_tool retire > "$fixture_root/permission.receipt" 2>&1; then fail insecure-archive-permission-accepted; fi
assert_failed_retire_receipt "$fixture_root/permission.receipt" insecure-archive-permission-receipt
assert_no_runtime_delete insecure-archive-permission-deleted-runtime

rm -rf "$fixture_root/archives" || fail reset-archives
: > "$fixture_log" || fail fixture-log-reset
run_tool archive > "$fixture_root/archive-partial.receipt" 2>&1 || fail partial-archive-run
if FAKE_FAIL_VOLUME_RM=1 run_tool retire > "$fixture_root/partial.receipt" 2>&1; then fail partial-retire-accepted; fi
partial_output=$(< "$fixture_root/partial.receipt")
case "$partial_output" in *'status=partial'*'container_deleted_count=4'*'network_deleted_count=1'*'volume_deleted_count=0'*) : ;; *) fail partial-receipt ;; esac
case "$partial_output" in *"$fixture_root"*|*fixture-secret-value*|*FAKE_SECRET*|*api-id*|*stage03-net*|*stage03-volume*) fail partial-receipt-leak ;; esac
for receipt_file in "$fixture_root"/*.receipt; do
    [ -f "$receipt_file" ] || continue
    receipt_output=$(< "$receipt_file")
    case "$receipt_output" in
        *"$fixture_root"*|*fixture-secret-value*|*FAKE_SECRET*|*api-id*|*stage03-net*|*stage03-volume*)
            fail failure-receipt-leak
            ;;
    esac
done

trap - EXIT HUP INT TERM
cleanup
printf '%s\n' 'shell-syntax: PASS'
printf '%s\n' 'ready-archive-lifecycle: PASS'
printf '%s\n' 'archive-completeness: PASS'
printf '%s\n' 'labelled-retirement: PASS'
printf '%s\n' 'partial-receipt: PASS'
printf '%s\n' 'retire-assets: PASS'
