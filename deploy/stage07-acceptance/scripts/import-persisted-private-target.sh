#!/bin/sh
set -eu

if [ "$#" -ne 2 ] || [ "$1" != "--not-before-utc" ] || [ -z "$2" ]; then
    printf '%s\n' '{"ok":false,"status":"blocked","source":"stage03_persisted_marker"}'
    exit 2
fi

not_before_utc=$2
if ! python3 -c '
from datetime import datetime
import sys
value = datetime.fromisoformat(sys.argv[1].replace("Z", "+00:00"))
if value.tzinfo is None:
    raise ValueError("timezone required")
' "$not_before_utc" >/dev/null 2>&1; then
    printf '%s\n' '{"ok":false,"status":"blocked","source":"stage03_persisted_marker"}'
    exit 2
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
deploy_dir=$(dirname "$script_dir")
source_root=$(CDPATH= cd -- "$deploy_dir/../.." && pwd)
runtime_dir="$deploy_dir/runtime"
env_file="$runtime_dir/.env.stage07-acceptance"
runtime_owner="$(id -u):$(id -g)"
helper_path="$source_root/backend/scripts/stage07_import_persisted_private_target.py"

read_value() {
    key=$1
    sed -n "s/^${key}=//p" "$env_file" | head -n 1
}

if [ ! -d "$runtime_dir" ] || [ ! -f "$env_file" ] || [ ! -f "$helper_path" ]; then
    printf '%s\n' '{"ok":false,"status":"failed","source":"stage03_persisted_marker"}'
    exit 2
fi

stage03_api_container=${STAGE03_API_CONTAINER:-$(read_value STAGE03_API_CONTAINER)}
stage07_api_image=${STAGE07_API_IMAGE:-$(read_value STAGE07_API_IMAGE)}
stage07_api_image=${stage07_api_image:-stage07-acceptance-api:latest}

if [ -z "$stage03_api_container" ]; then
    printf '%s\n' '{"ok":false,"status":"blocked","source":"stage03_persisted_marker"}'
    exit 2
fi

set +e
candidate_json=$(sudo docker exec -i "$stage03_api_container" \
    python - --select --not-before-utc "$not_before_utc" < "$helper_path" 2>/dev/null)
selector_exit=$?
set -e

if [ "$selector_exit" -ne 0 ]; then
    case "$candidate_json" in
        '{"ok":false,"status":"blocked","source":"stage03_persisted_marker"}')
            printf '%s\n' '{"ok":false,"status":"blocked","source":"stage03_persisted_marker"}'
            ;;
        *)
            printf '%s\n' '{"ok":false,"status":"failed","source":"stage03_persisted_marker"}'
            ;;
    esac
    exit 2
fi

set +e
receipt=$(printf '%s' "$candidate_json" | sudo docker run --rm -i \
    -v "$runtime_dir:/run/stage07:rw" \
    "$stage07_api_image" \
    python scripts/stage07_import_persisted_private_target.py \
    --apply-stdin --env-file /run/stage07/.env.stage07-acceptance 2>/dev/null)
apply_exit=$?
set -e

receipt_status=$(printf '%s' "$receipt" | python3 -c '
import json
import sys
payload = json.load(sys.stdin)
status = payload.get("status")
if payload.get("source") != "stage03_persisted_marker" or status not in {"captured", "blocked", "failed"}:
    raise ValueError("invalid receipt")
print(status)
' 2>/dev/null || true)

if [ "$apply_exit" -eq 0 ] && [ "$receipt_status" = "captured" ]; then
    if ! sudo chown "$runtime_owner" "$env_file" || ! sudo chmod 600 "$env_file"; then
        printf '%s\n' '{"ok":false,"status":"failed","source":"stage03_persisted_marker"}'
        exit 2
    fi
    printf '%s\n' '{"ok":true,"status":"captured","source":"stage03_persisted_marker"}'
    exit 0
fi

case "$receipt_status" in
    blocked)
        printf '%s\n' '{"ok":false,"status":"blocked","source":"stage03_persisted_marker"}'
        ;;
    *)
        printf '%s\n' '{"ok":false,"status":"failed","source":"stage03_persisted_marker"}'
        ;;
esac
exit 2
