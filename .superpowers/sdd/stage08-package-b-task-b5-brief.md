# Stage08 Package B Task B5：PostgreSQL 生命周期证据与 Package B 收口记录

## Status 与授权

- Task status：ready for task-level TDD；本文件是实现前简报，不宣称 Package B 或 Stage08 已完成。
- Authority：`STAGE_08_SOURCE_OF_TRUTH.md`、`STAGE_08_PACKAGE_B_MEMORY_BDD_AND_ACCEPTANCE.md`、`2026-07-18-stage08-package-b-business-memory.md` 的 Task B5，以及已落地的 B1–B4 合同与服务。
- 用户已授权连续推进。本任务不改变既有 schema、API、权限或技术选型；若 RED 暴露必须修改这些边界的缺陷，停止实现并上报，而不是扩展范围。

## Goal 与范围

对 B1–B4 已实现的 Business Memory 路径补齐**真实 disposable local PostgreSQL** 的收口证据，并把证据、RED/GREEN 过程、未测项和风险写入审计友好的文档。验收只针对现有行为；不新增产品功能。

允许的代码变更仅为 `backend/tests/integration/test_stage08_memory_postgres.py`。仅当新 RED 明确揭示已存在的持久化缺陷时，才允许对现有 service/UoW/model 做最小修复，并须在报告中记录原因、影响和验证。不得新增 migration、schema、HTTP API、权限 action、Telegram/Provider/Redis/RAG/LangGraph 或外部调用。

## BDD 验收映射

| Requirement | B5 的 PostgreSQL 证据 |
| --- | --- |
| B-01 | 当前 Alembic 单 head；`stage08_memory_items` / `stage08_memory_extraction_candidates` 的 JSONB、canonical status、unique `(workspace,type,fingerprint)` 和 lifecycle/read index 真实数据库约束/目录证据。 |
| B-02 | confirmed record 仅产生 reference-only outbox；同一 event 的重复 materialize 幂等；workspace lock/并发路径不制造重复 Memory。outbox、audit、Memory 不含未授权 field value。 |
| B-03 | B4 group candidate 在 configured PostgreSQL 中仅接受安全 projection；binding/member/TTL 失效不提升也不读取；不持久化 chat/raw/user 载体。 |
| B-04 | 跨 workspace 拒绝；TTL、source 删除/撤权、admin revoke 均即时 fail closed，并记录 canonical lifecycle 状态；并发/锁证据不以 in-memory 替代。 |
| B-05 | 既有 API 403/409 和字段撤权读取拒绝的回归；审计序列化扫描不含 raw/chat/user/prompt/response sentinel；B4 list/revoke 生命周期安全边界回归。 |

## 真实 PostgreSQL 边界

- 仅使用已配置的 `DATABASE_URL` 指向的 disposable local PostgreSQL。测试只创建带随机后缀的 workspace/base/table/record/binding，并以测试事务/fixture 清理；不得打印或写入连接凭据。
- 若本机没有 configured disposable PostgreSQL，标明跳过原因；不得用 SQLite、mock 或 in-memory 结果替代 PostgreSQL 证据。
- 不调用 Telegram、OpenRouter/Provider、webhook、部署或任何远程外部系统。

## TDD：RED → GREEN

1. 先在 `test_stage08_memory_postgres.py` 写 B5 acceptance tests，覆盖 confirmed-record reference-only outbox 的并发/幂等与生命周期/权限字段漂移 fail-closed；运行其目标子集并记录真实 RED 原因。
2. 若 RED 指向缺陷，在既有 B1–B4 service/UoW/model 做最小修复；若测试只是既有行为已覆盖，必须补充一个能说明 B5 组合验收的独立断言，不能把“已有绿灯”误记为 RED。
3. 运行 B5 PostgreSQL 测试，再运行计划规定的 Package B module suite；记录完整命令、退出码、测试数、跳过原因及无外部调用事实。

## Planned Files

| 操作 | 文件 | 责任 |
| --- | --- | --- |
| Create | `.superpowers/sdd/stage08-package-b-task-b5-brief.md` | 本任务范围、BDD 映射、TDD 与边界。 |
| Modify | `backend/tests/integration/test_stage08_memory_postgres.py` | B5 真实 local PostgreSQL acceptance tests。 |
| Create | `project-docs/08-implementation/evidence/stage08-package-b-memory.md` | migration/约束/生命周期/安全扫描/命令证据。 |
| Create | `.superpowers/sdd/stage08-package-b-task-b5-report.md` | 实施、RED/GREEN、验证、未测与风险。 |
| Create | `.superpowers/sdd/stage08-package-b-task-b5-review-package.md` | 交给独立复审的范围和检查项。 |

## 明确不做

- 不把 Package B 或 Stage08 写为 completed，不改真源、阶段计划或进度账本；独立复审通过后由父任务决定收口状态。
- 不补齐生产部署、真实 LLM 评测、向量/RAG、Milvus、Telegram 收发或历史聊天读取。
- 不改变 B3 的 `memory_policy`、B4 的 `Decimal("0.85")` 门槛、HMAC identity token、已有 API contract、权限矩阵或数据保留规则。
- 不做全后端套件替代目标 Package B 回归；任何未运行测试准确列为未测。

