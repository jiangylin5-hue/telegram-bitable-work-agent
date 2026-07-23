# Stage09：原生服务器部署与本地数据库实施计划

## Status

- Current Progress Update (2026-07-23, r24 browser handoff release activated): 已从 Git commit `ea77237` 封存并激活 `stage09-p1-20260723-r24`。source、venv、static 三条 `current` 已原子切换；真实数据库已升级至 `20260723_0033`。HTTPS handoff 为 `200` 且含 `Cache-Control: no-store`/`Referrer-Policy: no-referrer`；HTTP root 为 `308`，五项服务 active，PostgreSQL/Redis 仍不公开监听。仅在既有 ACME webroot 增加并保留固定无凭据 probe，未改 Caddy、Docker、DNS、webhook、allowlist、业务记录或 LLM。r23 工件与 root-only rollback 配置备份均保留。real initData 不可安全复用，真实 handoff smoke blocked；受控 menu `get` 成功但三次 `setChatMenuButton` 均为 HTTP `400`/`button` 类错误，菜单配置未完成。Telegram Desktop 人工验收待用户执行；详细脱敏证据见 `evidence/stage09-desktop-workspace-handoff-2026-07-23.md`。

- Current Progress Update (2026-07-23, r23 bounded activation passed): 在 r22 基线、同一 40 秒 fail-closed readiness gate 和服务账号隔离预检均通过后，已执行第三次且受限的 r23 原子 activation。三条 `current` target 已切至 r23；API、worker、outbox、Redis、Nginx 通过同一 gate。独立公网复验得到 HTTP `308`、固定 ACME `200`、HTTPS health/首页/静态资源均为 `200`；HTTP/TLS 仅由 Nginx 占有，PostgreSQL/Redis 仍不公网监听。此前 r23 失败的根因已确认是新建 venv 对服务账号不可 traverse/exec；经用户授权，只将 r23 venv 及其内容设为该服务账号可读/执行的收敛权限，随后以该账号完成 import、只读 migration 与隔离回环 API health 预检。r22 仍完整保留为回退工件。未执行 Docker retirement、release/venv/static cleanup、数据库/Redis 写入或 Telegram/LLM/Provider 调用；历史 Docker 资源仍为已归档但未删除状态。临时 verifier/orchestration 已清理。详细脱敏证据见 `evidence/stage09-native-ingress-cutover-2026-07-23.md`；下一步是用户重新打开 Telegram Mini App 的人工验收，通过前不得 retirement 或清理。
- Current Progress Update (2026-07-23, r23 bounded readiness gate local-ready): 已新增 sealed release 内的 `verify-activation-readiness.sh` 及 focused contract。gate 只接受受保护环境中提供的确切公网 hostname 与固定 ACME probe path；先即时检查一次，随后最多 `20` 次、每次间隔 `2` 秒的后续检查，并以启动后 `40` 秒真实 deadline 为上限（剩余时间不足时不再开启新的检查）。每次检查逐一要求 API/worker/outbox/Redis/Nginx 为 active，且 loopback/public HTTPS health 为 `200`；仅在达到 ready 后才检查 HTTPS 首页和静态页面、HTTP `308`、ACME `200`、80/443 仅由 Nginx 占有及 PostgreSQL/Redis 非公网边界。所有 curl 同时受 connect/max-time 与剩余 deadline 约束。任何失败或超时只输出固定脱敏 receipt 并非零退出。该 gate 不切换 symlink、不 restart service、不写数据库/Redis，也不触发 Telegram/LLM；r23 仍为 candidate，尚未 SSH 或在服务器运行本资产。下一次 r23 激活和 r22 回退均必须调用同一个 gate。
- Current Progress Update (2026-07-23, r23 activation gate abort / r22 recovered): 在已授权的单次 r23 激活中，三条 `current` symlink 曾原子切向 r23，并只重启 API/worker/outbox。restart 返回后立即执行的 health gate 得到回环 `000`、公网 HTTPS health `502`，因此脚本已按 fail-closed 策略自动将三个 target 回退 r22，并只重启同三项服务。回退后的首次无写入 probe 已实测三链接 r22、相关 unit active、回环 health、HTTPS health 与首页均为 `200`；连续三次后续回环/公网 health 也均为 `200`。只读 systemd 证据显示 API 为 `Type=simple`、没有 `ExecStartPost` 或 readiness notification，当前 r22 invocation 的导入/迁移/配置/bind 错误分类均为 `0`。该证据说明即时 gate 不足以等待服务就绪，但**不**足以宣布 r23 没有运行时错误或已经启动成功；r23 仍是 candidate，未 active。下一独立激活前必须实现并复核“一次即时检查 + 最多 `20` 次、每 `2` 秒后续检查”的有界 readiness gate，整个调用自启动起严格不超过 `40` 秒；超时即回退 r22 并用同一上限证明恢复。本轮未修改 service definition、Nginx、runtime env、数据库/Redis，未调用 Telegram/LLM/Provider，未删除任何 Docker、release、venv 或 static 资源。详见 `evidence/stage09-native-ingress-cutover-2026-07-23.md`。
- Current Progress Update (2026-07-23, ingress review correction): 独立复核指出 r22 紧急恢复证据未单独证明 HTTP listener；复核后的只读检查确认三条 `current` symlink 均严格解析到存在的同一 r22，因此不需要重链或 Stage09 service restart。真实故障是站点文件在证书签发后只保留 HTTPS renderer block，造成 HTTP/ACME 为 `000`。已使用已有 renderer 将 HTTP `80` ACME/308 block 与 HTTPS `443` block 合并为单一原生 Nginx site，`nginx -t`/reload、HTTP root `308`、HTTP ACME `200`、HTTPS health/root/static `200` 均实测通过；r23 未切换，历史资源未删除。更正前后证据见 `evidence/stage09-native-ingress-cutover-2026-07-23.md`。
- Current Progress Update (2026-07-23, native HTTPS recovery with r22 retained): 已在真实服务器将既有公网 hostname 的 HTTP/HTTPS 入口切换到原生 Nginx，并由真实 ACME webroot 签发证书。首次接管因 ACME probe 的 worker 读取权限导致 `403`，自动旧入口回退又暴露历史入口重启后的证书/上游网络类启动错误；因此按当次授权改为原生 Nginx 紧急恢复。最终公网 HTTPS health、首页与静态资源均为 `200`，Nginx 占有 TLS 入口，PostgreSQL/Redis 不公网暴露，API/worker/outbox/Redis/Nginx 均 active。`stage09-p1-20260723-r22` 仍是三条 `current` symlink 的运行版本；r23 仅保持候选，未切换；历史资源只完成 root-only archive，未删除容器/卷/镜像/release。完整脱敏账本见 `evidence/stage09-native-ingress-cutover-2026-07-23.md`。下一步是用户重新打开 Telegram Mini App 的人工验收；通过前不得 retirement 或清理。
- Current Progress Update (2026-07-23, r23 native ingress preflight): 已从已提交 HEAD `0d930d6` 的 `backend` 与 `deploy/stage09-native` 两棵 tracked source 构建不可变 `stage09-p1-20260723-r23` source/venv/static candidate，并在服务器完成 checksum、sealed release layout/assets、固定 `20260720_0032` 离线迁移、runtime/isolation 与原生 HTTP/HTTPS temporary-prefix `nginx -t`。RED gate 确认非法 hostname 被 r23 renderer 拒绝；GREEN gate 使用现行真实 hostname 但不记录其值，HTTP/HTTPS 均通过。该轮未切换三个 `current` symlink、未改 systemd；未写 `/etc`，仅以受限方式读取 runtime env 进行 validator；未写 Caddy/Docker/80/443/DNS/Telegram/LLM，未执行真实迁移或业务写入。before/after 均确认 r22 仍是运行版本，服务 active，回环和外部 health 为 200。脱敏证据见 `evidence/stage09-native-ingress-preflight-2026-07-23.md`；r23 仅是候选，不是已激活版本。
- Current Progress Update (2026-07-23, legacy Docker retirement approved): 用户已授权将历史 `telegram-bitable-stage03` Docker 栈在一致性归档后永久删除。只读盘点确认 Stage09 r22 已是 source/venv/static 三个 `current` symlink 的唯一运行版本；服务器 PostgreSQL 仅监听 loopback、`vector` extension 存在、Redis 使用 Unix socket，Stage09 API/worker/outbox/Redis/Nginx 均 active，回环和 `stage07.jiangtest1.online` HTTPS health/首页均为 200。发现旧 Docker Caddy 的落盘 Caddyfile 与其当前运行时路由不一致，容器重启可能恢复 502。该轮新增的 P1-C 原生 ingress 接管、归档、删除和回滚边界见 `STAGE_09_LEGACY_DOCKER_DECOMMISSION_DESIGN.md`；在文档规定的 preflight 完成前不停止或删除 Docker。
- Current Progress Update (2026-07-23, r22 first real workspace): 已真实激活 `stage09-p1-20260723-r22`。先以同一 PostgreSQL 事务完成首个工作区初始化演练并 rollback，再执行原子 source/venv/static 切换与真实提交。当前平台库有 1 个 workspace、1 个 owner member、1 条 active Telegram binding、1 个 Base、3 张表/3 条记录、1 个数字员工、1 条群聊—客户—项目映射和 1 条审计；同一 binding 的 Mini App bootstrap/Home 服务端核验分别返回 1 个 workspace、1 个 Base、1 条关系索引。API 回环和外部 HTTPS health 均为 200。人机 Telegram 页面复开验收仍待完成，详见 `evidence/stage09-first-workspace-provisioning-2026-07-23.md`。

