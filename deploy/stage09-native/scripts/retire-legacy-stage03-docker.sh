#!/bin/sh
# Archive and, only on explicit request, retire the fixed legacy Stage03 stack.
set -eu

PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH

project_name=telegram-bitable-stage03
archive_root=/var/backups/stage09-p1/legacy-stage03
nginx_config=/etc/nginx/sites-available/stage09-p1.conf
source_link=/opt/stage09-p1/current
venv_link=/opt/stage09-p1/current-venv
static_link=/var/www/stage09-p1/current
archive_work_dir=
ready_work_file=
repository_fixture=0

receipt() {
    printf '%s=%s\n' "$1" "$2"
}

fail() {
    receipt status failed
    exit 1
}

cleanup() {
    if [ -n "$ready_work_file" ]; then
        case "$ready_work_file" in
            "$archive_root"/.ready.*) rm -f -- "$ready_work_file" >/dev/null 2>&1 || : ;;
        esac
    fi
    if [ -n "$archive_work_dir" ]; then
        case "$archive_work_dir" in
            "$archive_root"/.archive.*|"$archive_root"/archive-*)
                rm -rf -- "$archive_work_dir" >/dev/null 2>&1 || :
                ;;
        esac
    fi
}

line_count() {
    printf '%s\n' "$1" | awk 'NF { count += 1 } END { print count + 0 }'
}

valid_resource_list() {
    list=$1
    [ -z "$list" ] && return 0
    if printf '%s\n' "$list" | grep -Ev '^[A-Za-z0-9][A-Za-z0-9_.:@/-]*$' >/dev/null; then
        return 1
    fi
}

set_digest() {
    printf '%s\n' "$1" | LC_ALL=C sort | sha256sum | awk '{ print $1 }'
}

select_containers() {
    docker ps -a \
        --filter "label=com.docker.compose.project=$project_name" \
        --format '{{.Names}}' 2>/dev/null
}

select_networks() {
    docker network ls \
        --filter "label=com.docker.compose.project=$project_name" \
        --format '{{.Name}}' 2>/dev/null
}

select_volumes() {
    docker volume ls \
        --filter "label=com.docker.compose.project=$project_name" \
        --format '{{.Name}}' 2>/dev/null
}

select_custom_images() {
    docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null |
        awk 'index($0, "telegram-bitable-stage03-") == 1'
}

service_container() {
    service=$1
    ids=$(docker ps -a \
        --filter "label=com.docker.compose.project=$project_name" \
        --filter "label=com.docker.compose.service=$service" \
        --format '{{.Names}}' 2>/dev/null) || return 1
    valid_resource_list "$ids" || return 1
    [ "$(line_count "$ids")" -eq 1 ] || return 1
    printf '%s\n' "$ids"
}

expected_link_exists() {
    link_path=$1
    if [ "$repository_fixture" -eq 1 ]; then
        [ -e "$link_path" ]
    else
        [ -L "$link_path" ]
    fi
}

write_inventory_record() {
    type=$1
    name=$2
    size_bytes=$3
    observed_at=$4
    output_file=$5
    printf '%s\n' "$size_bytes" | grep -Eq '^[0-9]+$' || return 1
    [ -n "$observed_at" ] || return 1
    record_sha256=$(
        printf '%s\t%s\t%s\t%s\n' "$type" "$name" "$size_bytes" "$observed_at" |
            sha256sum | awk '{ print $1 }'
    ) || return 1
    printf '%s\t%s\t%s\t%s\t%s\n' \
        "$type" "$name" "$size_bytes" "$observed_at" "$record_sha256" >> "$output_file"
}

