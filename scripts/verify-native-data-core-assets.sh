#!/bin/sh
set -eu

root=${1:-"$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"}
sql="$root/deploy/stage09-native/postgresql/stage09-p1-bootstrap.sql"
hba="$root/postgresql/stage09-p1-hba.conf.fragment"
redis="$root/redis/redis-stage09-p1.conf"
unit="$root/systemd/stage09-p1-redis.service"

fail() {
  printf '%s\n' "validation failed: $1" >&2
  exit 1
}

need_file() { [ -f "$1" ] || fail "required asset missing"; }
need() { grep -F -q -- "$2" "$1" || fail "$3"; }
deny() { ! grep -E -q -- "$2" "$1" || fail "$3"; }

need_file "$sql"
need_file "$hba"
need_file "$redis"
need_file "$unit"

need "$sql" '\set ON_ERROR_STOP on' 'postgresql stop-on-error missing'
need "$sql" '\getenv stage09_p1_database_password STAGE09_P1_DATABASE_PASSWORD' 'postgresql environment password lookup missing'
need "$sql" '\if :{?stage09_p1_database_password}' 'postgresql empty-password guard missing'
need "$sql" "PASSWORD :'stage09_p1_database_password'" 'postgresql password variable use missing'
need "$sql" 'LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT' 'postgresql least-privilege role flags missing'
need "$sql" 'REVOKE ALL ON DATABASE stage09_p1 FROM PUBLIC' 'postgresql public database revoke missing'
need "$sql" '\connect stage09_p1' 'postgresql target database connection missing'
need "$sql" 'CREATE EXTENSION IF NOT EXISTS vector' 'pgvector creation missing'
deny "$sql" 'Stage0[37]|stage0[37]|docker:|://|password[[:space:]]*=[[:space:]]*[^:]' 'postgresql forbidden marker or literal detected'

need "$hba" 'local   stage09_p1' 'hba local rule missing'
need "$hba" '127.0.0.1/32' 'hba loopback IPv4 rule missing'
need "$hba" '::1/128' 'hba loopback IPv6 rule missing'
need "$hba" 'scram-sha-256' 'hba scram authentication missing'
deny "$hba" '0\.0\.0\.0|hostssl|hostnossl|Stage0[37]|stage0[37]|docker' 'hba public or forbidden marker detected'

need "$redis" 'port 0' 'redis TCP disable missing'
need "$redis" 'unixsocket /run/stage09-p1/redis.sock' 'redis unix socket missing'
need "$redis" 'dir /var/lib/redis-stage09-p1' 'redis data directory missing'
need "$redis" 'appendonly yes' 'redis AOF missing'
need "$redis" 'protected-mode yes' 'redis protected mode missing'
deny "$redis" '^[[:space:]]*bind[[:space:]]|^[[:space:]]*port[[:space:]]+[^0]|Stage0[37]|stage0[37]|docker' 'redis network exposure or forbidden marker detected'

need "$unit" 'User=stage09-p1' 'systemd user missing'
need "$unit" 'Group=stage09-p1' 'systemd group missing'
need "$unit" 'EnvironmentFile=/etc/stage09-p1/runtime.env' 'systemd runtime environment file missing'
need "$unit" 'ExecStartPre=/usr/local/lib/stage09-p1/verify-native-isolation.sh' 'systemd N1 preflight missing'
need "$unit" 'RuntimeDirectory=stage09-p1' 'systemd runtime directory missing'
need "$unit" 'NoNewPrivileges=yes' 'systemd NoNewPrivileges missing'
need "$unit" 'PrivateTmp=yes' 'systemd PrivateTmp missing'
need "$unit" 'ProtectHome=yes' 'systemd ProtectHome missing'
need "$unit" 'ProtectSystem=strict' 'systemd ProtectSystem missing'
need "$unit" 'Restart=on-failure' 'systemd restart policy missing'
deny "$unit" 'NoNewPrivileges[[:space:]]*=[[:space:]]*no|PrivateTmp[[:space:]]*=[[:space:]]*no|ProtectHome[[:space:]]*=[[:space:]]*no|ProtectSystem[[:space:]]*=[[:space:]]*no|Stage0[37]|stage0[37]|docker' 'systemd unsafe override or forbidden marker detected'

printf '%s\n' 'native data-core assets: PASS'