- Current Progress Update (2026-07-23, r14 controlled Telegram smoke): 用户的唯一绑定 nonce 已真实经 Stage09 webhook 持久化；系统只将该事实 chat 写入完全相同的 receive/send allowlist，切换为 `restricted_test` 后重启 API、worker、outbox bridge 并通过 validator/health。实际 bot 回执严格经 send-request → confirm → outbox bridge/worker，最终 request=`sent`、outbox=`processed`、三类 test-send audit event 均存在。未扩大名单、未群发、未写业务表或确认 draft。完整脱敏证据见 `evidence/stage09-r14-real-runtime-and-provider-2026-07-23.md` 与 `2026-07-23-stage09-telegram-llm-real-smoke.md`；Stage07 UI 仍是独立验收项。

- Current Progress Update (2026-07-23, r14 real release / OpenRouter dry-run): 已真实激活 `stage09-p1-20260723-r14`，`current` 与 `current-venv` 均指向 r14；API、worker、outbox、Nginx 为 active，服务器回环和外部 HTTPS `/health` 均为 200。r12/r13 封装预检分别暴露 CRLF 非 shell 资产和 Git executable-bit 缺失；r14 已以密封包字节检查、服务器 release/service/data asset 校验、固定迁移和有界就绪等待通过，失败切换均自动回滚到 r11，未造成中断。真实 OpenRouter dry-run 已激活：12 个 Stage08 多 case 全部通过，9 个 Provider 调用完成、0 timeout；Telegram 仍为 `dry_run` 且名单为空。Bot webhook 已真实切换至 Stage09 HTTPS endpoint 并无 Telegram API 错误；尚未收到用户绑定消息，因此未启用 `restricted_test`、未发送 Telegram。完整脱敏证据见 `evidence/stage09-r14-real-runtime-and-provider-2026-07-23.md`。

