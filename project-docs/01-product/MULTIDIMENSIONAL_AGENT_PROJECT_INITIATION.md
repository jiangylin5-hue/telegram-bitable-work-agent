# Multidimensional Table And Agent Project Initiation

## Migration Note

- Migrated into this project on 2026-07-04 from `D:\广告saas\project-docs\01-product\MULTIDIMENSIONAL_AGENT_PROJECT_INITIATION.md`.
- This document is retained as product background and scenario reference.
- Links and references to Stage 07, existing SaaS backend, `/api/employee-ops/...`, and old project source-of-truth files are historical context, not binding constraints for this new project.
- Historical wording that says AI only generates drafts is superseded by the current project rule: Agent can query authorized business data and, after human confirmation, execute through `execution_ticket` and controlled tools.
- For the new project boundary, see [Telegram 多维表格和工作智能体新项目产品简报](TELEGRAM_MULTIDIMENSIONAL_AGENT_NEW_PROJECT_BRIEF.md).

## Status

- Document status: proposal draft
- Proposed direction: Feishu Bitable-style multidimensional table + agent operating system
- Current active stage: none selected after Stage 07 local acceptance closure
- Related source of truth: [IMPLEMENTATION_SOURCE_OF_TRUTH.md](../00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md)
- Related product charter: [PROJECT_CHARTER.md](PROJECT_CHARTER.md)
- Related functional outline: [FUNCTIONAL_OUTLINE.md](FUNCTIONAL_OUTLINE.md)
- Last closed stage: [STAGE_07_EMPLOYEE_ACCOUNT_OPS_DESK.md](../03-stages/STAGE_07_EMPLOYEE_ACCOUNT_OPS_DESK.md)
- Document boundary: this document collects project initiation thinking and next-stage candidate scope. It does not switch Active Stage, change schema/API contracts, or authorize implementation.
- Current Progress: 2026-07-04 作为迁移背景文档保留，并补充当前项目的高权限 Agent 与受控执行边界覆盖旧口径。

## 1. Project Initiation Summary

本项目的新方向是：以飞书多维表格和多维表格智能体为模板，把广告代理商内部的客户服务、账户生产、下户、绑卡、充值、消耗观察、风险跟进和服务审计，统一到一个可视化、可权限控制、可由 AI 协助处理的业务系统中。

这个方向不是简单给现有 SaaS 后台增加一个聊天机器人，而是重新定义一线业务工作台：

- Telegram 作为客户、销售、生产和客服的自然沟通入口。
- 多维表格作为客户、账户、服务、充值、风险和审计的结构化业务底座。
- AI 智能体作为数字员工，负责消息整理、需求识别、服务草稿、任务分派、提醒、日报和证据解释。
- 现有 SaaS 后端保留为权限、状态机、受控执行、幂等和 execution log 底座。

立项目标不是让 AI 直接替代所有员工，而是先把员工从大量重复、散乱、跨浏览器的操作中解放出来。员工未来更专注于找客户、维护客户关系、处理异常和做最终确认；系统和智能体承担流程整理、执行编排和审计沉淀。

## 2. Why This Direction

当前真实业务痛点来自用户描述和 Stage 07 文档共同指向的几个事实：

- 员工每天围绕客户、Meta 广告账户、BM invite、绑卡、充值、余额消耗和风险状态工作。
- 这些工作过去容易散落在 BM、卡台、浏览器、表格和聊天记录中。
- 员工可能同时打开几十个浏览器，查找和执行效率低，状态容易混乱。
- 销售、客服和生产之间的交接如果只靠聊天消息，很难形成可追踪、可审计、可复用的业务记录。
- 真实 BM invite、card binding 和 recharge 不能由前端、LLM 或聊天机器人直接执行，必须保留后端受控执行边界和 execution log。

飞书多维表格的价值在于把“表格、数据库、视图、权限、自动化、AI”组合成轻量业务系统。我们要效仿的是这种机制，而不是只模仿 UI 外观。

## 3. Feishu Bitable Practice To Emulate

对齐飞书多维表格和智能体时，建议学习以下可验证产品机制：

