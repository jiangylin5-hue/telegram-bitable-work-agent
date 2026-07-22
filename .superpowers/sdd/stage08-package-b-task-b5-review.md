# Stage08 Package B Task B5 独立复审

## 复审范围与方法

- 范围严格限于 B5 简报、实施报告、复审包、Package B BDD/计划、B1--B4 交付与复审记录、`backend/tests/integration/test_stage08_memory_postgres.py`，以及 `enqueue_confirmed_record_memory_event` 的最小 row-lock 修复。
- 未修改实现、未执行 Git 写操作，未调用 Telegram、Provider/OpenRouter、webhook、Redis、RAG、LangGraph、部署或任何外部系统。
- 工作树存在大量 Stage07/Stage08 的既有未提交内容；本复审没有将它们归因于 B5，也没有扩展其范围。

## 结论

**CHANGES REQUIRED（证据缺口，非已确认的生产逻辑错误）。**

生产代码的 row-lock 顺序与 in-memory 兼容分支均符合 B5 要求：已持久化 draft 的
`lock_record_change_draft_for_transition(draft.id)` 位于 outbox idempotency lookup 之前；SQLAlchemy UoW 使用
`SELECT ... FOR UPDATE`，in-memory UoW 仍返回既有 draft，因而不破坏既有直接服务测试。锁调用没有吞掉数据库异常的 `try/except`，失败会原样传播。

但是 B5 的唯一新增 confirmed-record 双会话 PostgreSQL 测试没有等待或观测第二会话真正阻塞在该 draft row lock 上。它在第二会话调用 enqueue **之前**设置 `contender_ready`，主会话随即 commit；因此第二会话可能只在第一会话释放锁后才开始加锁。当前断言只证明至少有一次 SQL 含 `FOR UPDATE`，不能证明这两个会话构成了所报告的 lock contention，也不能防止该测试在错误串行时序下误绿。B5 的目的正是 Package B 的 PostgreSQL 并发收口，这一证据不能缺失。

因此，本次复审不建议关闭 Package B。补齐下列 Important 后，重跑 B5 focused PG 与 Package B 计划套件并由独立复审确认，才可只关闭 **Package B**；这绝不表示 Stage08、Package C2、真实 LLM 评测或生产部署完成。

## Critical

无。

## Important

### I-01：confirmed-record 双会话测试没有证明第二会话被 draft 行锁阻塞

- 位置：`backend/tests/integration/test_stage08_memory_postgres.py:727-799`。
- 代码实现：`backend/app/services/stage08_memory.py:334-382`；`backend/app/services/stage06_platform.py:1445-1452`。
- 事实：第二线程在 `enqueue_in_second_session()` 内先读取 draft/record、取得 backend PID、调用 `contender_ready.set()`，然后才调用 `enqueue_confirmed_record_memory_event()`。主线程收到该 Event 后立即 `first_session.commit()`；没有 `pg_blocking_pids`、第二阶段 Event、SQL ordering assertion 或其他 barrier 确认第二线程已执行到 `FOR UPDATE` 且正在被第一会话阻塞。
- 影响：现有测试确实使用两个 PostgreSQL session，并最终得到同一个 event ID 和唯一一条 outbox；但它可在无实际 contention 的串行执行下通过。`stage08-package-b-task-b5-report.md` / evidence 中“第二事务等待 row lock、第一事务提交后再读取并复用”的表述超出当前可复跑测试的直接证据。
- 最小修复：复用本文件已有 `_wait_until_backend_is_blocked(...)` 模式。第一会话获取 draft lock、flush event 后，第二会话在 enqueue 前公开 PID；主线程必须以 `pg_blocking_pids(second_pid)` 观测它被第一 session PID 阻塞，确认阻塞后才 commit；随后断言第二会话返回同一 event ID，数据库仍恰好一条 reference-only outbox。应同时保留/新增 statement ordering 断言，确认该 draft `FOR UPDATE` 在 outbox idempotency SELECT 前发生。
- 不需要 migration、API、schema、权限、Telegram、Provider、Redis、RAG、LangGraph 或外部调用。

