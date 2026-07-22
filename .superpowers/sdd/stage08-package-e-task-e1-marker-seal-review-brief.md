# Stage08 Package E / E1 marker seal 修复后独立复审简报

## 范围与写入限制

对 E1 第三轮 marker seal 修复做全新独立复审。严禁修改生产代码、测试、既有文档/报告、DB、Docker 或任何外部系统。唯一允许新增：

- `.superpowers/sdd/stage08-package-e-task-e1-marker-seal-review-report.md`

## 必跑命令

在 `backend` 目录独立执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py
git diff --check -- app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py
```

## 必检项

1. `_SequentialStateUpdate` 是否直接构造失败；`object.__new__`、错误 issuer/snapshot/seal 或伪造 parent/result 是否由 reducer fail closed；repr/JSON/pickle 是否不能携带 parent/result。
2. 标记只能来自受控 `_sealed_node` 内部生成路径；它允许合法顺序 state 更新，但不能作为普通并行冲突的豁免。
3. false/true `policy_draft_allowed`、含 outcome 的同对象重复 branch、不同对象重复 branch、不同非空 digest/analysis/safe view、异 terminal 均 fail closed；零 outcome root seed 和实际图的十节点/三路读取/取消/草稿路径仍正常。
4. 复核对 Python 边界的表述：这是防止普通模块使用者误造数据的同进程载体，不是抵抗同一解释器任意恶意代码（其可读取源代码或内省）的安全沙箱。不要把这项理论限制误报为当前 public construction 漏洞。
5. 静态扫描确保无 DB/ORM、HTTP、Provider、Redis、Milvus、Telegram、Tool Gateway、API、密钥、checkpoint 或外部调用/写入；`checkpointer=None` 保留。

## 结论规则

中文写审查报告，列明精确命令、计数、发现、外部调用/写入、清理、剩余风险。只有 `0 Critical / 0 Important` 才可建议关闭 E1；不可宣称 E2-E4、Package E、真实 Provider、API、PostgreSQL 或部署完成。
