# Stage08 Package E / E1 实施报告

## Status

- Task：`E1 Private Collaboration Contracts 与 LangGraph Topology`
- Current Progress：实现与任务级验证已完成，等待 fresh independent review；本报告不关闭 E1、E2、Package E 或 Stage08。
- 数据与外部动作：未连接数据库、API、C3/D4 service、Tool Gateway、Redis、Milvus、Telegram、OpenRouter 或其他网络 Provider；没有真实外部写入。

## Changed files

- `backend/app/runtime/stage08_collaboration_contracts.py`
- `backend/app/agents/stage08_collaboration.py`
- `backend/tests/unit/test_stage08_collaboration_contracts.py`
- `backend/tests/unit/test_stage08_collaboration_graph.py`
- `.superpowers/sdd/stage08-package-e-task-e1-report.md`

## RED 证据

从 `backend` 执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
```

首次结果：测试收集阶段 `2 errors`，分别为缺少 `app.runtime.stage08_collaboration_contracts` 与 `app.agents.stage08_collaboration`。失败原因与 E1 尚未实现完全一致，不是测试拼写、fixture 或环境错误。

## GREEN 证据

从 `backend` 执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py
git diff --check -- app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
```

首轮结果：`30 passed in 0.57s`；reducer fail-closed 修复轮补充 6 项 graph tests 后为 `36 passed`；顺序 marker 密封修复再补 3 项负例后，最终新鲜复跑结果为 `39 passed in 0.58s`；`compileall` 与限定文件 `git diff --check` 均成功且无输出。

### Reducer fail-closed 修复轮

独立复审发现 reducer 可能以 OR 合并相互冲突的 draft policy，并静默折叠重复 read branch。修复前新增负例后，指定测试为 `3 failed, 33 passed`，失败精确覆盖：含 outcome 的同一对象重复 branch、false/true policy 冲突、不同非空 analysis 冲突；异终态负例因前一 analysis 断言先失败而未执行到。修复后全部 `36 passed`。

当前 reducer 只把 node wrapper 标记的“由精确 parent state 派生的单节点更新”视为顺序替换；真正并行合并时，重复 read branch、policy false/true、不同非空 digest/analysis/safe view 以及异终态全部 fail closed。零 read outcome 的原始同一 state 仍可作为 LangGraph root 调度 no-op，不破坏既有 topology。

第三轮复审进一步发现顺序 marker 可被普通构造。现已将 marker 改为 process-local sealed carrier：只有 `_sealed_node` 内部工厂持有 issuer，reducer 在顺序优化前验证 marker 精确类型、snapshot 类型、seal 及 parent/result sealed state。直接构造、`object.__new__` 空对象、错误 snapshot/seal 与 policy bypass marker 均拒绝。该边界是 Python 同进程的抗误用合同，不宣称构成可抵抗任意同解释器恶意代码的安全沙箱。

## Contract 实现

1. `AssistantQueryCommand`、`Stage08CollaborationState`、private material、provider input、draft intent 与临时 digest 均为 slots-only opaque carrier，只能经内部 factory 产生；没有 `__dict__`，pickle/JSON 失败，`repr` 不包含 query、actor、workspace/employee/record ID 或 payload。
2. 每个 private carrier 都持有 process-local seal；消费者重新验证具体 carrier、snapshot 类型与 seal，`object.__new__` 形成的伪对象不能进入 state 或 provider port。
3. `CollaborationBudget` 使用 strict/frozen/extra-forbid 固定 literal：depth `3`、parallel reads `3`、retrieval chunks `12`、wall `30_000ms`、provider `20_000ms`、retries `2`。漂移、负数与 bool 均拒绝。
4. `AnalysisDecision` 将 answer 限制为 1–2000 字符，拒绝 UUID；citation ordinal 只能是 `1..12`、严格递增且不重复；action 只允许 `read_only/draft_update/general_advice/deny`；draft intent 必须是 factory 产生的 opaque 对象。
5. `UnavailableContextCompressor` 与 `UnavailableAnalysisProvider` 只接受 sealed provider input、command 和重建后的固定 budget，并仅返回严格 unavailable outcome；模块未导入或构造任何网络 Provider。
6. `AssistantQuerySafeView` 与 citation 使用 strict/frozen/extra-forbid Pydantic contract；消费时深度重建并精确核对字段集合，拒绝通过 `model_construct` 后注入的额外/private 字段。safe view 只接受六个 terminal status，非终状态不能暴露。
7. terminal state 一旦形成，只允许保持同一 terminal，不允许转回 reading/analysing/policy 等非终态。

## LangGraph topology

- 固定注入十个 callable：`plan_request`、三个 read marker、`fan_in`、`compress_group_context`、`analyse`、`policy_gate`、`materialize_draft`、`finalize`。
- `plan_request` 后确定性 fan-out 到恰好三个 read marker；waiting edge 在三者完成后才进入 `fan_in`。
- read-only 路径为 `fan_in -> compress -> analyse -> policy -> finalize`；draft 请求只可从 `policy_gate` 进入 `materialize_draft -> finalize`。
- plan 阶段取消会跳过所有 read/action，只调用 `finalize`；后续 terminal 状态也通过固定 conditional edge 转到 `finalize`。
- 图显式 `compile(checkpointer=None)`。LangGraph 1.0.10 的 root channel 使用不可进入 node 的私有空 seed；所有 node wrapper 都在调用前后验证 sealed `Stage08CollaborationState`，公共 dict 无法进入图节点。

## 静态边界

测试用 AST 检查两个 production module 不导入 `requests`、`httpx`、`openai`、`redis`、`pymilvus`、`sqlalchemy` 或 `telegram`，也不引用 `Stage08ToolGateway`、`Stage06PlatformUnitOfWork`、`PostgresRetrievalProvider` 或 `OpenRouter`。E1 没有 ORM、数据库、API route、provider key、持久化、checkpoint 或外部动作入口。

## Skipped tests 与 remaining risks

- 按 E1 边界未运行 PostgreSQL/pgvector、API、C3/D4、Tool Gateway、真实 Provider、Telegram 或生产部署测试；这些属于 E2–E4、Package F 与部署阶段，不能计入 E1 通过证据。
- E1 的 node callback 目前只由 deterministic fake 实跑，尚未消费真实 C3/D4 opaque material，也不会生成真实 answer 或 draft。
- 当前实现需 fresh independent review；复审通过前不得宣布 E1 或 Package E 关闭。
- reducer 修复已完成任务级验证，但仍需 fresh independent review 确认并行与顺序更新区分没有引入新的 graph 路由回归。
- marker 密封修复仍需新的 fresh independent review；通过前不得关闭 E1。

## Temporary cleanup

- 没有创建临时数据库、容器、网络会话、测试数据或外部 artifact；无需 cleanup。