## Minor

无。

## 已核验的符合项

1. **锁的实现和 fallback。** `enqueue_confirmed_record_memory_event()` 先重取 transition lock，再重取 record、验证 confirmed/base/table/policy/field visibility，之后才计算 key 和查询既有 outbox；`SqlAlchemyStage06PlatformUnitOfWork` 的实现为 `.with_for_update()`。锁返回 `None` 时仅保留传入 draft，维持未注册 in-memory draft 的既有测试语义；SQL 层锁失败不会被转为成功或静默忽略。
2. **reference-only 与审计。** confirmed event payload 精确为六个 reference key：`workspace_id`、`table_id`、`record_id`、`record_version`、`policy_version`、`rule_index`。B5 PG 测试证明隐藏字段 sentinel 不进 payload；worker 的 item 只保存 policy 允许且当前可读的 `decision/status` 投影。审计 helper 的 after-state 只含 status/version，permission snapshot 只含固定 action；无 payload/scope/source refs/fingerprint/field key/source content。
3. **fail closed 生命周期。** B5 PG 覆盖 foreign workspace 读取不改变 item、owner TTL 转 `expired`、source record delete 转 `deleted`、字段撤权后安全读取拒绝并转 `deleted`。完整模块 suite 同时执行 B4 group candidate 的 `0.85`、binding revoke、exact-fingerprint revoke、TTL/version 优先级与 API 403/409 回归。
4. **数据库合同。** migration head 为唯一 `20260718_0029 (head)`；真实 catalog tests 覆盖两张表的 JSONB、canonical lifecycle status、精确 unique `(workspace,type,fingerprint)`、lifecycle index、workspace/self FK 和 version/confidence constraints。
5. **范围控制。** B5 已审生产改动只涉及 `stage08_memory.py` 的 lock 顺序；未发现新增 migration、schema、route/API、role/action、Telegram ingestion/client、Provider、Redis、RAG/vector、LangGraph 或部署配置。静态扫描在 B5 production surfaces 中没有 HTTP/Telegram client/OpenRouter/Redis/LangGraph/vector/send marker。

## 本次新鲜命令证据

```powershell
$env:STAGE08_MEMORY_IDENTITY_HMAC_KEY='b5-independent-review-key'
python -m pytest -q tests/integration/test_stage08_memory_postgres.py -k 'confirmed_record_outbox_enqueue_is_idempotent_across_competing_postgres_sessions or confirmed_record_postgres_outbox_redacts_hidden_field_and_fails_closed_on_field_revocation or memory_postgres_ttl_cross_workspace_and_deleted_source_fail_closed or group_candidate_postgres_idempotency_binding_revocation_and_audit_redaction or accepted_group_candidate_postgres_revoke_locks_exact_fingerprint_only'
# 5 passed, 8 deselected in 8.36s

python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_memory_confirmed_record.py tests/unit/test_stage08_memory_api.py tests/integration/test_stage08_memory_postgres.py
# 120 passed in 20.09s

python -m alembic heads
# 20260718_0029 (head)

python -m compileall -q app/services/stage08_memory.py tests/integration/test_stage08_memory_postgres.py
# exit 0

git diff --check -- backend/app/services/stage08_memory.py backend/tests/integration/test_stage08_memory_postgres.py
# exit 0
```

上述 evidence 使用现有 disposable local PostgreSQL；不等同 staging/production 证据。模块 suite 通过不消除 I-01：测试覆盖范围与其所宣称的并发阻塞证据不同。

## Package B 关闭判定

- 当前：**不可关闭 Package B**，原因仅为 I-01 的 PostgreSQL concurrency-evidence 缺口。
- I-01 修复、独立重跑和复审通过后：可将 Package B 标记为任务边界内关闭；仍不得把该结果外推为 Stage08、C2 群聊历史、真实 Provider/LLM 质量评测、生产 Telegram 或生产部署完成。

---

## Fix Round 2 独立复审

### 结论

**PASS。** 初审 I-01 已以真实、可观测的 PostgreSQL 行锁竞争证据关闭；未发现新的 Critical、Important 或 Minor。

