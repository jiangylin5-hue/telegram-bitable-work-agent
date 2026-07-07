# Stage 05 SDD

## Status

- Document status: active software design draft
- Scope: Stage 05 Agent graph、OpenRouter 主路径、多子 Agent、账户库存异常、草稿确认、受控发送、Bitable-like views 的软件设计
- Current Progress: 2026-07-07 Stage05 SDD created from confirmed scope. Local implementation has completed through Phase 05.6 Task11 and Task12 local readiness: runtime config, AgentRun evidence, Router/Supervisor workflow, Draft Agents, Account Inventory exception handling, Confirmation Branches, Customer Reply Send Request, Bitable-like Views, Local Acceptance Audit, staging-contract preflight, deployment config gate and redacted runtime summary command. Real Tencent Cloud staging, real OpenRouter, real Telegram allowlisted receipt and safety close remain pending explicit approval.

## 1. Design Overview

Stage 05 builds on Stage 04, which already proved:

- Real Telegram webhook ingress.
- Telegram customer binding.
- Bound `telegram_inbox` records.
- `intent_ready` placeholder.
- Redis/outbox worker runtime.
- Restricted allowlisted Telegram test send.
- Tencent Cloud staging deployment and safety close.

Stage 05 replaces the no-LLM placeholder with a real Agent workflow:

```text
messages.intent_status = intent_ready
-> Stage05 workflow service
-> LangGraph Supervisor
-> OpenRouter Message Intake Router
-> selected child agents
-> service draft persistence / account status update / manual review
-> confirmation and send/no-op evidence
-> views and audit
```

The design keeps business facts in PostgreSQL. LangGraph state is runtime orchestration state, not the source of truth. If LangGraph state and PostgreSQL disagree, PostgreSQL records and audit events win.

## 2. Existing Foundation To Reuse

| Existing area | Stage05 use |
| --- | --- |
| `messages` | Source Telegram records and intent state |
| `telegram_customer_bindings` | Customer identity context for bound messages |
| `service_drafts` | Core draft table for Agent outputs |
| `agent_runs` | Existing LLM/Agent evidence table, extended for Stage05 |
| `service_records` | Confirmation output for business drafts |
| `execution_logs` | No-op evidence for disabled provider paths |
| `telegram_send_requests` | Customer reply test send evidence |
| `account_inventory` | Inventory status and assignment facts |
| `account_status_events` | Account lifecycle/status evidence |
| `ops_audit_events` | Audit trail for every Agent and confirmation decision |
| `outbox_events` / Redis Streams | Runtime delivery and async worker boundary |
| `bitable_views.py` | Bitable-like operational view registry |

## 3. Runtime Components

### 3.0 Deferred Agent Skills / Capabilities Reference

Stage05 keeps an Agent skills/capabilities reference document inspired by the Feishu official `larksuite/cli` Skills structure, but does not implement a runtime capability registry before the main Stage05 workflow is complete and accepted.

Current Stage05 implementation should use direct Agent schemas, service policies and module-specific safety checks from the core Stage05 docs. The skills/capabilities document is retained as a high-similarity structural benchmark for the later post-acceptance Stage05 extension.

Deferred registry fields:

- trigger conditions;
- non-goals;
- required context;
- allowed tools;
- forbidden actions;
- output schema;
- Bitable endpoint;
- permission gate;
- confirmation gate;
- audit events;
- failure recovery.

This deferred item must not become a dynamic plugin marketplace, runtime skill installer or user-editable skill system in the main Stage05 delivery.

### 3.1 Stage05 Workflow Service

Responsibility:

- Load a single `Message` by id.
- Verify the message is bound and `intent_ready`.
- Set message to `agent_running`.
- Call Supervisor graph.
- Persist outputs through services, not direct ad hoc SQL.
- Set final message state to `routed`, `manual_review` or `agent_failed`.
- Record audit for all state transitions.

Non-goals:

- It does not call Telegram directly.
- It does not bypass confirmation.
- It does not write provider state.

### 3.2 Operations Supervisor Graph

Responsibility:

- Maintain `Stage05WorkflowState`.
- Call Message Intake Router.
- Decide selected child agents from Router intents.
- Execute child agents.
- Aggregate draft candidates and account inventory actions.
- Apply risk/low-confidence policy.
- Return a structured workflow result to the persistence service.

Graph shape:

```text
load_context
-> route_message
-> select_child_agents
-> run_child_agents
-> apply_policy
-> persist_results
-> finalize_message
```

Stage05 does not need a deep multi-level supervisor. One Supervisor plus child nodes is enough to prove the Agent pattern while keeping the stage shippable.

### 3.3 Message Intake Router

Responsibility:

- Build a compact, redacted LLM request.
- Include source message text, customer id, recent message summary and relevant inventory/service facts.
- Ask OpenRouter for strict JSON.
- Validate output schema.
- Return intent list and shared entities.

Router output:

```json
{
  "intents": [
    {
      "intent_type": "recharge",
      "confidence": 0.91,
      "entities": {"account_hint": "act_xxx", "amount": "100", "currency": "USD"},
      "risk_flags": [],
      "missing_fields": []
    }
  ],
  "overall_confidence": 0.88,
  "requires_manual_review": false,
  "manual_review_reasons": [],
  "redacted_summary": "Customer requested recharge and reply draft."
}
```

### 3.4 Child Draft Agents

Child agents are deterministic services around structured LLM/Router output. They may use simple validation rules and additional structured database context, but they do not independently call raw provider systems.

| Child agent | Output |
| --- | --- |
| Recharge Draft Agent | `service_drafts.draft_type = recharge` |
| Card Binding Draft Agent | `service_drafts.draft_type = card_binding` |
| BM Invite Draft Agent | `service_drafts.draft_type = bm_invite` |
| Customer Reply Draft Agent | `service_drafts.draft_type = customer_reply` |
| Account Inventory Agent | `account_assignment` draft, account status event or manual review |

### 3.5 Account Inventory Agent

This Agent is explicitly not an account production agent.

Allowed:

- Query account inventory.
- Identify candidate assignable accounts for draft suggestions.
- Generate `account_assignment` draft.
- Identify high-confidence risk/block/disabled status and mark it through `account_inventory` service.
- Write `account_status_events` and audit.
- Escalate ambiguous inventory state to manual review.

Forbidden:

- Create new inventory accounts.
- Import account production batches.
- Automatically recommend replacement after blocking an account.
- Automatically reserve replacement.
- Automatically redistribute account to a customer.
- Call Meta/BM/provider.

## 4. State Model

### 4.1 Message Intent Status

| State | Meaning | Allowed next |
| --- | --- | --- |
| `intent_ready` | Stage04 placeholder completed and message is ready for Agent | `agent_running` |
| `agent_running` | Stage05 graph is in progress | `routed`, `manual_review`, `agent_failed` |
| `routed` | One or more Stage05 outputs were persisted | terminal for this message unless manual re-run is requested |
| `manual_review` | Message needs human review before draft creation or action | terminal until manual action |
| `agent_failed` | Agent runtime/LLM/schema failure occurred | manual retry or review |

### 4.2 Service Draft Status

| Status | Meaning |
| --- | --- |
| `needs_more_info` | Intent is clear but required fields are missing |
| `pending_confirmation` | Draft is complete enough for human confirmation |
| `manual_review` | Draft/intent is too risky or ambiguous for normal confirmation |
| `confirmed` | Human confirmed the draft |
| `service_record_created` | Business draft produced no-op service evidence |
| `rejected` | Human rejected the draft |
| `blocked` | System blocked the draft due to policy or state |

### 4.3 Account Inventory Status

Stage05 uses existing and new status semantics:

| Status | Stage05 meaning |
| --- | --- |
| `unused` | Candidate inventory account, potentially assignable |
| `reserved` | Reserved by a separate confirmed process; Stage05 does not auto-reserve |
| `allocated` | Assigned to customer |
| `activated` | Activated account |
| `blocked` | High-confidence blocked/sealed account |
| `disabled` | Account disabled and not usable |
| `risk_controlled` | High-confidence risk-control signal; may require later operations |
| `recycled` | Returned/recycled by an explicit later process |
| `archived` | No longer active inventory |

Stage05 can automatically set only high-confidence abnormal states. It cannot automatically move an account to `reserved`, `allocated`, `activated`, `recycled` or `archived`.

## 5. Persistence And Transactions

For one message workflow:

1. Load message and verify current status.
2. Commit `agent_running` and audit before external LLM call.
3. Call OpenRouter outside long-lived DB transaction.
4. Validate LLM result.
5. Persist `agent_runs`.
6. Persist drafts/status events/manual review state in one transaction.
7. Commit final message state and audit.

This avoids holding DB locks while waiting for OpenRouter. If OpenRouter times out, message becomes `agent_failed` and can be retried manually.

## 6. Idempotency

| Operation | Idempotency key |
| --- | --- |
| Agent workflow for message | `agent-workflow:{message_id}:stage05` |
| Draft creation | `draft:{message_id}:{draft_type}:{intent_index}` |
| Account status auto-mark | `account-status:{account_inventory_id}:{after_status}:{message_id}` |
| Customer reply send request | `reply-send:{draft_id}` |
| Service/no-op evidence | `service:{draft_id}` and `noop-execution:{service_record_id}` |

Duplicate worker delivery must not create duplicate drafts, duplicate account status events, duplicate send requests or duplicate no-op evidence.

## 7. OpenRouter Integration

OpenRouter client must:

- Use OpenAI-compatible Chat Completions.
- Request JSON object output.
- Apply timeout.
- Return model name, request id, usage and latency.
- Never log API key.
- Convert HTTP/network/schema failures to safe error codes.

OpenRouter data persistence:

- Store structured output.
- Store redacted summary.
- Store model metadata.
- Store token/cost/latency if available.
- Do not expose full prompt or full raw response in Bitable-like views.

## 8. Error Handling

| Failure | Handling |
| --- | --- |
| Message not found | 404 or worker dead-letter with safe error |
| Message unbound | Do not run Stage05; keep/revert to manual review |
| Message not `intent_ready` | Stable conflict |
| OpenRouter key missing | Fail closed before external call |
| OpenRouter timeout | `agent_failed`, audit, no draft |
| Invalid JSON | `agent_failed`, audit `agent.output_invalid`, no draft |
| Low confidence | `manual_review`, no `pending_confirmation` draft |
| Clear missing fields | `needs_more_info` draft |
| High-confidence account blocked | Update inventory status, account status event, audit |
| Ambiguous account risk | `manual_review`, no status mutation |
| Confirm wrong state | Stable conflict, no mutation |
| Non-allowlisted reply target | Block send request, no Telegram call |

## 9. Observability

Every Stage05 run must be reconstructable from:

- `messages.trace_id`
- `agent_runs.trace_id`
- `service_drafts.trace_id`
- `account_status_events`
- `telegram_send_requests.trace_id`
- `service_records.trace_id`
- `execution_logs.trace_id`
- `ops_audit_events.trace_id`

The audit trail must identify the actor:

- `agent` for automated Agent output.
- `system` for worker/runtime transitions.
- `user` or internal actor id for confirmation.

## 10. Deployment Boundary

Stage05 uses the Stage04 Tencent Cloud staging environment. Runtime safety defaults:

- `TELEGRAM_SEND_MODE=dry_run`
- `PROVIDER_MODE=disabled`
- `LLM_ENABLED=false` unless Stage05 staging rehearsal explicitly enables it.
- test send allowlist absent except during confirmed rehearsal.

After rehearsal, staging must be returned to dry-run send mode and provider disabled.

