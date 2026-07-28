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
for utility in find grep od realpath; do
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
    backend/alembic/versions/20260723_0033_mini_app_browser_handoffs.py \
    backend/alembic/versions/20260728_0034_agent_event_runtime.py \
    mini-app/dist/browser-handoff.html \
    deploy/stage09-native/runtime/runtime.env.example \
    deploy/stage09-native/nginx/stage09-p1.conf.template \
    deploy/stage09-native/nginx/stage09-p1-public-http.conf.template \
    deploy/stage09-native/nginx/stage09-p1-public-https.conf.template \
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
    deploy/stage09-native/scripts/inspect-native-host-readiness.sh \
    deploy/stage09-native/scripts/render-caddy-stage09-host.sh \
    deploy/stage09-native/scripts/activate-public-ingress.sh \
    deploy/stage09-native/scripts/test-public-ingress-assets.sh \
    deploy/stage09-native/scripts/render-native-public-nginx.sh \
    deploy/stage09-native/scripts/test-native-public-ingress-assets.sh \
    deploy/stage09-native/scripts/verify-static-artifact-parity.sh \
    deploy/stage09-native/scripts/verify-activation-readiness.sh \
    deploy/stage09-native/scripts/test-readiness-gate.sh \
    deploy/stage09-native/scripts/retire-legacy-stage03-docker.sh \
    deploy/stage09-native/scripts/test-retire-legacy-stage03-docker.sh
do
    [ -f "$release_root/$required" ] && [ ! -L "$release_root/$required" ] || fail
done

# The browser handoff is a static page, not an API response.  Its sealed
# production artifact must never embed Telegram init-data or a ticket-shaped
# credential literal.
handoff_asset="$release_root/mini-app/dist/browser-handoff.html"
if grep -Eq 'tgWebAppData|ticket=' "$handoff_asset"; then
    fail
fi

# systemd executes the isolation guard directly from the sealed release. Keep
# every shipped deployment script executable so a Windows archive cannot turn
# an otherwise valid release into a 203/EXEC startup failure.
case "$(uname -s)" in
    MINGW*|MSYS*) : ;; # Git-Bash fixtures cannot faithfully represent Unix x bits.
    *)
        for script in "$release_root"/deploy/stage09-native/scripts/*.sh; do
            [ -f "$script" ] && [ -x "$script" ] || fail
        done
        ;;
esac

# Native service, SQL, Nginx and shell assets are all inspected by POSIX tools
# on the target host. Reject CRLF anywhere in their sealed tree before a
# release can become current: a CRLF unit or SQL file invalidates exact-line
# security validation just as surely as a CRLF shell script breaks dash.
if find "$release_root/deploy/stage09-native" -type f -print | while IFS= read -r asset; do
    if od -An -tx1 "$asset" | grep -Eq '(^|[[:space:]])0d([[:space:]]|$)'; then
        exit 1
    fi
done
then
    :
else
    fail
fi

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