| Feishu-style mechanism | Meaning for this project |
| --- | --- |
| 多表结构 | 客户、账户、服务、充值、风险、消息、任务、审计分别结构化，而不是只放一张大表 |
| 字段类型 | 金额、状态、人员、关联记录、附件、时间、单选、多选、公式和链接字段都有明确语义 |
| 多视图 | 同一批数据可以按表格、看板、日历、仪表盘、详情页和待办队列查看 |
| 关联记录 | 客户关联账户，账户关联服务记录，服务记录关联执行日志和 Telegram 消息 |
| 权限控制 | 谁能看、谁能改、谁能确认执行、谁能看敏感字段必须分层控制 |
| 自动化 | 状态变化触发提醒、分派、SLA 跟进、日报和异常升级 |
| AI 侧边栏/智能体 | AI 帮用户理解数据、生成草稿、提取信息、总结进展，但不绕过业务边界 |

本项目的对齐原则是：先效仿飞书“多维数据 + 多视图 + AI 协作”的成功模型，再结合广告代理商账户服务的安全边界落地。

## 4. Product Positioning

拟定产品定位：

广告代理商账户服务智能工作台。它把 Telegram 消息、多维业务表格、AI 数字员工和受控执行后台结合起来，帮助销售、客服、生产和管理者围绕 Meta 广告账户完成客户服务、账户生产、下户、绑卡、充值和风险跟进。

它不是：

- 通用投放 dashboard。
- 自动投放系统。
- 泛化广告创作工具。
- 单纯聊天机器人。
- 单纯 Excel/表格替代品。
- 允许 AI 直接执行真实资金或账户写入的 autopilot。

它是：

- 客户服务与账户生产的结构化工作台。
- 可视化业务数据库。
- Telegram 消息到服务请求的转化系统。
- AI 协助的数字员工系统。
- 可审计、可追踪、可权限控制的操作系统。

## 5. Confirmed Business Foundation

来自现有项目文档的已确认业务地基：

- 项目服务海外广告代理商内部员工。
- 当前核心 channel 是 Meta，不引入非 Meta channel。
- Stage 07 已完成客户列表、账户资产、服务记录三页 MVP。
- 当前后端已围绕 `/api/employee-ops/...` 建立 FastAPI、PostgreSQL、服务层、权限、幂等、audit 和 execution log 基线。
- 核心动作包括 `BM invite`、`card binding`、`recharge` 和 `spend/risk observation`。
- 真实写入必须经过后端 service、受控执行边界、幂等、安全检查和 execution log。
- Agent 不得绕过人工确认和受控执行边界；当前确认口径是 Agent 可通过授权工具查库和统计，并在人工确认后凭 `execution_ticket` 调用受控执行工具。

## 6. Proposed Future Role Model

现有 Stage 07 只有 `employee` 角色。用户现在提出的未来组织方式，可以作为下一阶段角色模型候选：

| Role | Proposed responsibility | Boundary |
| --- | --- | --- |
| Sales | 找客户、维护客户、在 Telegram 中收集客户需求、发起服务请求草稿 | 可看自己客户和服务进展，不默认拥有真实执行权限 |
| Customer Service | 回复客户、解释服务状态、跟进异常、维护客户体验 | 主要使用 AI 回复草稿和服务状态，不直接执行资金/账户写入 |
| Production/Ops | 处理账户生产、下户、绑卡、充值、异常状态和执行确认 | 可在授权范围内确认执行，仍受策略、额度和 execution log 约束 |
| Finance | 核对线下打款、充值金额、币种、收款状态和财务统计草稿 | 不能把线下打款记录直接等同于广告账户充值成功 |
| Manager/Admin | 配置权限、查看全局仪表盘、处理高风险升级和审计 | 可定义策略和审批规则，不绕过 execution log |
| AI Agent | 读取授权数据、整理消息、生成服务草稿、分派、提醒、汇总、解释证据；人工确认后通过受控工具执行 | 不裸调 provider，不绕过确认、权限、幂等和 execution log |

## 7. Core Business Scenarios

### Scenario A: Telegram Message To Service Draft

客户或销售在 Telegram 群里提出需求，例如下户、绑卡、充值或查询消耗。

