# Stage08 Package E / E2 消费期修复后独立复审简报

仅允许新增 `.superpowers/sdd/stage08-package-e-task-e2-consumption-review-report.md`。不得改源码、测试、既有报告、数据库、Docker 或外部系统。

必须独立重跑 137 focused unit tests、三模块 compileall 与 disposable pgvector 17 integration tests。

必检：

- C3 后 mapping/binding/status/version/pair 漂移时，D4 完全不调用，不能消费旧 scope/evidence；无 group proof 的正常无 target C1 路径不应被误报。
- compressor input/call/outcome/digest 的异常、shape drift、forged model 均只产生 compression degradation，不能冒泡或泄漏。
- `general_advice` 从不调用 D4；target fail-closed、D4 search/render/safe exception 修复不回归。
- 无 private data/exception/provider error 进入 safe view/repr/持久化 sink；无 API/schema/migration/HTTP/Telegram/real Provider/Redis/Milvus/Tool Gateway 副作用。

中文报告输出 Critical/Important/Minor。只有 `0 Critical / 0 Important` 才建议关闭 E2；不得声称 E3/E4/API/LLM/部署已完成。
