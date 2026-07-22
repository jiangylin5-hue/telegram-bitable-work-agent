# Stage08 Package E / E1 顺序更新标记密封修复简报

## 触发原因

第二次独立复审确认 `_SequentialStateUpdate(parent, result)` 可直接构造，攻击者可把旧 state 与伪造 marker 合并并跳过 fail-closed 冲突检查。E1 继续保持未关闭状态。

## 允许变更范围

- `backend/app/agents/stage08_collaboration.py`
- `backend/tests/unit/test_stage08_collaboration_graph.py`
- `.superpowers/sdd/stage08-package-e-task-e1-report.md`
- `.superpowers/sdd/stage08-package-e-task-e1-remediation-report.md`
- 新增 `.superpowers/sdd/stage08-package-e-task-e1-marker-seal-remediation-report.md`

禁止触碰其他源码、测试、数据库、Docker、API、Provider、网络、Telegram、Redis、Milvus、Tool Gateway、迁移或外部系统。

## 必须修复

1. 将 `_SequentialStateUpdate` 改为与 E1 私有 carrier 一致的 process-local anti-misuse sealed carrier：正常直接构造必须 `TypeError`；`object.__new__` 伪造、错误 snapshot、错误 issuer/seal 都必须在 reducer fail closed；`repr` 不可泄漏 parent/result，pickle/JSON 不可用。
2. 只能由 `_sealed_node` 内部的工厂产生合法 marker。reducer 接收 marker 时，必须验证具体类型、private snapshot 类型、seal、parent/result 都是有效 sealed state，之后才允许“`left is parent` 返回 result”的顺序更新优化。
3. 保持上次修复：并行 policy false/true、重复 branch（包括同对象）、不兼容 nonempty digest/analysis/safe view、异 terminal 均 fail closed；零 outcome 根 seed 的合法 no-op 与普通顺序节点更新仍能实际运行。
4. 将安全表述维持为 Python 同进程的抗误用边界，不能声称抵抗同一解释器内可运行任意恶意代码的安全沙箱；但模块使用者不得能以正常直接构造/API 伪造 marker。
5. 新增 RED 负例：直接构造 marker、`object.__new__` 伪造 marker、伪造 marker 尝试把 policy false 替换为 true，均被拒绝；保留原图完整路径与冲突测试。

## 验证

先测试应失败的 RED，再修复；在 `backend` 执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py
git diff --check -- app/agents/stage08_collaboration.py tests/unit/test_stage08_collaboration_graph.py
```

记录精确计数、无外部调用/写入。完成后不关闭 E1，等待新的独立复审。