`test_confirmed_record_outbox_enqueue_is_idempotent_across_competing_postgres_sessions` 现有两个明确阶段：主会话先执行 enqueue、持有 `record_change_drafts FOR UPDATE` 并 flush outbox；第二会话公布其 backend PID 后才进入 enqueue。主线程并非 sleep，而是调用 `_wait_until_backend_is_blocked(...)`，通过 PostgreSQL `pg_blocking_pids(second_pid)` 轮询并要求其中包含第一会话 PID；只有断言成功后才 `commit()` 释放 lock。随后第二会话返回与首会话同一 event ID，最终查询仍严格为一条同 aggregate 的 confirmed-record outbox。

`finally` 会在任何 timeout/assertion 后对仍开启的主事务 rollback，并 `executor.shutdown(wait=True)`；SQL event listener 也在外层 finally 移除。该测试不会通过未发生 lock contention 的串行时序。

### Critical

无。

### Important

无。

### Minor

无。

### I-01 关闭核验

1. **第二 session PID 可观测。** 第二 SQLAlchemy session 在进入 enqueue 前读取 `pg_backend_pid()`，写入 `contender_pids` 后才 signal `contender_ready`。
2. **第一 session 确实持有锁。** 第一 enqueue 在 code path 中先调用 `lock_record_change_draft_for_transition()`；测试在 `first_session.flush()` 后取得第一 PID，尚未提交事务。
3. **不是 sleep 推断。** `_wait_until_backend_is_blocked(stage06_postgres, blocked_pid=contender_pids[0], blocking_pid=first_pid)` 通过 observer connection 的 `pg_blocking_pids` 证明实际 PostgreSQL 阻塞关系，超时直接 fail。
4. **释放后的幂等结果。** 仅在上述断言后 commit；第二 future 在 15 秒有界等待内返回 `first_event.id`，verify session 确认对应 aggregate/event type 仅一行。
5. **顺序证明。** SQL capture 断言第一条 `record_change_drafts ... FOR UPDATE` 发生在第一条 `outbox_events ... idempotency_key` lookup 之前；服务实现也无 catch/隐式重试来吞掉 lock/database failure。
6. **资源清理。** 内层 finally rollback 未结束的第一事务并 shutdown executor；外层 finally 移除 listener。未发现线程、连接或事务残留的测试路径。

### 本轮新鲜验证

```powershell
$env:STAGE08_MEMORY_IDENTITY_HMAC_KEY='b5-fix-round-2-review-key'
python -m pytest -q tests/integration/test_stage08_memory_postgres.py -k 'confirmed_record_outbox_enqueue_is_idempotent_across_competing_postgres_sessions'
# 1 passed, 12 deselected in 3.40s

python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_memory_confirmed_record.py tests/unit/test_stage08_memory_api.py tests/integration/test_stage08_memory_postgres.py
# 120 passed in 29.17s

python -m alembic heads
# 20260718_0029 (head)

python -m compileall -q app/services/stage08_memory.py tests/integration/test_stage08_memory_postgres.py
# exit 0

git diff --check -- backend/app/services/stage08_memory.py backend/tests/integration/test_stage08_memory_postgres.py
# exit 0
```

生产 surface 的静态检索未发现 HTTP client、Telegram client/send、OpenRouter/Provider、Redis、LangGraph、Milvus/pgvector/vector marker。Fix Round 2 只改动 B5 PostgreSQL 测试与 B5 证据文档；没有 migration、model/schema、API/route、permission role/action 或外部系统范围扩大。

### Package B 关闭判定

在父任务按真源文档更新进度前提下，**现在可以关闭 Package B，且仅限 Package B**：B1--B5 的 local PostgreSQL、生命周期、幂等、脱敏、B4 candidate/API 映射证据及独立复审均已具备。

这不表示 Stage08 完成；Package C2 群聊窗口/历史原文、后续 RAG/pgvector、LangGraph 协作、真实 LLM 质量评测、生产 Telegram 和部署仍不在本次结论内。
