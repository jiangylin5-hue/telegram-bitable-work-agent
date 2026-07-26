# Stage09 LLM 技能启动器设计

## Status

- **Status:** approved for implementation — 用户于 2026-07-26 明确确认
- **Date:** 2026-07-26
- **Scope:** 将 AI 对话工作台的技能标签从前端提示词预填器升级为由后端 skill registry 驱动、由权限交集裁剪、真实参与 OpenRouter/LangGraph 执行并写入审计的技能启动器。
- **Architecture gate:** 用户已确认本设计的 API contract、runtime 和 permission intersection 变更；不增加数据库列或 Alembic migration，不授权部署、外部发送或真实业务写入。
- **Depends on:** `STAGE_06_LARKSUITE_SKILLS_INTEGRATION_DESIGN.md`、`backend/app/agents/stage06_skills.py`、`backend/app/agents/stage06_skill_matching.py`、`STAGE_09_CODEX_STYLE_AI_CONVERSATION_DESIGN.md`。
- **Detailed implementation plan:** `docs/superpowers/plans/2026-07-26-stage09-llm-skill-launcher.md`

## 1. 问题定义

当前 `CollaborationWorkbench.tsx` 内的六个技能标签由前端静态数组定义。标签只能预填：

- `query`
- `intent`
- `requested_action`

请求体没有 `skill_id`，`AssistantQueryCommand` 没有技能执行配置，`OpenRouterStage08AnalysisProvider` 的 system/user prompt 也不知道用户选了哪个技能。换言之，现有标签不是后端 skill，只是 UI shortcut。它们存在三个问题：

1. 标签名称可能暗示后端尚未执行的能力，例如“风险识别”“长期记忆”或“生成跟进草稿”。
2. 浏览器自行决定 `intent/action`，但不能证明数字员工、调用人和当前记录真的允许对应能力。
3. AgentRun 和 audit 无法回答“本次由哪个 manifest、哪个主技能、哪些自动护栏约束了 LLM”。

目标不是让浏览器加载任意 `SKILL.md`，也不是建立一个新的通用 Agent 框架。目标是复用现有 Stage06 静态 manifest，把其中已经 active、能由 Stage08 真实执行、适合对用户公开的技能，映射为有限的工作台技能入口。

## 2. 设计原则

### 2.1 Skill 是后端能力，不是提示词皮肤

点击技能只选择一个稳定 `skill_id`。技能的唯一真源是此前按 `larksuite/cli` 能力组织抽象出的 Stage06 manifest registry；不得为工作台复制另一套同名 skill 定义。技能的 `source_skill`、用途、允许 intent、允许 action、所需上下文、输出契约、确认策略和辅助护栏均由服务端 manifest 解析。浏览器不得发送 prompt fragment、tool name、allowed action list 或 confirmation policy。

### 2.2 一个主技能，若干服务端辅助技能

每次请求最多有一个用户可见的 `primary_skill_id`。后端根据 manifest 和动作自动附加 supporting/guardrail skills：

```text
primary user-facing skill
-> required foundation/data skill
-> shared policy guardrail
-> approval guardrail when a write-like draft is requested
-> permission-filtered runtime profile
-> context reads / LLM analysis / controlled draft
```

用户不直接选择 `platform-shared-policy` 或 `platform-approval`。它们是安全边界，不是业务快捷操作。

### 2.3 可见不等于可执行

技能目录可以返回有限的已知技能及其安全状态，但只有满足以下交集时才返回 `enabled=true`：

```text
active manifest
∩ public launcher allowlist
∩ digital employee allowed_actions
∩ digital employee accessible_tables/views/field_policy
∩ current caller workspace membership and employee grant
∩ current record visibility/write proof when required
∩ current Telegram chat mapping when required
∩ runtime-supported intent/action/output contract
```

任何未知、缺失、歧义或已撤销状态均 fail closed。`target_record_id` 存在本身不等于可写。

### 2.4 不执行任意本地技能文件

