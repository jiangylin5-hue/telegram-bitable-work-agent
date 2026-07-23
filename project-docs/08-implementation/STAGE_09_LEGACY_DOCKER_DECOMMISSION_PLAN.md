# Stage09 历史 Docker 下线实施计划

> **执行方式：** 本计划在当前 worktree 内逐任务执行；每个任务先写失败测试，再写最小实现，并在任务末尾提交。

**Goal：** 让原生 Nginx 安全接管 Stage09 的 HTTPS 入口，归档并下线历史 Stage03 Docker 运行时，回收无引用的 Stage09 发布包而不影响原生数据库、Redis 或 Telegram Mini App。

**Architecture：** 以一个只服务确切 hostname 的 Nginx HTTP/TLS renderer 取代 Caddy bridge；以一个仅识别固定 compose project 的 root-only retire script 完成归档和删除。原生 Uvicorn、PostgreSQL、pgvector、Redis 和 systemd unit 不改变。删除前保留 r22/r19 两个 release，且先通过公网和 Telegram 人工入口验证。

**Tech Stack：** POSIX shell、Nginx、Certbot/Let’s Encrypt、systemd、Docker CLI（仅下线旧资源）、PostgreSQL dump、Redis RDB、GitHub release branch。

## Global Constraints

- 不公开 PostgreSQL 5432、Redis 6379 或 Unix socket。
- 不读取或输出任何 runtime env、token、密码、消息正文、业务记录或归档正文。
- 固定保留 `stage09-p1-20260723-r22` 与 `stage09-p1-20260723-r19`；不删除当前 symlink 指向的文件。
- 仅删除 Docker label `com.docker.compose.project=telegram-bitable-stage03` 的容器、network、volume，以及自定义 `telegram-bitable-stage03-*` image；不执行 `docker system prune`，不删除 Docker daemon。
- 入口切换失败时恢复 Nginx 备份和 Caddy runtime JSON，不删除 Docker。

---

### Task 1：可验证的原生公网 Nginx renderer

**Files：**

- Create: `deploy/stage09-native/nginx/stage09-p1-public-http.conf.template`
- Create: `deploy/stage09-native/nginx/stage09-p1-public-https.conf.template`
- Create: `deploy/stage09-native/scripts/render-native-public-nginx.sh`
- Create: `deploy/stage09-native/scripts/test-native-public-ingress-assets.sh`
- Modify: `deploy/stage09-native/scripts/verify-release-layout.sh`
- Modify: `deploy/stage09-native/scripts/verify-release-assets.sh`
- Modify: `deploy/stage09-native/scripts/test-release-assets.sh`

**Interfaces：**

- Consumes: `STAGE09_P1_PUBLIC_HOSTNAME`, `STAGE09_P1_PUBLIC_MODE` (`http` or `https`), and in HTTPS mode `STAGE09_P1_CERTIFICATE_PATH` / `STAGE09_P1_CERTIFICATE_KEY_PATH`.
- Produces: stdout-only complete Nginx server block. On every invalid input it exits nonzero with exactly `native-public-nginx: fail` and never echoes input values.

- [ ] **Step 1: Write the failing renderer test**

```sh
http_output=$(STAGE09_P1_PUBLIC_HOSTNAME=stage07.jiangtest1.online \
  STAGE09_P1_PUBLIC_MODE=http \
  sh "$renderer") || fail http-render
assert_contains http-listen '    listen 80;' "$http_output"
assert_contains http-server-name '    server_name stage07.jiangtest1.online;' "$http_output"
assert_contains http-acme '        root /var/www/stage09-p1/acme;' "$http_output"

https_output=$(STAGE09_P1_PUBLIC_HOSTNAME=stage07.jiangtest1.online \
  STAGE09_P1_PUBLIC_MODE=https \
  STAGE09_P1_CERTIFICATE_PATH=/etc/letsencrypt/live/stage07.jiangtest1.online/fullchain.pem \
  STAGE09_P1_CERTIFICATE_KEY_PATH=/etc/letsencrypt/live/stage07.jiangtest1.online/privkey.pem \
  sh "$renderer") || fail https-render
assert_contains https-listen '    listen 443 ssl http2;' "$https_output"
assert_contains api-loopback '        proxy_pass http://127.0.0.1:18080;' "$https_output"
```

- [ ] **Step 2: Verify RED**

Run: `cd deploy/stage09-native && sh scripts/test-native-public-ingress-assets.sh`

Expected: nonzero because `render-native-public-nginx.sh` does not exist.

