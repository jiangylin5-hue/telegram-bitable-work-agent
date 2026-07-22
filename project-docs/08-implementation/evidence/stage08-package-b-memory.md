# Stage08 Package B：Business Memory 本地实现证据

## Evidence Status

- Scope：Task B5 为 B1–B4 的 PostgreSQL 生命周期与安全收口证据；本页不是 Package B 或 Stage08 的完成声明。
- Environment：已配置的 disposable local PostgreSQL，由 `STAGE06_LOCAL_DATABASE_URL` 的既有测试 fixture 在每个测试中重置 public schema 并迁移到 head。连接凭据未记录。
- External boundary：本任务没有调用 Telegram Bot API、webhook、OpenRouter/其他 Provider、Redis、RAG、LangGraph、Milvus 或部署接口。测试中的 Telegram 字段只为 B4 已有数据库模型的本地安全回归，不是网络 I/O。

## RED → GREEN：confirmed-record outbox 并发

### RED（真实 PostgreSQL）

新增 `test_confirmed_record_outbox_enqueue_is_idempotent_across_competing_postgres_sessions` 后，两个独立 SQLAlchemy session 对同一已确认 draft 直接调用 `enqueue_confirmed_record_memory_event`。首事务 flush 后持有 outbox 唯一键，第二事务在数据库等待；首事务提交后，第二事务报：

```text
IntegrityError: uq_outbox_events_idempotency_key
```

这证明原有“先查询、再插入”的幂等键逻辑不能在并发恢复/重放调用下安全复用已有 event。

### GREEN（最小修复）

`enqueue_confirmed_record_memory_event` 现在在查询 idempotency key 前复用既有 `lock_record_change_draft_for_transition(draft.id)`。正常已持久化 draft 的两个事务因此串行；第二事务在锁释放后读取并返回已提交的 reference-only event。为了保留既有 in-memory 直接服务测试的兼容性，不存在于 UoW 的 draft 不被错误拒绝；真实确认路径中的 draft 均已持久化并受 row lock 保护。

最终 PostgreSQL 测试同时证明：

- SQL 捕获出现 `record_change_drafts ... FOR UPDATE`；
- 两会话返回同一 outbox event ID；
- 数据库中同一 aggregate 的 `stage08.memory.confirmed_record.v1` 仅一行；
- event payload 仅含 `workspace_id`、`table_id`、`record_id`、`record_version`、`policy_version`、`rule_index`。

### Fix Round 1：服务器侧阻塞证据

独立复审指出，初版测试虽然使用了两个 PostgreSQL session，却可能在第二会话开始 `FOR UPDATE` 之前就提交第一会话，不能直接证明真实 contention。该问题是**测试证据缺口**，不是新发现的生产逻辑缺陷。

测试现改为两阶段协调，且没有以 sleep 作为锁断言：

1. 第一会话调用 enqueue、取得 `record_change_drafts FOR UPDATE`、flush outbox，并公开 PostgreSQL backend PID；
2. 第二会话先公开自身 backend PID，随后进入 enqueue；
3. 主测试通过 `pg_blocking_pids(second_pid)` 观察第二 backend 正被第一 backend 阻塞；只有此断言成立后才提交第一会话；
4. 第二会话随后返回相同 event ID；最终查询仍只有一条对应 outbox；SQL 捕获还验证 draft `FOR UPDATE` 位于 outbox `idempotency_key` lookup 之前。

失败路径的 `finally` 会 rollback 仍打开的第一事务，再等待 executor 退出，避免 assertion/timeout 留下测试连接。

## BDD 要求到可复跑证据

| Requirement | 证据 |
| --- | --- |
| B-01 | `test_memory_migration_has_contract_tables_constraints_and_indexes` 读取真实 PG catalog，验证 JSONB、canonical status check、unique fingerprint、lifecycle index 与 FK；`python -m alembic heads` 输出单一 `20260718_0029 (head)`。 |
| B-02 | 并发 confirmed-record outbox 用例验证 reference-only payload、draft row lock 和 idempotent reuse；worker 在独立事务 materialize 后只保存允许的 `decision/status` 投影。 |
| B-03 | 既有 group candidate PG 用例验证 `0.85` candidate、绑定撤销、精确 fingerprint revoke、无提交可见性与 audit redaction；不读取或发送 Telegram。 |
| B-04 | `test_memory_postgres_ttl_cross_workspace_and_deleted_source_fail_closed` 真实 PG 验证 foreign actor 读取为空且不改变状态、owner 的 TTL 读取转为 `expired`、source 删除读取转为 `deleted`。既有 group binding revoke 与 exact-revoke PG 回归仍在完整模块套件中运行。 |
| B-05 | `test_confirmed_record_postgres_outbox_redacts_hidden_field_and_fails_closed_on_field_revocation` 验证隐藏字段 sentinel 不进入 outbox/Memory Stage08 audit，字段权限撤回后读取为 `None` 且 Memory 转为 `deleted`。API 403/409 与安全回执由 `tests/unit/test_stage08_memory_api.py` 纳入完整回归。 |

## Fresh Verification

```powershell
$env:STAGE08_MEMORY_IDENTITY_HMAC_KEY='test-only-identity-key'
Push-Location backend
python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_memory_confirmed_record.py tests/unit/test_stage08_memory_api.py tests/integration/test_stage08_memory_postgres.py
python -m alembic heads
python -m compileall -q app/services/stage08_memory.py tests/integration/test_stage08_memory_postgres.py
Pop-Location
```

Fresh results:

- Package B module suite：Fix Round 1 fresh run 为 `120 passed in 20.67s`。
- Alembic：`20260718_0029 (head)`。
- `compileall`：exit 0。
- `git diff --check`（B5 修改范围）：exit 0。

## 未覆盖项与风险

- 本证据不等于完整后端套件、生产数据库、真实 Telegram 入站/发送、真实 Provider 评测、RAG/Milvus、LangGraph 或部署验证。
- API 的 403/409 是隔离的 unit/in-process route 回归，不是部署后的 HTTP 服务证据。
- Package B 是否可标为阶段收口仍须独立代码复审；本任务未修改 Stage08 真源、实现计划或进度账本。

## 临时清理

测试只使用 fixture 的 disposable public schema。一次中断曾留下本任务自己的 pytest 子进程；在确认其 command line 均为本任务 B5 单测后已结束，随后从干净数据库完成 fresh suite。没有保留测试数据、凭据、外部消息或部署产物。