Stage09 不根据客户端输入读取文件路径、插件目录或任意 `SKILL.md`，不动态 import 代码，不让 LLM 决定调用哪个 Python 函数。可执行技能来自版本化 Python registry 和固定公开 allowlist；manifest 只生成数据化 execution profile。

### 2.5 不新增持久化 schema

首版不增加 `digital_employees.skill_ids` 或新的 skill 表。可用技能从既有 `allowed_actions`、资源 scope、成员 grant 和运行时能力推导。实际选择写入已有 `AgentRun.input_summary`、`AgentRun.output_summary` 和 audit JSONB，因此不需要 Alembic migration。

若未来要求管理员逐员工配置独立 skill allowlist，再单独设计 schema 和管理 UI，不能在本次顺手加入。

## 3. 首批用户可见技能

首批只选取 Stage06 registry 中 `status=active`、能由现有 Stage08 读取/分析/草稿边界真实支持的技能。

| primary `skill_id` | UI 名称 | 首版动作 | 真实运行时关联 | 启用条件 |
| --- | --- | --- | --- | --- |
| `platform-base` | 查表问答 | `read_only`；满足严格写证明时可 `draft_update` | 表/视图/记录上下文；受控 record-change draft | 员工允许 `query` 或 `summarize`，至少一个已授权 active view；草稿另需当前记录、员工 `draft_update`、调用人字段写权限和员工字段策略交集 |
| `platform-tabular-analysis` | 汇总分析 | `read_only` | permission-filtered table view + retrieval；LLM 输出带安全引用 | 员工允许 `query` 或 `summarize`，至少一个已授权 active view |
| `platform-task` | 待办梳理 | `read_only`；满足严格写证明时可 `draft_update` | 从已授权表记录识别 work item；写入只生成待确认草稿 | 具备表读取能力；草稿条件同上，不支持直接创建/提交任务 |
| `platform-telegram-im` | 群聊上下文 | `read_only` | 只消费 Stage08 已脱敏、受 scope proof 约束的 group context | 当前用户在该 workspace 中只有一个有效 binding，且只有一个有效 business-context mapping；不支持直接发送 |

### 3.1 不作为首批标签的 active skills

| skill | 处理 | 原因 |
| --- | --- | --- |
| `platform-shared-policy` | 服务端始终自动附加 | 安全护栏，不是业务操作 |
| `platform-approval` | 仅 write-like draft 自动附加 | 用户不能通过点击审批技能自批或绕过确认 |
| `platform-contact` | 暂不公开 | Stage08 当前 analysis material 没有独立 contact-resolution read branch |
| `platform-file-import` | 保留在既有 Import UI | 文件选择、预览和 commit 有专门流程，不应伪装为聊天技能 |
| `platform-event` | 不公开 | 运行时基础设施能力 |
| `platform-tool-discovery` | 不公开 | 内部 capability discovery，不是最终用户动作 |
| `platform-skill-maker` | 不公开 | 开发/治理能力，不允许在业务工作台动态造技能 |

`risk_review` 和 `memory_lookup` 不再作为独立 skill tab：前者是 `platform-tabular-analysis` 的任务表述，后者是 Stage08 retrieval intent 而不是现有 active Stage06 skill。自由输入仍可由 server auto mode 使用 memory retrieval，但 UI 不把它冒充为独立 registry skill。

### 3.2 自动选择

Composer 保留“自动”模式，表达为 `skill_id=null`。自动模式不是让 LLM自由选工具，而是由后端 `build_stage06_skill_evidence` 和固定 launcher compatibility matrix 决定主技能；无法得到唯一可执行主技能时返回安全澄清/拒绝，不猜测。

显式技能和自动模式共用同一权限交集、execution profile、provider validation、draft-confirmation 和 audit 路径。

## 4. API Contract

### 4.1 技能目录

新增只读接口：

```http
GET /api/stage08/assistant/skills
    ?workspace_id={uuid}
    &employee_id={uuid}
    &target_record_id={uuid?}
```

身份继续使用现有 Telegram init data/cookie/header。服务端先执行 `digital_employee.invoke` workspace authorization，再校验 employee grant、employee/base status 和资源 scope。响应只暴露安全展示元数据：

