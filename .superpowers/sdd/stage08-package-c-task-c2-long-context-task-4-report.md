# Stage08 Package C2 Long Context — Task 4 实施报告

## Status

- Status: `DONE_WITH_CONCERNS`
- Scope: Task 4 only — opaque authority、受控长窗口、单条清除、30 天过期批量清除
- 未开始 Task 5；未修改 C1/C3、Memory、RAG、Provider、LangGraph、Redis、公开 API/schema、webhook/parser/ingestion、模型或迁移。

## Changed files

- `backend/app/runtime/stage08_group_context_contracts.py`
  - 新增固定预算常量、严格 count-only `GroupContextWindowView` / `GroupContextPurgeResult`，以及 dump/revalidate 门禁。
- `backend/app/services/stage08_group_context.py`
  - 新增只能由 factory 签发的 opaque authority/handle。
  - 新增每次操作重新验证 workspace/member/employee/base/table/binding/mapping/record/link/scope/version 的 fail-closed 服务。
  - 新增 latest-24 + 7-day half-life history 选择、120/60,000/24,000 边界和 30 天强制保留期。
  - 新增单条授权清除与过期批量锁定清除；不生成摘要、不调用 Provider。
- `backend/app/services/stage06_platform.py`
  - 仅增加 Task 4 所需 projection window read 和 expired projection narrow-lock UoW parity；SQL 使用 `FOR UPDATE SKIP LOCKED` 和 120 行批次。
- `backend/tests/unit/test_stage08_group_context_contracts.py`
  - 新增 8 个 strict/count-only/model_construct/budget/status 合约测试。
- `backend/tests/unit/test_stage08_group_context_service.py`
  - 新增 24 个 authority、关系重读、窗口、预算、序列化、漂移、清除和无副作用测试。
- `backend/tests/integration/test_stage08_group_context_postgres.py`
  - 新增真实 PostgreSQL 过期锁定、正文擦除、30 天 event-time 上限和幂等证据。
- `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-4-report.md`
  - 本报告。

## TDD RED / GREEN evidence

### Contracts

1. RED:
   - `Push-Location backend; python -m pytest -q tests/unit/test_stage08_group_context_contracts.py; ...`
   - exit `2`；collection 因 `app.runtime.stage08_group_context_contracts` 不存在而失败，符合缺失功能预期。
2. 首轮实现后测试发现测试自身用 substring `text` 错误命中 `context`：`1 failed, 7 passed`；修正为字段名集合检查，没有放宽生产合约。
3. GREEN: `8 passed`；最终联合回归无 Pydantic serializer warning。

### Service

1. RED:
   - `Push-Location backend; python -m pytest -q tests/unit/test_stage08_group_context_service.py; ...`
   - exit `2`；collection 因 `app.services.stage08_group_context` 不存在而失败。
2. GREEN: 首轮 `19 passed`。
3. 30 天 window 上限与全量 `accessible_tables` 当前有效性 RED: `2 failed, 19 deselected`；最小修复后 GREEN: `2 passed, 19 deselected`。
4. 过期维护按 event-time 强制 30 天 RED: `1 failed, 1 passed, 21 deselected`；UoW 增加 `event_cutoff` 后 GREEN: `2 passed, 21 deselected`。
5. 501 字符 newest fragment 不得挤占 history 固定 96 槽 RED: `1 failed, 23 deselected`；增加独立 history 计数后 GREEN: `1 passed, 23 deselected`。

## Final verification

- 指定联合回归：
  - `python -m pytest -q tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_service.py tests/unit/test_stage08_group_context_ingestion.py tests/integration/test_stage08_group_context_postgres.py`
  - Result: `59 passed in 13.47s`。
- 真实 PostgreSQL：
  - `python -m pytest -q -ra tests/integration/test_stage08_group_context_postgres.py`
  - 使用已批准 disposable `STAGE06_LOCAL_DATABASE_URL`；Task 4 增量前后最终为 `8 passed`，没有 skip。
  - 证明 expired/stale active projection 被窄锁、正文置空、状态改为 `purged`、重复执行为 0，current projection 保持不变。
- 编译：
  - `python -m compileall -q backend/app/runtime/stage08_group_context_contracts.py backend/app/services/stage08_group_context.py backend/app/services/stage06_platform.py`
  - exit `0`。
- `git diff --check`（限定 Task 4 文件）exit `0`；仅有既存 LF/CRLF 提示。
- Static/privacy scan：
  - 新 contracts/service 无 `raw_text`、`raw_caption`、`normalized_text`、`Message`、`source_message_id`。
  - `telegram_chat_id` / `telegram_user_id` 只在私有 factory 中验证现有 binding 是否为 group-like `chat_user`，不进入 authority repr、public view、handle 或返回值。
  - `backend/app/api`、`backend/app/schemas`、C1、Memory、Runtime、Tool Gateway 中 `content_fragment` 无命中。
  - 新 contracts/service 中 network/OpenRouter/Provider/LangGraph/Redis/vector/Memory/AgentRun/outbox/audit 无命中。
- `ruff` 未运行：当前 Python 环境没有安装 `ruff`（`No module named ruff`）。

## Privacy and behavior result