- Current Progress Update (2026-07-23, r12 controlled-runtime local-ready): 真实 LLM 与受限 Telegram 被 r11 runtime preflight 拒绝的原因已定位为运行时组合硬编码，而非服务或凭据错误。新的唯一 systemd `ExecStartPre` validator 已经本地 25 项 fixture、release-assets 与 public-ingress-assets 回归，且有独立复审：仅接受 baseline、真实 OpenRouter + Telegram dry-run、或精确匹配 chat allowlist 的 `restricted_test`；未知 Telegram allowlist、`real` 发送、Provider 启用、缺少 key/token、名单不一致与完整 prompt/response 保存均 fail closed。本条为 r14 发布前的 local-ready 记录，已由上方 r14 真实部署与 OpenRouter 证据取代。

- Current Progress Update (2026-07-23, r11 real public ingress): 已真实部署并切换原生 `stage09-p1-20260723-r11`。服务器先对密封包执行 checksum、release-layout、release-assets、runtime-preflight 与 public-ingress-assets 校验，再原子切换 source/venv/static symlink 并重启仅 Stage09 的 API、worker、outbox；四个 Stage09/Nginx 服务均为 active。已对专属 hostname 执行真实 Caddy/Nginx 写入：历史 Caddy 容器未重启、未替换；activation 从容器读取当前 Caddyfile，再以 stdin 校验并重载仅包含 Stage09 host 的候选配置。外部 HTTPS `/health` 和首页均实测 HTTP 200，Caddy 到 Nginx bridge health 亦通过。GitHub 远端 `codex/stage07-mini-app-ui` 已实测更新并与本地提交树一致。完整脱敏证据见 `evidence/stage09-r11-public-ingress-deployment-2026-07-23.md`。本条不代表 Telegram webhook、真实 Telegram 发送、真实 Provider/LLM 或 Stage07 Browser/UI 验收完成。

