#!/bin/sh
# P0a read-only host inventory. It never prints hostnames, IPs, paths, or data.
set -eu

fail() {
    printf '%s\n' 'host-readiness status=fail target_host_only=false' >&2
    exit 1
}

[ "$#" -eq 1 ] && [ "$1" = '--target-host-only' ] || fail

# This guard is intentionally visible to static review: no target action may
# follow this script without the explicit P0a-only flag.
for command_name in systemctl nginx redis-server psql python3 ss timedatectl df docker; do
    if command -v "$command_name" >/dev/null 2>&1; then
        printf '%s\n' "host-readiness status=present component=$command_name"
    else
        printf '%s\n' "host-readiness status=absent component=$command_name"
    fi
done

# Read-only, aggregate probes only. Their output is discarded so neither host
# identity nor business/runtime data becomes evidence text.
df -Pk / >/dev/null 2>&1 && printf '%s\n' 'host-readiness status=present component=disk' || printf '%s\n' 'host-readiness status=absent component=disk'
timedatectl show --property=NTPSynchronized --value >/dev/null 2>&1 && printf '%s\n' 'host-readiness status=present component=clock' || printf '%s\n' 'host-readiness status=absent component=clock'
ss -ltn '( sport = :80 or sport = :443 )' >/dev/null 2>&1 && printf '%s\n' 'host-readiness status=present component=https-listeners' || printf '%s\n' 'host-readiness status=absent component=https-listeners'

# Existing Caddy/Docker are detected only by tool presence; this does not
# inspect containers, configuration, environment, networks, or business data.
command -v docker >/dev/null 2>&1 && printf '%s\n' 'host-readiness status=present component=legacy-container-tooling' || printf '%s\n' 'host-readiness status=absent component=legacy-container-tooling'
command -v caddy >/dev/null 2>&1 && printf '%s\n' 'host-readiness status=present component=legacy-ingress-tooling' || printf '%s\n' 'host-readiness status=absent component=legacy-ingress-tooling'
printf '%s\n' 'host-readiness status=complete target_host_only=true'