- [ ] **Step 3: Write the minimal renderer and templates**

```sh
case "${STAGE09_P1_PUBLIC_MODE:-}" in
  http) template="$asset_root/nginx/stage09-p1-public-http.conf.template" ;;
  https) template="$asset_root/nginx/stage09-p1-public-https.conf.template" ;;
  *) fail ;;
esac

is_hostname "$hostname" || fail
has_forbidden_marker "$hostname" && fail
sed -e "s|{{STAGE09_P1_PUBLIC_HOSTNAME}}|$hostname|g" "$template"
```

The HTTP template contains only ACME webroot and a `308` HTTPS redirect. The HTTPS template contains TLS directives, the existing static rules and proxy to `127.0.0.1:18080`; it never contains `allow`, `deny`, Docker, Caddy, Stage03, Stage07 placeholders or a public database/Redis endpoint.

- [ ] **Step 4: Verify GREEN and rejection coverage**

Run: `cd deploy/stage09-native && sh scripts/test-native-public-ingress-assets.sh`

Expected: `http-render: PASS`, `https-render: PASS`, `invalid-hostname: PASS`, `forbidden-marker: PASS`, `missing-keypair: PASS`, `nginx-config-syntax: PASS` (or explicit `SKIPPED` when Nginx is absent).

- [ ] **Step 5: Seal the new assets**

Add the two templates, renderer and test script to `verify-release-layout.sh`; add matching assertions and inert fixture paths to the two release regression scripts. Verify that every new shell script is executable and CRLF-free.

Run: `cd deploy/stage09-native && sh scripts/test-release-assets.sh && sh scripts/verify-release-assets.sh`

Expected: both exit 0.

- [ ] **Step 6: Commit**

```sh
git add deploy/stage09-native/nginx deploy/stage09-native/scripts
git commit -m "feat(stage09): add native public nginx renderer"
```

### Task 2：历史 Docker 归档与下线脚本

**Files：**

- Create: `deploy/stage09-native/scripts/retire-legacy-stage03-docker.sh`
- Create: `deploy/stage09-native/scripts/test-retire-legacy-stage03-docker.sh`
- Modify: `deploy/stage09-native/scripts/verify-release-layout.sh`
- Modify: `deploy/stage09-native/scripts/verify-release-assets.sh`
- Modify: `deploy/stage09-native/scripts/test-release-assets.sh`

**Interfaces：**

- Consumes: unconditional production root execution, a fixed trusted `PATH=/usr/sbin:/usr/bin:/sbin:/bin`, and a single argument `archive` or `retire`. Production has no environment-controlled test mode or caller-supplied command path.
- Produces: only aggregate receipt fields. `archive` reports `status`, `archive_manifest`, resource counts and `custom_image_bytes_before=0`; `retire` reports `status`, `archive_manifest`, `custom_image_bytes_before` and completed delete counts for containers, networks, volumes and custom images. It does not print archive paths, Docker inspect JSON, environment values, resource names or data contents.
- `archive` runs while Caddy is still available, never stops or removes a container, validates the complete root-owned archive and atomically publishes a single ready marker. `retire` never creates a new archive and never calls `docker exec`; it strictly reloads the existing ready archive, revalidates owner/mode, every required artifact, manifest, PostgreSQL catalog, Redis header, parseable Caddy JSON and archived resource set, then removes only the fixed compose project’s resources. Every pre-delete failure emits one fixed redacted `status=failed` receipt with zero completed delete counts.

- [ ] **Step 1: Write the failing safety test**

```sh
script="$script_dir/retire-legacy-stage03-docker.sh"
[ -x "$script" ] || fail retire-script-missing
grep -Fqx 'project_name=telegram-bitable-stage03' "$script" || fail fixed-project
grep -Fq 'docker system prune' "$script" && fail global-prune-forbidden
grep -Fq 'docker volume rm' "$script" || fail labelled-volume-removal-missing
grep -Fq 'sha256sum' "$script" || fail manifest-missing
grep -Fq 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' "$script" || fail postgres-dump-missing
grep -Fq 'redis-cli --rdb' "$script" || fail redis-rdb-missing
```

- [ ] **Step 2: Verify RED**

Run: `cd deploy/stage09-native && sh scripts/test-retire-legacy-stage03-docker.sh`

Expected: nonzero because the retire script does not exist.

- [ ] **Step 3: Write the minimal root-only implementation**

