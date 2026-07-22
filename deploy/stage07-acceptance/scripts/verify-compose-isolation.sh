#!/bin/sh
set -eu

compose_file=${1:?usage: verify-compose-isolation.sh compose.yml}

if grep -Eq 'stage03_(postgres|redis)|telegram-bitable-stage03-(postgres|redis)' "$compose_file"; then
    printf '%s\n' 'compose_isolation=failed-shared-stage03-data-reference'
    exit 2
fi

for token in stage07_acceptance_postgres_data stage07_acceptance_redis_data stage07-api stage07-web; do
    if ! grep -Fq "$token" "$compose_file"; then
        printf '%s=missing\n' "$token"
        exit 2
    fi
done

printf '%s\n' 'compose_isolation=passed'
