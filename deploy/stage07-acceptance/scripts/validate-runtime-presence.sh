#!/bin/sh
set -eu

env_file=${1:?usage: validate-runtime-presence.sh /path/to/.env.stage07-acceptance}

if [ ! -f "$env_file" ]; then
    printf '%s\n' 'runtime_env=missing'
    exit 2
fi

read_value() {
    key=$1
    sed -n "s/^${key}=//p" "$env_file" | head -n 1
}

missing=0
for key in APP_ENV DATABASE_URL REDIS_URL OPENROUTER_API_KEY TELEGRAM_BOT_TOKEN TELEGRAM_WEBHOOK_SECRET TELEGRAM_SEND_MODE TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS STAGE07_TELEGRAM_BOT_USERNAME; do
    value=$(read_value "$key")
    if [ -n "$value" ]; then
        printf '%s=configured\n' "$key"
    else
        printf '%s=missing\n' "$key"
        missing=1
    fi
done

app_env=$(read_value APP_ENV)
if [ "$app_env" = production ]; then
    printf '%s\n' 'APP_ENV=production-forbidden'
    missing=1
else
    printf '%s\n' 'APP_ENV=non-production'
fi

send_mode=$(read_value TELEGRAM_SEND_MODE)
if [ "$send_mode" = restricted_test ]; then
    printf '%s\n' 'TELEGRAM_SEND_MODE=restricted_test'
else
    printf '%s\n' 'TELEGRAM_SEND_MODE=invalid'
    missing=1
fi

allowlist=$(read_value TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS)
case "$allowlist" in
    ''|*,*|*[[:space:]]*)
        printf '%s\n' 'TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS=not-exactly-one'
        missing=1
        ;;
    *)
        printf '%s\n' 'TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS=exactly-one'
        ;;
esac

username=$(read_value STAGE07_TELEGRAM_BOT_USERNAME)
if printf '%s' "$username" | grep -Eq '^[A-Za-z][A-Za-z0-9_]{1,28}[Bb][Oo][Tt]$'; then
    printf '%s\n' 'STAGE07_TELEGRAM_BOT_USERNAME=valid'
else
    printf '%s\n' 'STAGE07_TELEGRAM_BOT_USERNAME=invalid'
    missing=1
fi

if [ "$missing" -ne 0 ]; then
    exit 2
fi

printf '%s\n' 'runtime_preflight=passed'
