#!/bin/sh
# Archive and, only on explicit request, retire the fixed legacy Stage03 stack.
set -eu

project_name=telegram-bitable-stage03
archive_root=/var/backups/stage09-p1/legacy-stage03

receipt() {
    printf '%s=%s\n' "$1" "$2"
}

fail() {
    receipt status failed
    exit 1
}

line_count() {
    printf '%s\n' "$1" | awk 'NF { count += 1 } END { print count + 0 }'
}

service_container() {
    service=$1
    ids=$(docker ps -aq \
        --filter "label=com.docker.compose.project=$project_name" \
        --filter "label=com.docker.compose.service=$service" 2>/dev/null) || return 1
    [ "$(line_count "$ids")" -eq 1 ] || return 1
    printf '%s\n' "$ids"
}

archive_legacy_runtime() {
    containers=$(docker ps -aq --filter "label=com.docker.compose.project=$project_name" 2>/dev/null) || return 1
    [ -n "$containers" ] || return 1
    postgres_id=$(service_container postgres) || return 1
    redis_id=$(service_container redis) || return 1
    caddy_id=$(service_container caddy) || return 1

    networks=$(docker network ls -q --filter "label=com.docker.compose.project=$project_name" 2>/dev/null) || return 1
    volumes=$(docker volume ls -q --filter "label=com.docker.compose.project=$project_name" 2>/dev/null) || return 1
    all_images=$(docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null) || return 1
    images=$(printf '%s\n' "$all_images" | awk '/^telegram-bitable-stage03-/') || return 1
    container_count=$(line_count "$containers") || return 1
    volume_count=$(line_count "$volumes") || return 1
    image_count=$(line_count "$images") || return 1

    caddyfile_mount=$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/etc/caddy/Caddyfile"}}{{.Source}}{{end}}{{end}}' "$caddy_id" 2>/dev/null) || return 1
    [ -n "$caddyfile_mount" ] || return 1

    umask 077
    mkdir -p "$archive_root" 2>/dev/null || return 1
    archive_dir=$(mktemp -d "$archive_root/retirement.XXXXXX" 2>/dev/null) || return 1
    docker exec "$postgres_id" sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > "$archive_dir/postgres.dump" 2>/dev/null || return 1
    docker exec "$redis_id" sh -c 'redis-cli --rdb /tmp/legacy.rdb >/dev/null && cat /tmp/legacy.rdb && rm -f /tmp/legacy.rdb' > "$archive_dir/redis.rdb" 2>/dev/null || return 1
    docker exec "$caddy_id" cat /etc/caddy/Caddyfile > "$archive_dir/Caddyfile" 2>/dev/null || return 1
    docker exec "$caddy_id" sh -c 'wget -qO- http://127.0.0.1:2019/config/' > "$archive_dir/caddy-admin-config.json" 2>/dev/null || return 1
    [ -s "$archive_dir/postgres.dump" ] || return 1
    [ -s "$archive_dir/redis.rdb" ] || return 1
    [ -s "$archive_dir/Caddyfile" ] || return 1
    [ -s "$archive_dir/caddy-admin-config.json" ] || return 1
    (
        cd "$archive_dir" || exit 1
        sha256sum postgres.dump redis.rdb Caddyfile caddy-admin-config.json
    ) > "$archive_dir/manifest.sha256" 2>/dev/null || return 1
    [ -s "$archive_dir/manifest.sha256" ] || return 1
}

[ "$(id -u)" -eq 0 ] || fail
case "${1:-}" in
    archive|retire) mode=$1 ;;
    *) fail ;;
esac
for utility in awk docker id mkdir mktemp sha256sum; do
    command -v "$utility" >/dev/null 2>&1 || fail
done

archive_legacy_runtime || fail

released_bytes=0
if [ "$mode" = retire ]; then
    if [ -n "$images" ]; then
        released_bytes=$(docker image inspect --format '{{.Size}}' $images 2>/dev/null | awk '{ total += $1 } END { print total + 0 }') || fail
    fi
    docker rm -f $containers >/dev/null 2>&1 || fail
    [ -z "$networks" ] || docker network rm $networks >/dev/null 2>&1 || fail
    [ -z "$volumes" ] || docker volume rm $volumes >/dev/null 2>&1 || fail
    [ -z "$images" ] || docker image rm $images >/dev/null 2>&1 || fail
    receipt status retired
else
    receipt status archived
fi
receipt archive_manifest sealed
receipt container_count "$container_count"
receipt volume_count "$volume_count"
receipt image_count "$image_count"
receipt released_bytes "$released_bytes"
