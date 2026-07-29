# Stage11 多 Agent 协调中间层架构

## Status

- Document status: active implementation source
- Scope: Stage10 durable event runtime 上的任务入口、能力注册、并行编排、受控动作与复杂业务验收
- Current Progress: 2026-07-29 已在 r76 部署 read-side 多 command 协调、版本化 registry、capability→skill 固定绑定、最小 checkpoint、Redis specialist pool、严格动作 provider、受控 Tool Gateway 与 required-failure sibling terminalization；r75 真实 48 case 已完成，运行/安全通过但检索和动作质量门槛未通过
- Workflow version: `stage11.coordination.v1`

## 1. 目标与非目标

Stage11 把现有“一个 Supervisor 派发一个表格分析 Specialist”的链路升级为可恢复、可观测、可扩展的协调中间层。一次用户请求可以被拆成多个受权限约束的 Specialist command；Supervisor 等待全部必需结果后再做 fan-in，并把写入、创建任务和提醒转换为待确认的安全对象。

本阶段必须实现：

1. 统一 `Task Gateway`：把 HTTP、Telegram 或 Mini App 的请求标准化为一个稳定任务意图。
2. 版本化 `Agent Registry`：capability、command、输入输出、风险等级、允许工具和失败策略不再散落在代码分支中。
3. 多 Specialist fan-out/fan-in：至少支持表格事实、风险分析、日报总结和受控动作提议四种 capability；一个 run 可以拥有多个 command。
4. `Tool Gateway`：Agent 不直接写业务表、不直接发 Telegram；只创建现有 `RecordChangeDraft`、`ExecutionTicket` 或 `NotificationRequest`。
5. 可恢复控制面：checkpoint 记录已完成、待完成、失败和下一动作，不保存 prompt、完整对话、原始记录或模型密钥。
6. 复杂中文真实评测：多表联合、汇总、写入草稿、任务、提醒、权限拒绝和部分失败均有可复现真值。

本阶段不做：

- 自动确认或执行高风险写入；
- 自动发送 Telegram 消息；
- 给 Specialist 数据库连接、ORM、SQL 或 provider key；
- 用 Agent 自由选择任意工具；
- 以聊天正文或模型自述作为任务成功证据。

## 2. 现状审计与复用结论

| 现有模块 | 可复用能力 | Stage11 缺口 |
| --- | --- | --- |
| `AgentWorkflowRun` | scope hash、deadline、lease、workflow version、结果引用 | 缺少多 child 完成条件的实现 |
| `AgentCommand` | 一个 run 多 command、父子关系、幂等键、状态 | dispatch 当前硬编码单 capability/command |
| `AgentRunCheckpoint` | 最小控制状态、authorization/data version hash | checkpoint 当前只表达一个 pending command |
| outbox + Redis Streams | 事务后发布、pending recovery、dead letter | 只有 tabular stream worker |
| Stage08 collaboration | 权限过滤检索、真实 LLM 分析、safe view、execution ticket | 没有作为多 Specialist 的统一 handler |
| Stage06 digital employee | create/update draft、notification request、audit | 没有由统一动作提议契约驱动 |

结论：不新增第二套 run/checkpoint/draft/audit 数据模型。Stage11 只补齐协调层和安全适配器，写入仍走既有领域服务。

## 3. 总体架构

```text
API / Telegram / Mini App
        |
        v
Task Gateway -- identity + workspace + employee + requested action
        |
        v
Task Planner -- deterministic plan policy, no permission expansion
        |
        v
Supervisor / Orchestrator
        |
        +--> Agent Registry + Capability Policy
        |
        +--> command A: platform.tabular.analyse
        +--> command B: platform.risk.analyse
        +--> command C: platform.daily.summarise
        +--> controlled adapter D: platform.action.propose
        |
        v
Durable commands -> outbox -> Redis Streams -> Specialist handlers
        |
        v
Validated safe artifacts + specialist terminal events
        |
        v
Supervisor fan-in / partial-failure policy
        |
        +--> read-only safe answer
        +--> Tool Gateway -> pending draft / execution ticket / notification request
        |
        v
SSE safe projection + audit evidence
```

`SSE` 只负责把已持久化事件投影给浏览器，不承担 Agent 间通信。Agent 间的事实来源是 PostgreSQL command/event/checkpoint；Redis Streams 是投递层；SSE 是只读展示层。

## 4. Task Gateway 与任务意图

### 4.1 标准任务

`TaskRequest` 至少包含：

- `workspace_id`、`employee_id`、`actor_user_id`；
- `intent`：`business_fact`、`risk_review`、`daily_summary`、`controlled_action`、`mixed`；
- `requested_action`：`read_only`、`draft_create`、`draft_update`、`task_create`、`reminder_request`；
- `query`；
- 可选 `target_record_id`；
- `idempotency_key`；
- 可选用户固定的 `skill_id`。

一个自然语言 query 可以解析为多个 `TaskObjective`。每个 objective 都有 `objective_id`、`intent`、`requested_action`、依赖 objective、必需 capability、可选 capability 和预期安全落点。Task Gateway 保留原始请求的一次幂等边界，Planner 输出一个 DAG；不能把多语义 query 强制折叠为单枚举值。

