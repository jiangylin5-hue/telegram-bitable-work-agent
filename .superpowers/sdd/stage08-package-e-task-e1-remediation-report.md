# Stage08 Package E / E1 reducer fail-closed 修复报告

## Status

- Scope：仅修复 E1 reducer 的冲突合并语义。
- Current Progress：修复与任务级验证完成，等待 fresh independent review；不关闭 E1、E2、Package E 或 Stage08。
- 外部副作用：无数据库、API、Provider、HTTP、Redis、Milvus、Telegram、Tool Gateway、Docker、迁移或外部写入。

## Changed files

- `backend/app/agents/stage08_collaboration.py`
- `backend/tests/unit/test_stage08_collaboration_graph.py`
- `.superpowers/sdd/stage08-package-e-task-e1-report.md`
- `.superpowers/sdd/stage08-package-e-task-e1-remediation-report.md`

## RED 证据

从 `backend` 执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
```

修复前结果：`3 failed, 33 passed in 0.79s`。

- 含 read outcome 的同一 state 被 reducer 静默按 identity 返回，未拒绝重复 branch。
- draft policy `false/true` 被 OR 提升为 `true`，未 fail closed。
- 两个不同非空 `AnalysisDecision` 被右侧优先选取，未 fail closed。
- 同一组测试还包含两个不同对象的相同 branch、异终态冲突与零 outcome root no-op；前者原实现已拒绝，异终态断言因同测试中的 analysis 断言先失败而未到达，零 outcome 调度保持通过。

## GREEN 实现

1. 同一对象只有在 `read_outcomes` 为空时才能作为 root seed/no-op 返回；一旦含 branch，重复出现即 `collaboration_parallel_read_conflict`。
2. `policy_draft_allowed` 两侧不一致立即 `collaboration_parallel_policy_conflict`，不再 OR 或选择 `true`。
3. 两侧非空且不一致的 `compressed_digest`、`analysis_decision`、`safe_view` 分别用固定 conflict code 拒绝。
4. 只要一侧为 terminal 而两侧 status 不同，即 `collaboration_parallel_terminal_conflict`；不再使用终态优先级放行。
5. 为区分合法单节点状态推进与真正并行合并，sealed node 返回 process-local `_SequentialStateUpdate(parent, result)`。仅当 reducer 当前左值就是该精确 parent 时执行顺序替换；并行兄弟分支的 parent 不匹配，仍进入上述严格冲突检查。
6. 固定十节点、三路 read fan-out/fan-in、取消直达 `finalize`、显式 policy 后 draft 路由和 `checkpointer=None` 未改变。

## GREEN 证据

从 `backend` 执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py
git diff --check -- app/agents/stage08_collaboration.py tests/unit/test_stage08_collaboration_graph.py
```

该轮结果为 `36 passed in 0.49s`。后续顺序 marker 密封修复补充 3 项负例后，最新新鲜复跑为 `39 passed in 0.58s`；`compileall` 与限定文件 `git diff --check` 均成功且无输出。marker 细节见 `stage08-package-e-task-e1-marker-seal-remediation-report.md`。

## Skipped tests 与 remaining risks

- 按修复简报未运行数据库、API、C3/D4、真实 Provider、Telegram 或部署测试；这些不属于 reducer 修复证据。
- `_SequentialStateUpdate` 已在后续修复中升级为 process-local sealed anti-misuse carrier，不进入 checkpoint、DTO、日志或持久化；仍需 fresh independent review 检查 LangGraph 并行调度与密封语义。
- 没有临时数据库、容器、测试数据或网络 artifact 需要清理。
