#!/bin/sh
# Activate the Stage09 public ingress only after hostname, DNS and explicit
# operator approval. The existing public Caddy container is never replaced.
set -eu

release_root=/opt/stage09-p1/current
nginx_available=/etc/nginx/sites-available/stage09-p1.conf
nginx_enabled=/etc/nginx/sites-enabled/stage09-p1.conf
CADDYFILE_MOUNT=/etc/caddy/Caddyfile
ledger_dir=/var/lib/stage09-p1/evidence

fail() {
    printf '%s\n' 'public-ingress: fail' >&2
    exit 1
}

has_forbidden_marker() {
    printf '%s\n' "$1" | grep -Eqi 'stage03|stage07|docker|compose|container|placeholder'
}

is_ipv4() {
    value=$1
    old_ifs=$IFS
    IFS=.
    set -- $value
    IFS=$old_ifs
    [ "$#" -eq 4 ] || return 1
    for octet in "$@"; do
        case $octet in
            ''|*[!0-9]*) return 1 ;;
        esac
        [ "$octet" -ge 0 ] 2>/dev/null && [ "$octet" -le 255 ] 2>/dev/null || return 1
    done
}

is_private_ipv4() {
    value=$1
    is_ipv4 "$value" || return 1
    case $value in
        10.*|192.168.*) return 0 ;;
        172.*)
            second=$(printf '%s\n' "$value" | cut -d. -f2)
            [ "$second" -ge 16 ] 2>/dev/null && [ "$second" -le 31 ] 2>/dev/null
            return
            ;;
        *) return 1 ;;
    esac
}

is_hostname() {
    value=$1
    [ "${#value}" -le 253 ] || return 1
    case $value in
        *.*) ;;
        *) return 1 ;;
    esac
    printf '%s\n' "$value" | grep -Eq '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$'
}

file_count() {
    printf '%s\n' "$1" | awk 'NF { count += 1 } END { print count + 0 }'
}

rollback() {
    status=$?
    trap - EXIT HUP INT TERM
    [ "$status" -eq 0 ] && exit 0

    if [ "${caddy_changed:-0}" -eq 1 ] && [ -n "${caddy_backup:-}" ] && [ -f "$caddy_backup" ]; then
        docker exec -i "$caddy_id" caddy reload --config - --adapter caddyfile < "$caddy_backup" >/dev/null 2>&1 || :
    fi
    if [ "${nginx_changed:-0}" -eq 1 ] && [ -n "${nginx_backup:-}" ] && [ -f "$nginx_backup" ]; then
        cp "$nginx_backup" "$nginx_available" >/dev/null 2>&1 || :
        nginx -t >/dev/null 2>&1 && systemctl reload nginx >/dev/null 2>&1 || :
    fi

    printf '%s\n' 'public-ingress: failed-rolled-back' >&2
    exit "$status"
}

[ "$#" -eq 1 ] || fail
hostname=$1
[ "$(id -u)" -eq 0 ] || fail
for utility in docker nginx systemctl getent curl mktemp cp mv grep awk wc readlink date sleep; do
    command -v "$utility" >/dev/null 2>&1 || fail
done

is_hostname "$hostname" || fail
is_ipv4 "$hostname" && fail
has_forbidden_marker "$hostname" && fail
getent ahostsv4 "$hostname" >/dev/null 2>&1 || fail

renderer="$release_root/deploy/stage09-native/scripts/render-caddy-stage09-host.sh"
render_nginx="$release_root/deploy/stage09-native/scripts/render-nginx-config.sh"
[ -f "$renderer" ] && [ -f "$render_nginx" ] || fail
[ -f "$nginx_available" ] && [ -e "$nginx_enabled" ] || fail
[ "$(readlink -f "$nginx_enabled")" = "$nginx_available" ] || fail
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:18080/health >/dev/null

public_caddy_containers=$(docker ps --format '{{.ID}} {{.Image}} {{.Ports}}' | awk '$2 ~ /(^|\/)caddy([:@]|$)/ && $0 ~ /->80\/tcp/ && $0 ~ /->443\/tcp/ { print $1 }')
[ "$(file_count "$public_caddy_containers")" -eq 1 ] || fail
caddy_id=$public_caddy_containers

network_rows=$(docker inspect --format '{{range $name, $network := .NetworkSettings.Networks}}{{printf "%s|%s\n" $network.IPAddress $network.Gateway}}{{end}}' "$caddy_id")
[ "$(file_count "$network_rows")" -eq 1 ] || fail
caddy_address=${network_rows%%|*}
caddy_gateway=${network_rows#*|}
is_private_ipv4 "$caddy_address" || fail
is_private_ipv4 "$caddy_gateway" || fail

caddyfile_rows=$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/etc/caddy/Caddyfile"}}{{printf "%s\n" .Source}}{{end}}{{end}}' "$caddy_id")
[ "$(file_count "$caddyfile_rows")" -eq 1 ] || fail
caddyfile_host_path=$caddyfile_rows
[ -f "$caddyfile_host_path" ] || fail

umask 077
backup_dir=$(mktemp -d /var/lib/stage09-p1/public-ingress.XXXXXX) || fail
nginx_backup="$backup_dir/nginx.conf"
caddy_backup="$backup_dir/Caddyfile"
caddy_candidate="$backup_dir/Caddyfile.candidate"
nginx_temp="$nginx_available.stage09-tmp"
caddy_changed=0
nginx_changed=0
trap rollback EXIT HUP INT TERM

STAGE09_P1_NGINX_BIND_ADDRESS="$caddy_gateway" \
STAGE09_P1_NGINX_INTERNAL_PORT=18090 \
STAGE09_P1_CADDY_SOURCE_CIDR="$caddy_address/32" \
sh "$render_nginx" > "$nginx_temp"
cp "$nginx_available" "$nginx_backup"
mv "$nginx_temp" "$nginx_available"
nginx_changed=1
nginx -t >/dev/null
systemctl reload nginx
docker exec "$caddy_id" wget -q -O /dev/null "http://$caddy_gateway:18090/health"

rendered_block=$( \
    STAGE09_P1_PUBLIC_HOSTNAME="$hostname" \
    STAGE09_P1_CADDY_UPSTREAM_HOST="$caddy_gateway" \
    STAGE09_P1_CADDY_UPSTREAM_PORT=18090 \
    sh "$renderer"
)
docker exec "$caddy_id" cat /etc/caddy/Caddyfile > "$caddy_backup"
grep -Fq "# stage09-managed: $hostname" "$caddy_backup" && fail
grep -Fq "$hostname {" "$caddy_backup" && fail
cp "$caddy_backup" "$caddy_candidate"
printf '\n%s\n' "$rendered_block" >> "$caddy_candidate"
caddy_changed=1
docker exec -i "$caddy_id" caddy validate --config - --adapter caddyfile < "$caddy_candidate" >/dev/null
docker exec -i "$caddy_id" caddy reload --config - --adapter caddyfile < "$caddy_candidate" >/dev/null
attempt=0
until curl --fail --silent --show-error --max-time 15 "https://$hostname/health" >/dev/null; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 12 ]; then
        fail
    fi
    sleep 5
done

mkdir -p "$ledger_dir"
ledger_timestamp=$(date -u +%Y%m%dT%H%M%SZ)
printf '%s\n' 'status=activated' > "$ledger_dir/public-ingress-$ledger_timestamp.status"
printf '%s\n' 'public-ingress: activated'