典型 DAG：

```text
读取今日逾期项目 ----+--> 风险排序 --> 日报段落
读取负责人 ----------+             |
读取最近沟通 ---------+             +--> 任务提议 --> Tool Gateway draft
                                    +--> 提醒提议 --> NotificationRequest
```

并行只用于没有数据依赖的读取。动作提议依赖事实与风险输出；物化动作依赖 Supervisor fan-in、权限重验和版本重验。

Task Gateway 只做规范化、边界校验和身份绑定，不调用 LLM 判断权限。权限证明由当前 workspace membership、digital employee scope、table/view/field permission、目标记录和请求动作共同计算。

### 4.2 计划规则

计划采用确定性映射，避免 LLM 任意生成可执行拓扑：

| Intent / action | 必需 Specialist | 可选 Specialist | 最终落点 |
| --- | --- | --- | --- |
| `business_fact/read_only` | tabular | risk（问题含风险/逾期/异常） | safe answer |
| `risk_review/read_only` | tabular + risk | none | risk answer |
| `daily_summary/read_only` | tabular + daily | risk | daily answer |
| `draft_create` / `draft_update` | tabular + action | risk | `RecordChangeDraft` |
| `task_create` | tabular + action | risk | task-table `RecordChangeDraft` |
| `reminder_request` | tabular + action | risk | `NotificationRequest`，默认待确认或 blocked |
| `mixed` | tabular + risk + action | daily | answer + controlled proposal |

对于多语义 query，Planner 合并各 objective 的 capability 集合并保留依赖边；同一 capability 可以服务多个 objective，但结果必须能回溯到对应 objective。某个 objective 被权限拒绝时，其他合法 objective 可以继续，最终结果必须逐项标出 `completed`、`proposed`、`denied` 或 `degraded`，不能用一个笼统的“已完成”覆盖部分失败。

用户显式选择的 skill 只能缩小或固定已授权能力，不能扩大 employee 的 scope 或跳过必需 Specialist。

## 5. 版本化 Agent Registry

每个定义包含：

- `capability_id` 与 `command_type`；
- `handler_version`；
- `allowed_actions`；
- `allowed_tools`；
- `output_kind`；
- `risk_level`；
- `required_by_default`；
- `can_propose_write` 与 `can_execute_write`；
- 输入/输出 schema 版本；
- deadline 和重试上限。

初始注册项：

| Capability | Command | Execution skill | Output | 写权限 |
| --- | --- | --- | --- | --- |
| `platform.tabular.analyse` | `analyse_visible_records` | `platform-tabular-analysis` | `assistant_safe_view` | 无 |
| `platform.risk.analyse` | `analyse_visible_risks` | `platform-tabular-analysis` | `risk_safe_view` | 无 |
| `platform.daily.summarise` | `summarise_visible_operations` | `platform-tabular-analysis` | `daily_safe_view` | 无 |
| `platform.action.propose` | `propose_controlled_action` | `platform-task` | `controlled_action_proposal` | 仅提议 |

Registry 是不可变、版本化配置。风险识别和日报不是伪造的新 UI skill，而是 `platform-tabular-analysis` 下的独立运行 capability；动作提议映射到真实公开 `platform-task` skill。用户选择 skill、Task Gateway 选择 capability、worker 使用 execution skill 三者由 registry 明确关联，不再由每个 specialist 对同一 query 二次猜测。内部 `platform-shared-policy` 与 `platform-approval` 仍由 Stage08 强制附加，不作为用户可选标签。

handler 只能获得它对应的权限过滤输入引用，不能获得其他 command 的私有输入或数据库服务。

### 5.1 当前部署边界

r75 公网 `/api/stage10/agent-runs` 已把 tabular/risk/daily 三个只读 capability 作为 durable command 经 PostgreSQL、outbox、Redis Streams、worker 和 checkpoint 完整执行。`platform.action.propose` 已进入 Task Gateway/Registry 计划，但出于本阶段不改变公开写入 API contract 的约束，HTTP admission 会把它从 read-worker command 集合中移除；真实验收 runner 在读结果完成后调用同一后端 action provider，再经 Tool Gateway 物化为待确认对象。

因此，本阶段已经证明动作 provider、权限白名单、ticket、draft/notification 持久化和零外发，但尚未把 action proposal 本身做成可断点恢复的第四类 Redis command，也没有把动作候选解析入口暴露给 UI。后续若要宣称“统一 durable action run”，必须新增并确认 action request contract、授权候选解析器与 action worker；不能把验收 runner 适配器冒充成公网运行链路。

## 6. command、artifact、event 契约

### 6.1 Command envelope

command envelope 只传：标识符、capability、command type、scope proof 引用、输入 artifact 引用、deadline 和幂等 hash。不得包含 prompt、完整记录、字段值、聊天正文或 token。

每个 child command 的幂等键：

```text
sha256(run_id + plan_version + capability_id + command_type + ordinal)
```

同一个 run 重放时不得创建重复 child。

### 6.2 Safe artifact

