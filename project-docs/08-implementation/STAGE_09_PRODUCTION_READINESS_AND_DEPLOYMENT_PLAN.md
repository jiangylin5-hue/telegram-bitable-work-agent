# Stage09：生产就绪与受控上线计划

## Status

- Document status：P0 read-only audit complete; P1 Docker deployment path is superseded by the accepted native-server decision, and no package creation, server write, migration or service start has begun
- Scope：Stage08 开发完成后的生产就绪、部署、真实 Telegram controlled smoke、可观测性与回滚证据。
- Prerequisite status：Stage08 A–F 的开发/非生产质量证据已完成；Stage07 的内置 Browser UI 验收仍有历史缺口，不能被 Stage08 结果替代。

## 0. 2026-07-22 原生部署修订（优先于下文 Docker 表述）

用户已确认 P1/P2 不使用新的 Docker Compose、容器或 Docker 数据卷。所有本文件中关于新 Compose project、容器、image、volume、Docker network、`docker compose` 执行及 Docker Caddy alias 的 P1 实施细节均不再可执行，保留仅作为已废止的历史方案，不能据此创建任何资源。

现行且唯一可执行的 P1 设计为：原生 Ubuntu `systemd` + Python virtualenv + 本机 PostgreSQL/pgvector + 本机 Redis + 原生 Nginx；历史 Stage03 Docker/Caddy 只保留为未迁移 HTTPS ingress，并且只允许在经授权的独立 hostname 下增加一条 route。完整文件、权限、服务、数据库、备份、P0a、执行和回滚合同见 [Stage09 原生服务器部署与本地数据库实施计划](STAGE_09_NATIVE_SERVER_DEPLOYMENT_PLAN.md) 与 `TDR-017`。本修订不授权任何远程安装、Caddy 改动、数据库初始化、迁移或 Telegram 行为。

## 1. 目标与非目标

目标是在明确、可回滚、最小外部影响的条件下，将已验证的应用部署到指定服务器，并取得生产（或明确定义的 staging）证据：

```text
server inventory
-> immutable deployment input and secret presence gate
-> PostgreSQL/pgvector/Redis migration and health
-> API/Mini App HTTPS and webhook verification
-> allowlisted Telegram controlled smoke
-> observation window
-> rollback proof / launch decision
```

不做：

- 不将合成 OpenRouter 评测当作生产规模、成本或可用性证据；
- 不群发、不给客户群发消息、不自动确认草稿；
- 不绕过 Stage07 Browser/UI 验收；
- 不引入 Milvus、外部知识库、额外 Provider 或新的权限模型；
- 不打印、复制、提交任何密钥、数据库 URL、allowlist 或真实消息正文。

## 2. 上线分层与准入门

| 层级 | 目标 | 允许动作 | 必须先满足 |
| --- | --- | --- | --- |
| P0 Readiness audit | 只读确认服务器/域名/运行时/secret presence | 只读 SSH、版本/健康/配置 presence | 当前计划批准即可 |
| P1 Staging deploy | 可回滚的原生服务部署与迁移 | 原生 package/systemd、迁移、health、HTTPS | 原生 P0a 通过、目标服务器明确、备份与 rollback 命令可用 |
| P2 Controlled Telegram smoke | allowlist 私聊/测试群一条受控消息或 webhook 入站 | 指定 chat、单次确认、redacted receipt | P1 通过、用户确认目标 chat 与窗口 |
| P3 Limited pilot | 小范围真实业务使用 | 经 scope/permission 的 read/draft/confirm | Stage07 UI acceptance、观察/告警、退出开关 |
| P4 Production launch | 正式服务 | 已批准的生产流量 | P3 指标与运营签署 |

P0 已于 2026-07-22 完成。它确认远端是历史 Stage03 的 clean `fa645d9` worktree 与运行中 Stage03 Compose，具备 Docker/Redis/pgvector 基础但不允许原地替换；详见 `evidence/stage09-p0-readiness-inventory.md`。P1 及之后均需在执行前记录平行隔离目标、回滚点、外部影响与当前用户授权。

