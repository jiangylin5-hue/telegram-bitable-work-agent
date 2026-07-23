# Stage09 r23 原生 ingress 无破坏 preflight 证据

## Status

- Status: `preflight-pass-candidate-not-active`
- Date: `2026-07-23`
- Artifact: `stage09-p1-20260723-r23`
- Source commit: `0d930d677cbf059c9c9a3907dabc07e37aa7b355`
- Runtime release retained: `stage09-p1-20260723-r22`
- Scope: 仅构建和写入 r23 source/venv/static candidate、候选 checksum manifest 与临时 preflight 文件。
- Result: r23 通过候选级 preflight，但没有切换、激活、reload 或 restart；r22 继续提供服务。

本文只记录 artifact、脱敏 command ID、相对时序、boolean、聚合数量、退出状态和 HTTP status code。真实 hostname、服务器地址、SSH 身份、环境值、token、chat/user ID、Caddy runtime JSON、命令原文、动态路径值与业务行均未记录。artifact ID 与本文自定义 command ID 是 brief 要求的非敏感追踪键。

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

服务器持久写入仅包括以下语义范围，不在证据中重复实际路径值：

- r23 immutable source candidate；
- r23 isolated venv candidate；
- r23 static candidate；
- r23 checksum manifest。

候选 manifest SHA-256：

- `e4b45906b1c342dfb7352255a577cb3b913f5fded4e6bc5414120400833004a0`

服务器临时上传、venv build log/status、runtime copy、离线 SQL、Caddy runtime JSON、临时 hostname 列表、Nginx prefix 与临时证书均已删除；最终聚合检查为 `server_temporary_file_count=0`。没有删除任何旧 release、venv、static、backup、Docker、Caddy、数据库或业务资源。

## 3. r23 候选 preflight

| Check | Result | Server exit code |
| --- | --- | --- |
| uploaded source SHA-256 | `true` | `0` |
| uploaded static SHA-256 | `true` | `0` |
| source non-candidate entry count | `0` | `0` |
| source forbidden entry count | `0` | `0` |
| r23 targets absent before create | `true` | `0` |
| sealed release layout | `true` | `0` |
| sealed release assets | `true` | `0` |
| native service assets | `true` | `0` |
| native data assets | `true` | `0` |
| static symlink count | `0` | `0` |
| static `index.html` count | `1` | `0` |
| isolated venv build | `venv_ready=true` | `0` |
| fixed migration `20260720_0032 --sql` | `true` | `0` |
| actual database migration | `false`, `not-performed` | `N/A` |
| candidate runtime preflight | `true` | `0` |
| candidate native isolation | `true` | `0` |
| manifest full `sha256sum -c` | `true` | `0` |
| candidate complete | `true` | `0` |

runtime preflight 仅以受限方式读取 runtime env 并创建 root-only 临时副本，只把 artifact/release 两个候选定位字段改为 r23 后运行 validator/isolation。临时副本没有回显；未写 `/etc`，没有启动应用，也没有调用 Telegram、LLM、Provider、数据库或业务 API。

## 4. Nginx RED/GREEN gate

hostname 只从现行 Caddy Admin runtime 的只读临时 JSON 中筛选：候选必须指向内部 Stage09 upstream、外部 `/health` 返回 200，并被 r23 renderer 接受。检测到两个现行真实别名；两者均满足条件，但其值不进入证据。

| Gate | Result | Server exit code / HTTP status |
| --- | --- | --- |
| invalid hostname renderer RED | `invalid_hostname_rejected=true` | renderer nonzero as expected; enclosing check `0` |
| accepted real hostname count | `2` | external HTTP `200` for `2/2`; enclosing check `0` |
| HTTP candidate rendered | `true` | `0` |
| HTTP isolated-prefix `nginx -t` | `true` | `0` |
| HTTPS candidate rendered | `true` | `0` |
| HTTPS isolated-prefix `nginx -t` | `true` | `0` |
| temporary files root-owned | `true` | `0` |
| `/etc/nginx` write | `false`, `not-performed` | `N/A` |
| Nginx reload/restart | `false`, `not-performed` | `N/A` |
| port 80/443 bind | `false`, `not-performed` | `N/A` |

HTTP 与 HTTPS 均由 r23 `render-native-public-nginx.sh` 写入 root-owned `mktemp` prefix。HTTPS 仅使用该 prefix 内的一天期临时自签证书做语法验证；没有替换或读取生产证书，也没有启动 Nginx worker。

## 5. r22 before/after 不变证明

| Symlink role | Expected artifact | Before match | After match | Proof command IDs | Check exit code |
| --- | --- | --- | --- | --- | --- |
| source current | r22 | `true` | `true` | `SRV-09`, `SRV-16`, `SRV-18` | `0` |
| venv current | r22 | `true` | `true` | `SRV-09`, `SRV-16`, `SRV-18` | `0` |
| static current | r22 | `true` | `true` | `SRV-09`, `SRV-16`, `SRV-18` | `0` |

| Runtime check | Before | After | Proof command IDs | Exit code / HTTP status |
| --- | --- | --- | --- | --- |
| API/worker/outbox/Redis/Nginx active | `true` | `true` | `SRV-01`, `SRV-16`, `SRV-18` | final checks `0` |
| loopback `/health` | `200` | `200` | `SRV-01`, `SRV-16`, `SRV-18` | HTTP `200`; final checks `0` |
| active external hostname `/health` | `2/2 -> 200` | `2/2 -> 200` | `SRV-05`, `SRV-16`, `SRV-18` | HTTP `200`; checks `0` |

