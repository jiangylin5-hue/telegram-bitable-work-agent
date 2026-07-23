#!/bin/sh
# Static, repository-safe contract check for the N4A release validators.
set -eu

fail() { printf '%s\n' 'release-assets: fail' >&2; exit 1; }
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || fail
layout="$script_dir/verify-release-layout.sh"
manifest="$script_dir/create-release-manifest.sh"
migration="$script_dir/verify-fixed-migration-offline.sh"
test_script="$script_dir/test-release-assets.sh"
renderer="$script_dir/render-native-public-nginx.sh"
ingress_test="$script_dir/test-native-public-ingress-assets.sh"
readiness="$script_dir/verify-activation-readiness.sh"
readiness_test="$script_dir/test-readiness-gate.sh"
retire="$script_dir/retire-legacy-stage03-docker.sh"
retire_test="$script_dir/test-retire-legacy-stage03-docker.sh"
http_template="$script_dir/../nginx/stage09-p1-public-http.conf.template"
https_template="$script_dir/../nginx/stage09-p1-public-https.conf.template"

for script in "$layout" "$manifest" "$migration" "$test_script" "$renderer" "$ingress_test" "$readiness" "$readiness_test" "$retire" "$retire_test" "$0"; do sh -n "$script" || fail; done
grep -Fq 'release_base=/opt/stage09-p1/releases' "$layout" || fail
grep -Fq 'static-assets: external-p1-b-required' "$layout" || fail
grep -Fq "find \"\$release_root\" -type l" "$layout" || fail
grep -Fq 'realpath "$release_root"' "$layout" || fail
for required_path in \
    backend/alembic.ini \
    backend/alembic/versions/20260720_0032_stage08_knowledge_indexing.py \
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
    deploy/stage09-native/scripts/render-native-public-nginx.sh \
    deploy/stage09-native/scripts/test-native-public-ingress-assets.sh \
    deploy/stage09-native/scripts/verify-activation-readiness.sh \
    deploy/stage09-native/scripts/test-readiness-gate.sh \
    deploy/stage09-native/scripts/retire-legacy-stage03-docker.sh \
    deploy/stage09-native/scripts/test-retire-legacy-stage03-docker.sh
do
    grep -Fq "$required_path" "$layout" || fail