## 3. P0：只读基础设施盘点

### 输入

- SSH 目标别名及服务器归属；
- 部署目录、运行分支/commit、compose 文件；
- 域名、Caddy/HTTPS 终止位置；
- PostgreSQL、pgvector、Redis、磁盘与日志位置；
- server-side secret 的 presence（只记录布尔值，绝不读值）。

### 检查项

1. OS、Docker/Compose、磁盘、时钟、可用端口、服务进程。
2. 当前 container image、compose config、数据库 migration head、pgvector extension、Redis ping。
3. API health、Mini App 静态资源、Caddy TLS、Webhook route 的只读状态。
4. 运行时 env 只检查变量名 presence：Telegram、OpenRouter、database、Redis、webhook secret、send mode、retention flags。
5. 备份路径、最近一次数据库备份、可执行 rollback 版本与日志保留。

### P0 输出

`evidence/stage09-p0-readiness-inventory.md`，只包含版本、布尔值、状态码、容量桶与 redacted 命令结果。

## 4. P1：部署与数据库门

### 4.1 P1 的结论、授权边界与不可变约束

P1 是一个**并行、空数据、staging-only**部署包；它不是 Stage03 替换、不是生产切流，也不包含 P2 的真实 Telegram 行为。P0 已证实远端正在运行历史 `telegram-bitable-stage03`，其数据库 Alembic head 为 `20260707_0016`，且该库未启用 `vector` extension。因此不得把它当作 P1 的升级起点、备份源、回滚目标或任何连接字符串来源。

本节把 P1 分成两个连续但权限不同的工作面：

| 工作面 | 本地可做 | 需要执行当次的用户明确授权 | 明确禁止 |
| --- | --- | --- | --- |
| P1-A 本地包准备 | 审阅、创建/测试新的 Stage09 配置资产、离线渲染 Alembic SQL、生成不含秘密的 manifest | 否 | 访问服务器、创建 runtime 值、传输包、修改 Caddy、运行容器 |
| P1-B 远端隔离部署 | 仅按已审阅 P1-A artifact 执行 | 是；授权记录必须写明 hostname、服务器、固定 artifact、时间窗和可写资源 | 修改 Stage03 worktree/Compose/数据库/Redis/Caddy 既有 host；真实 Telegram 或 Provider 调用 |

以下常量是隔离命名合同，任何已存在的同名资源均为 `blocked`，不能通过覆盖、`down -v` 或重用来继续：

| 资源 | P1 固定命名/形式 | 隔离要求 |
| --- | --- | --- |
| Compose project | `stage09-p1` | 不能使用 `telegram-bitable-stage03` 或 `stage07-acceptance` |
| 远端工作目录 | `/home/ubuntu/stage09-p1` | 不写 `/home/ubuntu/telegram-bitable-work-agent`；`runtime/` 单独为 `0700` |
| PostgreSQL 服务/库/用户/卷 | `stage09-p1-postgres` / `stage09_p1` / `stage09_p1` / `stage09_p1_postgres_data` | 新建的空库和新 named volume；绝不连接历史 Stage03 PostgreSQL |
| Redis 服务/卷/逻辑库 | `stage09-p1-redis` / `stage09_p1_redis_data` / `redis://redis:6379/0` | 新实例、新卷；不读取历史 Redis key 或队列 |
| API 与 Web Caddy alias | `stage09-p1-api`、`stage09-p1-web` | 仅加入已盘点的 Caddy ingress Docker network；无 host port 映射 |
| 镜像标签 | `stage09-p1-api:<immutable-artifact-id>`、`stage09-p1-web:<immutable-artifact-id>` | `<immutable-artifact-id>` 必须是已审阅 commit 或内容哈希，不能使用 `latest` |
| Caddy host | `{{STAGE09_P1_HOSTNAME}}` | 一个新、已验证归属且解析到目标服务器的 hostname；本计划不创造或记录真实域名 |

