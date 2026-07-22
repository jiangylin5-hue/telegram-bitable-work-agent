#!/bin/sh
set -eu

template=${1:?usage: render-caddy-host.sh Caddyfile.stage07-host stage07.example.com}
domain=${2:?usage: render-caddy-host.sh Caddyfile.stage07-host stage07.example.com}

if ! printf '%s' "$domain" | grep -Eq '^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$'; then
    printf '%s\n' 'stage07_acceptance_domain=invalid' >&2
    exit 2
fi

sed "s/{{STAGE07_ACCEPTANCE_DOMAIN}}/${domain}/g" "$template"
