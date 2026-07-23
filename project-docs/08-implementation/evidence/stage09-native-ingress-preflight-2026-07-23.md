# Stage09 r23 原生 ingress 无破坏 preflight 证据

## Status

- Status: `preflight-pass-candidate-not-active`
- Date: `2026-07-23`
- Artifact: `stage09-p1-20260723-r23`
- Source commit: `0d930d677cbf059c9c9a3907dabc07e37aa7b355`
- Runtime release retained: `stage09-p1-20260723-r22`
- Scope: 仅构建和写入 r23 source/venv/static candidate、候选 checksum manifest 与临时 preflight 文件。
- Result: r23 通过候选级 preflight，但没有切换、激活、reload 或 restart；r22 继续提供服务。

本文只记录 artifact、boolean、聚合数量、退出状态和 HTTP status code。真实 hostname、服务器地址、SSH 身份、环境值、token、chat/user ID、Caddy runtime JSON 与业务行均未记录。

## 1. 本地构建与密封边界

| Check | Result |
| --- | --- |
| HEAD | `0d930d6` |
| Task2 `test-native-service-assets.sh` | `exit 0` |
| Task2 `test-native-data-assets.sh` | `exit 0` |
| Task2 `test-public-ingress-assets.sh` | `exit 0` |
| Task2 `test-native-public-ingress-assets.sh` | `exit 0` |
| Task2 `test-retire-legacy-stage03-docker.sh` | `exit 0`，六项 receipt 均 `PASS` |
| Task2 `test-release-assets.sh` | `exit 0` |
| Task2 `verify-release-assets.sh` | `exit 0` |
| `mini-app` production build | `npm.cmd run build`，`exit 0` |
| source archive roots | `backend` + `deploy/stage09-native` only |
| exact `.env` | `false` |
| `deploy/stage03` | `false` |
| `deploy/stage07-acceptance` | `false` |
| source archive static build | `false` |
| static archive `index.html` count | `1` |

source archive 由 `git archive HEAD -- backend deploy/stage09-native` 生成，不读取 worktree 未提交内容。Mini App static archive 只来自本轮成功的 `mini-app/dist`。

本地 archive SHA-256：

- source: `0a4ac108a9202278e98176cb4fb3af025da6c7311547292f20b9710f01484e05`
- static: `27afefeec63df4770f9ee66f10adca8d031c3a5516848059e634f574f92e0a9d`

本机没有 Nginx、PostgreSQL、Redis 或 systemd live fixture，因此 Task2 repository suite 对相应 live 项保留其既有 `SKIPPED`；这些项目没有被伪造成成功。服务器候选 preflight 在后续章节单独给出。

## 2. 上传与服务器写入范围

首次多文件 SCP 和后续 legacy SCP 都在传输层挂起并被连接关闭；只读检查确认当时远端四个目标均不存在，没有残留。随后改用带 `BatchMode`、`ConnectTimeout`、`ServerAliveInterval` 与 `ServerAliveCountMax` 的 SSH stdin，逐文件写入本轮固定 `.partial`，再原子改名。服务器重新计算两份 SHA-256，均为 `true`。

服务器持久写入仅包括：

- `/opt/stage09-p1/releases/stage09-p1-20260723-r23`
- `/opt/stage09-p1/venv/stage09-p1-20260723-r23`
- `/var/www/stage09-p1/stage09-p1-20260723-r23`
- `/opt/stage09-p1/releases/stage09-p1-20260723-r23.manifest.sha256`

候选 manifest SHA-256：

- `e4b45906b1c342dfb7352255a577cb3b913f5fded4e6bc5414120400833004a0`

服务器临时上传、venv build log/status、runtime copy、离线 SQL、Caddy runtime JSON、临时 hostname 列表、Nginx prefix 与临时证书均已删除；最终聚合检查为 `server_temporary_file_count=0`。没有删除任何旧 release、venv、static、backup、Docker、Caddy、数据库或业务资源。

