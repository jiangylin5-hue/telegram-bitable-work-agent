# Stage08 Package B Task B4 设计报告

## 结论

**DONE（仅设计）**：已写出 B4 的实现前中文任务简报；未修改生产代码、测试、阶段真源、BDD、计划、schema、迁移或权限模型。

## 已阅读文件

- `AGENTS.md`
- `project-docs/08-implementation/STAGE_08_SOURCE_OF_TRUTH.md`
- `project-docs/08-implementation/STAGE_08_PACKAGE_B_MEMORY_BDD_AND_ACCEPTANCE.md`
- `project-docs/08-implementation/STAGE_08_DATA_API_SECURITY_CONTRACT.md`
- `project-docs/08-implementation/STAGE_08_IMPLEMENTATION_PLAN.md`
- `project-docs/08-implementation/STAGE_08_SDD.md`
- `docs/superpowers/plans/2026-07-18-stage08-package-b-business-memory.md`
- `backend/app/runtime/stage08_memory_contracts.py`
- `backend/app/models/stage08_memory.py`
- `backend/app/services/stage08_memory.py`
- `backend/app/services/stage06_platform.py`
- `backend/app/models/stage06_platform.py`
- `backend/app/services/stage06_digital_employees.py`
- `backend/app/models/telegram.py`
- `backend/app/services/telegram_ingestion.py`
- `backend/app/services/telegram_update_parser.py`
- `backend/app/schemas/telegram_webhook.py`
- `backend/app/api/routes/stage08_runtime.py`
- `backend/app/api/routes/stage06_runtime.py`
- `backend/app/api/deps.py`
- `backend/app/services/stage06_authorization.py`
- `backend/app/services/stage06_identity.py`
- `backend/app/main.py`

## 关键设计决定

1. 部署阈值固化为 `Decimal("0.85")`，不允许请求、环境变量或 workspace 设置覆盖；低于阈值完全不落库。
2. 候选写入仅是内部 service，不提供 candidate-create HTTP endpoint。外部 API 仅提供现有合同要求的 Memory list 与 manager revoke。
3. 群聊输入经一个无文本、短命的 source adapter。持久层使用内部 message UUID 与 `stage06-binding:<uuid>` opaque ref，绝不写入 chat ID、Telegram user ID 或消息原文。
4. 现有 candidate 没有 Memory FK，因此 candidate 和提升的 Memory 共享精确 safe fingerprint；accepted candidate 的撤销只通过该 fingerprint 查找并锁定关联 item，避免错误撤销。
5. B4 的安全 read 输出删除 ID、scope、source reference、field key 与 group ref；只返回 type/status/version/已许可 payload/TTL。
6. 使用既有 `workspace.read` 与 `member.manage`，不创建 permission action 或 role。路由错误依照 Runtime 的 redacted validation 模式，不回显请求值。
7. 有效 binding/member 被撤销时标 `revoked`；source record 无法解析或格式损坏标 `deleted`；TTL 标 `expired`。三者立即 fail closed。

## 文档冲突的处理

- Package-B implementation plan 曾把 B4 BDD 写进可修改文件清单；本任务明确不得修改其他文档，且 BDD 已与 Stage08 真源一致，因此没有修改 BDD。
- B2 现有实现对所有 `group_chat_ref` 返回 `None`，与已确认 B-03 不完整。B4 只对严格的 `telegram_message + group_candidate_projection + stage06-binding:<uuid>` 路径开放重验，未放宽成通用 Telegram Memory。
- BDD 要求来源删除/撤权即时拒绝，而 B2 泛化路径只有 `deleted`。brief 为 B4 给出明确的 `deleted/revoked/expired` 区分，优先遵从 Stage08 真源和 BDD。

## 未解决风险

- 当前历史 `Message` 模型/ingestion 已存在 raw text、caption、normalized text 留存。B4 不读取、不新增也不返回这些字段，但无法在不扩大到 Telegram ingestion retention/schema 改造的前提下消除该历史留存；需要独立确认才能治理。
- `Stage06TelegramBinding` 没有 version 与持久化 chat type。B4 将 group/supergroup 判断限制在入站短命 adapter，上线后的 revalidation 依赖 active binding/member；若需要可审计的群类型版本/删除墓碑，需要 schema/API 独立确认。
- 归一化 payload 的结构/长度/禁用 key 能阻止原文载体和直接字段泄漏，但无法从任意自然语言值数学证明其不是逐字复述。可信 extraction producer 的数据契约与后续 Provider 评测仍是未来门禁。
- 本任务没有 candidate list/review UI；candidate ID 的受控获得方式应在后续已授权 UI/运营流程设计中定义，不能用新增公开 candidate-write/list API 规避权限。

## 验证与清理

- 这是仅文档设计任务，未运行测试，也未触发 Telegram、Provider、LLM、Redis、网络或外部写入。
- 未创建临时数据或构建产物；未执行 git stage/commit/reset/checkout/clean。
