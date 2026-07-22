# Stage08 Package E / E3-R2：原子执行边界、锁、rollback 与 replay

## 需求真源

阅读：

1. `docs/superpowers/plans/2026-07-22-stage08-e3-safe-execution-remediation.md` 的 **Task R2**；
2. `project-docs/08-implementation/decisions/STAGE_08_E3_SAFE_EXECUTION_ADAPTER_DECISION.md`；
3. `project-docs/08-implementation/decisions/STAGE_08_E_LANGGRAPH_COLLABORATION_CONTRACT.md`；
4. 已完成 R1 的 `.superpowers/sdd/stage08-package-e-task-e3-r1-report.md`，以及 R1 实际接口。

## 范围

- `backend/app/services/stage06_platform.py`
- `backend/app/services/stage08_collaboration.py`
- `backend/app/services/stage08_runtime.py`
- `backend/app/runtime/stage08_tool_gateway.py`
- `backend/tests/unit/test_stage08_collaboration_service.py`
- `backend/tests/integration/test_stage08_collaboration_postgres.py`
- 报告：`.superpowers/sdd/stage08-package-e-task-e3-r2-report.md`

不改公开 API、模型/migration、真实 Provider、Telegram 或部署；不 stage/commit/reset/checkout/clean/push。

## 精确行为

1. 只在 E3 safe context 下建立执行边界。InMemory 可完整恢复本次边界写入；SQLAlchemy 使用嵌套 savepoint，不可对外层请求事务调用 `rollback()` 或提前 `commit()`。
2. 同一边界锁顺序固定为：workspace → actor active member → employee/member grants → target record/table/field → active group binding/mapping → 被消费 projection/source → execution ticket。缺失、锁失败、状态/版本漂移或歧义立即 fail closed。
3. 在锁定后重建 E2 当前 scope，并对 R1 sealed draft intent 做 field/value 合法性及 actor/employee field permission 验证；然后 reservation/ticket → Gateway → pending draft → safe terminal summary。Gateway 的任何非 success、异常、取消、预算/时间异常都回滚 ticket、idempotency、draft、内部 audit/AgentRun，只保留一条安全 terminal failure summary。
4. 成功路径从本 execution 的 Gateway result 或受控 trace 查询获得 draft identity；不得访问 InMemory 私有列表、不得按同 record 的 pending draft 总量推断。
5. same idempotency key：先当前 scope 重验；成功时从 hash trace 对应的 pending draft 重放同一 safe view，不能二次执行 Gateway。different key：独立完整执行，不能因另一个 pending draft 误报 failed。
6. PostgreSQL 测试必须有真实 `SqlAlchemyStage06PlatformUnitOfWork` 和业务夹具，不得只做 `SELECT 1`；覆盖 success、same/different replay、Gateway exception rollback、cancel/timeout、record/member/employee/mapping/source revoke，以及 `pg_blocking_pids` 双会话锁阻塞和最终 cleanup。

## TDD / 验证

先新增至少以下 RED：

```python
def test_safe_gateway_exception_has_no_ticket_idempotency_draft_or_internal_audit_orphan(): ...
def test_safe_same_key_revalidates_then_replays_exact_pending_draft(): ...
def test_safe_different_keys_do_not_use_record_wide_pending_count(): ...
def test_safe_scope_revoke_after_lock_before_gateway_denies_and_rolls_back(): ...
```

运行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_service.py -k "safe or rollback or replay or revoke"
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_collaboration_postgres.py
```

最终运行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_collaboration_postgres.py
```

不打印数据库连接串或凭据。报告写精确 RED/GREEN、实际 PostgreSQL 锁/事务证据、清理计数、无网络/Telegram/Provider 调用和遗留风险。最终只回复 DONE/CONCERNS、测试摘要和报告路径。