```sh
project_name=telegram-bitable-stage03
archive_root=/var/backups/stage09-p1/legacy-stage03
[ "$(id -u)" -eq 0 ] || fail
case "${1:-}" in archive|retire) mode=$1 ;; *) fail ;; esac

containers=$(docker ps -aq --filter "label=com.docker.compose.project=$project_name")
[ -n "$containers" ] || fail
umask 077
archive_dir=$(mktemp -d "$archive_root/retirement.XXXXXX") || fail
docker exec "$postgres_id" sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > "$archive_dir/postgres.dump"
docker exec "$redis_id" sh -c 'redis-cli --rdb /tmp/legacy.rdb >/dev/null && cat /tmp/legacy.rdb && rm -f /tmp/legacy.rdb' > "$archive_dir/redis.rdb"
```

The script obtains the compose working directory and Caddy Admin runtime config through narrowly formatted Docker calls, archives compose/Caddy/Nginx configuration, the three Stage09 symlink targets, PostgreSQL custom-format dump, Redis RDB and a name/size/time/digest resource inventory, then seals every required artifact in `manifest.sha256`. `pg_restore -l`, the Redis header and Caddy runtime JSON parser must succeed before the ready marker is atomically published. The archive root, ready marker, archive directory and every artifact are rechecked for root ownership, `0700` directories and `0600` files. Docker image enumeration is captured before filtering so a failed `docker images` command cannot masquerade as an empty custom-image set. In `retire` mode it consumes only that ready archive, removes label-scoped containers/networks/volumes and only custom images prefixed `telegram-bitable-stage03-`; base `caddy`, `redis` and `pgvector` images remain. Missing, ambiguous, incomplete, invalid or live-set-mismatched ready evidence emits a fixed aggregate `status=failed` receipt and exits before any deletion. A deletion failure produces `status=partial`, a nonzero exit and only aggregate completed delete counts.

- [ ] **Step 4: Verify GREEN**

Run: `cd deploy/stage09-native && sh scripts/test-retire-legacy-stage03-docker.sh`

Expected: `shell-syntax: PASS`, `ready-archive-lifecycle: PASS`, `archive-completeness: PASS`, `labelled-retirement: PASS`, `partial-receipt: PASS`, `retire-assets: PASS`.

- [ ] **Step 5: Seal and commit**

Add the script and test to the sealed-release requirements and fixture allowlist, then run the entire Stage09 shell suite.

Run: `cd deploy/stage09-native && sh scripts/test-native-service-assets.sh && sh scripts/test-native-data-assets.sh && sh scripts/test-public-ingress-assets.sh && sh scripts/test-native-public-ingress-assets.sh && sh scripts/test-retire-legacy-stage03-docker.sh && sh scripts/test-release-assets.sh && sh scripts/verify-release-assets.sh`

Expected: all commands exit 0.

```sh
git add deploy/stage09-native
git commit -m "feat(stage09): archive and retire legacy docker runtime"
```

### Task 3：构建 r23 并进行无破坏服务器 preflight

**Files：**

- Modify: `project-docs/08-implementation/STAGE_09_NATIVE_SERVER_DEPLOYMENT_PLAN.md`
- Create: `project-docs/08-implementation/evidence/stage09-native-ingress-preflight-2026-07-23.md`

**Interfaces：**

- Consumes: committed source tree and existing r22 runtime env.
- Produces: an immutable `stage09-p1-20260723-r23` source/venv/static candidate with checksum manifest and a sanitized preflight receipt. It must not change the `current` symlinks.

- [ ] **Step 1: Build and verify the candidate**

Run local asset tests from Task 2, `cd mini-app && npm run build`, and build the sealed source archive from tracked `backend` and `deploy/stage09-native` paths only.

Expected: no `.env`, `deploy/stage03`, `deploy/stage07-acceptance`, Docker Compose runtime or static build artifact is included in the source archive.

- [ ] **Step 2: Upload without switching current**

On the server, extract r23 under `/opt/stage09-p1/releases/`, create its isolated venv, deploy static files under `/var/www/stage09-p1/`, then run release-layout, release-assets, fixed migration, runtime preflight and `nginx -t` only. Record artifact id, boolean checks and status codes; do not print env values.

- [ ] **Step 3: Verify RED/GREEN gate**

Before any switch, intentionally render the native public config with an invalid hostname and confirm it fails. Render HTTP and HTTPS candidates with the real hostname only into root-owned temporary files and confirm `nginx -t` passes.

- [ ] **Step 4: Commit evidence**

```sh
git add project-docs/08-implementation
git commit -m "docs(stage09): record native ingress preflight"
```

