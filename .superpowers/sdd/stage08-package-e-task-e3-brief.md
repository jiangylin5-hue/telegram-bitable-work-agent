# Stage08 Package E — Task E3 brief

## 目标

在不新增模型、迁移、公开 API、权限模型或真实外部调用的前提下，完成 E3 的分析、Policy Gate 与受控草稿创建：

`run_stage08_collaboration(uow, command, actor, deps, now) -> AssistantQuerySafeView`

只允许 Policy Gate 放行后的 `draft_update` 使用现有 `begin_execution_plan`、`Stage08ToolGateway` 和 `record_change_draft.create` 创建既有的 `pending_confirmation` 草稿。不得直接写业务记录、确认草稿、发送 Telegram、调用真实 Provider 或绕开现有 ticket/idempotency/audit 机制。

## 可改动范围

- 修改 `backend/app/services/stage08_collaboration.py`
- 修改 `backend/app/agents/stage08_collaboration.py`
- 修改 `backend/tests/unit/test_stage08_collaboration_service.py`
- 修改 `backend/tests/unit/test_stage08_collaboration_graph.py`
- 新增 `backend/tests/integration/test_stage08_collaboration_postgres.py`
- 新增并维护 `.superpowers/sdd/stage08-package-e-task-e3-report.md`

不要修改上述范围外的生产代码、模型、迁移、API 或项目文档。共享工作树是脏的；不要 stage、commit、reset、checkout、clean 或 push。

## 必须实现的行为

1. 调用已完成 E1/E2 的 `execute_collaboration_reads`，仅在 process-local 私有材料上分析；不可把 query、C3 群文本/digest、D4 private evidence、memory payload、raw prompt/response、UUID、field、score/vector、authority、provider error 写进 DB、Redis、checkpoint、AgentRun、audit、outbox、日志或 API DTO。
2. `AnalysisProvider` 输入/输出限制为：受控 answer、已有安全 citation ordinal、requested action、受限 draft intent。必须验证 ordinal、answer 大小、action 与 draft intent；unknown ordinal 或格式不合法必须 fail closed，不能创建草稿。
3. 分析 provider 不可用、超时、返回无效 shape 或抛异常时，不调用网络且映射为安全 `degraded` 或 `failed`，不持久化 raw answer。
4. Policy Gate 必须发生在任何 draft/ticket 之前，并在消费期重新验证 active member、employee、target record/view/field、business/source lifecycle、预算与 idempotency。范围不确定或被撤权必须拒绝。
5. 仅 `draft_update` 可继续：基于已验证的受限 intent 构造一个 `ExecutionPlan` 中的 `record_change_draft.create` invocation；先执行 `begin_execution_plan`，再通过 `Stage08ToolGateway`。结果必须是已有 `pending_confirmation` draft。
6. 取消、拒绝或异常必须 rollback 刚创建的 reservation/ticket，保证没有 orphan ticket。不得直接 ORM 写 record、直接确认 draft 或发送外部消息。
7. 每个 terminal run 使用 `uow.add_agent_run` 与 `record_audit_event` 写入严格白名单安全摘要。摘要只能含 graph/status/count/code/action/ticket-or-draft presence/hash trace/latency；不得包含 query、answer、private material、UUID、field 或 provider response。
8. 保持 LangGraph 拓扑和 `checkpointer=None`；E3 只为现有 analyse/policy_gate/materialize_draft/finalize 节点接入既定私有状态机，不得扩大公开状态。

## 先写 RED 测试

至少覆盖：

- provider 产生当前 safe material 中不存在的 citation ordinal：结果 `denied`，`draft_id is None`；
- 计划后撤销 target record 或 employee grant：结果 `denied` 或 `failed`，草稿计数 0、orphan ticket 计数 0；
- unavailable analysis：安全 `degraded` 且网络调用数 0；
- malformed provider、取消、预算超限、同/不同 idempotency、`pending_confirmation` draft、audit redaction 与 rollback cleanup。

## 验证

运行并记录：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_collaboration_postgres.py
```

PostgreSQL 只可使用已配置的本地 loopback disposable pgvector 实例，不要打印连接串或凭据。报告须记录 RED/GREEN、精确测试结果、是否有真实 provider/network/Telegram 调用（应为没有）、已知风险和改动文件。