- Current Progress Update (2026-07-23, local public-ingress assets): 已完成可随 sealed release 一起发布的 Caddy host renderer、public-ingress activation 与 fixture contract。activation 仅在明确传入 hostname、服务器 DNS 已解析并获得当次写入授权后运行；它动态发现唯一的历史 Caddy 及其可写 Caddyfile mount，将原生 Nginx 限制到已验证 bridge gateway 和 Caddy `/32`，并在任一步失败时恢复两份原配置。该资产尚未在服务器、DNS、Caddy、Nginx 或 Telegram 执行，不改变 Stage03。

- Current Progress Update (2026-07-23, read-only public-ingress audit): 当前 80/443 的唯一发布者是历史 Stage03 范围内的 Docker Caddy，不是可独立删除的 last30days 服务；宿主机 Caddy systemd 未运行。Caddy 的自定义私网、宿主机 bridge gateway 与 Caddy 单 IP 来源均已读取，现有 renderer 已实际接受“bridge bind + `/32` allowlist”候选，但尚未写入 Nginx。Stage09 runtime 与本机 ignored env 均没有独立 `hostname` / public base URL。未写入 Caddy、Nginx、DNS、Docker、runtime env 或 Telegram。完整脱敏审计见 `evidence/stage09-public-ingress-readiness-audit-2026-07-23.md`；下一步必须先取得独立 hostname 与其 DNS 指向，才可执行单 host 的 HTTPS 接入与 Telegram controlled smoke。

- Current Progress Update (2026-07-23, server local time): 已从已发布的 Stage08 验收源码树构建并真实激活 `stage09-p1-20260723-r5`。本机 `release-assets`、`runtime-preflight` 与 Mini App production build 通过；服务器端密封包校验、固定 `20260720_0032` 迁移、原子 release/venv/static 切换、systemd 服务和独立 root 回环检查均通过，上传临时目录已清理。完整脱敏证据见 `evidence/stage09-p1-native-r5-deployment-2026-07-23.md`。本条不代表公共 HTTPS、DNS、真实 Telegram 或 Provider 上线完成。