```json
{
  "manifest_version": "stage06-larksuite-skills-v1",
  "default_selection": "auto",
  "skills": [
    {
      "skill_id": "platform-tabular-analysis",
      "label": "汇总分析",
      "description": "基于已授权表格与视图整理结论",
      "enabled": true,
      "disabled_reason": null,
      "supported_intents": ["business_fact", "mixed"],
      "supported_actions": ["read_only"],
      "confirmation_policy": "read_only"
    }
  ]
}
```

约束：

- `disabled_reason` 只能使用白名单枚举，例如 `context_required`、`read_scope_unavailable`、`write_scope_unavailable`、`chat_scope_unavailable`、`runtime_unsupported`。
- 不返回 manifest trigger、negative trigger、forbidden action 细节、内部资源 ID、field policy、permission rule、prompt 或 tool routing。
- 目录是瞬时 capability snapshot，不是 authority ticket。发送请求时必须重新校验。
- 目录不可用时前端不得回退成静态“可用技能”；只保留自由输入的自动模式，或整体显示安全不可用。

### 4.2 查询请求

为同步和 SSE 共用的 `AssistantQueryRequest` 增加：

```python
skill_id: StrictStr | None = Field(default=None, min_length=1, max_length=120)
```

兼容语义：

- 缺省或 `null`：server auto mode。
- 非空：必须属于公开 launcher allowlist 且当前可执行。
- 现有 `intent` 和 `requested_action` 保留，以减少兼容性破坏，但必须与 server profile 兼容；后端不信任前端映射。
- 不兼容组合在 LLM 调用前失败；同步路由返回脱敏 4xx，SSE 在流内返回白名单 terminal error。

兼容矩阵：

| skill | allowed intent | allowed action |
| --- | --- | --- |
| `platform-base` | `business_fact`, `mixed` | `read_only`, conditional `draft_update` |
| `platform-tabular-analysis` | `business_fact`, `mixed` | `read_only` |
| `platform-task` | `business_fact`, `mixed` | `read_only`, conditional `draft_update` |
| `platform-telegram-im` | `mixed` | `read_only` |
| `null` / auto | 现有四类 intent | 现有 action，但仍由 matcher/profile/权限约束 |

### 4.3 安全结果

`AssistantQuerySafeView` 增加一个安全、可回放的选择摘要：

```json
{
  "skill": {
    "skill_id": "platform-tabular-analysis",
    "label": "汇总分析",
    "manifest_version": "stage06-larksuite-skills-v1",
    "selection_mode": "explicit"
  }
}
```

`selection_mode` 只允许 `explicit|auto`。该摘要不包含 prompt、内部 supporting skills 或权限细节。同步 `/query`、SSE `result.safe_view` 和 idempotent replay 必须完全一致。

### 4.4 幂等语义

`_query_fingerprint` 增加：

- resolved `primary_skill_id`
- `selection_mode`
- `manifest_version`

同一 idempotency key 改变 skill、skill mode 或 manifest semantics 时必须冲突，不得重放旧语义结果。`query`、intent、action、record 和 actor hash 的现有指纹规则保持。

## 5. 后端运行时架构

### 5.1 新增边界对象

在 API prepare 阶段构建不可由客户端伪造的内部对象：

```text
ResolvedAssistantSkillProfile
├── manifest_version
├── primary_skill_id
├── source_skill
├── selection_mode
├── supporting_skill_ids
├── allowed_intents
├── allowed_provider_actions
├── required_context
├── output_contract
├── confirmation_policy
└── safe_label
```

该对象由内部 factory 签发并放入 `AssistantQueryCommand` 的 private snapshot。不得把客户端 JSON 直接反序列化成 profile。

`source_skill` 只用于内部溯源和审计，证明 profile 来自原 `larksuite/cli` capability mapping；不得进入前端 SafeView 或被当成真实 Feishu/Lark API 调用。公开 label/description 仍由受控 launcher presentation 提供。

### 5.2 解析顺序