AI 智能体读取授权群消息，识别客户、账户、服务类型、金额、邮箱、币种、上下文证据和缺失信息。系统生成服务请求草稿，关联原始 Telegram 消息和客户/账户记录。

员工不需要从聊天记录里手动复制信息到多个后台；多维表格里自动出现待确认草稿。

### Scenario B: Sales Creates Customer Request

销售负责找客户和维护客户关系。当客户提出账户服务需求时，销售只需要在 Telegram 或工作台中提交自然语言请求。

系统根据客户归属、客户状态、账户状态和历史服务记录生成结构化草稿。销售可以补充信息，但不需要直接打开 BM、卡台或多个浏览器执行操作。

### Scenario C: Production Handles Account Work

生产或运营人员进入待办视图，看到按客户、账户、服务类型、风险等级和 SLA 排列的任务。

对于 BM invite、card binding 和 recharge，生产人员确认后，由后端 service 自动校验权限、策略、幂等和执行条件。低风险任务可以确认后自动执行；高风险、缺权限、金额异常或配置缺失的任务进入 blocked 或人工复核。

### Scenario D: Recharge Flow With Collection Separation

客户线下打款后，系统先记录 collection evidence。这个记录不能自动代表已到账，也不能代表广告账户已经充值。

AI 可以生成充值草稿，财务或生产确认金额、币种、账户和收款状态后，后端受控 recharge service 执行充值。充值执行成功需要 execution log，余额成功还需要 readback。readback 失败必须显示为 `readback_failed`。

### Scenario E: Spend And Risk Observation

系统持续展示客户级和账户级余额、今日/昨日/7D spend、低余额、空户、封户、异常消耗、缺权限、数据延迟和 unknown 状态。

AI 可以每日生成风险摘要和待处理列表，但不能把 unknown 或 stale data 编造成 0，也不能无证据解释投放原因。

### Scenario F: Service Record And Audit

所有 BM invite、card binding、recharge 和风险跟进都进入服务记录。

服务记录用于说明发生了什么、谁发起、谁确认、是否执行、执行 ID 是什么、失败原因是什么、下一步是什么。服务记录页仍然是审计和查询入口，不是危险重试入口。

### Scenario G: Daily Operating Report

AI 每天自动生成面向不同角色的日报：

- 销售日报：客户跟进、待补资料、客户请求进度。
- 生产日报：待处理下户、绑卡、充值、失败任务、blocked 任务。
- 财务日报：收款记录、充值草稿、readback_failed、金额异常。
- 管理日报：全局待办、SLA、失败率、风险账户、员工负载。

## 8. Multidimensional Data Tables

第一版建议围绕这些业务表建模：

| Table | Purpose | Important relations |
| --- | --- | --- |
| `customers` | 客户主数据、负责人、状态、最近触达 | 关联账户、群、服务记录、销售 |
| `customer_groups` | Telegram 群绑定、群成员、客户关系 | 关联客户、消息、权限 |
| `messages` | Telegram 消息摘要、原文引用、发送人、识别结果 | 关联客户、草稿、服务记录 |
| `account_assets` | Meta 广告账户、余额、spend、状态、风险、BM 权限 | 关联客户、服务记录、卡资源 |
| `service_drafts` | AI 或员工生成的服务草稿 | 关联消息、客户、账户、确认人 |
| `service_records` | 已创建服务、状态、幂等键、执行状态 | 关联执行日志、audit timeline |
| `payment_profiles` | tokenized payment profile 和安全卡资源 | 关联客户、账户绑定记录 |
| `recharge_records` | 收款记录、充值执行、readback 状态 | 关联服务记录和执行日志 |
| `risk_events` | 低余额、封户、异常消耗、stale data | 关联账户和服务跟进 |
| `execution_logs` | 真实执行证据 | 关联 BM invite、绑卡、充值 |
| `ops_audit_events` | 权限、状态流转、安全拦截和审计 | 关联所有关键实体 |

这些表不是都必须第一阶段落库。立项阶段先确定业务对象和关系，后续实施再按阶段收敛。

## 9. Visual Views

对齐飞书多维表格的多视图能力，建议设计这些视图：