- Current Progress Update (2026-07-23, server local time): P1-B 原生服务与内部 Nginx 已真实激活到 `stage09-p1-20260722-r4`（Git `bddf4e6`）。`20260720_0032` 迁移、Redis/API/worker/outbox、`127.0.0.1:18080` API 与 `127.0.0.1:18090` Nginx 静态/API 入口均有独立实测证据。该进度不代表公共 HTTPS、DNS、真实 Telegram 或 Provider 上线完成；公网入口仍是下一独立门禁。

- Document status：active — 2026-07-22 用户确认，替代 Stage09 中所有“新建 Docker Compose/容器/卷”的 P1 实施路径。
- Scope：Ubuntu 原生 `systemd` 服务、服务器本地 PostgreSQL + pgvector、原生 Redis、原生 Nginx 静态/反向代理，以及与历史 Caddy 的最小 HTTPS ingress 衔接。
- Out of scope：迁移或替换历史 Stage03 Docker 服务；将 PostgreSQL/Redis 暴露公网；真实 Telegram/Provider 调用；Stage07 Browser/UI 验收；购买或迁移到托管数据库。
- Current Progress：P0 与 P0a 只读盘点完成；P1-A 的 N1 runtime preflight、N2 原生 application/Nginx、经 N3 remediation 收敛的数据面离线资产，以及 N4A release manifest/固定 revision 离线迁移验证均为 local-ready only。P0a 证实原生 PostgreSQL/pgvector/Redis 尚未安装，80/443 被无容器的历史 `docker-proxy` 占用；任何远程写入与真实服务启动尚未开始。

## 0. P1-B 实施状态（2026-07-22）

本节取代 Status 中仍称为 `local-ready only` 的历史进度表述：原生 PostgreSQL 16 + pgvector、原生 Redis、隔离 runtime、独立数据库、r2 release、固定 revision 真实迁移及 API/worker/outbox 回环服务均已在服务器完成。完整脱敏证据见 `evidence/stage09-p1-native-loopback-deployment.md`。

当前唯一的上线主阻塞是公网 HTTPS ingress：遗留 `docker-proxy` 仍占用 80/443，且尚无新的专属 hostname/DNS。本轮继续保持 Docker、Stage03、Nginx 与 Caddy 不变；P1 现处于“服务器本机运行、等待独立公网入口”状态。

## 1. 决策与部署形态

Stage09 的新服务不使用 Docker。它们以一个受限的 `stage09-p1` Linux 账户运行，应用二进制和虚拟环境位于专用目录，运行时配置由 root 写入仅该账户可读的位置。历史 `telegram-bitable-stage03` Docker 项目继续运行且不发生变更。

```text
new hostname
  -> existing legacy Caddy (only one newly authorized host block)
  -> native Nginx on a non-public internal port
       -> static Mini App files
       -> native Uvicorn API on loopback / Unix socket
            -> native PostgreSQL + pgvector (local only)
            -> native Redis (local only)
       -> native systemd worker / outbox bridge
```

这里保留“既有 Caddy”并不等于新建 Docker 部署：它是未迁移 Stage03 的存量 HTTPS 入口。P1 只允许为一个独立 hostname 添加经验证的 route；不允许重启、升级、替换或改写任何 Stage03 host。等 Stage03 有独立迁移计划时，才可整体去除该遗留 Docker ingress。

## 2. P1-A：本地可审阅的原生部署资产

P1-A 先在仓库中建立下列文件，全部是模板、脚本或 unit 文件；它们不含真实 hostname、token、数据库 URL、密码、chat ID 或 webhook secret：