```text
parse strict request
-> authorize workspace action
-> resolve current employee/member/resource scope
-> resolve explicit or auto primary skill
-> intersect manifest / employee / caller / record / chat / runtime
-> validate intent/action compatibility
-> build immutable execution profile
-> fingerprint including resolved skill semantics
-> idempotency begin/replay
-> create AssistantQueryCommand
-> run existing Stage08 graph
```

技能解析必须发生在 provider 调用前。幂等 reservation 失败或 stream 被关闭时，继续使用现有 rollback/discard 规则。

### 5.3 Supporting skills

首版固定组合：

| primary | supporting/guardrail |
| --- | --- |
| `platform-base` | `platform-shared-policy`; draft 时再加 `platform-approval` |
| `platform-tabular-analysis` | `platform-base`, `platform-shared-policy` |
| `platform-task` | `platform-base`, `platform-shared-policy`; draft 时再加 `platform-approval` |
| `platform-telegram-im` | `platform-base`, `platform-shared-policy` |

Supporting skills 由服务端产生，不进入 UI 选择，也不能扩大 primary skill 的权限。

### 5.4 对 context/read graph 的影响

技能必须改变真实运行时约束，不只是出现在 prompt：

- `platform-base`：要求至少一个可执行 table/view source；若 action 为 draft，再执行 record/field current proof。
- `platform-tabular-analysis`：只允许 table/retrieval evidence 和 `read_only` provider action。
- `platform-task`：只使用已授权表/检索证据；输出只能是分析或待确认 record-change draft，不宣称任务已创建。
- `platform-telegram-im`：要求 current group scope proof；proof 缺失或撤销时在 provider 前拒绝，不把普通 table context 冒充群聊上下文。
- auto：matcher 得到候选后再与 runtime support matrix 相交，不能选 planned/future/reference-only skill。

现有 Stage08 context budgets、parallel reads、redaction 和 citation validation 保持上限，不因技能选择扩大。

### 5.5 对 LLM provider 的影响

`OpenRouterStage08AnalysisProvider._build_prompt` 增加服务端 profile 的安全投影：

```json
{
  "skill_profile": {
    "primary_skill_id": "platform-tabular-analysis",
    "purpose": "permission-scoped tabular analysis",
    "allowed_provider_actions": ["read_only"],
    "output_contract": "analysis_answer_with_citations",
    "confirmation_policy": "read_only"
  }
}
```

System prompt 明确：

- 只能执行 profile 允许的动作。
- 只能使用已有编号 evidence。
- supporting guardrail 优先于用户文本。
- 不得宣称调用未在 profile 中的 tool。
- draft 仍只是 proposal，必须等待确认。

Provider 返回后继续执行现有 strict JSON schema、citation validation、action validation 和 policy gate，并额外校验 action 属于 `allowed_provider_actions`。prompt 中不包含原始 manifest triggers、权限策略或密钥。

## 6. 权限与草稿证明

### 6.1 Read-only skill

目录和发送时均验证：

1. workspace/base/employee active；
2. 调用人有且只有一个 active workspace member；
3. 调用人满足 employee `access_mode/member grant`；
4. employee actions 包含 `query` 或 `summarize`；
5. employee 至少一个 accessible view/table 仍 active 且属于 employee base；
6. actor 对该 view/record 的读取由现有 service projection 成功。

### 6.2 Draft-capable skill

目录只在能证明“当前上下文存在至少一个可写字段交集”时把 `draft_update` 放入 `supported_actions`：

```text
target record active and visible
AND employee belongs to same workspace/base
AND target table is in employee.accessible_tables
AND employee.allowed_actions contains draft_update
AND actor can write at least one active target field
AND employee field_policy allows at least one of those fields
AND confirmation policy requires a draft
```

发送后，LLM 给出具体 `field_key`，现有 `_lock_and_revalidate_draft_scope` 必须在锁内再次验证该具体字段。目录证明不能替代执行时证明。

### 6.3 Telegram skill

目录查询不得信任客户端 chat ID。后端从当前 identity、workspace member、Telegram binding 和唯一 active business-context mapping 派生 scope proof。歧义、多条 mapping、过期 binding 或不匹配 target record 均返回 `enabled=false`。

