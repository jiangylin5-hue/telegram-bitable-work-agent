#!/bin/sh
# Statically validate the Stage09 N2 native service and Nginx assets.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
asset_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
unit_dir="$asset_root/systemd"
template="$asset_root/nginx/stage09-p1.conf.template"

fail() {
    printf '%s\n' 'native-service-assets: fail' >&2
    exit 1
}

require_exactly_one_directive() {
    expected=$1
    file=$2
    directive=${expected%%=*}
    count=$(grep -Ec "^[[:space:]]*$directive[[:space:]]*=" "$file" || true)
    [ "$count" -eq 1 ] || fail
    grep -Fqx "$expected" "$file" || fail
}

verify_unit() {
    unit_name=$1
    expected_start=$2
    expected_stage03_count=$3
    unit_file="$unit_dir/$unit_name"
    [ -r "$unit_file" ] || fail

    require_exactly_one_directive 'User=stage09-p1' "$unit_file"
    require_exactly_one_directive 'Group=stage09-p1' "$unit_file"
    require_exactly_one_directive 'WorkingDirectory=/opt/stage09-p1/current/backend' "$unit_file"
    require_exactly_one_directive 'EnvironmentFile=/etc/stage09-p1/runtime.env' "$unit_file"
    require_exactly_one_directive 'ExecStartPre=/opt/stage09-p1/current/deploy/stage09-native/scripts/verify-native-isolation.sh /etc/stage09-p1/runtime.env' "$unit_file"
    require_exactly_one_directive "$expected_start" "$unit_file"
    require_exactly_one_directive 'NoNewPrivileges=true' "$unit_file"
    require_exactly_one_directive 'PrivateTmp=true' "$unit_file"
    require_exactly_one_directive 'ProtectHome=true' "$unit_file"
    require_exactly_one_directive 'ProtectSystem=strict' "$unit_file"
    require_exactly_one_directive 'Restart=on-failure' "$unit_file"
    require_exactly_one_directive 'RestartSec=5s' "$unit_file"

    if grep -Eq '^[[:space:]]*(After|Before|Wants|Requires|BindsTo|PartOf)[[:space:]]*=' "$unit_file"; then
        fail
    fi
    if grep -Eqi '^[[:space:]]*(User|Group)[[:space:]]*=[[:space:]]*(root|ubuntu|postgres|redis)[[:space:]]*$' "$unit_file"; then
        fail
    fi
    stage03_count=$(grep -Eic 'stage03' "$unit_file" || true)
    [ "$stage03_count" -eq "$expected_stage03_count" ] || fail
    if grep -Eqi 'stage07|docker|compose|container|volume' "$unit_file"; then
        fail
    fi
}

verify_unit 'stage09-p1-api.service' \
    'ExecStart=/opt/stage09-p1/current-venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 18080' \
    0
verify_unit 'stage09-p1-worker.service' \
    'ExecStart=/opt/stage09-p1/current-venv/bin/python -m app.workers.stage03_runtime' \
    1
verify_unit 'stage09-p1-outbox-bridge.service' \
    'ExecStart=/opt/stage09-p1/current-venv/bin/python -m app.workers.stage03_outbox_bridge_runtime' \
    1
verify_unit 'stage09-p1-agent-outbox-publisher.service' \
    'ExecStart=/opt/stage09-p1/current-venv/bin/python -m app.workers.agent_event_outbox_runtime' \
    0
verify_unit 'stage09-p1-agent-tabular-worker.service' \
    'ExecStart=/opt/stage09-p1/current-venv/bin/python -m app.workers.agent_specialist_runtime' \
    0

[ -r "$template" ] || fail
grep -Fqx '    listen {{STAGE09_P1_NGINX_BIND_ADDRESS}}:{{STAGE09_P1_NGINX_INTERNAL_PORT}};' "$template" || fail
grep -Fqx '    root /var/www/stage09-p1/current;' "$template" || fail
grep -Fqx '    allow {{STAGE09_P1_CADDY_SOURCE_CIDR}};' "$template" || fail
grep -Fqx '    deny all;' "$template" || fail
grep -Fqx '        proxy_pass http://127.0.0.1:18080;' "$template" || fail
if grep -Eqi 'stage03|stage07|docker|compose|container|listen[[:space:]]+.*(80|443)' "$template"; then
    fail
fi

printf '%s\n' 'native-service-assets: pass'