| 资产 | 责任 |
| --- | --- |
| `deploy/stage09-native/systemd/stage09-p1-api.service` | 以受限账户运行 `uvicorn app.main:app`；仅监听 loopback 或 Unix socket；读取固定 release 与受保护 runtime env。 |
| `deploy/stage09-native/systemd/stage09-p1-worker.service` | 以同一受限账户运行现有 worker entry，不开放端口。 |
| `deploy/stage09-native/systemd/stage09-p1-outbox-bridge.service` | 以同一受限账户运行现有 outbox bridge，不开放端口。 |
| `deploy/stage09-native/nginx/stage09-p1.conf.template` | 静态资源和同源 API 反代；不监听 80/443，只由 P0a 确认的内部端口提供给历史 Caddy。 |
| `deploy/stage09-native/postgresql/stage09-p1-bootstrap.sql` | 仅创建独立 role/database、强制本地连接和 `vector` extension 的参数化模板；启动前拒绝缺失或空的目标机密码输入，绝不引用 Stage03 库。 |
| `deploy/stage09-native/redis/redis-stage09-p1.conf` | 仅 loopback/Unix socket、独立 data dir、AOF、受限权限。 |
| `deploy/stage09-native/runtime/runtime.env.example` | key-name contract 与 P1 安全默认值；真实文件是服务器上的 `/etc/stage09-p1/runtime.env`。 |
| `deploy/stage09-native/scripts/*` | key-presence、unit/端口/文件权限、PostgreSQL/Redis isolation 与 release manifest 检查；所有输出只记录布尔值、枚举、版本和状态码。 |

代码兼容边界：P1 的 `stage09-p1-worker.service` 和
`stage09-p1-outbox-bridge.service` 仅可在各自的唯一 `ExecStart` 行精确使用
`app.workers.stage03_runtime` 与 `app.workers.stage03_outbox_bridge_runtime`。
这两个历史 Python 模块名是受审计的**代码兼容名**，不是 Stage03 Docker、
systemd、数据库、Redis、网络或运行时依赖。它们在 P1 中只能读取 N1 已验证的
P1 runtime，并连接 P1 原生数据库和 Redis；不得连接、读取、迁移或复用任何
Stage03 Docker 资源。除此两个精确入口外，unit 不得出现任何 `stage03` 文本，
也不得出现 Stage03 目录、systemd service、Docker service/container/network/
volume/env 变量；所有 `stage07`、Docker/Compose/container/volume 标记仍须拒绝。

P1-A 交付必须有：`shellcheck` 或 `sh -n`、systemd unit 静态校验、Nginx `-t` 的无秘密 fixture、Alembic `upgrade 20260720_0032 --sql` 离线输出，以及明确定义的 release checksum。它只是 `local-ready`，不是已部署。
仓库的无秘密 Nginx fixture 可以在本机缺少 Nginx binary 时明确标记为
`SKIPPED`；它不能伪造或替代成功证据。目标服务器的 `nginx -t` 仍是 P0a 后、
P1-B 写入前的环境证据门。

## 3. 固定目录、账户和权限

| 项目 | 固定值/规则 |
| --- | --- |
| 应用运行账户 | `stage09-p1`，shell 为不可交互或受限；不得复用 `ubuntu`、PostgreSQL 或 Redis 系统账户。 |
| Redis 账户与 socket 组 | Redis 仅以 `stage09-redis:stage09-redis-socket` 运行；P1-B 只将 `stage09-p1` 加入 `stage09-redis-socket` 补充组，以访问 P1 Unix socket。 |
| Release 根目录 | `/opt/stage09-p1/releases/<artifact-id>`；`current` 仅指向一个经审阅的不可变 release。 |
| Python venv | `/opt/stage09-p1/venv/<artifact-id>`，不在历史项目目录复用虚拟环境。 |
| 运行时配置 | `/etc/stage09-p1/runtime.env`，目录 `0750 root:stage09-p1`，文件 `0640 root:stage09-p1`；不写入仓库、shell history、unit 正文或日志。 |
| 静态文件 | `/var/www/stage09-p1/<artifact-id>`，由 Nginx 只读；不含浏览器秘密。 |
| 日志 | journald 单元日志 + `/var/log/stage09-p1/` 的脱敏应用日志；不得记录原始 prompt、回复、消息正文、token、URL 或业务记录值。 |

