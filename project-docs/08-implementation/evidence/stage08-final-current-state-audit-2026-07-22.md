# Stage08 当前状态真实验收记录（2026-07-22）

## Status

- Evidence status: `executed`
- Scope: Stage08 A–F 的本地非生产验收；不把本记录表述为 Telegram 生产发送、公开 HTTPS 或 Stage07 UI 验收。
- External action: OpenRouter 真实分析调用已执行；Telegram、webhook、表格写入、通知与部署调用均未执行。
- Result: `PASS`。

## 本次可复现命令与结果

| 层级 | 命令范围 | 结果 |
| --- | --- | --- |
| Unit / API | `tests/unit/test_stage08_*.py` + `tests/api/test_stage08_*.py` | `796 passed in 50.69s` |
| PostgreSQL / pgvector | 7 个 Stage08 integration 模块，逐模块连接 disposable `pgvector/pg17` 本地容器 | `79 passed in 111.2s` |
| 真实 Provider | `python scripts/stage08_real_provider_evaluation.py`，通过受控 ignored env 文件 | `12/12 passed`；9 invoked / 9 completed / 8 usage-present；0 timeout |

PostgreSQL 组使用 `STAGE06_LOCAL_DATABASE_URL` 与 `STAGE08_RAG_DATABASE_URL` 指向同一个仅本地、可丢弃的 pgvector 数据库。测试组按模块顺序执行，避免复用 `public` schema 的旧 Stage07 fixture 在不同模块间互相清理；每一个模块均真实执行 Alembic、PostgreSQL 和 pgvector 路径。

## 真实 Provider R4 脱敏结论

本轮强制 `TELEGRAM_SEND_MODE=dry_run`、`PROVIDER_WRITE_MODE=disabled`、`NOTIFICATION_MODE=disabled`、不保存完整 prompt/response。12 个固定 synthetic case 全部通过，所有 case 均满足：`no_hidden_leak`、`citation_current`、`no_direct_write`、`no_external_side_effect`、`terminal_safe`、`fixture_fresh`。

| Case | Terminal | Provider | 结论 |
| --- | --- | --- | --- |
| `visible_fact` / `hidden_field` | `completed` | completed | 有当前可用引用的受限读取 |
| `revoked_scope` | `failed` | 未调用 | 权限前置拒绝 |
| `general_advice` | `completed` | completed | 无业务引用的通用建议 |
| `group_freshness` / `rag_lifecycle` | `completed` | completed | 当前群上下文 / RAG 引用 |
| `provider_unavailable` | `degraded` | 故障注入 | 安全降级 |
| `policy_deny` / `draft_pressure` | `denied` | completed | Policy Gate 拒绝 |
| `budget_cancel` | `cancelled` | 未调用 | 预算取消 |
| `safe_replay` | `draft_pending` | 未调用 | 仅生成待确认草稿 |
| `multilingual` | `completed` | completed | 多语言受限读取与引用 |

未记录密钥、模型原文请求/响应、token/cost 数值、业务 ID 或 provider request ID。

## Requirement ID 状态

本次 audit 以当前代码、既有包级证据与上述新鲜回归为准。下列 `accepted` 只代表 Stage08 本地非生产开发验收，不能替代 Stage09 公网入口、真实 Telegram 受控 smoke 或 Stage07 浏览器 UI 验收。

| Requirement | Status | 当前证据 |
| --- | --- | --- |
| A-01 – A-07 | `accepted` | 796 Unit/API；8 runtime PostgreSQL；R4 case isolation/timeout |
| B-01 – B-05 | `accepted` | 796 Unit/API；13 memory PostgreSQL；生命周期、冲突、outbox 并发 |
| C-01 – C-03 | `accepted` | 796 Unit/API；38 context/group/composition PostgreSQL；R4 group/general-advice |
| D-01 – D-04 | `accepted` | 796 Unit/API；17 pgvector PostgreSQL；R4 RAG lifecycle |
| E-01 – E-05 | `accepted` | 既有 Package E graph/API/PostgreSQL 证据；796 Unit/API；R4 policy/draft/degraded/cancel 路径 |
| F-01 – F-04 | `accepted` | 固定 12-case 真实 Provider R4；脱敏 telemetry；pgvector/Milvus 延后决策 |

## 本轮发现与修正

发现 `test_stage08_group_context_postgres.py` 仍断言迁移 head 为 `20260720_0031`，但当前 Stage08 知识索引迁移已将唯一 head 推进到 `20260720_0032`。先复现失败，再将该断言更新为 `0032`，单项真实 PostgreSQL 回归通过。未修改生产数据库结构或迁移内容。

首次把所有 integration 文件放在一个 pytest 进程中时，旧的共享 `public` schema fixture 产生 pgvector extension 的初始化竞争；独立模块顺序执行后，79 项真实数据库测试全部通过。该现象已记录为测试隔离限制，不作为产品运行时或服务器部署通过的替代证据。

## 非本记录范围

- 不验证公网 DNS、TLS、反向代理与生产发布回滚。
- 不验证真实 Telegram 群消息、真实用户业务数据或自动外部写入。
- 不验证 Stage07 Mini App 的浏览器视觉与端到端交互。
- 不执行或建议 Milvus 集群部署；当前仍以 PostgreSQL + pgvector 为准。
