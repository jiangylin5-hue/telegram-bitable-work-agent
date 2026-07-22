# Stage08 Package E / E1 reducer fail-closed 修复简报

## 触发原因

独立复审报告确认 E1 存在 `1 Important`：`_merge_collaboration_state` 以 OR 合并冲突的 `policy_draft_allowed`，可能把 false/true 提升为 true；同一对象的重复 read branch 又被 identity 快速返回静默折叠。E1 不得关闭，必须修复、补 RED 负例并重新独立复审。

## 允许范围

- 修改 `backend/app/agents/stage08_collaboration.py`
- 修改 `backend/tests/unit/test_stage08_collaboration_graph.py`
- 修改 `.superpowers/sdd/stage08-package-e-task-e1-report.md`，补充修复后的 RED/GREEN 证据
- 新增 `.superpowers/sdd/stage08-package-e-task-e1-remediation-report.md`

禁止修改其他文件；禁止数据库、API、Provider、HTTP、Redis、Milvus、Telegram、Tool Gateway、Docker、迁移或外部写入。

## 必须达成的语义

1. reducer 在任何重复 read branch 上 fail closed，不能因两个 outcome 是同一对象而放过。为兼容 LangGraph 对“尚无 read outcome 的原始同一 state”根 seed 合并，可仅对零 outcome 的同一对象作无条件 no-op；一旦存在 branch，就必须检查并拒绝重复。
2. 任意 `policy_draft_allowed` false/true 冲突必须抛出 fail-closed 错误，不能 OR、不能选择 true；两边相同才可继续。
3. 并行不可合并字段 `compressed_digest`、`analysis_decision`、`safe_view` 的非空不一致值必须 fail closed，不能采用右侧优先。异终态应同样 fail closed（抛错或映射为不可执行终态），不得放行 draft。
4. 不得破坏固定十节点、三读分支、取消直达 `finalize`、read-only/draft 路由或 `checkpointer=None`。
5. 补最小 RED 测试至少覆盖：false/true policy 冲突、含 outcome 的同一对象重复 branch、两个不同对象但相同 branch、非空 safe view/analysis/digest 冲突之一，以及原始零 outcome state 被正常图调度。

## 必须执行

先新增/调整负例并运行 RED（修复前应失败）；再最小修复并在 `backend` 执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py
git diff --check -- app/agents/stage08_collaboration.py tests/unit/test_stage08_collaboration_graph.py
```

报告要记录 RED/GREEN 精确计数、变更、无外部调用/写入、剩余风险。完成后不得自行关闭 E1，等待 fresh independent review。