write_inventory() {
    output_file=$1
    containers=$2
    networks=$3
    volumes=$4
    images=$5
    printf '%s\n' 'type	name	size_bytes	observed_at	sha256' > "$output_file" || return 1

    for name in $containers; do
        size_bytes=$(docker inspect --size --format '{{.SizeRootFs}}' "$name" 2>/dev/null) || return 1
        observed_at=$(docker inspect --format '{{.Created}}' "$name" 2>/dev/null) || return 1
        write_inventory_record container "$name" "$size_bytes" "$observed_at" "$output_file" || return 1
    done
    for name in $networks; do
        observed_at=$(docker network inspect --format '{{.Created}}' "$name" 2>/dev/null) || return 1
        write_inventory_record network "$name" 0 "$observed_at" "$output_file" || return 1
    done
    for name in $volumes; do
        volume_path=$(docker volume inspect --format '{{.Mountpoint}}' "$name" 2>/dev/null) || return 1
        [ -n "$volume_path" ] && [ -d "$volume_path" ] || return 1
        size_bytes=$(du -sb -- "$volume_path" 2>/dev/null | awk 'NR == 1 { print $1 }') || return 1
        observed_at=$(docker volume inspect --format '{{.CreatedAt}}' "$name" 2>/dev/null) || return 1
        write_inventory_record volume "$name" "$size_bytes" "$observed_at" "$output_file" || return 1
    done
    for name in $images; do
        size_bytes=$(docker image inspect --format '{{.Size}}' "$name" 2>/dev/null) || return 1
        observed_at=$(docker image inspect --format '{{.Created}}' "$name" 2>/dev/null) || return 1
        write_inventory_record image "$name" "$size_bytes" "$observed_at" "$output_file" || return 1
    done
}

write_state() {
    output_file=$1
    containers=$2
    networks=$3
    volumes=$4
    images=$5
    {
        printf '%s\n' 'format_version=1'
        printf 'project_name=%s\n' "$project_name"
        printf 'container_count=%s\n' "$(line_count "$containers")"
        printf 'container_set_sha256=%s\n' "$(set_digest "$containers")"
        printf 'network_count=%s\n' "$(line_count "$networks")"
        printf 'network_set_sha256=%s\n' "$(set_digest "$networks")"
        printf 'volume_count=%s\n' "$(line_count "$volumes")"
        printf 'volume_set_sha256=%s\n' "$(set_digest "$volumes")"
        printf 'image_count=%s\n' "$(line_count "$images")"
        printf 'image_set_sha256=%s\n' "$(set_digest "$images")"
    } > "$output_file"
}

required_artifacts='compose.yml
Caddyfile
caddy-runtime.json
postgres.dump
redis.rdb
inventory.tsv
nginx-stage09-p1.conf
stage09-source.target
stage09-venv.target
stage09-static.target
state'

verify_archive_dir() {
    archive_dir=$1
    [ -d "$archive_dir" ] && [ ! -L "$archive_dir" ] || return 1
    [ -f "$archive_dir/manifest.sha256" ] &&
        [ ! -L "$archive_dir/manifest.sha256" ] &&
        [ -s "$archive_dir/manifest.sha256" ] || return 1
    [ "$(wc -l < "$archive_dir/manifest.sha256")" -eq 11 ] || return 1

    for artifact in $required_artifacts; do
        [ -f "$archive_dir/$artifact" ] &&
            [ ! -L "$archive_dir/$artifact" ] &&
            [ -s "$archive_dir/$artifact" ] || return 1
        awk -v artifact="$artifact" '
            $2 == artifact && length($1) == 64 && $1 ~ /^[0-9a-f]+$/ { count += 1 }
            END { exit count == 1 ? 0 : 1 }
        ' "$archive_dir/manifest.sha256" || return 1
    done
    (
        cd "$archive_dir" || exit 1
        sha256sum -c manifest.sha256 >/dev/null 2>&1
    ) || return 1
    pg_restore -l "$archive_dir/postgres.dump" >/dev/null 2>&1 || return 1
    [ "$(dd if="$archive_dir/redis.rdb" bs=5 count=1 2>/dev/null)" = REDIS ] || return 1
}

