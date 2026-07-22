# Stage08 Package C2 — Task 4 `source_chat_type` 收口报告

## Status

- Status: `DONE_WITH_CONCERNS`
- Authority: 用户于 2026-07-20 明确确认 `source_chat_type` schema/migration。
- Scope: 只补 C2 projection 群来源 provenance；未开始 Task 5。

## Changed files

- `backend/alembic/versions/20260720_0031_stage08_group_context_source_type.py`
  - 增加 non-null `source_chat_type`，server default/backfill 为 `unknown`。
  - CHECK 只允许 `group | supergroup | unknown`。
  - eligibility index 加入 `source_chat_type`；downgrade 恢复旧 index 并删除约束/列。
- `backend/app/models/stage08_group_context.py`
  - 增加内部 ORM 字段、约束和索引定义。
- `backend/app/services/telegram_ingestion.py`
  - 仅 verified `group` / `supergroup` ingress 创建 projection，并写入解析后的精确类型；edit version 同样写入当前已验证类型。
- `backend/app/services/stage06_platform.py`
  - active/eligible/body-selection/count-only omission 查询均先过滤 `group` / `supergroup`。
- `backend/app/services/stage08_group_context.py`
  - fresh materialization 再次验证 source provenance drift，`unknown` 不得产生正文。
- `backend/tests/unit/test_stage08_group_context_ingestion.py`
  - 覆盖 group/supergroup new+edit、negative-ID channel 拒绝和 public carrier 隔离。
- `backend/tests/unit/test_stage08_group_context_service.py`
  - 覆盖 mixed valid/unknown、unknown 排除和 materialization provenance drift。
- `backend/tests/integration/test_stage08_group_context_postgres.py`
  - 覆盖列/default/check/single head、非法值拒绝、unknown default/backfill 与 SQL eligibility 排除、purge 不改 provenance。
- `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-4-source-chat-type-report.md`
  - 本报告。

## TDD RED evidence

### Ingress provenance

Command:

`python -m pytest -q tests/unit/test_stage08_group_context_ingestion.py -k 'new_group_message or edit_creates_version or negative_chat'`

Result: `3 failed, 1 passed, 16 deselected`。group/supergroup new 与 edit 均因 ORM 缺少 `source_chat_type` 发生预期 `AttributeError`；negative-ID channel 已由既有 verified parser 门禁拒绝。

### Service eligibility

Command:

`python -m pytest -q tests/unit/test_stage08_group_context_service.py -k 'verified_group_provenance'`

Result: `1 failed, 26 deselected`。构造 projection 时因缺少 ORM 字段发生预期 `TypeError`。

### PostgreSQL schema

Command:

`python -m pytest -q tests/integration/test_stage08_group_context_postgres.py -k 'migration_has_timezone'`

Result: `1 failed, 9 deselected`。inspector 缺少 `source_chat_type`，发生预期 `KeyError`。

## GREEN implementation evidence

### Unit and migration graph

- ingestion + service: `47 passed`；补充 supergroup edit 后最终三文件命令为 `58 passed`。
- `python -m alembic heads`: 唯一 `20260720_0031 (head)`。

### Real PostgreSQL

- `python -m pytest -q tests/integration/test_stage08_group_context_postgres.py`
  - Result: `10 passed in 14.49s`。
- 使用 disposable `STAGE06_LOCAL_DATABASE_URL` 执行 brief 指定流程：
  - `alembic upgrade head`
  - `alembic heads`
  - ingestion/service/PostgreSQL 三文件回归
  - Result: 单 head `20260720_0031`，`58 passed in 14.67s`。
- `DATABASE_URL` 在命令结束后恢复原状态。

### Reversibility RED / GREEN

首次真实执行 `alembic downgrade 20260719_0030` 时发现 CHECK constraint 名称被 naming convention 二次转换，PostgreSQL 返回 `UndefinedObject`；事务回滚，数据库没有半降级。修复 downgrade 使用 `conv("ck_stage08_group_projection_source_chat_type")` 后：

- real downgrade `0031 -> 0030`: pass；
- real upgrade `0030 -> 0031`: pass；
- disposable local database 最终留在 `0031` head。

### Final Task 4 regression

`python -m pytest -q tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_ingestion.py tests/unit/test_stage08_group_context_service.py tests/integration/test_stage08_group_context_postgres.py`

Result: `67 passed in 14.58s`。

- compileall（model/ingestion/UoW/group-context/migration）exit `0`。
- scoped `git diff --check` exit `0`；只有既存 LF/CRLF warning。

