# Stage08 Package E / E3-R2/R3：原子草稿执行、图终态与 PostgreSQL 主证据

## 需求真源

依次完整阅读：

1. `docs/superpowers/plans/2026-07-22-stage08-e3-safe-execution-remediation.md`；
2. `project-docs/08-implementation/decisions/STAGE_08_E3_SAFE_EXECUTION_ADAPTER_DECISION.md`；
3. `project-docs/08-implementation/decisions/STAGE_08_E_LANGGRAPH_COLLABORATION_CONTRACT.md`；
4. `project-docs/08-implementation/STAGE_08_PACKAGE_E_COLLABORATION_BDD_AND_ACCEPTANCE.md`；
5. 已关闭 R1 报告与复审：`.superpowers/sdd/stage08-package-e-task-e3-r1-report.md`、`.superpowers/sdd/stage08-package-e-task-e3-r1-remediation-review-report.md`。

用户于 2026-07-22 要求阶段功能完成度优先：仅覆盖首轮 E3 真实复审发现的 transaction rollback、scope revoke、idempotency replay、全 trace 脱敏和真实 PostgreSQL 主流程；不要新增纯假设的边缘测试或额外确认。

## 允许范围

- `backend/app/services/stage06_platform.py`
- `backend/app/services/stage08_collaboration.py`
- `backend/app/services/stage08_runtime.py`
- `backend/app/runtime/stage08_tool_gateway.py`
- `backend/app/agents/stage08_collaboration.py`
- `backend/tests/unit/test_stage08_collaboration_service.py`
- `backend/tests/unit/test_stage08_collaboration_graph.py`
- `backend/tests/integration/test_stage08_collaboration_postgres.py`
- `.superpowers/sdd/stage08-package-e-task-e3-r23-report.md`

不新增公开 API、schema/migration、global role、真实 Provider、Telegram、部署、直接 record 写入或草稿确认；不 stage/commit/reset/checkout/clean/push。

## 必须交付

1. `run_stage08_collaboration` 接入已关闭 R1 safe context 与 sealed field/value intent。草稿值必须来自 intent，而非 `{}`；当前 target record/table/field、actor、member、employee/action、employee member grant、C1/C2/C3/D4 business/source scope 必须在消费期重验。非法 field、无写权限、字段不存在、scope 漂移均 `denied`，不创建副作用。
2. 仅 safe E3 draft path 使用原子执行边界。InMemory 全量恢复本边界新增 side effects；SQLAlchemy 用 `session.begin_nested()`，不提交或回滚调用方外层事务。
3. 执行边界内顺序为：锁定当前 scope → 重验 → `begin_execution_plan(... safe_context=...)` → safe Gateway → 已认证 `pending_confirmation` draft → safe terminal persistence。Gateway exception/失败、cancel、timeout、provider invalid/unavailable 或 scope revoke 必须 rollback ticket/idempotency/draft/internal AgentRun/audit，不留 orphan；只能留白名单 terminal failure 记录。
4. 使用既有 lifecycle 锁，必要时在 UoW 中补最小 lock/query 接口，使 workspace/member/employee/grant/target record/group binding/mapping/consumed sources 在同一确定顺序中锁定。不能绕开 Tool Gateway 或直接写 record。
5. same idempotency：先 current-state 重验，随后从安全 trace 的 E3 pending draft 得到同一 safe view，绝不重复 Gateway；safe replay 不能消费 default-mode ticket。different idempotency：独立完整执行，不使用 record-wide pending 数量推导成功或失败。
6. 图仍保留 E1 固定十节点和 `checkpointer=None`；E3 node 将 unavailable analysis 映射为 `degraded` 且不调用 Gateway/network，未知 citation 为 `denied`，其它无效分析为固定 `failed`，真实 latency 使用 monotonic elapsed，不能硬编码 0。
7. 成功、same-key replay、deny/failed/degraded/cancel/timed-out 的完整 E3 trace 必须检查所有本次 AgentRun/audit/tool summary，不仅最后一条，且不含 query、answer、private context、field/value、record/draft/ticket UUID、provider payload。

## 必要 RED / GREEN

先写并运行失败用例（可按现有 fixture 最小化实现）：

```python
def test_safe_draft_uses_sealed_intent_and_leaves_source_record_unchanged(): ...
def test_safe_gateway_failure_rolls_back_ticket_idempotency_draft_and_internal_trace(): ...
def test_safe_revoke_before_gateway_denies_without_draft_or_orphan(): ...
def test_safe_same_key_revalidates_then_replays_same_draft_without_gateway(): ...
def test_unavailable_analysis_is_degraded_without_gateway_or_network(): ...
```

PostgreSQL 不允许仅 `SELECT 1`。使用 configured disposable loopback pgvector URL，构建真实 `SqlAlchemyStage06PlatformUnitOfWork`，至少验证：一条成功 pending draft、同 key replay、Gateway failure rollback、一个已复现 scope revoke 场景，以及一个由 `pg_blocking_pids` 证明的 shared lock 阻塞。测试结束后清理新增 ticket/draft/idempotency/AgentRun/audit，明确报告计数。

运行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_collaboration_postgres.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/services/stage06_platform.py app/services/stage08_collaboration.py app/services/stage08_runtime.py app/runtime/stage08_tool_gateway.py app/agents/stage08_collaboration.py
```

不得输出连接串或凭据。报告写精确 RED/GREEN 结果、变更文件、真实 PostgreSQL 证据、cleanup、无 Provider/Telegram/network/deployment 调用、保留给 E4/F 的风险。最终仅回复 DONE/CONCERNS、测试概述和报告路径。
