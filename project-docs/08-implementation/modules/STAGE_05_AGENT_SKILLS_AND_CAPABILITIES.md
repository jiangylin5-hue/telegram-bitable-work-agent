# Stage 05 Agent Skills And Capabilities

## Status

- Document status: post-acceptance reference draft
- Scope: Stage05 post-acceptance Agent skill/capability registry reference, using `larksuite/cli` official Skills as a high-similarity structural benchmark while adapting to Telegram + self-hosted backend + Bitable-like workflow boundaries.
- Current Progress: 2026-07-08 Added the dedicated [Stage 05 LarkSuite Skills Reference Audit](STAGE_05_LARKSUITE_SKILLS_REFERENCE_AUDIT.md), ranking all 27 official `larksuite/cli` skills by project priority and defining which patterns should be adapted into later static Agent skill/capability work. This module remains documentation only and does not add runtime registry code.

## 1. Purpose

This document is not a main Stage05 implementation requirement before final acceptance. It is retained so the later Stage05 skills extension has a clear reference instead of rediscovering the structure from scratch.

When the post-acceptance skills extension starts, Stage05 should not treat Agent skills as vague prompt abilities. Each business Agent should have a structured skill/capability contract that defines:

- When the capability should be used.
- When it must not be used.
- Which context must be resolved first.
- Which backend tools it may call.
- Which actions are forbidden.
- Which output schema it must produce.
- Which Bitable-like table/view/status is the endpoint.
- Which permission and confirmation gates apply.
- Which audit events must be written.
- Which failure recovery path is expected.

This mirrors the strongest design lesson from the Feishu official `larksuite/cli` skills: a skill is not just a prompt. It is a routing rule, safety boundary, tool contract, recovery guide and reference index.

## 2. Benchmark Source

Reference repository:

- `larksuite/cli`: https://github.com/larksuite/cli
- Official Lark/Feishu CLI maintained by the LarkSuite team.
- MIT licensed.
- Provides many AI Agent Skills under `skills/`, including Base, shared auth/security, IM, docs, sheets and workflow-oriented skills.

Most valuable references for this project:

| Feishu CLI Skill | Why it matters for us |
| --- | --- |
| `lark-base` | Closest structural reference for Bitable table/field/record/view/workflow/role operations |
| `lark-shared` | Strong reference for identity, permission, scope, high-risk write and error recovery rules |
| `lark-skill-maker` | Reference for how to define reusable skills from API/tool capabilities |
| `lark-im` | Reference for messaging send/reply history semantics, but must be adapted to Telegram |
| `lark-task` / workflow skills | Reference for task handoff, status and structured operational output |
| `lark-sheets` / docs skills | Reference for field/value and document-like data safety patterns |

Detailed 27-skill priority, scenario, trigger and business-flow analysis lives in [Stage 05 LarkSuite Skills Reference Audit](STAGE_05_LARKSUITE_SKILLS_REFERENCE_AUDIT.md). This module keeps the project capability contract and later registry guidance; the audit document keeps the full official-skill comparison.

Do not copy the business implementation. Our runtime is not Feishu CLI. Our system is:

```text
Telegram
-> FastAPI backend
-> PostgreSQL / Redis
-> LangGraph / OpenRouter
-> Bitable-like tables/views/permissions
-> controlled services and audit
```

The Feishu CLI skills are the structural and safety benchmark, not the execution layer.

## 3. Adaptation Principle

Stage05 should **highly imitate structure** and **adapt execution**.

Imitate:

- `When to use` and `Do not use` sections.
- Required ID/context resolution before action.
- Quick routing tables.
- Identity and permission rules.
- Write-before-read requirements.
- High-risk confirmation gates.
- Error recovery tables.
- Reference indexes for complex schemas.
- Explicit non-goals and fallback paths.

Adapt:

- Feishu `base_token`, `table_id`, `record_id` become our `customer_id`, `message_id`, `service_draft_id`, `account_inventory_id`, `telegram_send_request_id`.
- Feishu `--as user/bot` becomes our `actor_type`, `actor_id`, `role`, `agent identity`, and backend permission snapshot.
- Feishu CLI commands become our Tool Gateway/service calls.
- Feishu Base views become our Bitable-like view registry.
- Feishu high-risk CLI confirmation becomes our human confirmation + backend service state check.
- Feishu scope recovery becomes our permission-denied audit and manual operator recovery path.

## 4. Skill Contract Template