`Stage07 UI acceptance` **不是 P1 的替代物，也不会被 P1 通过**。P1 只证明隔离的服务、迁移、HTTPS 和观察面；P3 仍必须单独取得 Stage07 Browser/UI 验收、权限审计和 pilot 授权后才能开始。

### 4.2 现有资产与 P1 新包的文件边界

`deploy/stage07-acceptance/` 是已完成且已清理的 Stage07 S6 历史验收资产。它只能作为结构和安全模式的只读来源，不能被改名、原地复用或因 P1 被重新启用；其测试与 S6 证据仍依赖该路径。P1-A 需要新建下表所列的 Stage09 资产，并在单独的本地配置变更评审通过后才允许进入 P1-B。本次计划文本不创建这些部署资产，也不修改任何 Stage03 或 Stage07 资产。

| 文件 | P1-A 责任 | 必须保留/验证的来源模式 |
| --- | --- | --- |
| `deploy/stage09-p1/compose.yml` | `name: stage09-p1`；声明新 PostgreSQL/Redis 卷、`migrate` tools profile、API/worker/outbox/web，且仅 API/Web 接入外部 Caddy network | 参考 `deploy/stage07-acceptance/compose.yml` 的健康依赖和无 host port 模式；将所有 Stage07 名称替换为本节固定 P1 名称 |
| `deploy/stage09-p1/Dockerfile.web` 与 `deploy/stage09-p1/nginx.conf` | 从固定源码 artifact 构建同源 Mini App 静态服务；保持同源根路径 API 代理 | 参考同名 Stage07 文件；不得注入前端秘密、改写 API contract 或绕开 UI 验收 |
| `deploy/stage09-p1/Caddyfile.stage09-p1-host` | 只渲染一个 `{{STAGE09_P1_HOSTNAME}}` host；`/`、`/index.html`、`/assets/*`、`/favicon.ico` 到 `stage09-p1-web:80`，其余路径到 `stage09-p1-api:8000` | 参考 `deploy/stage07-acceptance/Caddyfile.stage07-host`；不得编辑 Stage03 host block 或新增 80/443 listener |
| `deploy/stage09-p1/runtime/.env.stage09-p1.example` | 只列 key 名和非秘密安全默认值；真实文件只在服务器 `runtime/.env.stage09-p1` 中创建 | 参考 Stage07 example 的“key-name contract”；`.gitignore` 必须只放行 example，不放行实际 env |
| `deploy/stage09-p1/scripts/verify-compose-isolation.sh` | 拒绝 `stage03`、`stage07` 数据卷/数据库/容器引用，并检查本节全部 P1 服务 alias/卷名 | 参考 Stage07 isolation script；失败时只输出固定状态，不输出 env 或 URL |
| `deploy/stage09-p1/scripts/validate-runtime-presence.sh` | 仅输出 `configured`/`missing`/安全枚举，执行 4.3 的 P1 状态断言 | 参考 Stage07 presence script；不得读取、回显或哈希秘密值 |
| `deploy/stage09-p1/scripts/render-caddy-host.sh` | 仅验证 hostname 格式并渲染模板 | 参考 Stage07 render script；真实 hostname 不进入 Git、报告或证据正文 |
| `project-docs/08-implementation/evidence/stage09-p1-deployment-ledger.md` | P1-B 执行时新建的脱敏账本；每步只记录状态、UTC、固定 artifact id、head、布尔值和退出码 | 参考 P0 evidence 的脱敏规则；不得保存命令含秘密参数的完整文本、chat ID、消息正文或 raw log |

P1-A 完成前必须运行下列**本地只读/离线**类别命令并把结果记为 `local-ready`，而不是 P1 已部署：

