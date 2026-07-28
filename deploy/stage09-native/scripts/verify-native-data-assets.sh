#!/bin/sh
# Statically validate the Stage09 N3 native data-plane assets.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
asset_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
postgres_dir="$asset_root/postgresql"
systemd_dir="$asset_root/systemd"
redis_dir="$asset_root/redis"
bootstrap_sql="$postgres_dir/stage09-p1-bootstrap.sql"
hba_fragment="$postgres_dir/stage09-p1-hba.conf.fragment"
redis_config="$redis_dir/redis-stage09-p1.conf"
redis_unit="$systemd_dir/stage09-p1-redis.service"
migrate_unit="$systemd_dir/stage09-p1-migrate.service"

fail() {
    printf '%s\n' 'native-data-assets: fail' >&2
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

require_absent_directive() {
    directive=$1
    file=$2
    if grep -Eq "^[[:space:]]*$directive[[:space:]]*(=|$)" "$file"; then
        fail
    fi
}

require_exactly_one_text() {
    expected=$1
    file=$2
    [ "$(grep -Fxc "$expected" "$file" || true)" -eq 1 ] || fail
}

require_absent_markers() {
    file=$1
    if grep -Eqi 'stage03|stage07|docker|compose|container|volume' "$file"; then
        fail
    fi
}

for asset in "$bootstrap_sql" "$hba_fragment" "$redis_config" "$redis_unit" "$migrate_unit"; do
    [ -r "$asset" ] || fail
    require_absent_markers "$asset"
done

# Bootstrap only receives its password through psql's target-side environment,
# and rejects both an absent variable and an empty value before role creation.
require_exactly_one_text '\set ON_ERROR_STOP on' "$bootstrap_sql"
require_exactly_one_text '\getenv stage09_p1_database_password STAGE09_P1_DATABASE_PASSWORD' "$bootstrap_sql"
require_exactly_one_text '\if :{?stage09_p1_database_password}' "$bootstrap_sql"
require_exactly_one_text "SELECT length(:'stage09_p1_database_password') > 0 AS stage09_p1_password_present \\gset" "$bootstrap_sql"
require_exactly_one_text '\if :stage09_p1_password_present' "$bootstrap_sql"
[ "$(grep -Fxc '\quit 1' "$bootstrap_sql" || true)" -eq 2 ] || fail
require_exactly_one_text 'ALTER ROLE stage09_p1 LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT' "$bootstrap_sql"
require_exactly_one_text "  PASSWORD :'stage09_p1_database_password';" "$bootstrap_sql"
[ "$(grep -Ec 'CREATE[[:space:]]+ROLE' "$bootstrap_sql" || true)" -eq 1 ] || fail
[ "$(grep -Ec 'CREATE[[:space:]]+DATABASE' "$bootstrap_sql" || true)" -eq 1 ] || fail
[ "$(grep -Ec 'ALTER[[:space:]]+ROLE' "$bootstrap_sql" || true)" -eq 1 ] || fail
require_exactly_one_text 'REVOKE ALL ON DATABASE stage09_p1 FROM PUBLIC;' "$bootstrap_sql"
require_exactly_one_text '\connect stage09_p1' "$bootstrap_sql"
require_exactly_one_text 'REVOKE ALL ON SCHEMA public FROM PUBLIC;' "$bootstrap_sql"
require_exactly_one_text 'CREATE EXTENSION IF NOT EXISTS vector;' "$bootstrap_sql"
if grep -Eqi 'postgresql:|://|[[:space:]]host[[:space:]]|token|password[[:space:]]*=[[:space:]]*[^[:space:]]' "$bootstrap_sql"; then
    fail
fi

# HBA accepts only the fixed P1 role/database pair over local transports.
[ "$(grep -Evc '^[[:space:]]*($|#.*|local[[:space:]]+stage09_p1[[:space:]]+stage09_p1[[:space:]]+scram-sha-256|host[[:space:]]+stage09_p1[[:space:]]+stage09_p1[[:space:]]+(127\.0\.0\.1/32|::1/128)[[:space:]]+scram-sha-256)[[:space:]]*$' "$hba_fragment" || true)" -eq 0 ] || fail
[ "$(grep -Ec '^[[:space:]]*local[[:space:]]+stage09_p1[[:space:]]+stage09_p1[[:space:]]+scram-sha-256[[:space:]]*$' "$hba_fragment" || true)" -eq 1 ] || fail
[ "$(grep -Ec '^[[:space:]]*host[[:space:]]+stage09_p1[[:space:]]+stage09_p1[[:space:]]+127\.0\.0\.1/32[[:space:]]+scram-sha-256[[:space:]]*$' "$hba_fragment" || true)" -eq 1 ] || fail
[ "$(grep -Ec '^[[:space:]]*host[[:space:]]+stage09_p1[[:space:]]+stage09_p1[[:space:]]+::1/128[[:space:]]+scram-sha-256[[:space:]]*$' "$hba_fragment" || true)" -eq 1 ] || fail

# Redis has no TCP fallback: one private Unix socket is created by systemd with
# a dedicated primary group that the app account receives only as a supplement.
require_exactly_one_text 'protected-mode yes' "$redis_config"
require_exactly_one_text 'port 0' "$redis_config"
require_exactly_one_text 'unixsocket /run/stage09-p1/redis.sock' "$redis_config"
require_exactly_one_text 'unixsocketperm 770' "$redis_config"
require_exactly_one_text 'dir /var/lib/redis-stage09-p1' "$redis_config"
require_exactly_one_text 'appendonly yes' "$redis_config"
[ "$(grep -Ec '^[[:space:]]*port[[:space:]]+' "$redis_config" || true)" -eq 1 ] || fail
[ "$(grep -Ec '^[[:space:]]*unixsocket[[:space:]]+' "$redis_config" || true)" -eq 1 ] || fail
if grep -Eqi '^[[:space:]]*(bind|replicaof|slaveof|requirepass|masterauth|aclfile)[[:space:]]+' "$redis_config"; then
    fail
fi

require_exactly_one_directive 'Type=simple' "$redis_unit"
require_exactly_one_directive 'User=stage09-redis' "$redis_unit"
require_exactly_one_directive 'Group=stage09-redis-socket' "$redis_unit"
require_exactly_one_directive 'WorkingDirectory=/var/lib/redis-stage09-p1' "$redis_unit"
require_exactly_one_directive 'RuntimeDirectory=stage09-p1' "$redis_unit"
require_exactly_one_directive 'RuntimeDirectoryMode=0750' "$redis_unit"
require_exactly_one_directive 'StateDirectory=redis-stage09-p1' "$redis_unit"
require_exactly_one_directive 'StateDirectoryMode=0710' "$redis_unit"
require_exactly_one_directive 'UMask=0077' "$redis_unit"
require_exactly_one_directive 'ExecStart=/usr/bin/redis-server /opt/stage09-p1/current/deploy/stage09-native/redis/redis-stage09-p1.conf --supervised systemd' "$redis_unit"
require_exactly_one_directive 'NoNewPrivileges=true' "$redis_unit"
require_exactly_one_directive 'PrivateTmp=true' "$redis_unit"
require_exactly_one_directive 'ProtectHome=true' "$redis_unit"
require_exactly_one_directive 'ProtectSystem=strict' "$redis_unit"
require_exactly_one_directive 'Restart=on-failure' "$redis_unit"
require_exactly_one_directive 'RestartSec=5s' "$redis_unit"
require_exactly_one_text '[Install]' "$redis_unit"
require_exactly_one_directive 'WantedBy=multi-user.target' "$redis_unit"
require_absent_directive 'EnvironmentFile' "$redis_unit"
require_absent_directive 'ExecStartPre' "$redis_unit"
require_absent_directive 'SupplementaryGroups' "$redis_unit"

# The migration runs once against the fixed revision, using the app runtime
# contract; it must never be enabled automatically or target an unpinned head.
require_exactly_one_directive 'Type=oneshot' "$migrate_unit"
require_exactly_one_directive 'User=stage09-p1' "$migrate_unit"
require_exactly_one_directive 'Group=stage09-p1' "$migrate_unit"
require_exactly_one_directive 'WorkingDirectory=/opt/stage09-p1/current/backend' "$migrate_unit"
require_exactly_one_directive 'EnvironmentFile=/etc/stage09-p1/runtime.env' "$migrate_unit"
require_exactly_one_directive 'ExecStartPre=/opt/stage09-p1/current/deploy/stage09-native/scripts/verify-native-isolation.sh /etc/stage09-p1/runtime.env' "$migrate_unit"
require_exactly_one_directive 'ExecStart=/opt/stage09-p1/current-venv/bin/alembic upgrade 20260728_0034' "$migrate_unit"
require_exactly_one_directive 'NoNewPrivileges=true' "$migrate_unit"
require_exactly_one_directive 'PrivateTmp=true' "$migrate_unit"
require_exactly_one_directive 'ProtectHome=true' "$migrate_unit"
require_exactly_one_directive 'ProtectSystem=strict' "$migrate_unit"
if grep -Eqi 'alembic[[:space:]].*(head|latest)|database_url|postgresql://' "$migrate_unit"; then
    fail
fi
if grep -Eq '^[[:space:]]*\[Install\][[:space:]]*$|^[[:space:]]*WantedBy[[:space:]]*=' "$migrate_unit"; then
    fail
fi

printf '%s\n' 'native-data-assets: pass'
