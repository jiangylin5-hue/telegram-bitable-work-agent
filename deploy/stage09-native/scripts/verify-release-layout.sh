#!/bin/sh
# Verify a sealed, fixed-location Stage09 release without disclosing paths.
set -eu

release_base=/opt/stage09-p1/releases

fail() {
    printf '%s\n' 'release-layout: fail' >&2
    printf '%s\n' 'artifact-id: unavailable' >&2
    exit 1
}

release_root=${1:-}
artifact_id=${2:-}
[ "$#" -eq 2 ] || fail
for utility in find grep realpath; do
    command -v "$utility" >/dev/null 2>&1 || fail
done
printf '%s\n' "$artifact_id" | grep -Eq '^stage09-p1-[a-z0-9][a-z0-9._-]*$' || fail
case "$artifact_id" in *latest*) fail ;; esac
[ "$release_root" = "$release_base/$artifact_id" ] || fail
[ -d "$release_root" ] && [ ! -L "$release_root" ] || fail
resolved_release_root=$(realpath "$release_root") || fail
[ "$resolved_release_root" = "$release_root" ] || fail

# Reject every link: a release checksum must never traverse an alternate tree.
[ -z "$(find "$release_root" -type l -print -quit)" ] || fail

# The release bundle must be complete before any target-side service, data or
# ingress action. These are fixed current P1-B paths; every item must be an
# in-tree regular file instead of a link into an alternate release tree.
for required in \
    backend/alembic.ini \
    backend/alembic/versions/20260720_0032_stage08_knowledge_indexing.py \
    deploy/stage09-native/runtime/runtime.env.example \
    deploy/stage09-native/nginx/stage09-p1.conf.template \
    deploy/stage09-native/postgresql/stage09-p1-bootstrap.sql \
    deploy/stage09-native/postgresql/stage09-p1-hba.conf.fragment \
    deploy/stage09-native/redis/redis-stage09-p1.conf \
    deploy/stage09-native/systemd/stage09-p1-api.service \
    deploy/stage09-native/systemd/stage09-p1-worker.service \
    deploy/stage09-native/systemd/stage09-p1-outbox-bridge.service \
    deploy/stage09-native/systemd/stage09-p1-redis.service \
    deploy/stage09-native/systemd/stage09-p1-migrate.service \
    deploy/stage09-native/scripts/validate-runtime-presence.sh \
    deploy/stage09-native/scripts/verify-native-isolation.sh \
    deploy/stage09-native/scripts/verify-native-service-assets.sh \
    deploy/stage09-native/scripts/verify-native-data-assets.sh \
    deploy/stage09-native/scripts/verify-release-layout.sh \
    deploy/stage09-native/scripts/create-release-manifest.sh \
    deploy/stage09-native/scripts/verify-fixed-migration-offline.sh \
    deploy/stage09-native/scripts/verify-release-assets.sh \
    deploy/stage09-native/scripts/inspect-native-host-readiness.sh
do
    [ -f "$release_root/$required" ] && [ ! -L "$release_root/$required" ] || fail
done

# Built frontend assets are deployed separately at /var/www/stage09-p1/<id>.
# The source release must not pretend to contain P1-B static assets.
forbidden=$(find "$release_root" \( \
    \( -name '.env' -o -name '.env.*' \) ! -path "$release_root/backend/.env.example" -o \
    -name 'runtime.env' -o \
    -name '.git' -o -name 'node_modules' -o -name 'secrets' \
\) -print -quit)
[ -z "$forbidden" ] || fail

printf '%s\n' 'release-layout: pass'
printf '%s\n' "artifact-id: $artifact_id"
printf '%s\n' 'static-assets: external-p1-b-required'
