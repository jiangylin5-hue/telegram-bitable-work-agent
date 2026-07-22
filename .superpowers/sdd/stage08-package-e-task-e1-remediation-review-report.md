# Stage08 Package E / E1 修复后独立复审报告

## 结论

- **不建议关闭 E1，需继续修复后再做 fresh independent review。**
- 分级：**0 Critical / 1 Important / 0 Minor**。
- 阻塞项是 E1 私有 LangGraph 根通道 reducer 的可伪造顺序更新标记；它可绕过刚修复的并行冲突检测，把拒绝草稿的状态替换为允许草稿的状态。

## 复审范围与边界

只读检查了 E1 的两个生产模块、两个单测、E1 实施/初审/修复报告及本次修复简报：

- `backend/app/runtime/stage08_collaboration_contracts.py`
- `backend/app/agents/stage08_collaboration.py`
- `backend/tests/unit/test_stage08_collaboration_contracts.py`
- `backend/tests/unit/test_stage08_collaboration_graph.py`
- `.superpowers/sdd/stage08-package-e-task-e1-report.md`
- `.superpowers/sdd/stage08-package-e-task-e1-review-report.md`
- `.superpowers/sdd/stage08-package-e-task-e1-remediation-brief.md`
- `.superpowers/sdd/stage08-package-e-task-e1-remediation-report.md`

本复审未修改生产代码、测试、既有报告、数据库、Docker 或任何外部系统；仅新增本报告。

## 独立复现结果

在 `backend` 目录实际执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py
git diff --check -- app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
```

结果：`36 passed in 0.57s`；`compileall` 成功且无输出；限定文件的 `git diff --check` 成功且无输出。

静态依赖扫描只命中 `stage08_collaboration.py:167` 的显式 `compile(checkpointer=None)`；未发现 DB/ORM、HTTP/网络、Provider、Redis、Milvus、Telegram、Tool Gateway、API 路由、密钥或外部写入依赖。

## 已确认通过的修复行为

- 直接将 `policy_draft_allowed=False` 与 `True` 作为并行状态合并时，reducer 会抛出 `collaboration_parallel_policy_conflict`，不再通过 OR 提升为允许。
- 同一对象已含 read outcome 时，以及不同对象重复同一 read branch 时，均会抛出 `collaboration_parallel_read_conflict`；零 outcome 的同一根状态仍可作为 LangGraph root seed no-op。
- 两个不同的非空 `compressed_digest`、`analysis_decision` 或 `safe_view` 会经过 `_require_compatible_optional` 做严格兼容检查；异 terminal status 会抛出 `collaboration_parallel_terminal_conflict`。
- 固定十节点、三路读取 fan-out/fan-in、取消直达 `finalize`、draft 仅在 policy 后进入 materialization、`checkpointer=None` 均保留，且对应单测通过。

## Important — `_SequentialStateUpdate` 可被公开构造，绕过 fail-closed reducer

`backend/app/agents/stage08_collaboration.py:59-75` 的 `_SequentialStateUpdate` 具有公开可调用的构造器和可读的 `parent`、`result` slot。虽然名称带前导下划线且未在 `__all__` 导出，但 Python 模块属性仍可由模块外精确导入和实例化；这不满足修复简报所要求的“parent/result marker 不可由公开构造伪造”。

`_merge_collaboration_state` 在第 213-218 行对该对象只验证其中两个 state carrier 有效，随后若 `left is right.parent` 便直接返回 `right.result`，不会执行第 226 行起的 policy、可选字段、terminal 或 read branch 冲突检查。因此伪造 marker 可跳过 fail-closed 合并。

本复审实际在内存中复现了以下等价命令（无网络、DB 或外部写入）：

```powershell
python -c "from app.agents.stage08_collaboration import _SequentialStateUpdate, _merge_collaboration_state; ...; forged=_SequentialStateUpdate(parent=denied,result=allowed); result=_merge_collaboration_state(denied,forged); print(F.policy_allows_draft(result))"
```

输出为：

```text
True
_SequentialStateUpdate
True True
```

其中 `denied` 是同一已分析 `draft_update` 命令的 `policy_draft_allowed=False` state，`allowed` 是 `True` state。正常的并行合并会拒绝该冲突，但公开构造 marker 后返回 `True`，即把拒绝状态替换为允许状态。

**修复建议：**将顺序更新 marker 也改为同一模块私有 issuer/seal 所保护的 opaque carrier，或让 reducer 仅接受由不可公开构造的封装路径产生的内部 token；同时新增负例，证明模块外无法构造 marker，且伪造 parent/result 不会绕过 policy/read/terminal/optional-field 的冲突检查。修复后需重新运行本报告的三条命令，并进行一次新的独立复审。

## 外部调用、清理与剩余风险

- 本复审仅运行本地单测、Python 编译、静态扫描和内存中的 reducer 复现；未连接 PostgreSQL/pgvector、Redis、Milvus、HTTP/OpenRouter、Telegram、Docker 或部署环境，未执行真实外部写入。
- 未创建业务数据、迁移、容器或网络 artifact；除本报告外无复审交付物需要清理。
- E2-E4、真实 Provider、API、PostgreSQL 与部署均未在本复审范围内，不能标记为完成。