- public Pydantic carrier 只有 contract version、status、固定计数、预算用量和 `compression_required`；extra 字段、正文、ID、source ref、crafted `model_construct` 经 revalidation 被拒。
- authority、projection handle、selected fragment、window 均为 private non-Pydantic/non-dataclass slots 对象；普通 JSON 序列化失败，repr 不含正文或内部 ID。
- C2 仅给出 `compression_required = raw_selected_chars > 24000`；没有压缩、摘要、持久化 digest、C1/C3 merge 或 Provider 调用。
- 读取和单条清除每次重新建立并比对当前 authority signature；member/employee/mapping/record relation/scope/version 漂移均返回固定 unavailable/0 路径，不返回正文。
- maintenance 只选择 active nonempty controlled projection，不锁、不读历史 `Message` 行。

## External actions and cleanup

- 没有 Telegram 网络调用、外部写入、Provider/LLM 调用、部署、公开 API 写入、Memory/RAG/C1/C3 action。
- 唯一数据库写入是 disposable local PostgreSQL integration test transaction，最终 rollback/fixture cleanup。
- 没有新临时脚本、测试数据文件或需清理工件。

## Remaining risks / concerns

- Python private/issuer 是进程内可信代码边界，不是针对同进程恶意模块反射的安全沙箱；公开路由和反序列化入口仍为零。
- normal Telegram group delete/revoke 仍不可观测；本任务只兑现 server-authorised purge 与 30 天 best-effort retention。
- 过期维护每批最多锁 120 行，需要调度方重复运行；调度不属于 Task 4。
- 当前默认非 disposable 数据库仍存在既有 orphan-revision 风险；本任务未使用、未修复该默认库，只使用 `STAGE06_LOCAL_DATABASE_URL`。
- 全 backend suite 按任务优先级未运行；已运行 Task 4 指定的 C2 联合回归和真实 PostgreSQL 集成套件。

## Independent review fixes — 2026-07-20

本节覆盖前文较早的 `59 passed / PostgreSQL 8 passed` 数字；审查修复后的最终证据为 `63 passed`，其中 PostgreSQL 文件共 9 个测试。

### 1. Critical stale-text closure

- RED:
  - `python -m pytest -q tests/unit/test_stage08_group_context_service.py -k 'built_window_revalidates'`
  - collection exit `2`：缺少 `_materialize_group_context_window`，证明旧 window 没有要求的 fresh read 门禁。
- GREEN:
  - 同命令 `3 passed, 23 deselected`。
- 修复：
  - `_GroupContextWindow` 不再保存 `_SelectedGroupContextFragment` 或正文副本，只保存 authority nonce、opaque projection handles、顺序和 count-only view。
  - 新增 private `_materialize_group_context_window`：每次内部消费前重新验证 authority、business scope、mapping/version、projection ownership、active lifecycle、30 天保留期和 500 字符上限，然后按 handle 顺序从当前 projection fresh-read 正文。
  - window 建立后发生 purge、member 失效或 mapping version drift，fresh materialization 固定返回 unavailable/空 fragments，不能得到旧正文。

### 2. Nested safe-view reconstruction

- RED:
  - `python -m pytest -q tests/unit/test_stage08_group_context_contracts.py -k 'deeply_rebuilds'`
  - `1 failed`：恶意 `GroupContextBudgetUsage` 子类及 `leaked_text` 原样存活。
- GREEN:
  - 同命令 `1 passed, 8 deselected`。
- 修复：
  - validator 只从 `usage` / `omissions` 读取固定标量字段，分别重建 exact base model，再重建 outer view。
  - nested subclass extra、dict carrier、negative `model_construct` count 均无法越过二次验证。

### 3. PostgreSQL eligible-body / count-only omission split

- RED:
  - `python -m pytest -q tests/integration/test_stage08_group_context_postgres.py -k 'counts_old_rows'`
  - `1 failed`：SQL UoW 尚无 count-only omission 与 bounded eligible read 方法。
- GREEN:
  - 同命令 `1 passed, 8 deselected`。
- 修复：
  - `count_group_message_projection_window_omissions` 只执行 aggregate count，分别计算 age omission 和超过 120 条的 limit omission，不 materialize projection body。
  - `list_eligible_group_message_projections_for_window` 在 SQL 层先过滤 `retention_expires_at > now`、`event_at > event_cutoff`、active/nonempty/current mapping，再按确定性顺序 `LIMIT 120` 选择正文。
  - PostgreSQL 测试证明 1 条 over-30-day body 不进入 eligible objects，122 条当前 body 只返回 120 条，age/limit omission 分别为 1/2。

### Channel provenance limitation（未擅自改 schema）

- 审查确认当前 `Stage06TelegramBinding` 没有可信持久化 `chat_type` / group provenance 字段，仅凭 `telegram_chat_id` 正负号不能形成严格授权事实。
- 已移除 `telegram_chat_id.startswith("-")` 的符号推断，不再声称它可区分 private/channel/group。
- 本任务没有新增模型字段、迁移、schema/API 或临时旁路。严格 private/channel fail-closed 仍需单独确认持久化 provenance 方案后实施；在此之前这是明确未关闭的限制。

### Review-fix final verification

- `python -m pytest -q tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_service.py tests/unit/test_stage08_group_context_ingestion.py tests/integration/test_stage08_group_context_postgres.py`
  - Result: `63 passed in 13.86s`。
- `python -m compileall -q ...`：exit `0`。
- scoped `git diff --check`：exit `0`，仅既存 LF/CRLF warning。
- static scan：window class 无 `_selected_fragments`；new contracts/service 无 historical Message raw fields、`source_message_id` 或 chat-ID sign heuristic。
