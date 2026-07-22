# Stage08 Package E / E1 顺序 marker 密封修复报告

## Status

- Scope：仅修复 `_SequentialStateUpdate` 的正常构造伪造与 reducer bypass。
- Current Progress：实现和任务级验证完成，等待 fresh independent review；不关闭 E1、E2、Package E 或 Stage08。
- 边界定义：这是 Python 同进程模块的抗误用合同，不是抵抗同一解释器内任意恶意代码的安全沙箱。
- 外部副作用：无数据库、Docker、API、Provider、网络、Telegram、Redis、Milvus、Tool Gateway、迁移或外部写入。

## Changed files

- `backend/app/agents/stage08_collaboration.py`
- `backend/tests/unit/test_stage08_collaboration_graph.py`
- `.superpowers/sdd/stage08-package-e-task-e1-report.md`
- `.superpowers/sdd/stage08-package-e-task-e1-remediation-report.md`
- `.superpowers/sdd/stage08-package-e-task-e1-marker-seal-remediation-report.md`

## RED 证据

从 `backend` 执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
```

修复前结果：`3 failed, 36 passed in 0.71s`。

- `_SequentialStateUpdate(parent=..., result=...)` 普通直接构造没有抛错。
- `object.__new__` 形成的空 marker 导致非预期 `AttributeError`，没有用固定 fail-closed code 拒绝。
- 伪造 marker 可把 policy `false` state 顺序替换为 `true` state，绕开前一轮并行冲突校验。

## GREEN 实现

1. marker 改为 slots-only `_sealed_snapshot` carrier；`__new__` 要求精确 class 与 process-local issuer，普通直接构造固定抛出 `collaboration_sequential_update_unavailable`。
2. `_sealed_node` 是唯一 marker 生产入口，经内部工厂先验证 parent/result 均为有效 sealed state，再写入带 process-local seal 的精确 snapshot。
3. reducer 在执行 `left is parent -> result` 优化前，重验 marker 精确类型、snapshot 精确类型、seal identity，以及 parent/result 的 state seal。空 marker、错误 snapshot、错误 seal 和伪造 policy bypass 均用固定 TypeError fail closed。
4. marker 的 `repr` 只显示 opaque 标签，不含 parent/result；无 `__dict__`，pickle 和 JSON 序列化失败。
5. 前轮 reducer 规则保持：policy false/true、重复 branch、冲突 nonempty digest/analysis/safe view 与异 terminal 均拒绝；零 outcome root no-op、普通顺序更新、完整十节点、三读 fan-out、取消路径、draft policy gate 与 `checkpointer=None` 均继续通过。

## GREEN 证据

从 `backend` 执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py
git diff --check -- app/agents/stage08_collaboration.py tests/unit/test_stage08_collaboration_graph.py
```

最终新鲜复跑结果：`39 passed in 0.58s`；`compileall` 与限定文件 `git diff --check` 均成功且无输出。

## Skipped tests 与 remaining risks

- 本轮未运行数据库、API、C3/D4、真实 Provider、Telegram 或部署测试；这些不属于 marker 修复范围。
- Python 同进程如果允许任意恶意代码读取模块私有全局并调用底层反射能力，不属于本 anti-misuse carrier 的保证范围；本修复保证普通构造、公开 API 使用及错误 snapshot/seal 不能伪造 marker。
- 当前需要 fresh independent review；通过前不得关闭 E1。
- 无临时数据库、容器、网络会话或测试 artifact 需要清理。