## 7. 审计与可观测性

不新增表。扩展现有安全 JSON summary：

```json
{
  "skill_manifest_version": "stage06-larksuite-skills-v1",
  "primary_skill_id": "platform-tabular-analysis",
  "skill_selection_mode": "explicit",
  "supporting_skill_ids": ["platform-base", "platform-shared-policy"],
  "skill_resolution": "allowed"
}
```

要求：

- `AgentRun.input_summary` 记录 manifest version、primary ID、selection mode，不记录 query 原文。
- `AgentRun.output_summary` 和 terminal audit 记录相同技能摘要、最终 status 和 action。
- `tool_calls` 只能记录稳定工具名和 aggregate status，不保存 record field values 或群聊原文。
- deny/degraded/failed 也记录已解析的安全技能摘要；在 skill 解析前失败则记录固定 reason code，不伪造选择。
- SSE 不新增暴露 supporting skills 的中间事件；最终只使用 `SafeView.skill`。

## 8. 前端设计

### 8.1 数据源

删除 `CollaborationWorkbench.tsx` 内静态 `SkillDefinition[]` 的能力真源地位。工作台打开、employee 变化或 target record 变化时查询技能目录，按 `(workspace, employee, record)` 作为 query key。

前端只维护：

- 选中的 `skill_id|null`
- 目录返回的安全 label/description/state
- 用户可编辑 query
- 与目录声明相容的 intent/action 表单值

### 8.2 展示

`SkillStrip` 展示：

- “自动”
- 服务端返回的四类精选技能
- disabled 项可见但不可点击，并显示短原因
- draft-capable 技能只有目录明确返回 `draft_update` 时才能进入草稿模式

点击标签会选择 `skill_id`、填入一条可编辑的任务建议并聚焦 Composer。标签本身不自动发送，不显示“已调用”。

发送后 timeline 的用户请求行显示安全技能 label；最终以 `result.safe_view.skill` 回校。如果显式请求与结果技能不一致，客户端 fail closed，不将结果标为完成。

### 8.3 失败与缓存

- skills API 失败：不使用旧静态技能兜底；显示“技能目录暂不可用”，自动模式是否可用以服务端兼容路径为准。
- employee/record 切换：清除已选 skill，取消旧目录请求，防止旧 scope 的 enabled 状态漂移到新上下文。
- 目录是展示快照；真正提交仍可能因权限撤销而失败，UI 必须把它展示为终态拒绝而不是自动降级到别的技能。

### 8.4 窄屏记录上下文入口

在 `max-width: 900px` 时，记录详情占据整个 viewport；Base 工具栏中的 `AI 对话` 因而不可触达。记录详情头部必须提供仅在窄屏可见的“在当前记录中打开 AI 对话”入口。它只复用现有 `openCollaboration(trigger)`：不关闭记录详情、不构造客户端 record scope、不改变 `skill_id`、权限、API 或持久化模型。这样 `currentRecordId` 仍来自已打开的、服务端投影的详情记录；关闭 Ledgerline 后焦点回到该入口。编辑状态下隐藏入口，避免把未保存的人类编辑与 AI 协作混在同一动作中。Ledgerline backdrop 必须是覆盖 viewport 的固定 modal layer，且 z-index 高于记录详情；不能依赖 portal 在 document flow 中的偶然顺序。

## 9. 实施步骤

### Step 1：契约 RED

修改/新增测试，证明：

- skills catalog 只返回 curated active skills；
- explicit/auto request 的 schema 和兼容矩阵；
- unknown/inactive/internal skill fail closed；
- permission、employee grant、record write proof、Telegram proof 的 enabled/disabled；
- sync/SSE/replay 返回相同 safe skill summary；
- fingerprint 区分 skill 和 manifest version。

### Step 2：服务端 registry adapter

新增 Stage09 launcher allowlist、safe presentation metadata、compatibility matrix 和 `ResolvedAssistantSkillProfile` factory。复用 Stage06 registry/matcher，不修改 manifest 存储模型。