应用 `systemd` unit 至少使用 `User=stage09-p1`、`Group=stage09-p1`、`NoNewPrivileges=true`、`PrivateTmp=true`、明确 `WorkingDirectory`、`EnvironmentFile=/etc/stage09-p1/runtime.env` 和 restart/backoff。Redis unit 使用独立 `stage09-redis:stage09-redis-socket`，不读取 application runtime env、也不执行 application preflight；Redis data dir 只归 Redis 账户所有，应用账户不可读。 

P1 固定 `APP_ENV=staging`，因此 `TELEGRAM_WEBHOOK_SECRET` 是应用启动所需的 runtime key，必须存在且只能在目标机的 `/etc/stage09-p1/runtime.env` 中设置。它是随机的、仅用于本地 webhook 校验的 nonce；不是 Bot token，不会启用 Telegram，也不会写入任何外部系统。预检只检查其 presence，绝不回显或记录其值。

## 4. 本地 PostgreSQL、pgvector 与 Redis

### 4.1 PostgreSQL

- 使用服务器原生 PostgreSQL 16 和与其**相同主版本**匹配的 pgvector 包/扩展；安装后在 P1 的新数据库内执行一次 `CREATE EXTENSION vector`。
- 新角色、新数据库与新 schema 仅使用 `stage09_p1` 命名；不能连接、读取、备份、迁移、downgrade 或复制 Stage03 PostgreSQL。
- PostgreSQL 监听 Unix socket 或 `127.0.0.1`，`pg_hba.conf` 只允许 `stage09-p1` 服务账户和本机受控运维入口。禁止 `0.0.0.0`、安全组放通或公网端口。
- 实际迁移固定到唯一 revision `20260720_0032`。先离线 SQL，再对新空库执行 upgrade；须验证唯一 Alembic head、`vector` extension 和 Stage08 索引。不得用未记录的 `head` 或 `latest` 代替。

### 4.2 Redis

- 使用一个独立原生 Redis 配置，固定 `port 0`，仅提供 `/run/stage09-p1/redis.sock` Unix socket，data dir 为 `/var/lib/redis-stage09-p1`，启用 AOF。
- P1-B 创建 `stage09-redis:stage09-redis-socket`，仅将应用账户 `stage09-p1` 加入该 socket 补充组；Redis 进程不读取 `/etc/stage09-p1/runtime.env`，worker/outbox 仅通过固定 socket URL 连接 P1 Redis。socket/port、data dir 不得与 Stage03 Docker Redis 共享。

### 4.3 备份与购买托管库的界线

P1/P2 是空数据或受控 smoke，优先本机数据库，暂不采购托管数据库。P3 前必须完成：

1. 加密的异机 PostgreSQL base backup/WAL 或等效连续备份；
2. 每日逻辑备份作为额外恢复路径；
3. 至少一次对隔离恢复目标的恢复演练，记录 RPO/RTO；
4. 磁盘、连接数、慢查询、备份新鲜度、恢复失败和 Redis 持久化告警。

若需要多节点/跨可用区高可用、单机故障不能接受、实测 RTO/RPO 不满足业务、持续备份与恢复无法由团队稳定运行，或单机数据库已达容量/性能 SLO，则将 PostgreSQL 迁移到托管实例。pgvector 保持与 PostgreSQL 同库，不额外购买向量数据库。

## 5. P0a：不写入的原生部署前置盘点

P1-B 前先做一次只读 P0a，不读取 secret 值或业务数据：

