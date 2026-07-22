# Stage08 Package E / E2 独立复审简报

## 目的

独立审查 E2 受控 C3/D4 reads 与短命群压缩实现。只允许创建 `.superpowers/sdd/stage08-package-e-task-e2-review-report.md`；不得改动任何源码、测试、既有报告、数据库、Docker 或外部系统。

## 范围

- `backend/app/services/stage08_context_composition.py`
- `backend/app/services/stage08_collaboration.py`
- E2 涉及的 unit/integration tests、E1 contracts/graph、C3/D4 service 及 E2 实施报告/合同/BDD/计划。

## 必跑

1. E2 聚焦 unit：C3、D4 retrieval、E1 contracts/graph、E2 service。
2. `compileall` 三个 E2 生产模块。
3. 使用现有专用 disposable pgvector 环境运行 `tests/integration/test_stage08_retrieval_pgvector.py`；若环境不可用，只能报告阻塞，不能把 skip 计为通过。

## 必审性质

- C3 pending material 只能短命、opaque、不可 JSON/pickle/repr 泄漏；digest 后重读 current authority/window/source lineage，且不持久化。
- E2 只能从 sealed command/actor/current employee/member/binding 推导 scope；target/关联/撤权/源生命周期歧义 fail closed。
- C3/D4 material、query、digest、UUID、field、score、authority 不能进入 safe view/result repr/DB/audit/outbox/idempotency/log/checkpoint。
- compressor unavailable/异常/无效输出需安全降级，同时保留合法非群 C1 material；D4 failure 不能污染其他结果。
- 最多 3 reads；general advice 只在无业务材料和显式 intent 下发生。
- E1 no-checkpoint topology 不能被破坏；没有 HTTP/OpenRouter/Telegram/Redis/Milvus/Tool Gateway/API/migration/真实 provider 或外部写入。
- PostgreSQL member revoke case 没有残留源/chunk/outbox/idempotency/audit。

## 结论规则

用中文出具 `Critical`/`Important`/`Minor` 结论和实际命令计数。只有 `0 Critical / 0 Important` 可建议关闭 E2。不得将 E3/E4、Package E、真实 LLM、API、生产部署或 Telegram 视为完成。
