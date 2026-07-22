# Stage08 Package E / E1 独立复审简报

## 审查目标

对 E1「私有协作契约与无 checkpoint LangGraph 拓扑」做独立复审。只在现有工作区执行只读检查、测试和创建下述审查报告；不得修改生产代码、测试、计划、文档、数据库、Docker 或任何外部系统。

## 可检查范围

- `backend/app/runtime/stage08_collaboration_contracts.py`
- `backend/app/agents/stage08_collaboration.py`
- `backend/tests/unit/test_stage08_collaboration_contracts.py`
- `backend/tests/unit/test_stage08_collaboration_graph.py`
- `.superpowers/sdd/stage08-package-e-task-e1-report.md`
- Package E 设计、契约、BDD、实施计划。

唯一允许新增的文件：

- `.superpowers/sdd/stage08-package-e-task-e1-review-report.md`

## 必须独立验证

在 `backend` 中执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py
```

另做源代码审查，至少回答：

1. `AssistantQueryCommand`、私有 state/material/provider input 是否不能由正常公开 API 构造、JSON/pickle 序列化或 `repr` 泄漏 query、身份、业务 ID、payload；伪造对象、`model_construct` 夹带字段是否被拒绝。
2. `CollaborationBudget` 是否严格固定在 E1 预算；bool/float/负数/超额或额外字段是否不可绕过。
3. 编译图是否正好十个允许节点，显式 `checkpointer=None`，取消是否直达 `finalize`，读取扇出是否恰好三支且汇合后才继续；read-only 与 draft 分支是否不能反向跳转。
4. reducer 是否在平行结果不一致、命令不一致、重复 branch 时 fail closed，且不会丢失终态或提升 `draft_allowed`。
5. 是否引入 DB/ORM、HTTP、Provider、Redis、Milvus、Telegram、Tool Gateway、API route、checkpoint、密钥或外部副作用。必要时做静态 import/references scan。
6. 仅限 Python 的 process-local 抗误用边界是否被如实表述：不要把可读源码内私有对象说成跨进程、对恶意本地代码的安全边界。

## 结论格式

报告中文撰写，包含审查范围、实际命令与输出摘要、关键负向审查、外部调用/写入情况、剩余风险和清理说明。按 `Critical` / `Important` / `Minor` 分级；只有 `0 Critical / 0 Important` 才可建议关闭 E1。不要把 E2-E4、Package E、真实 Provider、API、PostgreSQL 或部署说成已完成。
