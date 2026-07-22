# Stage08 Package E / E1：Private Collaboration Contracts 与 LangGraph Topology 实施简报

## 前置与目标

- Status：`implementation boundary approved by the existing user-confirmed Stage08 plan`
- 先完整阅读：Package E design、`STAGE_08_E_LANGGRAPH_COLLABORATION_CONTRACT.md`、Package E BDD、E implementation plan、现有 Stage05 supervisor、Stage06 live employee、Stage08 context/retrieval contracts。
- 目标：只创建不接数据库/不接 API/不接 Provider 的私有协作合同和固定 LangGraph topology，让 E2 能注入 C3/D4 adapters。不得实现读取、压缩、分析、草稿、HTTP route 或持久化。

## 唯一允许文件

- Create：`backend/app/runtime/stage08_collaboration_contracts.py`
- Create：`backend/app/agents/stage08_collaboration.py`
- Create：`backend/tests/unit/test_stage08_collaboration_contracts.py`
- Create：`backend/tests/unit/test_stage08_collaboration_graph.py`
- Create：`.superpowers/sdd/stage08-package-e-task-e1-report.md`

禁止修改 models、migrations、UoW、services、API、schemas、main、C3/D4 文件、Docker/configuration、Git state 或外部系统。

## 必须实现的合同

1. **Private command/state。** `AssistantQueryCommand`、private material/state 和 provider input 必须由仅内部 factory 产生；slots-only、不可 JSON/pickle、`repr` 不泄露 query、actor/employee/resource ID 或 payload。它们不是 API model，不得从 dict/model_construct 构造。
2. **固定 budget。** `CollaborationBudget` 只能接受准确固定值：graph depth `3`、parallel reads `3`、retrieval chunks `12`、wall `30_000ms`、provider `20_000ms`、retries `2`。任意 client override、负数、bool、超限或值漂移被拒绝。
3. **Provider port。** `ContextCompressor` 与 `AnalysisProvider` 是纯 internal protocol；`UnavailableContextCompressor`、`UnavailableAnalysisProvider` 不能进行网络调用，只返回严格 unavailable outcome。定义严格 `AnalysisDecision`：answer 最大 2000 chars、citation ordinals `1..12` 递增无重复、action 只 `read_only/draft_update/general_advice/deny`，draft intent 只能内部对象且没有 resource/tool/field/scope/authority carrier。
4. **Safe terminal view。** `AssistantQuerySafeView` frozen/strict/reconstructed validation，只允许 `status`、`answer`、安全 citation label+ordinal、degradation codes、可选 draft ID；拒绝 built/forged model 上的 extra fields，`repr`/exception 不得带 private carrier。E1 不生成真实 answer/draft。
5. **Topology only。** `Stage08CollaborationNodes` 注入十个 node callable：`plan_request`、三个 fan-out read marker、`fan_in`、`compress_group_context`、`analyse`、`policy_gate`、`materialize_draft`、`finalize`。`build_stage08_collaboration_graph(nodes)` 使用 `StateGraph`、固定 conditional state transition、确定性 fan-out/fan-in、`checkpointer=None`；无 Node 可访问 service/ORM/tool/provider key。Graph 正常运行仅使用 fake callbacks。
6. **Terminal grammar。** 唯一 terminal `completed/draft_pending/denied/failed/cancelled/timed_out`；终态不可转回 reading/analysing/policy。非终状态不可暴露为 safe API view。

## TDD 和验证

先写 RED，然后最小 GREEN。新增测试至少证明：

- private command/state/port input 不能由 client dict、pickle、json 或 spoofed constructed object 形成，`repr` 无 query/UUID；
- budget exact values和类型严格；
- provider unavailable 无 network/import；bad decision（ordinal 0/13/重复/未知 action/过长 answer/extra draft carrier）被拒绝；
- safe view built extra/private field、error/repr injection 拒绝；
- graph node 集合和边精确、无 checkpointer、fan-out 不超过 3、terminal mapping 和 cancellation path 正确；
- AST/static scan 没有 `requests/httpx/OpenAI/OpenRouter/Telegram/Redis/Milvus/sqlalchemy` import，也没有 `Stage08ToolGateway`、`Stage06PlatformUnitOfWork` 或 direct provider construction。

从 `backend`：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py
```

报告必须中文记录 RED/GREEN 命令、contract/topology、静态边界、无 database/API/provider/external action、跳过项和风险。不得关闭 E1/E2/Package E/Stage08；完成后等待独立复审。