Each Stage05 Agent capability should be defined with this shape:

```text
Skill ID:
Owning Agent:
When to use:
Do not use:
Required context:
Allowed tools:
Forbidden actions:
Output schema:
Bitable endpoint:
Permission gate:
Confirmation gate:
Idempotency key:
Audit events:
Failure recovery:
References:
```

This is intentionally close to the Feishu CLI skill style but uses project-specific backend concepts.

## 5. Stage05 Capability Registry

### 5.1 Operations Supervisor Agent

| Capability | When to use | Bitable endpoint |
| --- | --- | --- |
| `workflow_orchestration` | A bound Telegram message reaches `intent_ready` | `messages.intent_status`, `agent_runs`, audit |
| `child_agent_dispatch` | Router returns one or more actionable intents | `agent_runs.created_entity_refs` |
| `manual_review_gate` | Router confidence is low or policy blocks direct draft | `agent_review_queue` |
| `result_persistence_gate` | Child agents return drafts/status actions | `service_drafts`, `account_status_events`, audit |

Forbidden:

- Confirming drafts.
- Sending Telegram messages.
- Executing provider actions.
- Mutating account allocation directly.

### 5.2 Message Intake Router Agent

| Capability | When to use | Bitable endpoint |
| --- | --- | --- |
| `multi_intent_classification` | Message may include several business requests | `agent_runs.output_summary` |
| `entity_extraction` | Message contains account hints, amount, BM, card, reply request | `agent_runs.output_summary` and child draft payloads |
| `risk_and_missing_context_detection` | Message is ambiguous, risky or incomplete | `agent_review_queue`, `service_drafts.missing_fields` |
| `irrelevant_or_unknown_detection` | Message is not actionable business content | `messages.intent_status`, audit |

Required context:

- `message_id`
- bound `customer_id`
- normalized text or redacted text summary
- recent context summary if available

Forbidden:

- Inventing account ids or statuses.
- Treating Telegram sender as permission.
- Creating drafts directly without Supervisor persistence policy.

### 5.3 Account Inventory Agent

| Capability | When to use | Bitable endpoint |
| --- | --- | --- |
| `inventory_query` | Need available/current account status context | `account_inventory` view |
| `account_assignment_draft` | Customer asks for an account | `service_drafts.draft_type = account_assignment` |
| `account_risk_detection` | Message says account is blocked, disabled or risk-controlled | `account_status_events`, audit |
| `auto_mark_high_confidence_exception` | Account and abnormal state are both high-confidence | `account_inventory.inventory_status` |
| `ambiguous_inventory_review` | Account risk or ownership is unclear | `agent_review_queue` |

Required context:

- Existing `account_inventory_id` or resolvable account hint.
- Bound customer context.
- Source message id.
- Risk confidence and reason.

Forbidden:

- Account production.
- Account import.
- Replacement recommendation after automatic abnormal marking.
- Automatic reservation.
- Automatic assignment or redistribution.
- Provider calls.

### 5.4 Recharge Draft Agent

| Capability | When to use | Bitable endpoint |
| --- | --- | --- |
| `recharge_request_parsing` | Router identifies recharge intent | `service_drafts.draft_type = recharge` |
| `amount_currency_extraction` | Message includes amount/currency | draft payload |
| `missing_recharge_field_detection` | Account, amount or currency is missing | `service_drafts.status = needs_more_info` |
| `recharge_risk_flagging` | Account status or amount is risky | `risk_flags`, `manual_review` |

Forbidden:

- Calling recharge provider.
- Claiming recharge success.
- Creating execution ticket for real recharge in Stage05.

### 5.5 Card Binding Draft Agent

| Capability | When to use | Bitable endpoint |
| --- | --- | --- |
| `card_binding_request_parsing` | Router identifies card binding intent | `service_drafts.draft_type = card_binding` |
| `safe_payment_reference_detection` | Message references tokenized/allowed card profile | draft payload |
| `sensitive_card_data_block` | Raw card/CVV/full card data appears | `manual_review`, audit |
| `missing_binding_field_detection` | Account or payment profile is missing | `needs_more_info` |

Forbidden:

- Storing raw card number.
- Storing CVV.
- Calling card platform.
- Binding card in provider.

### 5.6 BM Invite Draft Agent