| View | Main user | Value |
| --- | --- | --- |
| 客户总表 | 销售、客服、管理 | 一眼看到客户、负责人、余额、风险、服务进度 |
| 账户资产表 | 生产、运营 | 围绕账户处理下户、绑卡、充值和风险 |
| 服务看板 | 销售、生产、客服 | 按 `draft`、`pending_confirmation`、`executing`、`blocked`、`failed`、`succeeded` 跟进任务 |
| 充值视图 | 财务、生产 | 分离线下收款、充值执行和余额回读 |
| 风险仪表盘 | 生产、管理 | 低余额、封户、异常消耗、数据延迟和 blocked 任务 |
| Telegram 收件箱 | 销售、客服、AI | 把群消息转成结构化请求和待办 |
| AI 草稿队列 | 生产、财务、管理 | 集中确认 AI 生成的操作草稿 |
| 审计视图 | 管理、运营 | 查看 execution log、audit timeline 和失败原因 |

## 10. AI Agent Scope

AI 智能体应优先承担这些工作：

- 读取授权 Telegram 消息和业务表数据。
- 从消息中抽取客户、账户、服务类型、金额、邮箱、币种和证据。
- 生成 BM invite、card binding、recharge、风险跟进和客户回复草稿。
- 提醒缺失信息，例如缺 account、缺金额、缺收款确认、缺 tokenized profile。
- 根据状态自动分派给销售、生产、财务或管理者。
- 生成日报、周报和异常摘要。
- 解释服务记录、失败原因、execution log 和 readback 状态。
- 发现重复请求并提示可能的 idempotency 命中。

AI 智能体不得承担这些工作：

- 不裸调 Meta、BM、卡台或充值 provider 写入。
- 不绕过 Tool Gateway、人工确认、`execution_ticket`、权限、策略、幂等和 execution log。
- 不绕过员工确认、权限、策略、幂等和 execution log。
- 不把没有 execution log 的动作说成已成功。
- 不把 unknown、stale data、missing permission 编造成确定事实。
- 不接触 raw card number、CVV、完整卡图或未脱敏支付凭证。
- 不对投放效果做超出现有证据的诊断承诺。

## 11. Confirmation And Execution Model

推荐执行模型：

```text
Telegram / Mini App message
-> AI extracts intent and evidence
-> service draft is created
-> authorized human confirms
-> backend service checks permission, policy, idempotency and safety
-> controlled executor / write_service executes when allowed
-> execution log and audit events are written
-> Telegram and table views show result
```

执行策略分级：

| Risk level | Suggested behavior |
| --- | --- |
| Low-risk and complete data | 授权员工确认后自动执行 |
| Missing data | 进入补资料状态，AI 提醒相关人员 |
| High amount or abnormal account | 进入人工复核或管理审批候选 |
| Missing permission or stale provider data | blocked，不执行真实写入 |
| Provider/card-platform unavailable | failed safely，记录服务状态和失败原因 |

## 12. Permission Model

多维表格系统必须有权限设置，建议至少包含五层：

| Layer | What it controls |
| --- | --- |
| Record permission | 谁能看哪些客户、账户、服务记录和 Telegram 群 |
| Action permission | 谁能创建草稿、确认执行、取消、复核、导出 |
| Field permission | 谁能看金额、卡资源、失败原因、execution ID、敏感备注 |
| View permission | 销售、生产、财务、管理看到不同视图 |
| Agent permission | AI 能读取哪些表、哪些群、哪些字段，能生成哪些类型草稿 |

第一版可以从当前 `employee_customer_scopes` 扩展，而不是一上来做复杂组织系统。关键是不要让 Telegram 群成员身份直接等同于系统权限。

## 13. Proposed MVP Scope

建议下一阶段 MVP 聚焦一个闭环：

```text
Telegram 群消息
-> AI 服务请求草稿
-> 多维表格可视化待办
-> 人工确认
-> 后端受控执行或 blocked
-> execution log / audit
-> Telegram 结果回传
```

第一阶段允许：

