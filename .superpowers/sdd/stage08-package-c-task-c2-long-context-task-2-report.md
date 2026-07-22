# Stage08 Package C2 Long Context — Task 2 Report

## Status

- Task status：`DONE_WITH_CONCERNS`
- Scope：仅完成 C2 Task 2 的 ORM model、Alembic migration、Stage06 UoW parity 与聚焦真实 PostgreSQL test。
- 未开始 Task 3；没有 webhook/parser/Telegram ingress 改动。

## Changed files

1. `backend/app/models/stage08_group_context.py`
   - 新增 `Stage08GroupBusinessContextBinding`。
   - 新增 `Stage08GroupMessageProjection`。
   - 用 PostgreSQL-compatible FK、partial unique index、unique/check/index 约束固定 mapping version/status、每 binding 单 active mapping、source version、lifecycle、retention 顺序与 500 Unicode code-point 上限。
2. `backend/alembic/versions/20260719_0030_stage08_group_context.py`
   - 在 `20260718_0029` 后新增单一 revision `20260719_0030`，创建两张表及与 ORM 对应的约束/索引；downgrade 仅反向删除本 revision 对象。
3. `backend/app/models/__init__.py`
   - 注册并导出两个 C2 model，确保 metadata/Alembic/test 可见。
4. `backend/app/services/stage06_platform.py`
   - 为 protocol、in-memory UoW 和 SQLAlchemy UoW 对等增加 mapping/projection 的 add/get/list/lifecycle-lock/purge 方法。
   - active projection list 仅返回目标 mapping 下尚未过期、正文未擦除的 `active` 投影，按 `event_at DESC, id DESC` 稳定排序。
   - purge 在 lifecycle lock 后擦除受控正文并改为 `purged`；不锁、不读取 raw `Message` 字段。
5. `backend/tests/integration/test_stage08_group_context_postgres.py`
   - 使用现有 disposable real PostgreSQL fixture 覆盖 migration shape、partial active uniqueness、FK、version/lifecycle/retention/duplicate-source-version、500/501 Unicode code-point 边界、active list、lock、purge 和 timestamptz offset normalization。
6. `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-2-report.md`
   - 本报告。

## TDD evidence

### RED

Command：

```powershell
Push-Location backend; python -m pytest -q tests/integration/test_stage08_group_context_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Result：exit `2`，test collection 明确失败：

```text
ModuleNotFoundError: No module named 'app.models.stage08_group_context'
1 error in 1.30s
```

该失败由尚不存在的 C2 model/UoW 合同造成，不是测试拼写或环境跳过。

### First GREEN attempt and environment concern

按 brief 原命令运行：

```powershell
Push-Location backend; python -m alembic upgrade head; python -m alembic heads; python -m pytest -q tests/integration/test_stage08_group_context_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Observed：

- 默认 `DATABASE_URL` 所指旧库的 `alembic upgrade head` 失败：`Can't locate revision identified by '0004_stage_06_action_contracts'`。
- source migration graph 仍只报告 `20260719_0030 (head)`。
- real PostgreSQL fixture 自行使用 `STAGE06_LOCAL_DATABASE_URL`、重置 disposable public schema 并升级到 head，聚焦测试为 `5 passed in 7.61s`。
- PowerShell 组合命令的最终 exit 来自 pytest，因此显示 exit `0`；本报告不把前置 upgrade 失败隐藏为完整成功。

### Corrected disposable local PostgreSQL GREEN

仅将 `DATABASE_URL` 临时指向已批准的 `STAGE06_LOCAL_DATABASE_URL`，命令结束后恢复原值：

```powershell
$env:DATABASE_URL = $env:STAGE06_LOCAL_DATABASE_URL
Push-Location backend
python -m alembic upgrade head
python -m alembic heads
python -m pytest -q tests/integration/test_stage08_group_context_postgres.py
Pop-Location
```

Result：exit `0`：

```text
20260719_0030 (head)
..... [100%]
5 passed in 7.13s
```

Evidence count：5 个聚焦测试，全部在 disposable real local PostgreSQL 上执行；未用 SQLite 或 mock DB 冒充。

报告完成前最终复跑：`20260719_0030 (head)`，`5 passed in 8.05s`，`git diff --check` exit `0`（仅既有换行风格提示）。

## Static and privacy verification

Executed：

```powershell
Push-Location backend
python -m compileall -q app/models/stage08_group_context.py app/services/stage06_platform.py alembic/versions/20260719_0030_stage08_group_context.py tests/integration/test_stage08_group_context_postgres.py
Pop-Location
```

- compile exit `0`。
- production model/migration prohibited dependency scan 对 `raw_text|raw_caption|normalized_text|TelegramBot|sendMessage|httpx|requests|OpenRouter|APIRouter|add_api_route|Redis|pgvector|LangGraph|MemoryItem|AgentRun` 无 match（`rg` exit `1`，表示无匹配）。
- `backend/app/schemas`、`backend/app/api`、`backend/app/runtime` 无 `content_fragment` match；受控正文没有进入 public DTO/runtime carrier/API。
- `git diff --check` 对 Task 2 文件 exit `0`；仅有 shared worktree 既有 LF/CRLF 提示，没有 whitespace error。

## Self-review

- 数据库通过 partial unique index 保证同一个 Stage06 binding 同时最多一个 active mapping，并保留不同 version 的 inactive/history 行。
- 数据库无法仅凭现有 `records -> tables -> bases -> workspaces` 间接链用普通 FK 表达 customer/project same-workspace 业务语义；Task 2 保留完整 FK，测试证明有效 fixture 的链条同 workspace，Task 4 service 必须按批准合同每次 re-read 并对 workspace/relation drift fail closed。
- `event_at`、`edited_at`、`retention_expires_at` 使用 PostgreSQL `timestamptz`；offset input 由 PostgreSQL 正规化为同一 UTC instant。数据库不伪造“只接受 +00:00”这一无法由 timestamptz 保留原 offset 的承诺。
- `id` 是批准 decision 指定的同 `event_at` 稳定 internal tiebreak；没有新增可输出的 chat/message/update identifier。
- purge UoW 只提供内部最小生命周期 primitive；authority、scope、idempotent bulk-expiry、revalidation 属于 Task 4，未提前实现。

## Explicit exclusions

本任务没有进行 webhook、API route、Telegram network/outgoing write、Provider/LLM、Memory、RAG/vector、Context window/compression、Redis、LangGraph、deployment 或任何外部系统写入。没有读取、回填、迁移或删除历史 `Message.raw_text`、`raw_caption`、`normalized_text`。没有 stage、commit、reset、checkout 或 clean。

## Remaining risks / next-task boundary

1. 默认 `DATABASE_URL` 的旧库仍带仓库已不存在的 revision `0004_stage_06_action_contracts`；这不是 Task 2 schema bug。生产/共享库迁移前必须单独核对该库 revision 历史，不得直接 stamp 或删除。
2. Task 3 才能在 verified new/edited ingress transaction 中创建/版本化投影；当前没有 writer，因此本表不会自动接收消息。
3. Task 4 才实现 opaque authority、mapping/business scope re-read、120/60,000 selector、authorized purge service 和 compression signal。
4. 没有运行全 backend suite；本报告只声明 Task 2 的 5 个 focused real-PostgreSQL tests 和 static checks。

## Temporary cleanup

- 未创建临时脚本、测试数据库文件、secret dump、Telegram 消息、外部 artifact 或可清理 deployment 资源。
- disposable PostgreSQL fixture 每次重置测试 schema；本任务保留的只有源码、migration、test 与本报告。