done
grep -Fq 'handoff_asset="$release_root/mini-app/dist/browser-handoff.html"' "$layout" || fail
grep -Fq "grep -Eq 'tgWebAppData|ticket=' \"\$handoff_asset\"" "$layout" || fail
grep -Fq -- "-name '.env'" "$layout" || fail
grep -Fq -- "-name 'runtime.env'" "$layout" || fail
grep -Fq -- "-name '.git'" "$layout" || fail
grep -Fq -- "-name 'node_modules'" "$layout" || fail
grep -Fq -- "-name 'secrets'" "$layout" || fail
grep -Fq 'LC_ALL=C sort' "$manifest" || fail
grep -Fq 'sha256sum' "$manifest" || fail
grep -Fq 'mv -f "$temp_path" "$output_file"' "$manifest" || fail
grep -Fqx "offline_database_url='postgresql+psycopg://stage09_p1:offline-placeholder@127.0.0.1:5432/stage09_p1'" "$migration" || fail
[ "$(grep -Fc 'env -u DATABASE_URL "DATABASE_URL=$offline_database_url"' "$migration")" -eq 2 ] || fail
grep -Fq 'venv_root="/opt/stage09-p1/venv/$artifact_id"' "$migration" || fail
grep -Fq 'python_bin="$venv_root/bin/python"' "$migration" || fail
grep -Fq 'resolved_python=$(realpath "$python_bin") || fail' "$migration" || fail
grep -Fq '"$venv_root"/*|/usr/bin/python3|/usr/bin/python3.12' "$migration" || fail
grep -Fq 'for utility in env grep mktemp mv realpath rm; do' "$migration" || fail
if grep -Fq '[ ! -L "$python_bin" ]' "$migration"; then fail; fi
if grep -Fq 'python_bin="$resolved_python"' "$migration"; then fail; fi
if grep -Eq 'runtime\.env|source[[:space:]]|ads_agent' "$migration"; then fail; fi
grep -Fq 'cmp -s "$manifest_one" "$manifest_two"' "$test_script" || fail
grep -Fq 'fixture-secret-value' "$test_script" || fail
grep -Fq 'expected_executable=' "$test_script" || fail
grep -Fq '[ "$0" = "$expected_executable" ] || exit 94' "$test_script" || fail
grep -Fq 'fake-python-link-target' "$test_script" || fail
grep -Fq 'heads-fixed-stage09-offline-url' "$test_script" || fail
grep -Fq 'upgrade-fixed-stage09-offline-url' "$test_script" || fail
grep -Fq 'migration-external-python-symlink-accepted' "$test_script" || fail
grep -Fq 'migration-external-python-symlink-output-created' "$test_script" || fail
grep -Fq 'missing-critical-unit-layout-accepted' "$test_script" || fail
grep -Fq 'missing-critical-unit-manifest-accepted' "$test_script" || fail
grep -Fq 'stage09-p1-api.service' "$test_script" || fail
if grep -Eq 'cat[[:space:]]*>|<<' "$test_script"; then fail; fi
grep -Fqx 'project_name=telegram-bitable-stage03' "$retire" || fail
grep -Fqx 'PATH=/usr/sbin:/usr/bin:/sbin:/bin' "$retire" || fail
grep -Fqx 'required_owner_uid=0' "$retire" || fail
grep -Fq 'RETIRE_LEGACY_TEST_' "$retire" && fail
grep -Fq 'docker system prune' "$retire" && fail
grep -Fq 'load_ready_archive || return 2' "$retire" || fail
grep -Fq 'write_ready_marker' "$retire" || fail
grep -Fq 'pg_restore -l' "$retire" || fail
grep -Fq 'python3 -m json.tool' "$retire" || fail
grep -Fq 'secure_archive_file' "$retire" || fail
grep -Fq 'all_images=$(docker images' "$retire" || fail
grep -Fq 'failed_retire_receipt' "$retire" || fail
grep -Fq 'custom_image_bytes_before' "$retire" || fail
grep -Fq 'released_bytes' "$retire" && fail
grep -Fq 'telegram-bitable-stage03-' "$retire" || fail
grep -Fq 'ready-archive-lifecycle: PASS' "$retire_test" || fail
grep -Fq 'partial-receipt: PASS' "$retire_test" || fail
grep -Fq 'retire-assets: PASS' "$retire_test" || fail
grep -Fq 'native-public-nginx: fail' "$renderer" || fail
grep -Fq 'STAGE09_P1_PUBLIC_HOSTNAME' "$renderer" || fail
grep -Fq 'STAGE09_P1_CERTIFICATE_PATH' "$renderer" || fail
grep -Fq 'STAGE09_P1_CERTIFICATE_KEY_PATH' "$renderer" || fail
grep -Fq 'listen 80;' "$http_template" || fail
grep -Fq 'root /var/www/stage09-p1/acme;' "$http_template" || fail
grep -Fq 'return 308 https://$host$request_uri;' "$http_template" || fail
grep -Fq 'listen 443 ssl http2;' "$https_template" || fail
grep -Fq 'proxy_pass http://127.0.0.1:18080;' "$https_template" || fail
grep -Fq 'location = /browser-handoff.html {' "$https_template" || fail
grep -Fq 'try_files /browser-handoff.html =404;' "$https_template" || fail
grep -Fq 'add_header Cache-Control "no-store" always;' "$https_template" || fail
grep -Fq 'add_header Referrer-Policy "no-referrer" always;' "$https_template" || fail
if grep -Eiq 'allow|deny|docker|caddy|stage03|stage07|5432|6379' "$http_template" "$https_template"; then fail; fi
grep -Fqx 'PATH=/usr/sbin:/usr/bin:/sbin:/bin' "$readiness" || fail
grep -Fqx 'max_retry_attempts=20' "$readiness" || fail
grep -Fqx 'interval_seconds=2' "$readiness" || fail
grep -Fqx 'total_deadline_seconds=40' "$readiness" || fail
grep -Fqx 'retry_attempt=0' "$readiness" || fail
grep -Fqx 'deadline_epoch=$((start_epoch + total_deadline_seconds))' "$readiness" || fail
grep -Fq -- '--connect-timeout "$curl_timeout" --max-time "$curl_timeout"' "$readiness" || fail
grep -Fq 'listener_row_owned_only_by_nginx' "$readiness" || fail
grep -Fq 'stage09-p1-api' "$readiness" || fail
grep -Fq 'stage09-p1-worker' "$readiness" || fail
grep -Fq 'stage09-p1-outbox-bridge' "$readiness" || fail
grep -Fq 'stage09-p1-redis' "$readiness" || fail
grep -Fq 'readiness-gate: fail' "$readiness" || fail
grep -Fq 'assert_pass immediate-success' "$readiness_test" || fail
grep -Fq 'for inactive_unit in stage09-p1-api stage09-p1-worker stage09-p1-outbox-bridge stage09-p1-redis nginx; do' "$readiness_test" || fail
grep -Fq 'assert_redacted_failure loopback-health' "$readiness_test" || fail
grep -Fq 'assert_redacted_failure https-root' "$readiness_test" || fail
grep -Fq 'assert_redacted_failure http-redirect' "$readiness_test" || fail
grep -Fq 'assert_redacted_failure acme' "$readiness_test" || fail
grep -Fq 'for listener_mode in http-non-nginx http-extra https-non-nginx https-extra db-public redis-public; do' "$readiness_test" || fail
printf '%s\n' 'release-assets: pass'
