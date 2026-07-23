#!/bin/sh
# Static safety contract for the legacy Stage03 Docker archive/retirement tool.
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
grep -Fq 'docker system prune' "$script" && fail global-prune-forbidden
grep -Fq 'docker volume rm' "$script" || fail labelled-volume-removal-missing
grep -Fq 'sha256sum' "$script" || fail manifest-missing
grep -Fq 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' "$script" || fail postgres-dump-missing
grep -Fq 'redis-cli --rdb' "$script" || fail redis-rdb-missing
grep -Fq 'archive_legacy_runtime || fail' "$script" || fail archive-before-retire-missing
grep -Fq '[ -s "$archive_dir/manifest.sha256" ] || return 1' "$script" || fail manifest-verification-missing
grep -Fq 'docker ps -aq --filter "label=com.docker.compose.project=$project_name"' "$script" || fail labelled-container-selection-missing
grep -Fq 'docker network ls -q --filter "label=com.docker.compose.project=$project_name"' "$script" || fail labelled-network-selection-missing
grep -Fq 'docker volume ls -q --filter "label=com.docker.compose.project=$project_name"' "$script" || fail labelled-volume-selection-missing
grep -Fq 'docker images --format' "$script" || fail custom-image-selection-missing
grep -Fq 'telegram-bitable-stage03-' "$script" || fail custom-image-prefix-missing
if grep -Eq 'docker image rm[^\n]*(caddy|redis|pgvector)' "$script"; then fail generic-image-removal-forbidden; fi
if grep -Fq '{{json' "$script"; then fail docker-inspect-json-forbidden; fi
if grep -Eq '^[[:space:]]*(echo|cat)[[:space:]]' "$script"; then fail raw-output-command-forbidden; fi

manifest_line=$(grep -n -F '[ -s "$archive_dir/manifest.sha256" ] || return 1' "$script" | cut -d: -f1) || fail manifest-line-missing
remove_line=$(grep -n -F 'docker rm -f $containers' "$script" | cut -d: -f1) || fail container-removal-missing
[ "$manifest_line" -lt "$remove_line" ] || fail archive-before-stop

printf '%s\n' 'shell-syntax: PASS'
printf '%s\n' 'fixed-project: PASS'
printf '%s\n' 'global-prune-forbidden: PASS'
printf '%s\n' 'archive-before-stop: PASS'
printf '%s\n' 'generic-image-retention: PASS'
printf '%s\n' 'retire-assets: PASS'
