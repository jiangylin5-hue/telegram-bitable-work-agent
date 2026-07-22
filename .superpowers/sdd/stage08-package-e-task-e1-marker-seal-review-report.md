# Stage08 Package E / E1 marker seal 修复后独立复审报告

## 范围与结论

- 审查日期：2026-07-21
- 审查范围：`_SequentialStateUpdate` 的受控构造、seal 校验、reducer 的 fail-closed 行为，以及 E1 图的私有性边界。
- 审查写入：仅新增本报告；未修改生产代码、测试、既有文档、数据库、Docker 或外部系统。
- 结论：**0 Critical / 0 Important / 0 Minor**。可建议关闭 E1 的 marker seal 复审项；这不表示 E2--E4、Package E、真实 Provider、API、PostgreSQL 或部署已完成。

## 复现实测

在 `backend` 目录执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py
git diff --check -- app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
```

结果：`39 passed in 0.47s`；`compileall` 退出码为 0；指定文件的 `git diff --check` 退出码为 0。

额外以独立内联脚本复核了 marker 的实际边界，结果如下：

| 场景 | 实测结果 |
| --- | --- |
| 普通直接构造 `_SequentialStateUpdate(parent=..., result=...)` | 抛出 `TypeError`，拒绝。 |
| `object.__new__(_SequentialStateUpdate)` 裸对象进入 reducer | 抛出 `TypeError`，拒绝。 |
| 错误 issuer | 构造时抛出 `TypeError`，拒绝。 |
| 错误 snapshot 类型（用私有 issuer 仅为复核 reducer） | reducer 抛出 `TypeError: collaboration_sequential_update_unavailable`。 |
| 正确 snapshot 类型但错误 seal | reducer 抛出同一 `TypeError`。 |
| 伪造的 `parent=denied / result=allowed` | reducer 未接受 marker；正常状态合并亦抛出 `ValueError: collaboration_parallel_policy_conflict`。 |
| 由 `_sealed_node` 生成、且 `parent` 为同一对象的合法无变化节点 | reducer 仅接受这一精确顺序转换。 |
| `repr`、`json.dumps`、`pickle.dumps` | `repr` 不携带 parent/result；JSON 与 pickle 均拒绝序列化。 |

现有测试还覆盖：零 outcome root seed、10 个固定节点、3 路读取与 fan-in、取消路径、草稿路径、false/true policy 冲突、重复 branch、不同 analysis/safe view/digest 和不同 terminal 状态的 fail-closed 行为。

## 代码审查发现

1. marker 不在公开构造路径中：默认或错误 issuer 均不能构造；`__slots__`、禁止属性读取/写入、不可 pickle 和不暴露敏感 `repr` 一并降低误用和泄漏风险。
2. reducer 对 marker 使用精确类型、snapshot 类型和对象身份 seal 三重检查；即使手工以 `object.__new__` 制作外壳，或塞入形状正确但 seal 错误的 snapshot，也会在 reducer 前失败。
3. 合法 marker 仅由 `_sealed_node` 在节点返回已校验的私有 state 后创建；只有 reducer 左侧正好是该 marker 的 `parent` 对象时，才能作为顺序状态更新通过。否则回到普通并行合并规则，policy、read branch、analysis、digest、safe view 与 terminal 冲突均 fail closed。
4. 静态扫描与源码阅读确认 E1 两个模块没有 DB/ORM、HTTP、Provider、Redis、Milvus、Telegram、Tool Gateway、API、密钥或外部调用依赖；图继续显式 `compile(checkpointer=None)`。

## 威胁模型边界

这里的 seal 是**同一进程中防止普通模块调用者误造数据的受控边界**，而不是抵抗同一 Python 解释器中任意恶意代码的安全沙箱。后者能够读取私有模块变量、内省对象或直接调用内部函数；这属于本次设计和复审简报明确排除的威胁模型，不能误报为当前公开构造漏洞。

为验证 reducer 而手工导入私有 issuer 并传入错误 snapshot 时，carrier 外壳可以被构造，但它无法通过 reducer 的 snapshot/seal 校验；生产受控路径不会传递该 issuer。此行为符合“入口可被内部构造、消费点必须 fail closed”的实现目标。

## 外部状态、清理与剩余风险

- 外部调用/写入：无。未触发网络、数据库、Docker、Redis、Telegram、LLM/Provider、API 或部署。
- 清理：没有创建临时文件、容器或测试数据，无需清理。
- 剩余风险：E1 是进程内私有拓扑与契约地基；之后 E2 接入 C3/D4、E3 provider/policy/draft、E4 API/持久化时，必须分别重新做边界审查和集成验证，不能把本报告外推为后续能力的验收证据。
