# Stage08 Package E / E1 修复后独立复审简报

## 目标与边界

复审 E1 reducer fail-closed 修复，确认前次 `1 Important` 已被真正消除。禁止修改生产代码、测试、既有报告、数据库、Docker 或外部系统。唯一允许新增：

- `.superpowers/sdd/stage08-package-e-task-e1-remediation-review-report.md`

审查范围为 E1 两个生产模块、两个测试、E1 实施/复审/修复报告及本修复简报。

## 必须独立复现

在 `backend` 下执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py
git diff --check -- app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
```

## 必检安全性质

1. false/true 的 `policy_draft_allowed` 并行合并必须 fail closed，不能以 OR/右侧优先/终态优先放行为 true。
2. 相同对象含有 read outcome 时，以及不同对象包含同一 read branch 时，都必须 fail closed；零 outcome 的原始同一 state 可为仅限 LangGraph root 调度的 no-op，但不可成为一般豁免。
3. 不同非空 `compressed_digest`、`analysis_decision`、`safe_view` 与异 terminal status 必须 fail closed；确认合法顺序节点更新不被错误拒绝。
4. parent/result marker 若用于区分顺序更新和并行结果，必须不可由公开构造/伪造输入绕过，且不泄漏到 repr/JSON/pickle/public DTO/checkpoint。
5. 十节点、三路读取、取消直达 `finalize`、draft 仅经 policy、`checkpointer=None` 仍成立。
6. 静态检查无 DB/ORM、HTTP/网络、Provider、Redis、Milvus、Telegram、Tool Gateway、API 路由、密钥和外部写入依赖。

## 结论

报告用中文，注明实际命令和精确计数、阻塞项、无外部调用/写入、剩余风险与清理。仅当 `0 Critical / 0 Important` 可建议关闭 E1；不能把 E2-E4、Package E、Provider、API、PostgreSQL 或部署标为完成。
