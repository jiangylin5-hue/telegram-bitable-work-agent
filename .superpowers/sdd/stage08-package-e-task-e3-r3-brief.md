# Stage08 Package E / E3-R3：图集成、终态与全 trace 安全验收

## 需求真源

阅读：

1. `docs/superpowers/plans/2026-07-22-stage08-e3-safe-execution-remediation.md` 的 **Task R3**；
2. `project-docs/08-implementation/decisions/STAGE_08_E3_SAFE_EXECUTION_ADAPTER_DECISION.md`；
3. `project-docs/08-implementation/decisions/STAGE_08_E_LANGGRAPH_COLLABORATION_CONTRACT.md`；
4. R1、R2 报告和实际接口。

## 范围

- `backend/app/agents/stage08_collaboration.py`
- `backend/app/services/stage08_collaboration.py`
- `backend/tests/unit/test_stage08_collaboration_graph.py`
- `backend/tests/unit/test_stage08_collaboration_service.py`
- `backend/tests/integration/test_stage08_collaboration_postgres.py`
- `.superpowers/sdd/stage08-package-e-task-e3-report.md`
- `.superpowers/sdd/stage08-package-e-task-e3-r3-report.md`

不改 API/migration/Provider/Telegram/部署；不得 stage/commit/reset/checkout/clean/push。

## 精确行为

1. 固定十节点拓扑、节点名和 `checkpointer=None` 不变；不得将 private material 加入公开图状态。
2. E2 `execute_collaboration_reads` 后：analysis unavailable 为 `degraded` 且不调用 Gateway/network；shape/forgery/unknown citation 为 `failed` 或 `denied` 的固定安全结果；Policy deny 为 `denied`；cancel/timeout 保持各自终态。
3. 只有 R2 safe boundary 返回已认证的 `pending_confirmation` draft 时才进入 `draft_pending`。answer、citation、degradation、safe draft id 必须符合 `AssistantQuerySafeView` 合同。
4. terminal AgentRun/audit 使用真实 monotonic elapsed `latency_ms`，不硬编码 0；不得写 query/answer/private material/field/value/UUID/provider payload。
5. 完整 trace 审计检查所有持久对象和安全输出，不能只检查最后一条 audit。

## 最低 RED / GREEN

```python
def test_unavailable_analysis_is_degraded_without_gateway_or_network(): ...
def test_full_safe_draft_trace_has_no_forbidden_values_in_all_agent_runs_audits_or_tool_summaries(): ...
def test_cancelled_or_timed_out_safe_execution_has_no_draft_or_orphan(): ...
```

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_context_composition_service.py tests/unit/test_stage08_retrieval_provider.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py tests/integration/test_stage08_collaboration_postgres.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/runtime/stage08_contracts.py app/services/stage08_collaboration.py app/services/stage08_runtime.py app/runtime/stage08_tool_gateway.py app/services/stage06_digital_employees.py app/services/stage06_platform.py app/agents/stage08_collaboration.py
```

报告写精确通过数、PostgreSQL evidence、全 trace 脱敏扫描、无 Provider/Telegram/network/deployment 调用、E3 尚未涵盖的 E4/F 风险。独立复审必须同时通过 spec-compliance 和 code-quality，才可关闭 E3。