```sh
# 固定来源；若工作树中的 Stage08 发布范围不干净或 artifact 不可复现，停止。
git rev-parse --verify <reviewed-stage08-commit>
git diff --check

# 对 P1 的新 compose 做变量不插值的结构审阅；不连接服务器或数据库。
docker compose --project-directory deploy/stage09-p1 \
  -f deploy/stage09-p1/compose.yml config --no-interpolate
sh deploy/stage09-p1/scripts/verify-compose-isolation.sh deploy/stage09-p1/compose.yml

# 固定目标 revision 的 offline SQL，不使用 "head" 或 "latest" 作为执行记录。
cd backend && alembic upgrade 20260720_0032 --sql > <redacted-local-artifact>/stage09-p1-upgrade.sql
```

当前本地 Alembic 链的已知目标是 `20260720_0032`；P1-B 当天必须再次由被部署 artifact 内的 `alembic heads` 确认其恰为唯一 head。若后来存在新的、已审阅 migration，则部署记录必须同时更新固定 revision、downgrade 路径和本节命令；不能悄悄回退到 `head`。

### 4.3 P1 runtime key-presence 与安全运行态

远端真实 env 只能位于 `/home/ubuntu/stage09-p1/runtime/.env.stage09-p1`，目录模式 `0700`、文件模式 `0600`，由执行 P1-B 的部署用户拥有。所有 Compose 命令均显式使用 `--env-file runtime/.env.stage09-p1`；`STAGE09_P1_ENV_FILE` 与每个服务的 `env_file` 必须指向同一个文件。任何 `env`、`printenv`、`docker inspect` 的完整输出都不是允许证据。

| 类别 | key-presence / 值断言 | P1 要求 |
| --- | --- | --- |
| 必须存在 | `APP_ENV`、`POSTGRES_USER`、`POSTGRES_PASSWORD`、`POSTGRES_DB`、`DATABASE_URL`、`REDIS_URL`、`TELEGRAM_WEBHOOK_SECRET`、`STAGE09_P1_CADDY_NETWORK` | presence-only；`APP_ENV=staging`；URL 只可指向 P1 Compose service，不能含 Stage03/Stage07 名称 |
| 禁止外部副作用 | `TELEGRAM_SEND_MODE`、`LLM_ENABLED`、`AGENT_WORKFLOW_MODE`、`PROVIDER_MODE`、`AGENT_SAVE_FULL_PROMPT`、`AGENT_SAVE_FULL_RESPONSE` | 分别严格为 `dry_run`、`false`、`fake`、`disabled`、`false`、`false`；migrate/API/worker/outbox 必须一致 |
| Telegram P2 前冻结 | `TELEGRAM_BOT_TOKEN`、`TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS`、`STAGE07_TELEGRAM_BOT_USERNAME`、`TELEGRAM_ALLOWED_CHAT_IDS`、`TELEGRAM_ALLOWED_USER_IDS` | P1 不要求 token 或 username；所有 allowlist 必须为空/未配置，不能把 P2 目标预先写入 P1 runtime |
| Provider P2/P3 前冻结 | `OPENROUTER_API_KEY`、`OPENROUTER_MODEL`、`OPENROUTER_BASE_URL` | P1 不要求 key presence；若运维保留 key，验证器也只允许报告 presence，且 `LLM_ENABLED=false` 保证不调用 |

P1 的 runtime validator 必须在值读取后只输出例如 `DATABASE_URL=configured`、`TELEGRAM_SEND_MODE=dry_run`、`P1_ALLOWLIST=empty`、`runtime_preflight=passed`。它应额外拒绝以下情况：非 `staging` `APP_ENV`、`restricted_test`、非空 Telegram allowlist、`LLM_ENABLED=true`、`real_openrouter`、`PROVIDER_MODE!=disabled`、任一 URL 含 `stage03`/`stage07`，或 Caddy network 未在 P0 当天只读盘点中确认。

### 4.4 P1-B 前置门与只读证据