- Telegram 群绑定和消息只读接入。
- 客户、账户、服务记录与 Telegram 群的关联。
- AI 生成服务草稿。
- 草稿确认队列。
- 服务看板和基础多维表格视图。
- 针对 BM invite、card binding、recharge 的确认后受控执行入口。
- 状态提醒、日报和异常摘要。

第一阶段不做：

- AI 绕过确认和受控工具直接执行真实写入。
- 完整客户门户。
- 完整财务账本、发票、对账单和结算。
- 非 Meta channel。
- 复杂多层组织架构。
- 投放自动优化或 AI 自动投放诊断。
- 保存 raw payment credential。

## 14. Success Metrics

业务成功指标建议：

- 销售从客户消息到服务草稿的平均时间明显下降。
- 生产人员不再需要从多处聊天和浏览器手动拼接客户、账户和服务信息。
- BM invite、card binding、recharge 请求 100% 进入服务记录。
- 真实成功声明 100% 有 `execution_id` 和 execution log。
- 重复请求通过 idempotency 被识别，不重复危险执行。
- 低余额、封户、异常消耗、readback_failed 等关键风险能自动进入提醒或看板。
- 每日销售、生产、财务和管理日报能由 AI 基于结构化数据生成。
- 客户回复草稿能减少客服重复沟通，但不越权承诺未完成事项。

## 15. Risks And Guardrails

| Risk | Guardrail |
| --- | --- |
| AI 越权执行真实操作 | Agent 可以生成草稿和调用授权工具；真实执行必须走后端 service、人工确认、`execution_ticket` 和 execution log |
| Telegram 群消息噪声大 | 先做只读接入、消息分类和人工确认，不自动把所有消息变任务 |
| 权限和客户归属混乱 | 以系统客户/账户 scope 为准，Telegram 群身份只是辅助线索 |
| 充值与收款混淆 | collection record 和 recharge execution 必须分开 |
| 服务重复提交 | 每个服务草稿和执行请求必须有 client request ID / idempotency key |
| 数据延迟造成误判 | 所有余额、spend 和风险指标带 freshness / last read time |
| 员工依赖 AI 编造结论 | AI 回复必须引用服务状态、execution log、readback 或明确标记缺失数据 |
| 产品重新膨胀 | 下一阶段只做消息到草稿到确认执行的一条闭环 |

## 16. Relationship With Existing SaaS Backend

现有 SaaS 后台不应废弃，而应从“一线主工作台”退到“执行与审计底座”：

- 现有 FastAPI backend 继续承载权限、幂等、状态机和受控执行。
- 现有 PostgreSQL 继续承载客户、账户、服务记录、审计和 execution log。
- 现有 `/app` 可以逐步演进为多维表格工作台或被 Telegram Mini App 复用。
- 新方向应先新增消息、草稿、视图和智能体层，不破坏 Stage 07 已验收闭环。

## 17. Open Questions

下一步立项评审需要确认：

1. 第一阶段是否以 Telegram 群消息接入作为主入口。
2. 第一阶段是否优先做充值流程，因为它同时涉及销售、财务、生产和执行日志。
3. 销售、客服、生产、财务和管理是否需要在第一版拆成真实系统角色，还是先用 scope + action permission 过渡。
4. Telegram Mini App 是否作为第一版多维表格主界面，还是先复用现有 Web `/app`。
5. AI 草稿是否只做 BM invite、card binding、recharge，还是也包含风险跟进和客户回复草稿。
6. 哪些动作允许“员工确认后自动执行”，哪些必须进入二次复核。
7. 是否需要把这份 proposal 升级为下一阶段 active stage file。

## 18. Recommended Next Step

建议把下一阶段命名为：

```text
Stage 08 - Multidimensional Agent Operations
```

推荐第一阶段目标：

```text
建立 Telegram 消息到服务请求草稿，再到多维表格确认队列，再到后端受控执行和审计回传的最小闭环。
```

推荐先做的业务切片：

```text
客户充值请求
-> Telegram 消息识别
-> recharge draft
-> 财务/生产确认
-> backend recharge service
-> execution log + readback
-> Telegram 回传
```

原因是充值流程最能体现当前业务价值，也最能验证多维表格、AI 智能体、权限、人工确认、受控执行和审计日志是否真正闭环。
