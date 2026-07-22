# Stage08 Package E / E1 独立复审报告

## 结论

- **结论：不建议关闭 E1；需先修复后再做一次 fresh independent review。**
- 分级：**0 Critical / 1 Important / 1 Minor**。
- 阻塞原因不是外部系统风险：当前 E1 没有 API、数据库、Provider、Tool Gateway 或 Telegram 调用入口；阻塞的是其作为后续 `draft_update` 安全基础的并行 reducer 未能 fail closed。

## 审查范围

只读审查了下列 E1 范围文件及其设计、合约、BDD 和实施计划：

- `backend/app/runtime/stage08_collaboration_contracts.py`
- `backend/app/agents/stage08_collaboration.py`
- `backend/tests/unit/test_stage08_collaboration_contracts.py`
- `backend/tests/unit/test_stage08_collaboration_graph.py`
- `.superpowers/sdd/stage08-package-e-task-e1-report.md`
- `docs/superpowers/specs/2026-07-21-stage08-package-e-langgraph-collaboration-design.md`
- `project-docs/08-implementation/decisions/STAGE_08_E_LANGGRAPH_COLLABORATION_CONTRACT.md`
- `project-docs/08-implementation/STAGE_08_PACKAGE_E_COLLABORATION_BDD_AND_ACCEPTANCE.md`
- `docs/superpowers/plans/2026-07-21-stage08-package-e-langgraph-collaboration.md`

本复审未修改生产代码、测试、计划、数据库、Docker 或外部系统；仅新增本报告。

## 独立执行的验证

在 `backend` 目录执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py
```

结果：`32 passed in 0.49s`；`compileall` 无输出且成功。

另执行了限定模块的静态依赖扫描与 diff 空白检查：

```powershell
rg -n -i "sqlalchemy|requests|httpx|openai|redis|pymilvus|milvus|telegram|openrouter|toolgateway|stage08toolgateway|stage06platformunitofwork|postgresretrievalprovider|socket|urllib|aiohttp|boto|checkpoint|os\.environ|os\.getenv|subprocess" backend/app/runtime/stage08_collaboration_contracts.py backend/app/agents/stage08_collaboration.py
git diff --check -- backend/app/runtime/stage08_collaboration_contracts.py backend/app/agents/stage08_collaboration.py backend/tests/unit/test_stage08_collaboration_contracts.py backend/tests/unit/test_stage08_collaboration_graph.py
```

扫描命中仅为 `stage08_collaboration.py:149` 的显式 `checkpointer=None`；没有 DB/ORM、HTTP、Provider、Redis/Milvus、Telegram、Tool Gateway、API route、密钥或进程/网络依赖。`git diff --check` 成功。

## 已确认的正向证据

- 图实际编译为规定的十个节点，包含三条读取分支、汇合、`finalize -> END`，且显式 `compile(checkpointer=None)`；现有拓扑、取消、只读和草稿路径测试均通过。
- `AssistantQueryCommand`、私有 state/material/provider input、draft intent 与 digest 都是 slots-only opaque carrier。正常构造、`pickle`、JSON、`repr` 泄漏以及普通 `object.__new__` 伪造的负例已在独立运行的测试中通过。
- `CollaborationBudget` 是 strict/frozen/extra-forbid 的固定 literal 预算；bool、浮点、负数、越界和额外字段不能通过正常校验。
- `UnavailableContextCompressor` 与 `UnavailableAnalysisProvider` 只接受 sealed input 并返回严格 unavailable outcome；没有真实 Provider 或网络调用。
- 设计对安全边界的表述正确：opaque carrier 仅是 Python **process-local 抗误用边界**，不是针对能在同一解释器运行任意恶意代码者的安全沙箱。本复审未将它误报为跨进程或恶意本地代码防护。

## 发现

### Important — reducer 会在冲突合并时提升 `policy_draft_allowed`，且重复 branch 未 fail closed

**证据：** [`backend/app/agents/stage08_collaboration.py`](D:/telegram多维表格和工作智能体的开发/.worktrees/stage07-mini-app-ui/backend/app/agents/stage08_collaboration.py) 第 245–248 行将左右状态的 `policy_draft_allowed` 用逻辑 OR 合并；第 222–225 行只在同一 branch 的两个 outcome 不是同一对象时抛错。第 199–200 行还会对同一 state 对象直接返回。

使用公开的 factory 生成同一 command 的 analysed 状态后，分别生成 policy false/true 状态，再直接调用 reducer，实际输出为：

```text
conflicting_policy_merge= True
same_object_duplicate_branch_merge= 1
```

这违反 E1 复审简报中“并行结果不一致、命令不一致、重复 branch 均 fail closed，且不能提升 `draft_allowed`”的明确要求。虽然当前固定拓扑中的 `policy_gate` 不是设计上的 fan-out 节点，reducer 是整个私有状态根通道的合并函数；重试、错误的节点实现或未来并发调度一旦交给它两个不同 policy 结果，就可能把一个拒绝与一个允许合成为允许，并在后续路由进入 `materialize_draft`。同一对象被重复派发也不应被静默折叠。

**建议修复：**

1. 合并前逐项检测单写字段冲突：`policy_draft_allowed`、`compressed_digest`、`analysis_decision`、`safe_view` 和终态之间的非同值冲突都应拒绝或映射到不可执行的 fail-closed 终态，不能采用右侧优先或 OR。
2. 对任何重复 read branch 一律拒绝；不能以对象 identity 作为“不是重复”的例外。
3. 增加覆盖 conflict false/true、same-object duplicate branch、不同 terminal/safe view 冲突的 unit tests；修复后重跑本报告中的命令和独立复审。

当前没有 E3 draft materializer 或 API，所以该问题尚不能产生真实写入；但它会成为 E3 policy-before-draft 的安全前提，故为 Important 且阻塞 E1 关闭。

### Minor — 实施报告的测试计数与独立复验不一致

`stage08-package-e-task-e1-report.md` 记载 `30 passed in 0.57s`，而当前相同命令的独立结果是 `32 passed in 0.49s`。这不影响当前测试通过，但应在修复 Important 后同步更新实现报告，避免后续证据台账无法精确追溯。

## 外部调用、写入与清理

- 本复审只运行了本地 Python 单测、编译与静态扫描；未连接 PostgreSQL/pgvector、Redis、Milvus、HTTP、OpenRouter、Telegram 或任何部署环境。
- 未执行真实外部写入，未创建或修改数据库、容器、迁移和业务数据。
- 除本报告外未创建审查交付物；无需要清理的临时数据。

## 后续门槛

修复上述 Important 并补足负例后，重新执行 E1 两个指定命令和独立复审。只有获得 **0 Critical / 0 Important**，才建议关闭 E1 并进入 E2；不得因此将 E2–E4、真实 Provider、API、PostgreSQL、Telegram 或部署宣称为已完成。