以下条目必须在远端写入前逐项记录为 `passed`；任一失败则 P1 为 `blocked`，不得创建目录、镜像、卷、数据库、Caddy host 或 runtime 文件。

1. 当次明确授权存在，且仅授权 P1-B 的 hostname、固定 artifact、目标服务器和维护时间窗；不含 P2 Telegram、Provider 或生产切流。
2. 本地 artifact 为固定 commit/内容哈希，`git diff --check` 通过，P1-A isolation、runtime-presence（使用无秘密 fixture）及 offline migration SQL 均已通过。
3. P0 所述 Stage03 API 仍返回其既有健康状态；P1 ledger 仅记录 HTTP 状态码，不保存响应体或历史业务日志。
4. 已由只读命令确定一个可加入的既有 Caddy Docker network；P1 只能使用该**名称**，不接入 Stage03 application network，也不使用 Stage03 PostgreSQL/Redis service/name/volume。
5. 新 hostname 已由授权人提供，并在 DNS 层只读确认解析到目标服务器；不得猜测、生成或把真实 hostname 写入仓库。
6. P1 database 是新卷上的空库；已验证 PostgreSQL/pgvector image 可用，并将 `CREATE EXTENSION IF NOT EXISTS vector` 的迁移能力限于该新库。
7. 已写明 rollback owner、前一稳定 Stage03 状态的只读检查方式、P1 目录/卷清理条件，以及“schema 只在 P1 空库中”的恢复策略。

允许的只读命令类别包括：`git rev-parse`/artifact checksum、`docker compose config`、`docker network inspect <validated-caddy-network>`、`docker ps`/`docker volume ls`、`df -h`、`date -u`、`getent hosts <user-provided-hostname>`、`caddy validate`（对候选文件）和 Stage03/P1 的 `curl -fsS -o /dev/null -w '%{http_code}'`。每个命令的 redacted receipt 只允许记录 exit code、状态码、布尔值、版本和容量桶。

### 4.5 P1-B 执行 runbook（按序，不可跳步）

#### Step 1：封存输入与远端隔离目录

1. 在本地生成 `artifact-manifest.json`，包含固定 commit/内容哈希、Docker build context checksum、P1 compose/Caddy template/script checksums 和目标 Alembic revision `20260720_0032`；不含 hostname、URL、env 或秘密。
2. 仅在获得 P1-B 授权后，将该固定 artifact 传入新的 `/home/ubuntu/stage09-p1`。禁止 `git pull`、在历史 Stage03 worktree 覆盖文件、从 Stage03 复制数据库或从运行容器 `commit` 镜像。
3. 在远端创建 `runtime/`（`0700`）和最小 runtime 文件（`0600`），由授权部署用户写入；随后运行 P1 runtime presence validator。validator 失败必须删除刚创建的 P1 runtime 文件和目录，且不启动任何服务。
4. 在部署目录中以 `--env-file runtime/.env.stage09-p1` 运行 `docker compose ... config`，记录 redacted 配置 digest。若 project name、服务名、volume、network alias 或任一 URL 不符合 4.1/4.3，停止并清理 P1 目录。

#### Step 2：只启动 P1 基础设施，并执行 migration dry-run

1. 使用新的 Compose project 启动**仅** `postgres` 与 `redis`，等待它们各自 healthcheck healthy。此步允许写入仅限 `stage09_p1_postgres_data`、`stage09_p1_redis_data` 与 P1 网络；不得创建 API/worker/outbox/web 或 Caddy host。
2. 在 P1 `migrate` image 内运行 `alembic heads`，要求输出唯一 `20260720_0032`；运行 `alembic upgrade 20260720_0032 --sql` 生成临时 SQL，并只检查 revision、`CREATE EXTENSION ... vector`、表/索引语句存在。SQL 文件属于临时 artifact，不进入 Git、日志或最终 ledger。
3. dry-run 通过后，使用 `migrate` tools profile 执行一次 `alembic upgrade 20260720_0032`。`migrate` 的 env 必须仍为 4.3 的 P1 安全运行态，因此它不能调用 Telegram、OpenRouter 或 Provider。
4. 仅连接 P1 PostgreSQL，验证 `alembic_version` 恰为 `20260720_0032`、`vector` extension 已启用，并对预期 Stage08 schema/索引做存在性检查。禁止查询业务记录、导入 fixture、复制历史数据或对 Stage03 数据库做任何 SQL。