ready_marker_files() {
    find "$archive_root" -maxdepth 1 -type f \
        \( -name 'ready*' -o -name '.ready.*' \) -print 2>/dev/null
}

write_ready_marker() {
    archive_name=$1
    markers=$(ready_marker_files) || return 1
    [ "$(line_count "$markers")" -eq 0 ] || return 1
    ready_work_file=$(mktemp "$archive_root/.ready.XXXXXX" 2>/dev/null) || return 1
    printf '%s\n' "$archive_name" > "$ready_work_file" || return 1
    chmod 600 "$ready_work_file" 2>/dev/null || return 1
    mv -f -- "$ready_work_file" "$archive_root/ready" 2>/dev/null || return 1
    ready_work_file=
}

archive_legacy_runtime() {
    mkdir -p "$archive_root" 2>/dev/null || return 1
    chmod 700 "$archive_root" 2>/dev/null || return 1
    markers=$(ready_marker_files) || return 1
    [ "$(line_count "$markers")" -eq 0 ] || return 1

    containers=$(select_containers) || return 1
    networks=$(select_networks) || return 1
    volumes=$(select_volumes) || return 1
    images=$(select_custom_images) || return 1
    valid_resource_list "$containers" || return 1
    valid_resource_list "$networks" || return 1
    valid_resource_list "$volumes" || return 1
    valid_resource_list "$images" || return 1
    [ "$(line_count "$containers")" -gt 0 ] || return 1

    postgres_id=$(service_container postgres) || return 1
    redis_id=$(service_container redis) || return 1
    caddy_id=$(service_container caddy) || return 1
    compose_dir=$(
        docker inspect \
            --format '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}' \
            "$caddy_id" 2>/dev/null
    ) || return 1
    [ -d "$compose_dir" ] && [ -f "$compose_dir/compose.yml" ] || return 1
    [ -f "$nginx_config" ] || return 1
    expected_link_exists "$source_link" &&
        expected_link_exists "$venv_link" &&
        expected_link_exists "$static_link" || return 1

    archive_work_dir=$(mktemp -d "$archive_root/.archive.XXXXXX" 2>/dev/null) || return 1
    chmod 700 "$archive_work_dir" 2>/dev/null || return 1

    cp -- "$compose_dir/compose.yml" "$archive_work_dir/compose.yml" 2>/dev/null || return 1
    cp -- "$nginx_config" "$archive_work_dir/nginx-stage09-p1.conf" 2>/dev/null || return 1
    docker exec "$postgres_id" sh -c \
        'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' \
        > "$archive_work_dir/postgres.dump" 2>/dev/null || return 1
    docker exec "$redis_id" sh -c \
        'tmp=/tmp/stage09-legacy-stage03-redis.rdb; rm -f "$tmp"; trap '\''rm -f "$tmp"'\'' EXIT HUP INT TERM; redis-cli --rdb "$tmp" >/dev/null && cat "$tmp"' \
        > "$archive_work_dir/redis.rdb" 2>/dev/null || return 1
    docker exec "$caddy_id" cat /etc/caddy/Caddyfile \
        > "$archive_work_dir/Caddyfile" 2>/dev/null || return 1
    docker exec "$caddy_id" sh -c \
        'wget -qO- http://127.0.0.1:2019/config/' \
        > "$archive_work_dir/caddy-runtime.json" 2>/dev/null || return 1
    readlink "$source_link" > "$archive_work_dir/stage09-source.target" 2>/dev/null || return 1
    readlink "$venv_link" > "$archive_work_dir/stage09-venv.target" 2>/dev/null || return 1
    readlink "$static_link" > "$archive_work_dir/stage09-static.target" 2>/dev/null || return 1
    write_inventory "$archive_work_dir/inventory.tsv" \
        "$containers" "$networks" "$volumes" "$images" || return 1
    write_state "$archive_work_dir/state" \
        "$containers" "$networks" "$volumes" "$images" || return 1
    chmod 600 "$archive_work_dir"/* 2>/dev/null || return 1

    (
        cd "$archive_work_dir" || exit 1
        : > manifest.sha256
        for artifact in $required_artifacts; do
            artifact_sha256=$(sha256sum "$artifact" | awk '{ print $1 }') || exit 1
            printf '%s  %s\n' "$artifact_sha256" "$artifact" >> manifest.sha256
        done
        chmod 600 manifest.sha256
    ) 2>/dev/null || return 1
    verify_archive_dir "$archive_work_dir" || return 1

    archive_name="archive-$(date -u '+%Y%m%dT%H%M%SZ')-$$"
    printf '%s\n' "$archive_name" | grep -Eq '^archive-[0-9]{8}T[0-9]{6}Z-[0-9]+$' || return 1
    archive_final_dir="$archive_root/$archive_name"
    [ ! -e "$archive_final_dir" ] || return 1
    mv -- "$archive_work_dir" "$archive_final_dir" 2>/dev/null || return 1
    archive_work_dir=$archive_final_dir
    write_ready_marker "$archive_name" || return 1
    archive_work_dir=

    container_count=$(line_count "$containers")
    network_count=$(line_count "$networks")
    volume_count=$(line_count "$volumes")
    image_count=$(line_count "$images")
}

state_value() {
    key=$1
    state_file=$2
    awk -F= -v key="$key" '
        $1 == key { count += 1; value = substr($0, length(key) + 2) }
        END {
            if (count != 1 || value == "") exit 1
            print value
        }
    ' "$state_file"
}

load_ready_archive() {
    [ -d "$archive_root" ] && [ ! -L "$archive_root" ] || return 1
    markers=$(ready_marker_files) || return 1
    [ "$(line_count "$markers")" -eq 1 ] || return 1
    [ "$markers" = "$archive_root/ready" ] &&
        [ -f "$archive_root/ready" ] &&
        [ ! -L "$archive_root/ready" ] || return 1
    archive_name=$(awk '
        { count += 1; value = $0 }
        END {
            if (count != 1 || value == "") exit 1
            print value
        }
    ' "$archive_root/ready") || return 1
    printf '%s\n' "$archive_name" | grep -Eq '^archive-[0-9]{8}T[0-9]{6}Z-[0-9]+$' || return 1
    archive_dir="$archive_root/$archive_name"
    verify_archive_dir "$archive_dir" || return 1

    state_file="$archive_dir/state"
    [ "$(wc -l < "$state_file")" -eq 10 ] || return 1
    [ "$(state_value format_version "$state_file")" = 1 ] || return 1
    [ "$(state_value project_name "$state_file")" = "$project_name" ] || return 1

    containers=$(select_containers) || return 1
    networks=$(select_networks) || return 1
    volumes=$(select_volumes) || return 1
    images=$(select_custom_images) || return 1
    valid_resource_list "$containers" || return 1
    valid_resource_list "$networks" || return 1
    valid_resource_list "$volumes" || return 1
    valid_resource_list "$images" || return 1

    [ "$(state_value container_count "$state_file")" = "$(line_count "$containers")" ] || return 1
    [ "$(state_value container_set_sha256 "$state_file")" = "$(set_digest "$containers")" ] || return 1
    [ "$(state_value network_count "$state_file")" = "$(line_count "$networks")" ] || return 1
    [ "$(state_value network_set_sha256 "$state_file")" = "$(set_digest "$networks")" ] || return 1
    [ "$(state_value volume_count "$state_file")" = "$(line_count "$volumes")" ] || return 1
    [ "$(state_value volume_set_sha256 "$state_file")" = "$(set_digest "$volumes")" ] || return 1
    [ "$(state_value image_count "$state_file")" = "$(line_count "$images")" ] || return 1
    [ "$(state_value image_set_sha256 "$state_file")" = "$(set_digest "$images")" ] || return 1
}

custom_image_bytes() {
    images=$1
    total=0
    for image in $images; do
        size=$(docker image inspect --format '{{.Size}}' "$image" 2>/dev/null) || return 1
        printf '%s\n' "$size" | grep -Eq '^[0-9]+$' || return 1
        total=$((total + size))
    done
    printf '%s\n' "$total"
}

retire_ready_runtime() {
    load_ready_archive || return 1
    custom_image_bytes_before=$(custom_image_bytes "$images") || return 1

    container_deleted_count=0
    network_deleted_count=0
    volume_deleted_count=0
    image_deleted_count=0
    partial=0

    for resource in $containers; do
        if docker rm -f "$resource" >/dev/null 2>&1; then
            container_deleted_count=$((container_deleted_count + 1))
        else
            partial=1
        fi
    done
    for resource in $networks; do
        if docker network rm "$resource" >/dev/null 2>&1; then
            network_deleted_count=$((network_deleted_count + 1))
        else
            partial=1
        fi
    done
    for resource in $volumes; do
        if docker volume rm "$resource" >/dev/null 2>&1; then
            volume_deleted_count=$((volume_deleted_count + 1))
        else
            partial=1
        fi
    done
    for resource in $images; do
        case "$resource" in
            telegram-bitable-stage03-*) : ;;
            *) partial=1; continue ;;
        esac
        if docker image rm "$resource" >/dev/null 2>&1; then
            image_deleted_count=$((image_deleted_count + 1))
        else
            partial=1
        fi
    done

    if [ "$partial" -eq 0 ]; then
        receipt status retired
    else
        receipt status partial
    fi
    receipt archive_manifest ready
    receipt custom_image_bytes_before "$custom_image_bytes_before"
    receipt container_deleted_count "$container_deleted_count"
    receipt network_deleted_count "$network_deleted_count"
    receipt volume_deleted_count "$volume_deleted_count"
    receipt image_deleted_count "$image_deleted_count"
    [ "$partial" -eq 0 ]
}

case "${RETIRE_LEGACY_TEST_MODE-}" in
    repository-fixture)
        [ -n "${RETIRE_LEGACY_TEST_ROOT-}" ] &&
            [ -d "${RETIRE_LEGACY_TEST_ROOT-}" ] &&
            [ -n "${RETIRE_LEGACY_TEST_BIN-}" ] &&
            [ -d "${RETIRE_LEGACY_TEST_BIN-}" ] || fail
        PATH="$RETIRE_LEGACY_TEST_BIN:$PATH"
        export PATH
        repository_fixture=1
        archive_root="$RETIRE_LEGACY_TEST_ROOT/archives"
        nginx_config="$RETIRE_LEGACY_TEST_ROOT/nginx/stage09-p1.conf"
        source_link="$RETIRE_LEGACY_TEST_ROOT/links/source-current"
        venv_link="$RETIRE_LEGACY_TEST_ROOT/links/venv-current"
        static_link="$RETIRE_LEGACY_TEST_ROOT/links/static-current"
        ;;
    '')
        [ "$(id -u)" -eq 0 ] || fail
        ;;
    *)
        fail
        ;;
esac

case "${1:-}" in
    archive|retire) mode=$1 ;;
    *) fail ;;
esac
[ "$#" -eq 1 ] || fail
for utility in awk cat chmod cp date dd docker du find grep id mkdir mktemp mv pg_restore readlink rm sha256sum sort wc; do
    command -v "$utility" >/dev/null 2>&1 || fail
done

umask 077
trap cleanup EXIT HUP INT TERM

if [ "$mode" = archive ]; then
    archive_legacy_runtime || fail
    receipt status archived
    receipt archive_manifest ready
    receipt container_count "$container_count"
    receipt network_count "$network_count"
    receipt volume_count "$volume_count"
    receipt image_count "$image_count"
    receipt custom_image_bytes_before 0
else
    retire_ready_runtime || exit 1
fi
