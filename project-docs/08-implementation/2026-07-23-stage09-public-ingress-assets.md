# Stage09 Public Ingress Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为已验证的 Stage03 Docker Caddy → Stage09 原生 Nginx 链路提供可审阅、可回滚、尚不执行公网写入的部署资产。

**Architecture:** 新增 host renderer 只根据受控 hostname 与私网 upstream 生成独立 Caddy block。activation script 在真正执行时动态发现唯一的 80/443 Caddy 容器、其 Caddyfile host mount、Caddy 私网 IP 与 bridge gateway；先将 Nginx 限制在 gateway 和 Caddy `/32`，再追加唯一标记 block。任何校验/健康检查失败都恢复 Nginx 与 Caddyfile 的备份。脚本不会停止、替换、升级或重建 Stage03 容器。

**Tech Stack:** POSIX `sh`、Docker CLI、Caddy CLI、Nginx、现有 `render-nginx-config.sh`、Git Bash fixture tests。

## Global Constraints

- 仅在用户提供 hostname、DNS 已解析、且明确授权后，activation script 才可在服务器执行。
- 不监听 `0.0.0.0`、不改 80/443、不给 PostgreSQL/Redis 增加网络暴露。
- Nginx bridge listener 必须只绑定已发现的私网 gateway，并只 `allow` Caddy 单 IP `/32`。
- Caddy 只能追加一个带 `stage09-managed` marker 的 host block；原有 host 的字节内容不可修改。
- Caddyfile 必须是容器 `/etc/caddy/Caddyfile` 的可写 host mount；发现 0 或多于 1 个公开 Caddy 容器即 fail closed。
- 所有输出只可含状态、布尔值、artifact id 与 hostname；不得打印 token、runtime env、数据库 URL、Caddyfile 原文、bridge IP 或业务数据。
- 真实公网、Caddy、Nginx、DNS、Telegram 写入不在本计划的本地实现阶段执行。

---

### Task 1: 受控 Caddy host renderer

**Files:**

- Create: `deploy/stage09-native/scripts/render-caddy-stage09-host.sh`
- Create: `deploy/stage09-native/scripts/test-public-ingress-assets.sh`

**Interfaces:**

- Consumes: `STAGE09_P1_PUBLIC_HOSTNAME`、`STAGE09_P1_CADDY_UPSTREAM_HOST`、`STAGE09_P1_CADDY_UPSTREAM_PORT`。
- Produces: stdout 上唯一的 Caddyfile block；成功输出不含诊断。
- Exit: 输入缺失、非 FQDN、含空格/路径/通配符、非私网 IPv4、端口非 `18090` 或包含 Stage03/Stage07/Docker marker 时退出非 0。

- [x] **Step 1: 写 failing renderer test**

```sh
STAGE09_P1_PUBLIC_HOSTNAME=agent.example.com \
STAGE09_P1_CADDY_UPSTREAM_HOST=172.20.0.1 \
STAGE09_P1_CADDY_UPSTREAM_PORT=18090 \
sh "$renderer" > "$tmpdir/rendered"
grep -Fxq '# stage09-managed: agent.example.com' "$tmpdir/rendered"
grep -Fxq 'agent.example.com {' "$tmpdir/rendered"
grep -Fxq '    reverse_proxy 172.20.0.1:18090' "$tmpdir/rendered"
```

同时用循环断言以下输入失败且 stdout 为空：`localhost`、`*.example.com`、`agent example.com`、`agent.example.com/health`、`8.8.8.8`、`stage03.example.com`、`stage07.example.com`、非私网 upstream、非 `18090` 端口。

- [x] **Step 2: 执行 RED**

Run: `sh deploy/stage09-native/scripts/test-public-ingress-assets.sh`

Expected: FAIL，原因是 renderer 尚不存在。

- [x] **Step 3: 实现最小 renderer**

```sh
#!/bin/sh
set -eu
fail() { printf '%s\n' 'caddy-host-render: fail' >&2; exit 1; }
# 验证 hostname 为至少一个点、每段 RFC 1123 风格、总长 <= 253。
# 验证 upstream 为 RFC1918 IPv4，port 恰为 18090。
# 拒绝 stage03/stage07/docker/compose/container/placeholder 标记。
# 成功时只输出 marker、hostname block 与 reverse_proxy。
```

输出固定为：

```caddyfile
# stage09-managed: agent.example.com
agent.example.com {
    reverse_proxy 172.20.0.1:18090
}
```

- [x] **Step 4: 执行 GREEN**

Run: `sh deploy/stage09-native/scripts/test-public-ingress-assets.sh`

Expected: renderer valid/invalid fixture 全部 PASS。

- [x] **Step 5: Commit**

```bash
git add deploy/stage09-native/scripts/render-caddy-stage09-host.sh deploy/stage09-native/scripts/test-public-ingress-assets.sh
git commit -m "feat: add Stage09 Caddy host renderer"
```

### Task 2: 原子 public-ingress activation script

**Files:**

- Create: `deploy/stage09-native/scripts/activate-public-ingress.sh`
- Modify: `deploy/stage09-native/scripts/test-public-ingress-assets.sh`

**Interfaces:**

