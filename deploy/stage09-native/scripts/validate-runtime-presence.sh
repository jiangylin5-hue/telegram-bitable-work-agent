#!/bin/sh
# Validate the Stage09 P1 runtime key-name contract without printing values.
set -eu

runtime_file=${1:-/etc/stage09-p1/runtime.env}

fail() {
    printf '%s\n' "runtime-validation: fail ($1)" >&2
    exit 1
}

[ -r "$runtime_file" ] || fail "runtime-file-unreadable"

if grep -Eqi 'stage03|stage07|docker|compose|volume|container|non[-_ ]?dry[-_ ]?run' "$runtime_file"; then
    fail "historical-or-container-marker"
fi

if awk -F= '
    /^[[:space:]]*($|#)/ { next }
    /^[A-Za-z_][A-Za-z0-9_]*=/ { if (seen[$1]++) duplicate = 1 }
    END { exit duplicate ? 0 : 1 }
' "$runtime_file"; then
    fail "duplicate-key"
fi

value_for() {
    awk -v wanted="$1" '
        /^[[:space:]]*($|#)/ { next }
        /^[A-Za-z_][A-Za-z0-9_]*=/ {
            key = $0
            sub(/=.*/, "", key)
            if (key == wanted) {
                value = $0
                sub(/^[^=]*=/, "", value)
                sub(/^[[:space:]]+/, "", value)
                sub(/[[:space:]]+$/, "", value)
                print value
                exit
            }
        }
    ' "$runtime_file"
}

require_value() {
    required_value=$(value_for "$1")
    [ -n "$required_value" ] || fail "missing-$1"
}

for required_key in \
    APP_ENV POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB DATABASE_URL REDIS_URL \
    TELEGRAM_WEBHOOK_SECRET STAGE09_P1_ARTIFACT_ID STAGE09_P1_RELEASE_DIR \
    STAGE09_P1_NGINX_INTERNAL_PORT
do
    require_value "$required_key"
done

app_env=$(value_for APP_ENV)
[ "$app_env" = "staging" ] || fail "unsafe-APP_ENV"

telegram_send_mode=$(value_for TELEGRAM_SEND_MODE)
[ "$telegram_send_mode" = "dry_run" ] || fail "unsafe-TELEGRAM_SEND_MODE"
llm_enabled=$(value_for LLM_ENABLED)
[ "$llm_enabled" = "false" ] || fail "unsafe-LLM_ENABLED"
agent_workflow_mode=$(value_for AGENT_WORKFLOW_MODE)
[ "$agent_workflow_mode" = "fake" ] || fail "unsafe-AGENT_WORKFLOW_MODE"
provider_mode=$(value_for PROVIDER_MODE)
[ "$provider_mode" = "disabled" ] || fail "unsafe-PROVIDER_MODE"
save_full_prompt=$(value_for AGENT_SAVE_FULL_PROMPT)
[ "$save_full_prompt" = "false" ] || fail "unsafe-AGENT_SAVE_FULL_PROMPT"
save_full_response=$(value_for AGENT_SAVE_FULL_RESPONSE)
[ "$save_full_response" = "false" ] || fail "unsafe-AGENT_SAVE_FULL_RESPONSE"

if ! awk -F= '
    /^[[:space:]]*($|#)/ { next }
    /^[A-Za-z_][A-Za-z0-9_]*=/ {
        key = $1
        value = $0
        sub(/^[^=]*=/, "", value)
        sub(/^[[:space:]]+/, "", value)
        sub(/[[:space:]]+$/, "", value)
        if ((key ~ /^TELEGRAM_.*ALLOW/) || key == "STAGE06_NOTIFICATION_ALLOWED_CHAT_IDS") {
            if (value != "") invalid = 1
        }
    }
    END { exit invalid ? 1 : 0 }
' "$runtime_file"; then
    fail "nonempty-telegram-allowlist"
fi

validate_postgres_url() {
    # The complete URL is whitelisted to prevent query/socket host overrides.
    printf '%s\n' "$1" | grep -Eq '^(postgresql\+psycopg://stage09_p1:[^@/?#%&]+@127\.0\.0\.1:5432/stage09_p1|postgresql\+psycopg://stage09_p1:[^@/?#%&]+@\[::1\]:5432/stage09_p1|postgresql\+psycopg://stage09_p1:[^@/?#%&]+@/stage09_p1\?host=/var/run/postgresql)$'
}

validate_redis_url() {
    # P1 uses one private Unix socket, with no TCP fallback endpoint.
    [ "$1" = 'unix:///run/stage09-p1/redis.sock?db=0' ]
}

database_url=$(value_for DATABASE_URL)
validate_postgres_url "$database_url" || fail "unsafe-DATABASE_URL"
redis_url=$(value_for REDIS_URL)
validate_redis_url "$redis_url" || fail "unsafe-REDIS_URL"

artifact_id=$(value_for STAGE09_P1_ARTIFACT_ID)
case "$artifact_id" in *latest*) fail "unsafe-STAGE09_P1_ARTIFACT_ID" ;; esac
printf '%s\n' "$artifact_id" | grep -Eq '^stage09-p1-[a-z0-9][a-z0-9._-]*$' || \
    fail "unsafe-STAGE09_P1_ARTIFACT_ID"

release_dir=$(value_for STAGE09_P1_RELEASE_DIR)
[ "$release_dir" = "/opt/stage09-p1/releases/$artifact_id" ] || \
    fail "unsafe-STAGE09_P1_RELEASE_DIR"

nginx_port=$(value_for STAGE09_P1_NGINX_INTERNAL_PORT)
case "$nginx_port" in ''|*[!0-9]*) fail "unsafe-STAGE09_P1_NGINX_INTERNAL_PORT" ;; esac
[ "$nginx_port" -ge 1024 ] && [ "$nginx_port" -le 65535 ] || \
    fail "unsafe-STAGE09_P1_NGINX_INTERNAL_PORT"

printf '%s\n' "APP_ENV: staging"
for configured_key in \
    POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB DATABASE_URL REDIS_URL \
    TELEGRAM_WEBHOOK_SECRET STAGE09_P1_ARTIFACT_ID STAGE09_P1_RELEASE_DIR \
    STAGE09_P1_NGINX_INTERNAL_PORT
do
    printf '%s\n' "$configured_key: configured"
done
printf '%s\n' "TELEGRAM_ALLOWLISTS: empty"
printf '%s\n' "TELEGRAM_SEND_MODE: dry_run"
printf '%s\n' "LLM_ENABLED: false"
printf '%s\n' "AGENT_WORKFLOW_MODE: fake"
printf '%s\n' "PROVIDER_MODE: disabled"
printf '%s\n' "AGENT_SAVE_FULL_PROMPT: false"
printf '%s\n' "AGENT_SAVE_FULL_RESPONSE: false"
printf '%s\n' "runtime-validation: pass"