### Step 3：目录接口

实现 `GET /api/stage08/assistant/skills`，复用现有 identity、authorization、employee scope 和 read/write permission helpers。所有 reason code 脱敏并白名单化。

### Step 4：查询链路

扩展 request、command、fingerprint、prepare、runtime 和 replay projection。同步与 SSE 必须共享同一 resolver，不得复制两套技能判断。

### Step 5：Provider 与 policy

把安全 execution profile 放入 provider input；增加 provider action/profile 交叉校验；确保 draft、deny、general advice 和 citation 既有规则不回归。

### Step 6：审计

在现有 AgentRun/audit JSON summary 中持久化安全技能摘要，验证失败/拒绝/成功均可追踪且无 query/evidence 泄露。

### Step 7：前端目录与 SkillStrip

先写 parser/type/query cache/reducer 测试，再删除静态能力真源，渲染 server catalog；实现 explicit/auto selection、scope change reset、disabled reasons 和 result skill 回校。

### Step 8：恢复 Task 4 UI 收尾

在动态技能接入后继续修复：

- `result -> finalizing -> done+EOF -> completed`
- explicit draft proof
- Ledgerline 宽屏 dialog
- focus trap/background isolation/focus restore
- reducer request ID/sequence 防御
- near-bottom auto follow

### Step 9：全量验收与审计

执行 backend focused/full tests、frontend focused/full tests、TypeScript、production build、deployment asset render tests、browser/Product Design QA、security audit、docs truth audit、temporary cleanup 和 `git diff --check`。全部通过后才按既定规则一次性 squash/commit。

## 10. Acceptance Criteria

1. 任一技能标签都来自服务端目录，并映射到一个 active Stage06 manifest；浏览器不再以静态数组宣称能力。
2. 显式技能真实进入 `AssistantQueryCommand`、LLM prompt profile、provider action validation、AgentRun 和 audit。
3. auto mode 只由确定性 matcher + runtime allowlist 选择，不让 LLM 自由提升能力。
4. 内部护栏 skill 自动附加且不可被用户取消；planned/future/reference-only/internal skills 不可执行。
5. employee/caller/resource/chat/field 任一权限撤销后，目录或发送时 fail closed。
6. `platform-telegram-im` 没有当前 chat proof 时不可用；`platform-task/base` 没有严格字段写证明时不提供 `draft_update`。
7. 同步、SSE 和 replay 的 SafeView skill summary 完全一致，幂等 key 不跨 skill/manifest 语义重放。
8. Provider 不能返回 profile 未允许的 action，不能宣称实际发送、写入或创建任务。
9. 审计只记录稳定技能元数据，不记录 query、prompt、原始 evidence、群聊原文或秘密。
10. 既有 Stage08 context/retrieval/draft-confirmation、SSE 安全状态和全量测试不回归。

## 11. Out Of Scope

- 动态安装或执行第三方 Codex skills/plugins；
- 从任意磁盘路径读取 `SKILL.md`；
- 数字员工独立 skill allowlist 的数据库配置；
- 联系人目录工具、文件导入、Telegram 发送或任务直接创建；
- 新 conversation history 表；
- schema migration；
- 生产部署、真实数据写入或外部发送。

## 12. Confirmation Required

实施需要用户明确确认以下整体变更：

1. 新增只读 skills catalog API。
2. `AssistantQueryRequest` 新增可选 `skill_id`。
3. `AssistantQuerySafeView` 新增安全 skill summary。
4. command/provider/idempotency/audit 纳入版本化 skill profile。
5. 首批公开技能固定为 `platform-base`、`platform-tabular-analysis`、`platform-task`、`platform-telegram-im`；其余 active skills 按本设计作为内部护栏、现有专用 UI 或暂不公开。
6. 首版不增加数据库 schema；员工技能可用性从既有 actions/scope/permissions 动态推导。

上述六项于 2026-07-26 获用户整体确认，进入 TDD 实施。该确认不授权数据库 schema 扩展、部署、外部发送或真实业务写入。