### Task 4：受控公网切换、真实验收与旧资源清理

**Files：**

- Modify: `/etc/nginx/sites-available/stage09-p1.conf` on server only
- Create: `/var/backups/stage09-p1/legacy-stage03/<UTC>/` on server only
- Create: `project-docs/08-implementation/evidence/stage09-native-ingress-cutover-2026-07-23.md`
- Modify: `project-docs/08-implementation/STAGE_09_NATIVE_SERVER_DEPLOYMENT_PLAN.md`

**Interfaces：**

- Consumes: r23 candidate, verified Nginx renderer and root-only legacy archive.
- Produces: r23 as all three `current` symlink targets; valid native HTTPS endpoint; a retained r19 rollback; a root-only archive; zero legacy Docker resources after final user-visible acceptance.

- [ ] **Step 1: Archive first**

Run `retire-legacy-stage03-docker.sh archive` as root. Verify the manifest, PostgreSQL dump and Redis RDB are nonempty. Record counts only. If this command fails, stop and leave all containers running.

- [ ] **Step 2: Switch HTTP ownership and issue TLS**

Install/verify Certbot, write the HTTP-only candidate, run `nginx -t`, stop only the legacy Caddy container, reload Nginx, and obtain the certificate through its ACME webroot. If issuance fails, restore the saved Nginx config, start Caddy and load the archived runtime JSON before returning failure.

- [ ] **Step 3: Activate HTTPS and r23**

Write the HTTPS candidate, `nginx -t`, reload Nginx, atomically repoint the three Stage09 `current` symlinks to r23 and restart only Stage09 API/worker/outbox services. Keep r19 intact. Immediately invoke the sealed `verify-activation-readiness.sh --verify` with the protected hostname and fixed ACME probe-path contract. The verifier itself is read-only: it makes one immediate ready check and then at most `20` further checks at `2`-second intervals, with a hard `40`-second deadline from invocation (so it may make fewer follow-up checks when time is exhausted); every ready check requires each of API/worker/outbox/Redis/Nginx active plus loopback/public HTTPS health `200`. Every curl has bounded connect/max time and cannot outlive the remaining deadline. Only after ready does it validate HTTPS root/static, HTTP `308`, ACME `200`, that every 80/443 listener owner is Nginx, and PostgreSQL/Redis non-public boundaries.

If the gate exits nonzero, atomically restore all three saved r22 targets, restart only API/worker/outbox, and invoke the **same** verifier for r22. If r22 also fails its bounded gate, stop and record only the redacted failure receipt; do not attempt a second r23 switch, retire legacy Docker, or remove release artifacts.

- [ ] **Step 4: Fresh automated production checks**

The bounded verifier replaces the old one-shot health bundle. Retain only source release (`r23` or restored `r22`), verifier exit status, and aggregate pass/fail evidence. Do not record hostname, probe path, endpoint body, listener rows, runtime environment or data-plane details. A verifier `pass` is the single automated evidence for:

- five required units active;
- loopback and public HTTPS health `200` in the same attempt;
- HTTPS root/static and ACME `200`, HTTP root `308`;
- native Nginx owns HTTP/TLS listeners;
- PostgreSQL and Redis have no public TCP listener.

- [ ] **Step 5: Telegram Mini App acceptance**

User closes the existing Mini App window, clicks the Bot’s “打开工作区” button again, and confirms that the workspace is visible and relationship navigation is operable. If not, restore the archived Caddy runtime route before deleting Docker.

- [ ] **Step 6: Permanently retire and reclaim**

After the successful real UI confirmation, run `retire-legacy-stage03-docker.sh retire`. Then delete every unreferenced Stage09 source/venv/static artifact except r22/r19, verify root symlinks still resolve to r23, calculate reclaimed bytes, and run the checks from Step 4 again.

- [ ] **Step 7: Record and commit evidence**

```sh
git add project-docs/08-implementation
git commit -m "docs(stage09): record native ingress cutover"
git push origin codex/stage07-mini-app-ui
```

## Plan self-review

- Spec coverage: Tasks 1–2 implement the reusable configuration and archival primitives; Task 3 gates their server use; Task 4 performs the only destructive actions after archive, automated checks and user-visible Mini App validation.
- 占位符检查：未发现未决占位内容、延期实现表述或未指定的删除范围。
- Interface consistency: Task 1 renderer output is the only Nginx source used by Task 4; Task 2 archive mode is a prerequisite of Task 4 retire mode; Task 4 retains r22/r19 consistently with the global constraint.