最初尝试从落盘 Caddyfile 发现 hostname 时得到候选数 `0`，因为现行 Stage09 route 只存在于 Caddy Admin runtime；这不是 health 失败。改用只读 Admin JSON 后确认两个现行别名均返回 200。过程中未修改 Caddyfile、Admin config、容器或网络。

## 6. 脱敏服务器 command ledger

`Relative checkpoint` 是相对于“创建 r23 candidate”这一动作的阶段标记，不是推算的 wall-clock 时间。表中不伪造命令原文、UTC 时间、hostname、环境值、身份值或动态路径值。失败诊断也保留真实退出码。

| Order | Command ID | Relative checkpoint | Action | Result / status | Exit code |
| --- | --- | --- | --- | --- | --- |
| 01 | `SRV-01` | `before-write` | r22 symlink/service/loopback 与静态 hostname 发现初检 | symlink match `true`；services `true`；loopback HTTP `200`；静态 hostname 发现未命中 | `1` |
| 02 | `SRV-02` | `before-write` | 只读静态 Caddy 元数据诊断 | 容器聚合数量有效；managed marker count `0` | `0` |
| 03 | `SRV-03` | `before-write` | 只读落盘 route 诊断 | hostname candidate count `0`；未形成 external health 结论 | `1` |
| 04 | `SRV-04` | `before-write` | 只读 Admin runtime 单一候选假设检查 | candidate count `2`，单一候选假设不成立 | `1` |
| 05 | `SRV-05` | `before-write` | 只读 Admin runtime 全候选 health 检查 | external HTTP `200` for `2/2`；before health gate complete | `0` |
| 06 | `SRV-06` | `before-write` | 上传残留诊断脚本首次解析 | 未执行文件结论，shell parse fail | `1` |
| 07 | `SRV-07` | `before-write` | 修正后的上传残留诊断 | 四个目标均不存在，hash status `false` because absent | `0` |
| 08 | `SRV-08` | `upload` | 受控 SSH stdin 传输 | file count `4/4`；transport complete | `0` |
| 09 | `SRV-09` | `after-upload-before-create` | server hash、archive boundary、target absence、r22 expected-match gate | all required boolean `true`；forbidden entry count `0` | `0` |
| 10 | `SRV-10` | `candidate-create` | source/static seal、layout/assets 与 manifest | all validators pass；static symlink count `0` | `0` |
| 11 | `SRV-11` | `candidate-create` | isolated venv background start | start accepted | `0` |
| 12 | `SRV-12` | `candidate-create` | venv status query first attempt | query shell parse fail；build unaffected | `1` |
| 13 | `SRV-13` | `candidate-create` | venv completion query | `venv_ready=true`；build exit `0` | `0` |
| 14 | `SRV-14` | `candidate-preflight` | sealed layout/assets、fixed migration offline、runtime/isolation | five booleans `true` | `0` |
| 15 | `SRV-15` | `candidate-preflight` | Nginx RED/GREEN temporary-prefix gate | invalid hostname rejected；HTTP/HTTPS `nginx -t=true`；external HTTP `200` | `0` |
| 16 | `SRV-16` | `after-preflight` | candidate completeness、manifest、r22/service/health after proof | candidate/manifest `true`；r22 match `true`；loopback/external HTTP `200` | `0` |
| 17 | `SRV-17` | `after-preflight` | 本轮 server temporary cleanup | remaining count `0` | `0` |
| 18 | `SRV-18` | `final-verification` | final manifest/process/temp/r22/service/health proof | all booleans `true`；loopback/external HTTP `200` | `0` |

传输层另有两次本地 SCP 调用因连接级挂起被工具终止，退出码均为 `124`。它们不是成功的 server check；`SRV-07` 已证明无远端残留，`SRV-08` 是最终成功传输路径。

## 7. 禁止项与后续门禁

下表是本次 action ledger 的 before/after 审计，不冒充未采集的 filesystem snapshot，也不伪造命令原文。

| Boundary | Before action count | After action count | Status |
| --- | --- | --- | --- |
| source/current symlink switch | `0` | `0` | `not-performed`; expected r22 match `true` |
| venv/current symlink switch | `0` | `0` | `not-performed`; expected r22 match `true` |
| static/current symlink switch | `0` | `0` | `not-performed`; expected r22 match `true` |
| systemd unit write/reload/restart | `0` | `0` | `not-performed`; services remained active |
| `/etc` write | `0` | `0` | `not-performed`; runtime env was read only in a restricted validator flow |
| Caddy/Docker write | `0` | `0` | `not-performed`; runtime inspection only |
| DNS write | `0` | `0` | `not-performed` |
| port 80/443 bind | `0` | `0` | `not-performed`; `nginx -t` only |
| Telegram write/call | `0` | `0` | `not-performed` |
| LLM/Provider call | `0` | `0` | `not-performed` |
| real migration | `0` | `0` | `not-performed`; offline SQL only |
| business data read/write | `0` | `0` | `not-performed` |
| old resource deletion | `0` | `0` | `not-performed` |

r23 仍是 `candidate-not-active`。任何 source/venv/static 原子切换、systemd 行为、原生 ingress 写入或历史 Docker retirement 都是新的独立授权门禁，不由本次 preflight 自动允许。