## 3. r23 候选 preflight

| Check | Result |
| --- | --- |
| uploaded source SHA-256 | `true` |
| uploaded static SHA-256 | `true` |
| source non-candidate entry count | `0` |
| source forbidden entry count | `0` |
| r23 targets absent before create | `true` |
| sealed release layout | `true` |
| sealed release assets | `true` |
| native service assets | `true` |
| native data assets | `true` |
| static symlink count | `0` |
| static `index.html` count | `1` |
| isolated venv build | `exit_code=0`, `venv_ready=true` |
| fixed migration `20260720_0032 --sql` | `true` |
| actual database migration | `false` |
| candidate runtime preflight | `true` |
| candidate native isolation | `true` |
| manifest full `sha256sum -c` | `true` |
| candidate complete | `true` |

runtime preflight 使用 `/etc/stage09-p1/runtime.env` 的 root-only 临时副本，只把 `STAGE09_P1_ARTIFACT_ID` 与 `STAGE09_P1_RELEASE_DIR` 改为 r23 后运行 validator/isolation。临时副本没有回显；没有写回 `/etc`，没有启动应用，也没有调用 Telegram、LLM、Provider、数据库或业务 API。

## 4. Nginx RED/GREEN gate

hostname 只从现行 Caddy Admin runtime 的只读临时 JSON 中筛选：候选必须指向 Stage09 内部 `:18090` upstream、外部 `/health` 返回 200，并被 r23 renderer 接受。检测到两个现行真实别名；两者均满足条件，但其值不进入证据。

| Gate | Result |
| --- | --- |
| invalid hostname renderer RED | `invalid_hostname_rejected=true` |
| accepted real hostname count | `2` |
| HTTP candidate rendered | `true` |
| HTTP isolated-prefix `nginx -t` | `true` |
| HTTPS candidate rendered | `true` |
| HTTPS isolated-prefix `nginx -t` | `true` |
| temporary files root-owned | `true` |
| `/etc/nginx` write | `false` |
| Nginx reload/restart | `false` |
| port 80/443 bind | `false` |

HTTP 与 HTTPS 均由 r23 `render-native-public-nginx.sh` 写入 root-owned `mktemp` prefix。HTTPS 仅使用该 prefix 内的一天期临时自签证书做语法验证；没有替换或读取生产证书，也没有启动 Nginx worker。

## 5. r22 before/after 不变证明

| Check | Before | After |
| --- | --- | --- |
| `/opt/stage09-p1/current` resolves to r22 | `true` | `true` |
| `/opt/stage09-p1/current-venv` resolves to r22 | `true` | `true` |
| `/var/www/stage09-p1/current` resolves to r22 | `true` | `true` |
| API/worker/outbox/Redis/Nginx active | `true` | `true` |
| loopback `/health` | `200` | `200` |
| active external hostname `/health` | `2/2 -> 200` | `2/2 -> 200` |

最初尝试从落盘 Caddyfile 发现 hostname 时得到候选数 `0`，因为现行 Stage09 route 只存在于 Caddy Admin runtime；这不是 health 失败。改用只读 Admin JSON 后确认两个现行别名均返回 200。过程中未修改 Caddyfile、Admin config、容器或网络。

## 6. 禁止项与后续门禁

| Boundary | Performed |
| --- | --- |
| source/current symlink switch | `false` |
| venv/current symlink switch | `false` |
| static/current symlink switch | `false` |
| systemd unit write/reload/restart | `false` |
| `/etc` Nginx write | `false` |
| Caddy/Docker write | `false` |
| DNS write | `false` |
| Telegram write/call | `false` |
| LLM/Provider call | `false` |
| real migration | `false` |
| business data read/write | `false` |
| old resource deletion | `false` |

r23 仍是 `candidate-not-active`。任何 source/venv/static 原子切换、systemd 行为、原生 ingress 写入或历史 Docker retirement 都是新的独立授权门禁，不由本次 preflight 自动允许。