- Consumes: 一个 positional `hostname`；现有 `/opt/stage09-p1/current`、`/etc/nginx/sites-available/stage09-p1.conf`、Docker Caddy container。
- Produces: 成功时受限 Nginx bridge listener 和单一 Caddy host；失败时恢复两个原配置文件，并 reload 恢复服务。
- Preconditions: hostname 与 `getent ahostsv4` 均有效；恰好一个公开 Caddy 容器；Caddyfile host mount 可写；Caddy 私网 IP/gateway 均存在；r5 内部 Nginx health 当前为 green。

- [x] **Step 1: 为 fail-closed 静态合同写 failing tests**

```sh
grep -Fq 'docker ps --format' "$activator"
grep -Fq 'CADDYFILE_MOUNT' "$activator"
grep -Fq 'STAGE09_P1_CADDY_SOURCE_CIDR="$caddy_address/32"' "$activator"
grep -Fq 'nginx -t' "$activator"
grep -Fq 'caddy validate' "$activator"
grep -Fq 'caddy reload' "$activator"
grep -Fq 'rollback' "$activator"
! grep -Eqi 'docker (stop|rm|restart|compose)|0\.0\.0\.0|host\.docker\.internal' "$activator"
```

- [x] **Step 2: 执行 RED**

Run: `sh deploy/stage09-native/scripts/test-public-ingress-assets.sh`

Expected: FAIL，原因是 activation script 尚不存在或缺少 required contract。

- [x] **Step 3: 实现 activation script**

实现顺序固定为：

```text
validate hostname and DNS
→ discover exactly one public Caddy container + writable Caddyfile mount
→ discover Caddy address and host bridge gateway
→ render Nginx with gateway bind / Caddy /32 allowlist
→ backup and atomically replace Nginx config
→ nginx -t + reload + Caddy-container-to-18090 health check
→ render unique Caddy block
→ backup Caddyfile + append only marker block
→ caddy validate + reload
→ verify host HTTPS/health
→ persist only redacted status ledger
```

`trap` rollback 必须恢复原 Nginx 和 Caddyfile；校验/reload Nginx；在原 Caddyfile 恢复后执行 Caddy reload。任何已经存在的 hostname marker、Caddyfile 多 mount、DNS 缺失、Caddy health 失败、Caddy validate/reload 失败都必须 fail closed。

- [x] **Step 4: 执行 GREEN**

Run: `sh deploy/stage09-native/scripts/test-public-ingress-assets.sh && sh -n deploy/stage09-native/scripts/activate-public-ingress.sh`

Expected: PASS；不在本机或服务器执行 activation script。

- [x] **Step 5: Commit**

```bash
git add deploy/stage09-native/scripts/activate-public-ingress.sh deploy/stage09-native/scripts/test-public-ingress-assets.sh
git commit -m "feat: add controlled Stage09 public ingress activation"
```

### Task 3: 发布资产与上线前合同

**Files:**

- Modify: `deploy/stage09-native/scripts/verify-release-layout.sh`
- Modify: `deploy/stage09-native/scripts/test-release-assets.sh`
- Modify: `project-docs/08-implementation/STAGE_09_NATIVE_SERVER_DEPLOYMENT_PLAN.md`
- Modify: `project-docs/08-implementation/evidence/stage09-public-ingress-readiness-audit-2026-07-23.md`

**Interfaces:**

- Release layout requires renderer、activator 和其 fixture test as sealed regular-file Stage09 assets；服务器以 `sh` 调用它们，保持与既有 100644 脚本一致。
- Evidence must state that these are local-ready assets, not authorization to execute them.

- [x] **Step 1: 写 failing release-completeness assertion**

在 `test-release-assets.sh` 的 required asset loop 加入：

```sh
deploy/stage09-native/scripts/render-caddy-stage09-host.sh \
deploy/stage09-native/scripts/activate-public-ingress.sh \
deploy/stage09-native/scripts/test-public-ingress-assets.sh
```

- [x] **Step 2: 执行 RED**

Run: `sh deploy/stage09-native/scripts/test-release-assets.sh`

Expected: FAIL，原因是 release verifier 还未把 public ingress assets 视为 sealed release requirement。

- [x] **Step 3: 最小修改 layout verifier 与文档**

在 `verify-release-layout.sh` 添加三个精确路径与 regular-file 检查；更新 Stage09 文档的 P2 preflight 与 rollback 说明，明确后续仍需要 hostname/DNS/explicit write authorization。

- [x] **Step 4: 执行 GREEN 和回归**

```bash
sh deploy/stage09-native/scripts/test-public-ingress-assets.sh
sh deploy/stage09-native/scripts/test-release-assets.sh
sh deploy/stage09-native/scripts/test-runtime-preflight.sh
sh -n deploy/stage09-native/scripts/render-caddy-stage09-host.sh
sh -n deploy/stage09-native/scripts/activate-public-ingress.sh
```

Expected: 全部 PASS；不触发 Docker、Nginx、Caddy、DNS 或 Telegram 写入。

- [x] **Step 5: Commit**

```bash
git add deploy/stage09-native project-docs/08-implementation
git commit -m "docs: prepare Stage09 public ingress release gate"
```

## Plan Self-Review

- Spec coverage: 覆盖已发现 Caddy bridge、Nginx `/32` 限制、Caddy 单 host、DNS gate、validate/reload、回滚、静态回归与文档边界。
- Placeholder scan: 无 `TODO`、`TBD` 或“适当处理”类步骤；所有生产写入均明确在 hostname/DNS/授权后才执行。
- Interface consistency: renderer 的三个环境变量由 activator 唯一供应；activator 使用 release 中的 renderer；release verifier 固定这三个脚本路径。