1. 检查可用的 PostgreSQL 16/pgvector 安装源、Redis、Python 3.12+、Nginx、systemd、磁盘、时钟与防火墙状态。
2. 查找历史 Docker Caddy 所在 bridge network 及其到宿主机内部端口的**已验证**连通方式；不得猜测 `host.docker.internal`、bridge gateway 或公网 IP。
3. 查明可用的非公开内部端口/Unix socket，并确认 Nginx 对外暴露仅允许来自已验证的遗留 Caddy route；80/443 继续仅由历史 Caddy 占用。
4. 确认新的 hostname 已由用户提供、DNS 指向目标服务器；只在受保护的服务器临时文件中处理 hostname，证据不记录实际值。
5. 记录备份位置的 presence、异机目标可用性和 rollback owner；不能获取值或列出凭据。

任何 P0a 条目失败，P1-B 标为 `blocked`，不安装包、不创建账户、不初始化数据库、不写 unit、不改 Nginx/Caddy。

## 6. P1-B：受控原生部署顺序

获得当次服务器、hostname、固定 artifact、维护窗口和可写资源的明确授权后，严格按以下顺序执行：

1. **封存 artifact**：校验 commit、release checksum、Alembic 固定目标 `20260720_0032` 和 P1-A 预检；不在服务器执行 `git pull`，不改历史 Stage03 checkout。
2. **创建原生隔离面**：创建 `stage09-p1` 账户、目录、runtime env 及权限；运行 key-presence validator。P1 安全值必须是 `TELEGRAM_SEND_MODE=dry_run`、`LLM_ENABLED=false`、`AGENT_WORKFLOW_MODE=fake`、`PROVIDER_MODE=disabled`、`AGENT_SAVE_FULL_PROMPT=false`、`AGENT_SAVE_FULL_RESPONSE=false`，所有 Telegram allowlist 为空。
3. **初始化数据面**：安装匹配版本的 PostgreSQL/pgvector 与 Redis；创建新的 `stage09_p1` 数据库/角色、`stage09-redis:stage09-redis-socket` 与 Redis data dir，只将 `stage09-p1` 加入 socket 补充组。Redis unit 不接收 application runtime env，应用账户不读取 Redis data dir。先离线 migration SQL，再执行 `alembic upgrade 20260720_0032`；只检查 P1 schema/extension，不查询业务行。
4. **启动原生应用**：安装 release venv，启用 API、worker、outbox systemd units；检查 unit active、API 内部健康、Redis ping、PostgreSQL head 和 extension。不得触发 Telegram webhook、Provider、draft 确认或业务 API 写入。
5. **启动 Nginx 并衔接 HTTPS**：先用候选配置 `nginx -t`；Nginx 仅提供已验证的内部入口。随后仅为独立 hostname 在历史 Caddy 加一个 host block，先 `caddy validate`、备份、append、reload；再次读取 Stage03 原 host 健康。不得改其容器、端口、镜像或其他 host。
6. **观察和回滚证据**：在明确 UTC 窗口观察 unit restart、5xx、DB/Redis 连接、磁盘、队列、dry-run、Provider invocation 和 Stage03 健康。每一步写入脱敏 ledger：状态、UTC、artifact id、revision、写入范围、退出码、rollback readiness；不保存 hostname、secret、业务数据或 raw log。

## 7. 回滚

回滚优先级为：移除单一 P1 Caddy host → reload 并验证 Stage03 → 停止/disable P1 systemd units → 关闭 P1 Nginx → 删除 P1 release/runtime 文件 → 仅在确认空数据时删除 P1 本地数据库、role、Redis data dir。不得重启、缩容、迁移或回滚 Stage03 Docker 服务、数据或 Caddy 其他 host。

P1 只有在以下条件同时满足时才可标记完成：固定 artifact 与唯一 revision 已证实；新本地 PostgreSQL 的 `vector` 和 schema/索引正确；所有运行服务持续 dry-run/LLM-off/provider-disabled/empty allowlist；内部 API、静态站与独立 HTTPS 可用；Stage03 不受影响；观察窗口无禁止副作用；并存在经过实际验证的回滚路径。P1 成功不自动启用 P2，也不代替 Stage07 Browser/UI 验收。
