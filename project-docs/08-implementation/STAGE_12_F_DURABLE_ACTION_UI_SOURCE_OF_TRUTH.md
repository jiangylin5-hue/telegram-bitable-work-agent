# Stage12-F Durable Action 与确认 UI 实施真源

## Status

- Document status: active implementation source of truth
- Scope: Stage12-F only
- Current Progress: 2026-07-30 comprehensive audit reopened acceptance. Durable models, candidate components, encrypted payload, Action worker, Tool Gateway draft flow, API/SSE and Mini App have broad local evidence; the reproduced employee/table/actor-field reauthorization defect and missing independent kill switch were repaired by TDD. F remains `partial-local` because public admission still receives action/optional-target hints, Digital Employee `field_policy` is not intersected, real Redis is absent and the A–E chain is not connected. Not deployed; no production migration or 48 Case × 3 campaign.
- Approval basis: 用户已确认 Stage12 Quality Architecture V2、两张新增表、Action API/SSE、Tool Gateway 唯一写入边界及 A–F 顺序

## Goal

把 Stage12-B 的逻辑 `ActionSlot` 模板和 Stage12-C 的授权查询结果，展开为可恢复、可审计、必须人工确认的 durable action。Mini App 能逐项查看 Objective 和 Action，编辑允许字段并确认或拒绝；确认前不得修改业务 Record，也不得发送 Telegram。

## Fixed Scope

本阶段只实现以下 action canonical enum：

```text
record.create
record.update
task.create
reminder.request
```

新增且只新增：

- `agent_objective_runs`
- `agent_action_slots`
- `GET /api/stage10/agent-runs/{run_id}/objectives`
- `GET /api/stage10/agent-runs/{run_id}/actions`
- `GET /api/stage10/agent-runs/{run_id}/evidence/{evidence_id}`
- `POST /api/stage10/agent-runs/{run_id}/actions/{slot_id}/confirm`
- `POST /api/stage10/agent-runs/{run_id}/actions/{slot_id}/reject`
- Stage12 Objective/Action safe SSE projection
- Mini App Objective timeline 与 proposal review/edit/confirm/reject UI

不新增 action kind，不允许客户端提交 QueryPlan 或 AuthorizedCandidateSet，不替换现有权限引擎，不绕过 Stage08 Tool Gateway，不直接发送 Telegram。

## Reuse Decisions

源码审计确认以下现有能力继续作为唯一执行底座：

- `agent_workflow_runs`、`agent_commands`、`agent_artifacts`、`agent_events`、`agent_outbox_events`、`agent_private_inputs`
- `AgentControlledToolGateway` 到 `Stage08ToolGateway` 的受控 materialization
- `record_change_drafts`、`notification_requests` 与 Stage08 execution ticket
- Stage06/Stage07 的 record draft 确认、拒绝、字段权限、record version 与 audit 逻辑
- 现有 `AGENT_EVENT_RUNTIME_ENABLED`、workspace allowlist 与 embedded/Redis worker 模式

Stage12-F 不创建第二套业务写入服务。Action worker 只可调用 `AgentControlledToolGateway.materialize()`，其产物只能是 `pending_confirmation` draft 或受策略约束的 notification request；实际业务写入由用户确认 API 触发现有后端服务完成。

## Durable Contracts

### ObjectiveRun

`agent_objective_runs` 保存 Objective 的控制状态，不保存 Query、Evidence 正文或 Provider Prompt。

```text
id UUID PK
run_id UUID FK
objective_key varchar(80)
kind varchar(40)
required boolean
status queued|running|completed|proposed|denied|degraded|failed|cancelled
dependency_keys JSONB array of unique bounded strings
command_id UUID nullable FK
result_artifact_id UUID nullable FK
error_code varchar(120) nullable
created_at / updated_at
UNIQUE(run_id, objective_key)
INDEX(run_id, status)
```

### ActionSlotRun

`agent_action_slots` 保存安全控制字段和 opaque private payload ref；具体 assignments、提醒正文和敏感 target 不进入 `control_json`。

```text
id UUID PK
run_id UUID FK
objective_run_id UUID FK
slot_key varchar(80)
action_kind varchar(40)
status queued|running|proposed|pending_confirmation|confirmed|executed|denied|degraded|failed|rejected|conflicted|cancelled|expired
proposal_version integer >= 1
control_json JSONB
private_payload_ref varchar(200)
target_scope_hash char(64)
data_version_hash char(64) nullable
materialized_resource_id UUID nullable
execution_ticket_id UUID nullable
idempotency_key_hash char(64) UNIQUE
created_at / updated_at
INDEX(run_id, status)
INDEX(objective_run_id, status)
INDEX(updated_at, status)
```

`control_json` 只允许 action kind、confirmation policy、dependency/evidence opaque refs、editable field descriptors 和安全摘要。private payload 复用加密 private input/artifact 机制，并绑定 run、slot、scope hash、过期时间和 AAD。

## Action Expansion And Candidate Resolution

数据依赖动作必须按以下顺序展开：