若 dry-run、真实 migration、single-head、extension 或 schema/索引检查任一失败：保留脱敏失败状态，停止 P1 project，删除仅 P1 新建目录/卷；不对历史 Stage03 执行 downgrade、upgrade、restart 或 Caddy reload。

#### Step 3：启动应用，但保持无 Telegram/Provider 写入

1. 构建或加载 manifest 指定的不可变 API/Web image；镜像标签必须包含 artifact id，`latest` 是阻断条件。
2. 启动 P1 `api`、`worker`、`outbox-bridge`、`web`。API/Web 无 host port；只有它们可加入已验证的 Caddy ingress network，worker/outbox 只能使用 P1 default network。
3. 检查容器状态、PostgreSQL/Redis health、API 内网 `/health`。当前接口语义为 HTTP `200` 与 `{"status":"ok"}`；仅记录 status code 和 JSON schema 匹配布尔值。
4. 对 P1 的 webhook 路径发起不带 `X-Telegram-Bot-Api-Secret-Token` 的空/无效请求，预期 `403 telegram_webhook_forbidden`，并确认没有 P1 `messages`、`outbox_events` 或 audit 新记录。该检查不使用 Telegram 网络、真实 update 或真实身份数据。
5. 记录 API/worker/outbox 对 `TELEGRAM_SEND_MODE=dry_run`、`LLM_ENABLED=false`、`PROVIDER_MODE=disabled` 的 presence-only 证明；不得执行能够发送消息、确认 draft、调用 Provider 或写业务记录的 API。

#### Step 4：新增一个隔离 Caddy host 并验证 HTTPS

1. 仅在 hostname 已解析后，使用 `render-caddy-host.sh` 生成候选 host block。渲染输入及产物中真实 hostname 只留在受保护的服务器临时文件，不复制到 ledger、截图、Git 或聊天。
2. 对候选配置执行 `caddy validate`；在写入前保存现有 Caddy config 的受保护备份路径和 checksum，并记录 Stage03 host 未改的只读摘要。
3. 只追加一个 P1 host block，reload Caddy 后验证：P1 hostname 的 `/`、`/index.html`、`/assets/*`、`/favicon.ico` 到 `stage09-p1-web`；`/health` 和非静态 API 路径到 `stage09-p1-api`。同时再次只读检查 Stage03 既有 host 仍为可用状态。
4. 只记录 TLS handshake/HTTP 状态码、静态资源状态、API health 和 Caddy validate/reload exit code。HTTPS 成功不是 Telegram webhook、Mini App `initData`、UI 验收或真实业务读写的证据。

#### Step 5：观察窗口、关闭条件与 ledger

至少完成一个明确起止 UTC 的无外部写入观察窗口。允许读取 P1 容器的计数、健康、队列深度、DB/Redis 连接、CPU/内存/磁盘桶和脱敏错误类别；不得归档 raw request、prompt、answer、用户/聊天 ID、记录值、数据库 URL、token、webhook secret 或 message body。观察期间任一以下项为失败：P1 外发尝试、non-dry-run、Provider invocation、非空 allowlist、P1 容器访问 Stage03 数据源、Caddy 路由影响 Stage03、迁移非唯一 head、未解释的 5xx/worker crash/outbox 积压。