## Security and privacy result

- `channel` / `private` 不创建 C2 projection；negative Telegram chat ID 不能把 `channel` 提升为 group。
- 新 verified projection 只写 parser 已验证的 `group` / `supergroup`；无 `getChat`、无 chat-ID 形状推断、无新网络调用。
- 历史/缺省行是 `unknown`。SQL body query 在选取正文前使用 `source_chat_type IN ('group','supergroup')`，因此 unknown body 不 materialize；count-only omission 同样只针对合资格类型。
- fresh materialization 再检查 source type；已计划 window 对应行若漂移为 `unknown`，返回 unavailable/空 fragments。
- purge/expiry purge 只清空正文和改变 lifecycle，不修改 `source_chat_type`。
- 全仓静态定位显示该字段仅存在于 ORM、migration、私有 ingestion/UoW/group-context 服务和 focused tests；public API/schema、audit、outbox、Memory、RAG/vector、Provider、AgentRun/Checkpoint 无命中。
- public safe view、Telegram safe view 和异常返回不含 source type、正文或身份组合。

## Exclusions and cleanup

- 无 public route/schema/response 变更。
- 无 Telegram 网络、Provider/LLM、Memory、RAG/vector、Redis、LangGraph、audit/outbox、Mini App、部署或生产写入。
- 外部状态写入仅为已批准 disposable local PostgreSQL migration/integration；最终数据库回到 `0031` head。
- 无临时脚本、临时文件或残留测试数据需要清理。

## Remaining concerns

- 当前默认非 disposable 数据库仍有既有 orphan-revision 风险；本任务没有对其 stamp、删除、修复或宣称通过，只使用 `STAGE06_LOCAL_DATABASE_URL`。
- `source_chat_type` 的不可编辑性由内部写入边界、无 public mutation surface 和查询 fail-closed 保证；数据库 CHECK 保证枚举合法，但没有另加 update trigger。新增 trigger 不在确认范围内。
- 未运行全 backend suite；按低测试优先级要求运行了完整 C2 Task 4 regression、真实 PostgreSQL、migration upgrade/downgrade 和静态门禁。
- 当前 Python 环境仍未安装 `ruff`；未运行 ruff。

## Final review fix — fresh materialization SQL eligibility

### Finding

独立复审确认：旧 `_materialize_group_context_window` 先调用无条件 `get_group_message_projection(id)` 读取整行，再在 Python 中拒绝 `unknown`。虽然没有向外返回正文，但 unknown body 已经越过 SQL eligibility 边界被加载，违反 approved provenance contract。

### RED

1. Unit guard:
   - `python -m pytest -q tests/unit/test_stage08_group_context_service.py -k 'oversized_fragment'`
   - Result: `1 failed, 26 deselected`；测试禁止 unconditional get，旧 materializer 触发 `fresh_materialization_must_use_eligible_uow_query`。
2. Real PostgreSQL:
   - `python -m pytest -q tests/integration/test_stage08_group_context_postgres.py -k 'fresh_handle_query'`
   - Result: `1 failed, 10 deselected`；SQL UoW 尚无专用 eligible-handle query。

### GREEN

- 新增 `get_eligible_group_message_projection_for_materialization` 的 Protocol、InMemory 和 SQLAlchemy parity。
- SQL 在选择完整 projection/body 前同时约束：
  - projection id；
  - current business-context mapping id；
  - `source_chat_type IN ('group', 'supergroup')`；
  - lifecycle `active`；
  - body 非空；
  - `retention_expires_at > now`；
  - `event_at > event_cutoff`；
  - `LIMIT 1`。
- private fresh materializer 只使用该 eligible query；代码静态扫描确认不再调用 unconditional `get_group_message_projection`。
- focused unit GREEN: `1 passed, 26 deselected`。
- real PostgreSQL GREEN: `1 passed, 10 deselected`；handle 对应数据库行从 `group` 漂移为 `unknown` 后，SQL 返回 `None`，结果中无正文。
- 最终 C2 Task 4 回归：`68 passed in 16.32s`。
- compileall exit `0`；scoped `git diff --check` exit `0`，仅既存 LF/CRLF warning。

### Scope confirmation

- 未新增 migration、模型字段、API/schema、网络调用、C1/C3、Provider、Memory、RAG、Redis、LangGraph、audit/outbox 或部署改动。
- 本修复保留了此前 window 不持有正文、fresh authority/scope revalidation、deep safe-view reconstruction、bounded window query、30 天清理和 `source_chat_type` migration 全部行为。