```text
logical ActionSlot template
-> resolve referenced Structured Query Result
-> re-authorize workspace/employee/table/view/field scope
-> build AuthorizedCandidateSet
-> expand one or many concrete slots according to expansion_policy
-> persist objective/slot/command/outbox atomically
```

规则：

- candidate 只能来自当前授权数据和 Schema，不得来自 Evaluation Gold。
- 空候选：本 slot `denied`，不得影响同 Query 的其他合法 slot。
- 多候选且策略不允许展开：`denied` 或等待用户消歧，不让 Provider 猜测。
- 字段无权或 required field 缺失：`denied`。
- `record.update` 必须保存当前 record version proof。
- 多动作逐 slot 隔离；冲突 slot 不覆盖合法 task/reminder slot。

## Worker And Tool Gateway

Action command 使用独立 topic/consumer group，并沿用 `agent-command.v1` envelope、outbox publish、lease、retry、deadline 和 idempotency 规则。embedded 模式用于本地确定性测试；production-like 仍要求 Redis worker。

Worker 执行：

1. 校验 capability、slot、private payload、scope hash、deadline 和 idempotency。
2. 调用 Action Specialist 生成 typed proposal。
3. 运行 semantic validator；失败写稳定错误码，不 materialize。
4. 调用 `AgentControlledToolGateway.materialize()`。
5. 只持久化 pending draft 或 blocked/pending notification，记录 execution ticket/resource ref。
6. 写 `action.proposed`、`action.pending_confirmation` 或 `action.denied/degraded/conflicted` 事件。

确认前业务 Record mutation count 和 Telegram send count 必须均为 0。

## Confirm And Reject

Confirm request 必须包含：

- `proposal_version`
- `record_version`（`record.update` 必填）
- 用户编辑后的允许字段值；不得出现未授权字段
- 新的 `Idempotency-Key`

确认时重新验证 caller、workspace、employee、table/view/field scope、action allowlist、proposal version、record version 和当前 resource state。然后调用现有 draft/notification 确认服务；禁止在 API route 内直接写 Record 或调用 Telegram provider。

稳定响应：

- proposal/record version 漂移：`409 action_version_conflict`
- 已确认后的同 key 重放：返回同一 receipt，`replayed=true`
- 同 slot 不同 payload 复用 key：`409 idempotency_conflict`
- 权限漂移：`403 action_scope_changed`
- 已拒绝/过期/非法状态：`409 action_invalid_state`

Reject 只将 slot 和其 pending draft/notification 转入拒绝/取消安全终态并写 audit，不产生业务写入或外发。

## Safe API And SSE

所有 Objective/Action/Evidence 读取都重新授权。API 只返回 safe summary、状态、opaque refs、可编辑授权字段和版本；隐藏字段名、内部 target、Prompt、raw Provider response、stack trace 均不得返回。

SSE 在现有 `Last-Event-ID`、严格递增 sequence 和 terminal 规则上增加安全投影：

```text
plan.accepted
objective.queued
objective.started
objective.completed
objective.degraded
objective.denied
action.proposed
action.pending_confirmation
action.confirmed
action.executed
action.conflicted
run.completed
run.degraded
run.failed
```

前端 reducer 必须拒绝未知字段、跨 run、乱序、重复 event id 冲突和 terminal 后事件。

## Mini App

在现有 Collaboration Workbench 内新增：

- Objective 分项状态 timeline
- Action proposal card
- 仅对授权 editable fields 的编辑
- 明确的“确认后才写入/发送”提示
- confirm/reject 按钮、提交中状态和幂等重试
- version conflict、scope changed、expired 的恢复提示
- 桌面和 Telegram Mini App 响应式及键盘可访问性

前端不得根据自然语言推断完成状态，也不得把本地状态当成服务端确认 receipt。

## Acceptance Criteria

- migration 升降级、约束、索引和 Alembic single head 通过。
- Objective/Action repository、状态机、private payload、candidate resolver 单元测试通过。
- blind ActionSlot、空/多候选、字段无权、record version drift、局部冲突通过。
- durable command/outbox/embedded/Redis worker、retry/replay/recovery 通过。
- pending draft/blocked notification 持久化通过；确认前 Record mutation=0、Telegram send=0。
- objectives/actions/evidence/confirm/reject API 的授权、幂等、冲突和安全输出通过。
- SSE 顺序、恢复、Objective/Action 安全投影通过。
- Mini App reducer、API、proposal edit/confirm/reject 与浏览器点击验收通过。
- 隔离 workspace 真实 LLM Action proposal 验证通过；不做真实业务写入，不做 Telegram 发送。
- 更新 Stage12-F acceptance/evidence、`Current Progress`、handoff 和总验收索引。

## Out Of Scope

- 生产部署或生产 workspace 激活。
- 真实 Telegram 发送。
- 绕过确认的自动写入。
- 新 action kind、资金/账户操作或外部 Provider write。
- 48 Case × 3 全量真实模型评测；它属于 Stage12 最终总验收。