Specialist 输出先写 artifact，再写 `agent.completed`。artifact 必须：

- 与 run 的 `scope_hash` 一致；
- content hash 可验证；
- 只包含 permission-filtered safe view 或结构化动作提议；
- 通过 output schema 校验；
- 不含模型 prompt、provider response 原文、隐藏字段或未授权记录。

### 6.3 Checkpoint

fan-out 后 checkpoint 控制面：

```json
{
  "completed_command_ids": [],
  "pending_command_ids": ["...", "..."],
  "failed_command_ids": [],
  "retry_count": 0,
  "next_action": "wait_children"
}
```

fan-in 只依据 command 终态与验证后的 artifact 引用。每次恢复必须重新计算 actor、workspace、employee、field permission 和 data version；scope 变化则停止，不能带着旧 proof 继续。

## 7. 并发、fan-in 与失败语义

1. Supervisor 在一个事务中创建全部 child command 和 outbox rows，再写 `commands.dispatched` checkpoint。
2. 不同 capability 可以由不同 worker 并行消费；同一 capability 的 consumer group 保证竞争消费。
3. Specialist 只能把自己的 command 标记为 `completed`、`degraded` 或 `failed`，无权完成 run。
4. Supervisor 收到 child 终态后锁 run，读取所有计划内 command：
   - 仍有 pending/running：更新 checkpoint，继续等待；
   - 必需 child 失败：run 为 `failed`，同一事务把仍处于 queued/running 的 sibling 标记为 `failed`，不产生动作对象，也不让 terminal run 继续重试；
   - 可选 child 失败：run 为 `degraded`，允许以剩余已验证 artifact 生成安全结果；
   - 全部必需 child 成功：进入 `fan_in`；
   - scope/data version 漂移：`scope_revoked` 或受控重新规划，不盲目合并。
5. 只有 Supervisor 能写 `run.completed`、`run.degraded`、`run.failed`。

并发冲突依赖数据库 version + lease；超时 worker 不得覆盖新版本。Redis 重复投递依赖 command 幂等状态安全重放。

## 8. Tool Gateway 与受控动作

### 8.1 结构化动作提议

`ControlledActionProposal` 包含：

- `action_type`：`create_record`、`update_record`、`create_task`、`request_reminder`；
- `table_id` / `record_id` / `source_record_id`；
- `proposed_values`；
- reminder 的 channel、target、message 和 send policy；
- `reason`、`source_artifact_refs`、`expected_version`；
- `requires_confirmation=true`。

### 8.2 物化规则

- `create_record` 调用 `create_create_record_draft`；
- `update_record` 调用现有 update draft 领域服务；
- `create_task` 必须映射到任务表字段后调用 create draft；
- `request_reminder` 调用 `create_notification_request`，server mode 默认为 disabled；
- 物化后创建或关联 execution ticket，并写 audit；
- 权限不足、字段不可写、记录版本漂移、负责人不可见时不创建任何草稿/提醒，返回明确安全拒绝；
- Supervisor 和 Specialist 均不能调用 confirm/send。

“生成任务”成功的持久化证据是 pending task record draft；“提醒负责人”成功的证据是 pending/blocked notification request。模型文本说“已创建”不算成功。

## 9. 安全与隐私不变量

1. `effective_scope = employee_scope ∩ caller_scope ∩ channel_scope`。
2. 检索前过滤 workspace/base/table/view/field/record；输出后再做引用和字段白名单校验。
3. 对不存在与无权限资源采用一致的安全返回，防止枚举。
4. Action Specialist 只产出 proposal，Tool Gateway 独立重验权限。
5. checkpoint、event、Redis payload、SSE 不出现 query 正文、表格原始值、provider key 或隐藏字段。
6. 真实评测仅使用隔离的虚构数据；禁止发送 Telegram 或写 provider 侧数据。

## 10. 可观测性与验收证据

每个 run 至少可追踪：plan version、capability 列表、command 状态、重试次数、worker latency、LLM latency、artifact validation、fan-in 决策、draft/ticket/notification 引用、scope/data version 和最终状态。

验收必须同时证明：

- 两个以上 Specialist command 确实存在并独立终结；
- 第一个 child 完成时 run 不会提前完成；
- fan-in 仅使用验证后的 artifact；
- write-like case 只生成待确认对象；
- denied case 没有副作用；
- SSE 可断线续传且只展示 safe projection；
- PostgreSQL、Redis、OpenRouter 均为真实调用；
- 所有临时 fixture 可清理或被明确标记为保留测试资产。

## 11. 实施步骤

1. 先写 contract/registry/planner 单元测试，再实现版本化 registry 和 Task Gateway。
2. 写多 command、乱序完成、重复投递、必需/可选失败测试，再重构 Supervisor fan-out/fan-in。
3. 写动作提议、权限拒绝、幂等、零副作用测试，再实现 Tool Gateway 适配器。
4. 写复杂 fixture 与离线 truth scorer，再接真实 PostgreSQL、Redis、OpenRouter。
5. 完成后运行 focused、full backend、frontend、browser、staging smoke 与安全审计；一次性提交并更新 PR。