`stage09-p1-deployment-ledger.md` 的每一步至少记录：`Step`、`UTC`、`Artifact ID`、`Target revision`、`Write scope`（`none`/`stage09-p1-only`）、`Result`（`passed`/`failed`/`blocked`）、`Rollback readiness`、`Evidence reference`。不记录真实 hostname、命令参数、秘密值、数据库内容或任何 Telegram 数据。

### 4.6 P1 回滚与成功判定

P1 回滚优先级是**先切断 P1 ingress，再停止 P1 应用，最后处置 P1 空数据**：

1. 任何 P1 异常先保留脱敏 receipt，移除刚添加的单个 P1 Caddy host block，使用已验证的备份恢复并 reload；确认 Stage03 host 仍健康。
2. 停止 `stage09-p1` 的 API/worker/outbox/web。永不停止、重启、缩容或回滚 `telegram-bitable-stage03`。
3. 因为 P1 只允许新建空库，migration 回滚首选 `docker compose -p stage09-p1 down -v` 后删除 `/home/ubuntu/stage09-p1` runtime；只有在已记录 `20260720_0032` downgrade dry-run 成功、且需要保留 P1 空环境排障时，才可对**P1 数据库**执行明确 revision 的 downgrade。不得对 Stage03 database 执行任何 downgrade。
4. 删除 P1 runtime 文件、临时 Caddy 渲染文件、offline SQL、构建缓存和含环境变量的临时 shell history；保留仅脱敏 ledger、manifest checksum、migration revision、状态码和 rollback result。

P1 只有同时满足以下条件才可标记 `complete`：固定 artifact 与唯一 `20260720_0032` head 可追溯；P1 新库的 `vector` 与 schema/索引验证通过；runtime 全程 `dry_run`/LLM-off/provider-disabled/empty allowlist；API、静态资源和独立 HTTPS host 健康；Stage03 读回健康未受影响；观察窗口无禁止副作用；并且 ledger 含可执行的 Caddy/app/data rollback evidence。P1 完成只解锁“可以另行申请 P2 授权”，不自动开启 P2，也不满足 P3 的 Stage07 UI acceptance 门。

## 5. P2：真实 Telegram controlled smoke

该层是外部写入，必须在单独执行记录中声明 chat、用户授权、消息类型、发送上限与回收方式。

- 只允许一个明确 allowlisted 私聊或测试群；禁止客户群和群发。
- 入站 smoke：发送固定无业务信息的测试文本，验证 webhook → signature/identity → controlled ingress → audit/reference record。
- 出站 smoke：仅在 pending confirmation 经指定用户确认后，发送一条固定无业务信息的测试消息；验证 receipt/send log，不保留 message body。
- 结束后恢复 `dry_run`、清除 allowlist、核验无待发 outbox。

## 6. P3/P4 观察与生产 SLO

启动 limited pilot 前，至少建立：

- API 5xx、webhook reject、worker/outbox delay、Redis/DB connection、draft confirmation conflict；
- Provider availability、timeout bucket、usage presence（不存 raw prompt/answer/token/cost）；
- retrieval current-state reject、revocation/delete lag、Memory conflict；
- Telegram send receipt/failure、allowlist violation、dry-run violation；
- 业务/权限审计可追溯性与告警负责人。

生产负载积累后，才可按 Stage08 Package F 的 Milvus future trigger 评估检索扩展。

## 7. 阶段退出条件

| Gate | Evidence |
| --- | --- |
| P0 complete | redacted server inventory、风险和执行目标 |
| P1 complete | backup/rollback、migration、health/HTTPS、observation 证据 |
| P2 complete | 单个 allowlisted Telegram controlled smoke 与 safety close 证据 |
| P3 ready | Stage07 UI acceptance、监控告警、权限审计、limited pilot 计划 |
| P4 accepted | 用户/运营明确发布决策及 pilot 成功证据 |

未完成任一前置门时，只能报告该层 `blocked` 或 `evidenced-pending`，不得用本计划或 Stage08 评测代替生产事实。