| Capability | When to use | Bitable endpoint |
| --- | --- | --- |
| `bm_invite_request_parsing` | Router identifies BM invite intent | `service_drafts.draft_type = bm_invite` |
| `invitee_hint_extraction` | Message contains email/contact/user hint | draft payload |
| `bm_context_missing_detection` | BM or invitee is missing | `needs_more_info` |
| `bm_invite_risk_flagging` | Invite target or customer ownership is ambiguous | `manual_review` |

Forbidden:

- Sending invite.
- Calling Meta/BM provider.
- Claiming invite succeeded.

### 5.7 Customer Reply Draft Agent

| Capability | When to use | Bitable endpoint |
| --- | --- | --- |
| `reply_draft_generation` | Router identifies customer_reply intent | `service_drafts.draft_type = customer_reply` |
| `safe_customer_language` | Reply must avoid overpromising or leaking internal state | draft payload |
| `confirmation_handoff` | Reply is ready for human confirmation | `pending_confirmation` |
| `reply_send_request_creation` | Human confirms reply | `telegram_send_requests` |

Forbidden:

- Sending without human confirmation.
- Sending to real customer chat in Stage05.
- Sending to customer group.
- Saying provider action succeeded without evidence.

## 6. Tool Gateway Mapping

Stage05 capabilities should map to backend service/tool names, not raw SQL.

| Capability family | Allowed service/tool pattern |
| --- | --- |
| Query message/customer context | `query_message_context`, `query_customer_context` |
| Query inventory | `query_account_inventory`, `query_customer_assigned_accounts` |
| Create draft | `create_service_draft` |
| Mark account exception | `mark_account_inventory_exception` |
| Record AgentRun | `record_agent_run` |
| Confirmation | `confirm_service_draft` |
| Customer reply send | `create_customer_reply_send_request`, Stage04 send worker |
| Audit | `record_audit_event` |

Forbidden direct access:

- raw PostgreSQL connection by Agent.
- raw SQL generated by LLM.
- provider token access.
- direct Telegram Bot call by LLM/Agent.

## 7. Reference Index Pattern

Like `lark-base` keeps separate references for field JSON, cell values, workflow schema and role config, Stage05 should keep references separated when content grows.

Initial references are the module docs:

- Agent graph and routing.
- Account inventory agent.
- Draft agents.
- Confirmation and send.
- Bitable views.
- OpenRouter evidence.

If implementation details become large, split later references such as:

- `STAGE_05_ROUTER_OUTPUT_SCHEMA.md`
- `STAGE_05_AGENT_TOOL_GATEWAY.md`
- `STAGE_05_DRAFT_PAYLOAD_SCHEMAS.md`
- `STAGE_05_ACCOUNT_EXCEPTION_POLICY.md`

Do not put large schema blobs into prompts if they can live as versioned docs and typed Pydantic schemas.

## 8. Error Recovery Pattern

Each capability must have a recovery table. Minimum entries:

| Failure | Recovery |
| --- | --- |
| Required context missing | stop, write manual review or stable error |
| Permission denied | write audit, do not retry as a stronger actor |
| Low confidence | manual review |
| Ambiguous account | manual review |
| Non-allowlisted send target | block send, no Telegram call |
| Provider action requested | create draft/no-op evidence only, no provider call |
| Output schema invalid | `agent_failed`, no draft |

This mirrors Feishu CLI error recovery tables but uses our backend states.

## 9. Post-Acceptance Acceptance Criteria

These criteria apply only after the main Stage05 workflow has completed final acceptance and the separate skills extension starts.

- Stage05 keeps this Agent skill/capability reference doc.
- A later implementation plan adds code-level capability registry or constants.
- Router prompt and child agent code reference capability names only in that later extension.
- Later tests assert that forbidden capabilities are rejected.
- Later Account Inventory Agent tests prove no account production and no automatic replacement distribution through skills.
- Bitable views expose capability output status, not hidden prompt internals, only if the later extension adds runtime capability output.

## 10. Implementation Guidance

The later skills extension should start with a static registry, not a dynamic marketplace:

```text
agent_capabilities = {
  "account_inventory_agent": [
    "inventory_query",
    "account_assignment_draft",
    "account_risk_detection",
    "auto_mark_high_confidence_exception",
    "ambiguous_inventory_review"
  ]
}
```

This is enough for:

- prompt construction.
- policy checks.
- audit.
- tests.
- future migration to dynamic skills.

Do not build a plugin marketplace, runtime skill installer or user-editable skill system in the main Stage05 delivery.

Do not implement this registry before Stage05 main workflow completion, final acceptance and safety review.
