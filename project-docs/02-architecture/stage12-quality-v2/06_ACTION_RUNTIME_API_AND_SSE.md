# Stage12 Action、Durable Runtime、API 与 SSE

> Parent index: [README.md](README.md)

## 12. ActionSlot 与 Durable Action

### 12.1 ActionSlot 契约

```json
{
  "slot_id": "act-01",
  "objective_id": "obj-03",
  "action_kind": "task.create",
  "target_selector": {
    "table_key": "tasks",
    "source_record_codes": ["MT-017"]
  },
  "assignments": {
    "title": "评审 Fjord 回滚方案",
    "source_work_item": "MT-017",
    "due_date": "2026-07-30"
  },
  "confirmation_policy": "required",
  "conflict_group": null
}
```

动作 canonical enum 固定为：

```text
record.create
record.update
task.create
reminder.request
```

`draft_create`、`draft_update` 只表示入口意图或确认策略，不再与 Provider action name 混用。

### 12.2 AuthorizedCandidateSet

后端根据 ActionSlot 和当前权限产生候选：

```text
allowed target tables
allowed record IDs/codes
allowed field keys/types/options
required fields
current record versions
allowed assignee/recipient identities
confirmation policy
```

Action Provider 只能从候选中选择；候选为空时返回明确 deny。评测不得直接从 Gold truth 构造 candidate。

### 12.3 Durable 流程

```text
ActionSlot parsed
-> candidate resolution
-> action command persisted
-> Redis action stream
-> Action Specialist proposal
-> proposal semantic validation
-> execution ticket
-> pending draft / blocked notification
-> SSE action.pending_confirmation
-> user review/edit/confirm
-> scope + version revalidation
-> backend service write/send
-> audit event
```

确认前不得修改业务 Record，也不得发送 Telegram。确认后执行必须使用新的幂等键，并重验字段权限和 record version；版本漂移返回 conflict，不自动覆盖。

## 13. Durable Runtime 与数据模型

### 13.1 复用现有对象

继续复用：

- `agent_workflow_runs`
- `agent_commands`
- `agent_run_checkpoints`
- `agent_artifacts`
- `agent_events`
- `agent_outbox_events`
- `agent_private_inputs`
- Stage08 execution ticket、draft、notification 和 audit 表

### 13.2 提议新增对象

为避免把 Objective 状态塞入 event text 或 checkpoint，提议新增：

#### `agent_objective_runs`

```text
id UUID PK
run_id UUID FK
objective_key varchar(80)
kind varchar(40)
required boolean
status varchar(32)
dependency_keys JSONB
command_id UUID nullable
result_artifact_id UUID nullable
error_code varchar(120) nullable
created_at / updated_at
UNIQUE(run_id, objective_key)
```

#### `agent_action_slots`

```text
id UUID PK
run_id UUID FK
objective_run_id UUID FK
slot_key varchar(80)
action_kind varchar(40)
status varchar(32)
control_json JSONB
private_payload_ref varchar(200)
target_scope_hash char(64)
data_version_hash char(64) nullable
idempotency_key_hash char(64) UNIQUE
created_at / updated_at
```

`control_json` 只保存 action kind、状态、确认策略和依赖引用；具体字段值、提醒正文和敏感 target 信息进入加密 private payload/artifact。

### 13.3 Checkpoint

Checkpoint 只新增以下安全控制字段：

```text
task_spec_version
completed_objective_keys
failed_objective_keys
pending_action_slot_keys
budget_remaining
authorization_hash
data_version_hash
```

不保存 Query、EvidenceBundle 正文、Provider Prompt 或聊天历史。

### 13.4 数据库约束与索引

提议 schema 必须具备：

- `agent_objective_runs` 对 `(run_id, objective_key)` 唯一。
- `status` 使用 CheckConstraint，允许 `queued/running/completed/proposed/denied/degraded/failed/cancelled`。
- `dependency_keys` 必须是 JSON array of unique string，由 repository 和 contract validator 双重检查。
- `agent_action_slots` 对 `idempotency_key_hash` 唯一，防止 worker retry 生成重复 draft。
- `target_scope_hash`、`data_version_hash` 使用 64 位 lowercase hex constraint。
- 索引 `(run_id,status)`、`(objective_run_id,status)`、`(updated_at,status)` 支持 fan-in 和 recovery scan。
- FK 默认禁止级联删除业务证据；run retention job 按审计策略显式清理。

Embedding V2 建议新增独立版本表或 additive column，不修改旧 8 维向量的语义：

```text
knowledge_embedding_profiles
  profile_id, model_revision, dimension, metric, status, created_at

knowledge_chunk_embeddings
  chunk_id, source_version, profile_id, embedding vector(N), content_hash
  UNIQUE(chunk_id, source_version, profile_id)
```

如果选定维度 `N` 后使用独立表，可以保留旧 Stage08 chunk 数据并按 profile 灰度切换。每个具体维度需要独立 pgvector column/index；禁止在同一索引中混合不同维度。

### 13.5 API Contract 提案

现有创建 run 请求保持兼容，新增可选 `contract_version="task-spec.v2"`。服务端仍以用户 Query 为入口，不允许客户端直接提交已授权 QueryPlan。

建议新增安全只读端点：

```text
GET /api/stage10/agent-runs/{run_id}/objectives
GET /api/stage10/agent-runs/{run_id}/actions
GET /api/stage10/agent-runs/{run_id}/evidence/{evidence_id}
POST /api/stage10/agent-runs/{run_id}/actions/{slot_id}/confirm
POST /api/stage10/agent-runs/{run_id}/actions/{slot_id}/reject
```

`objectives` 只返回 kind/status/safe summary；`actions` 返回可编辑 proposal 的授权字段；`evidence` 每次读取重新验证当前用户权限。Confirm request 必须包含 proposal version、record version 和新的 idempotency key。

确认返回：

```json
{
  "slot_id": "act-01",
  "status": "executing",
  "execution_ticket_id": "uuid",
  "replayed": false
}
```

版本冲突返回稳定 `409 action_version_conflict`，字段权限变化返回 `403 action_scope_changed`，不能使用统一 500。

### 13.6 SSE Event Contract

新增安全事件类型：

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

事件 payload 示例：

```json
{
  "event_id": "123",
  "event_type": "objective.completed",
  "run_id": "uuid",
  "objective_id": "obj-01",
  "capability": "platform.tabular.analyse",
  "status": "completed",
  "safe_summary": "已找到 2 个符合条件的项目",
  "artifact_ref": "opaque-safe-ref"
}
```

SSE 不返回原始 Prompt、隐藏字段、Provider raw response 或内部 stack trace。客户端用 `Last-Event-ID` 恢复；terminal event 之后同一 run 不再产生新的业务事件，只允许审计/清理事件进入内部流。


