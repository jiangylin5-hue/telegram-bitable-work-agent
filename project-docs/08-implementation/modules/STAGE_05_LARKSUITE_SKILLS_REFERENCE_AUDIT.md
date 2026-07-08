# Stage 05 LarkSuite Skills Reference Audit

## Status

- Document status: post-acceptance reference audit
- Scope: Analyze the 27 official `larksuite/cli` skills, rank their priority for this Telegram + Bitable-like Agent project, and define which skill patterns should be adapted into later Stage05 skill/capability work.
- Current Progress: 2026-07-08 Created after Stage05 functional/staging acceptance. This document is a design and audit artifact only. It does not add runtime registry code, does not install official Lark skills, does not call Lark/Feishu APIs, and does not change staging or production state.

## 1. Source And Decision Boundary

Reference source:

- Official repository: https://github.com/larksuite/cli
- Official skills directory: https://github.com/larksuite/cli/tree/main/skills
- Retrieval date: 2026-07-08
- Observed skill count: 27 skill directories under `skills/`

This project should not directly import or run the official Lark/Feishu skill runtime. The project runtime is:

```text
Telegram
-> FastAPI backend
-> PostgreSQL / Redis
-> LangGraph / OpenRouter
-> Bitable-like tables/views/permissions
-> Tool Gateway services
-> human confirmation
-> audit and execution evidence
```

Therefore, "接入 skills" in this project means:

- Reuse the official skill structure and routing discipline.
- Adapt business scope to Telegram, advertising agency operations and self-hosted Bitable-like records.
- Keep official `use / do not use`, permission, confirmation, recovery and reference-index patterns.
- Replace official Lark CLI commands with backend Tool Gateway service calls.
- Keep runtime implementation static and testable before any later dynamic registry.

It does not mean:

- Installing `lark-cli` skills into the production Agent.
- Letting the Agent call Lark/Feishu APIs directly.
- Copying Feishu auth, token, chat, Base or OpenAPI semantics as business truth.
- Creating a dynamic marketplace or user-editable skill system in Stage05.

## 2. Priority Definitions

| Priority | Meaning | Implementation Meaning |
| --- | --- | --- |
| P0 | Must adapt first | Required foundation for any later project skill registry. Without these, routing, permission, event intake and Bitable endpoint discipline are unstable. |
| P1 | Adapt in the first business skill extension | Directly supports current or near-next advertising agency workflows, but depends on P0 governance. |
| P2 | Keep as reference only for later stages | Valuable structure, but not required for current Telegram service-draft workflows. |
| P3 | Do not adapt unless future scope changes | Domain is unrelated, high-risk, or would distract from the current product boundary. |

## 3. Executive Priority Order

| Rank | Official Skill | Project Adapter Name | Priority | Decision |
| --- | --- | --- | --- | --- |
| 1 | `lark-base` | `project-bitable-base` | P0 | Adapt as the core Bitable table/field/record/view/workflow/permission skill. |
| 2 | `lark-shared` | `project-shared-policy` | P0 | Adapt as shared identity, permission, confirmation, JSON/error and high-risk action rules. |
| 3 | `lark-im` | `project-telegram-channel` | P0 | Adapt messaging semantics to Telegram ingress, send request, allowlist, binding and receipt evidence. |
| 4 | `lark-event` | `project-event-consumer` | P0 | Adapt bounded event consumption and worker contracts to Telegram webhook + Redis worker. |
| 5 | `lark-skill-maker` | `project-skill-maker` | P0 | Adapt as the authoring standard for project skills and capability contracts. |
| 6 | `lark-task` | `project-task-handoff` | P1 | Adapt task/status handoff to `service_drafts`, `pending_confirmation` and `agent_review_queue`. |
| 7 | `lark-contact` | `project-contact-binding` | P1 | Adapt identity resolution to Telegram sender, customer, operator and contact binding. |
| 8 | `lark-approval` | `project-confirmation-approval` | P1 | Adapt approval thinking to draft confirmation, rejection, more-info and escalation. |
| 9 | `lark-sheets` | `project-tabular-analysis` | P1 | Adapt tabular value, formula, batch write and statistic safety patterns. |
| 10 | `lark-workflow-standup-report` | `project-daily-operations-report` | P1 | Adapt workflow pattern to customer/company daily operations reports. |
| 11 | `lark-workflow-meeting-summary` | `project-period-summary-report` | P1 | Adapt workflow summary pattern to weekly service/recharge/risk summaries, not meetings. |
| 12 | `lark-openapi-explorer` | `project-tool-discovery-governance` | P1 | Adapt as controlled Tool Gateway discovery governance, never as raw external API access by Agent. |
| 13 | `lark-doc` | `project-doc-reference` | P2 | Reference for SOP/report document structures. Not current runtime. |
| 14 | `lark-drive` | `project-file-evidence-reference` | P2 | Reference for future attachment/import/export evidence handling. |
| 15 | `lark-markdown` | `project-markdown-reference` | P2 | Reference for internal Markdown artifact editing, not business Agent runtime. |
| 16 | `lark-wiki` | `project-knowledge-space-reference` | P2 | Reference for later SOP/knowledge space organization. Stage05 has no RAG/wiki runtime. |
| 17 | `lark-apps` | `project-app-ops-reference` | P2 | Reference for env/log/trace/deployment guardrails, not app hosting. |
| 18 | `lark-mail` | `project-mail-channel-candidate` | P2 | Possible future channel skill if email becomes a product channel. |
| 19 | `lark-calendar` | `project-schedule-candidate` | P2 | Possible future reminder/scheduling skill. |
| 20 | `lark-slides` | `project-presentation-report-reference` | P2 | Possible future report export reference. |
| 21 | `lark-whiteboard` | `project-diagram-reference` | P2 | Possible architecture/process diagram reference only. |
| 22 | `lark-minutes` | none | P3 | Do not adapt now. Meeting transcription is outside current business boundary. |
| 23 | `lark-note` | none | P3 | Do not adapt now. Note lookup is outside current business boundary. |
| 24 | `lark-vc` | none | P3 | Do not adapt now. Historical video meeting is unrelated to Stage05 flows. |
| 25 | `lark-vc-agent` | none | P3 | Do not adapt now. Real meeting participation is high-risk and unrelated. |
| 26 | `lark-okr` | none | P3 | Do not adapt now. OKR management is not advertising operations workflow. |
| 27 | `lark-attendance` | none | P3 | Do not adapt. Attendance records are unrelated. |

## 4. P0 Skills To Adapt First

### 4.1 `project-bitable-base` From `lark-base`

Official responsibility:

- Operates Lark Base: bases, tables, fields, records, views, forms, dashboard, workflow and role permissions.
- Resolves tokens and IDs before writes.
- Separates import/file work, auth work and Base work.
- Uses references for complex field JSON, cell values, formulas, lookup and data query DSL.

Project responsibility:

- Own the Bitable-like product constitution at runtime.
- Define how every Agent output becomes a table record, status, view row, automation trigger or audit event.
- Provide the common skill vocabulary for `telegram_inbox`, `service_drafts`, `agent_review_queue`, `pending_confirmation`, `customer_reply_send_requests`, `account_inventory`, `account_status_events`, `service_records`, `execution_logs` and `ops_audit_events`.

Business scenarios:

- A Telegram message asks to recharge an ad account and the system must create a `service_drafts` row.
- A message says an account is blocked, disabled, banned, frozen or risk-controlled and the system must mark `account_inventory` only when confidence and ownership are high.
- A human operator opens the pending work surface and needs drafts sorted by status, customer, missing fields, risk and confirmation state.
- A customer reply draft is confirmed and must create a linked `telegram_send_requests` row, then appear in `customer_reply_send_requests`.
- A manual review item must preserve why the Agent did not produce a draft.

Trigger conditions:

- User or message mentions table-like work: draft, record, view, queue, pending confirmation, audit, account inventory, service record, recharge record, customer report.
- Router has produced one or more actionable intents and needs to persist outputs.
- Any skill claims it has completed work but has not yet written a Bitable-like endpoint.
- Any operation needs field-level masking, row scope, status transitions or view projection.

Solved business flows:

```text
Telegram message
-> normalized message context
-> selected business skill
-> create/update Bitable-like record
-> update status/view
-> write audit
-> expose to operator via API/view
```

Required context:

- `message_id`
- `customer_id` or explicit unbound/manual-review reason
- target table or view
- target record id when updating
- field schema and allowed status transitions
- actor identity and permission snapshot

Allowed tools:

- `query_message_context`
- `query_customer_context`
- `query_bitable_view_schema`
- `create_service_draft`
- `update_service_draft_status`
- `query_account_inventory`
- `mark_account_inventory_exception`
- `create_agent_review_item`
- `record_audit_event`

Forbidden actions:

- Raw SQL generated by an LLM.
- Writing a business fact that has no table endpoint.
- Updating account allocation, provider status, funds movement or customer sends without the appropriate higher-level confirmation skill.
- Treating in-memory LangGraph state as final business completion.

Acceptance signals:

- Every selected Agent output has a record id or explicit manual-review id.
- Every write has an idempotency key.
- Every status change has an audit event.
- Views show enough operator evidence without exposing raw LLM prompt/response or secrets.

### 4.2 `project-shared-policy` From `lark-shared`

Official responsibility:

- Handles setup, auth, user vs bot identity, scopes, JSON contracts, update notices and high-risk approval protocol.

Project responsibility:

- Define shared policy for all project skills: actor identity, role, permission snapshot, high-risk action protocol, error envelope, retry behavior and audit requirements.
- Prevent privilege escalation from generic Agent roles.
- Make every skill explain what it can do, cannot do and what happens when permission is missing.

Business scenarios:

- A draft confirmation request arrives from a generic `agent` actor and must be rejected.
- A Telegram send request targets a non-allowlisted chat in Stage05 and must be blocked before any Bot API call.
- A customer asks for "帮我直接充一下" and the Agent must create draft/no-op evidence only, not execute funds movement.
- The Account Inventory Agent sees "这个户封了" and may mark exception only if account and customer ownership are known and policy allows that mutation.

Trigger conditions:

- Any skill wants to read or write scoped business data.
- Any operation has a side effect.
- Any operation touches external channels, provider adapters, account status, service records, confirmation or execution logs.
- Any error indicates missing permission, missing context, stale data, blocked target or policy violation.

Solved business flows:

```text
skill intent
-> actor identity check
-> role and scope check
-> stage policy check
-> confirmation/ticket requirement check
-> allowed service call or blocked audit
```

Required context:

- `actor_type`
- `actor_id`
- `role`
- `customer_scope`
- `stage_policy`
- `permission_snapshot`
- operation kind: read, draft-write, confirmation, send, provider-write

Allowed tools:

- `evaluate_permission`
- `require_manager_or_admin`
- `validate_stage05_send_policy`
- `record_policy_denial`
- `record_audit_event`

Forbidden actions:

- Retrying as a stronger actor after permission denial.
- Letting an Agent self-confirm its own draft.
- Treating Telegram sender identity as system permission.
- Hiding policy denials as successful no-ops.

Acceptance signals:

- Denials are explicit and audited.
- Manager/admin-only actions are enforced.
- Stage policy blocks provider writes, funds movement, production launch, customer group sends and automatic replacement distribution.

### 4.3 `project-telegram-channel` From `lark-im`

Official responsibility:

- Handles IM messages, chats, threads, message resources, cards, reactions and callbacks.
- Distinguishes bot/user identity and chat permissions.
- Defines message relationships and resource-download boundaries.

Project responsibility:

- Adapt messaging semantics to Telegram Bot API and the existing Stage03/Stage04 ingestion/send-request design.
- Own message intake, customer binding context, reply draft handoff, restricted send request creation and receipt evidence.

Business scenarios:

- A real Telegram customer message arrives and becomes a bound inbox row.
- A single message contains "给 123 充 200U，再回复客户说已收到" and should produce `recharge` and `customer_reply` drafts.
- A human confirms a `customer_reply` draft and the system creates a Stage05 allowlisted private test send request.
- A message arrives from an unbound chat and should enter manual review or binding workflow, not business Agent flow.

Trigger conditions:

- Input source is Telegram webhook, Telegram inbox, Telegram send request or Telegram receipt.
- User asks to send, reply, search incoming message, bind sender, inspect chat/user id or test allowlisted delivery.
- Customer reply draft is ready for confirmation or linked send creation.

Solved business flows:

```text
Telegram webhook
-> verify secret and parse update
-> bind chat/user to customer if possible
-> telegram_inbox row
-> intent_ready
-> Agent workflow
-> customer_reply draft
-> human confirmation
-> telegram_send_requests row
-> worker sends only if Stage05 allowlist passes
-> receipt/audit/view update
```

Required context:

- `telegram_message_id`
- `chat_id` stored securely and masked where required
- `telegram_user_id`
- binding record
- `customer_id`
- Stage05 send mode and allowlist presence
- `service_draft_id` for replies

Allowed tools:

- `query_telegram_inbox_message`
- `query_customer_binding`
- `create_customer_reply_send_request`
- `validate_telegram_send_target`
- `record_telegram_send_result`
- `record_audit_event`

Forbidden actions:

- Direct Bot API calls by LLM or Agent.
- Sending to real customer chat in Stage05.
- Sending to customer groups in Stage05.
- Storing raw allowlist values in git or docs.
- Treating a generated reply draft as already sent.

Acceptance signals:

- Ingress and send flows are separate.
- Every send request is linked to a draft and confirmation.
- Worker-time checks repeat confirm-time checks.
- Non-allowlisted target creates blocked evidence, not a Telegram call.

### 4.4 `project-event-consumer` From `lark-event`

Official responsibility:

- Consumes real-time events as NDJSON, supports bounded runs, timeout, ready marker and subprocess-friendly contracts.

Project responsibility:

- Define how webhook and Redis worker processing stays bounded, observable and recoverable.
- Provide the event-consumption contract for `telegram.message_received`, `telegram.message_processed`, Agent workflow jobs, send jobs and audit jobs.

Business scenarios:

- A webhook writes inbox/outbox records and the worker processes them exactly once or idempotently.
- A staging test needs a bounded run that waits for one Telegram message and then stops.
- A failed Agent workflow must leave a recoverable event, audit entry and stable status.
- A send worker must prove it processed or blocked a send request without looping forever.

Trigger conditions:

- Any task starts from webhook, queue, stream, outbox or worker processing.
- Any test or runbook needs bounded event consumption.
- Any event handler must expose ready, timeout, max events, retry or dead-letter behavior.

Solved business flows:

```text
event created
-> durable outbox/stream entry
-> worker claims event
-> idempotency check
-> service handler
-> status/audit update
-> ack or retry/dead-letter
```

Required context:

- event name
- trace id
- idempotency key
- source record id
- worker identity
- max retry / timeout policy

Allowed tools:

- `enqueue_outbox_event`
- `claim_worker_job`
- `record_worker_result`
- `record_worker_failure`
- `record_audit_event`

Forbidden actions:

- Infinite polling in tests or runbooks.
- Acknowledging a failed side effect as success.
- Retrying unsafe external sends without idempotency.
- Dropping unhandled events without audit.

Acceptance signals:

- Bounded local/staging tests can prove one event was consumed.
- Every failure path leaves inspectable state.
- Duplicate events do not duplicate drafts, sends or account mutations.

### 4.5 `project-skill-maker` From `lark-skill-maker`

Official responsibility:

- Creates custom Lark CLI skills from API operations or multi-step workflows.

Project responsibility:

- Define the project-specific skill contract and authoring rules for future Agent skill files or static registry entries.
- Ensure skills are discoverable by trigger descriptions and safe by explicit non-goals.

Business scenarios:

- A new business skill is proposed for customer daily report.
- A future provider execution skill is proposed for recharge readback.
- A new account replacement flow is requested, but Stage05 forbids automatic replacement distribution.
- A report/balance query skill is added after the Stage05 `tg:184365909` manual-review gap.

Trigger conditions:

- A new skill/capability is proposed.
- An existing skill boundary changes.
- A skill needs new tools, permissions, tables, outputs or forbidden actions.
- A skill caused false positives, false negatives or unsafe routing.

Required skill contract:

```text
Skill ID:
Priority:
Owning Agent:
When to use:
Do not use:
Positive triggers:
Negative triggers:
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
Acceptance tests:
Reference docs:
```

Forbidden actions:

- Adding a skill with no table endpoint.
- Adding a skill with only a prose prompt and no schema.
- Adding a skill that bypasses Tool Gateway.
- Adding a runtime marketplace before a static registry is proven.

Acceptance signals:

- Each new skill has trigger tests and negative-trigger tests.
- Each skill has at least one real or realistic Telegram case.
- Each skill has expected table/view/audit evidence.

## 5. P1 Skills For First Business Extension

### 5.1 `project-task-handoff` From `lark-task`

Purpose:

- Convert official task/checklist/status thinking into project operational work queues.
- This is the right place for handoffs that are not immediately executable by Agent.

Business scenarios:

- A draft needs human confirmation.
- A message is ambiguous and enters `agent_review_queue`.
- A customer asks for something unsupported, such as spend/balance query in Stage05, and the system must create a review item or future-stage note.
- A business draft is confirmed and produces a service record/no-op evidence task trail.

Triggers:

- `needs_more_info`
- `manual_review`
- `pending_confirmation`
- `operator_follow_up`
- unsupported but business-relevant intent
- policy-blocked intent needing human decision

Solved flows:

```text
Agent uncertainty or blocked action
-> task/review item
-> operator queue view
-> operator action
-> draft status/service record/audit update
```

Must not solve:

- Full project management.
- User-facing task board UI in Stage05.
- Automatic execution after task creation.

### 5.2 `project-contact-binding` From `lark-contact`

Purpose:

- Adapt person/contact resolution to Telegram sender, Telegram chat, customer, internal operator and allowed contact hints.

Business scenarios:

- New Telegram sender needs binding to a customer.
- A BM invite message contains an email and must identify it as invitee hint, not internal operator.
- A customer reply needs to address the customer safely without exposing internal account state.
- Operator action needs `actor_id` and role attribution.

Triggers:

- Unbound Telegram message.
- Message contains names, phone-like hints, emails or BM invite targets.
- A workflow needs to know whether the actor is customer, manager, admin or Agent.

Solved flows:

```text
chat/user/contact hint
-> binding lookup
-> customer/operator/contact candidate
-> disambiguation or manual review
-> bound context for downstream skill
```

Must not solve:

- Full organization chart.
- Bulk contact import.
- Treating any email as permission to invite or send.

### 5.3 `project-confirmation-approval` From `lark-approval`

Purpose:

- Adapt official approval routing and failure handling into project draft confirmation.

Business scenarios:

- Confirm `customer_reply` and create linked send request.
- Confirm `recharge`, `card_binding` or `bm_invite` as no-op/service evidence in Stage05.
- Reject a draft with reason.
- Request more information from customer/operator.
- Escalate a risky or ambiguous draft.

Triggers:

- User/operator acts on `pending_confirmation`.
- Draft status transitions from `pending_confirmation`.
- A skill proposes high-risk action or external write.

Solved flows:

```text
draft pending confirmation
-> manager/admin action
-> status transition
-> service record / no-op evidence / send request / escalation
-> audit
```

Must not solve:

- Native Feishu approval.
- Agent self-approval.
- Execution ticket generation for real provider writes in Stage05.

### 5.4 `project-tabular-analysis` From `lark-sheets`

Purpose:

- Reuse table value, formula, batch update and statistical thinking for Bitable-like records and later reports.

Business scenarios:

- Summarize drafts by customer, type, status and risk.
- Calculate customer daily spend later.
- Produce company-level daily report later.
- Validate bulk table operations before mutating many records.

Triggers:

- User asks for totals, summaries, trends, ranking, grouped counts or operational views.
- A report workflow needs structured table reads.
- A batch update or migration-like operation is proposed.

Solved flows:

```text
structured records
-> scoped query
-> aggregation/statistics
-> report draft or view output
-> audit/evidence
```

Must not solve:

- Turning the product into a spreadsheet clone.
- Financial modeling unrelated to ad operations.
- Raw SQL or ad hoc CSV manipulation when service/query APIs exist.

### 5.5 `project-daily-operations-report` From `lark-workflow-standup-report`

Purpose:

- Reuse simple workflow composition to produce daily operational summaries.

Business scenarios:

- Daily customer report: spend, recharge status, account exceptions, pending confirmations.
- Daily internal report: service draft counts, send status, account inventory exceptions, unresolved manual reviews.
- Morning operator digest: what needs action today.

Triggers:

- User asks "今天有什么待处理", "客户日报", "公司日报", "汇总一下昨天".
- Scheduled job wants to generate a daily digest.
- Manager asks for current operational queue status.

Solved flows:

```text
date range
-> query scoped tables/views
-> aggregate facts
-> draft report
-> human confirmation or internal view
-> send later only through policy gate
```

Must not solve:

- Sending reports to real customers in Stage05.
- Inventing spend/balance facts not present in database.
- Using RAG as source of financial truth.

### 5.6 `project-period-summary-report` From `lark-workflow-meeting-summary`

Purpose:

- Reuse period-summary workflow shape, but replace meeting minutes with service operations.

Business scenarios:

- Weekly customer operations summary.
- Review of recharge requests and no-op evidence.
- Summary of account exceptions by customer.
- Summary of manual review backlog.

Triggers:

- User asks for weekly/monthly/period summary.
- Operator wants a post-incident summary.
- Manager wants acceptance evidence summarized by trace id or customer.

Solved flows:

```text
period filter
-> collect service records, drafts, audit, account events
-> group by customer/workflow/status
-> produce structured summary
-> link evidence records
```

Must not solve:

- Meeting transcription.
- Audio/video files.
- Freeform narrative without source records.

### 5.7 `project-tool-discovery-governance` From `lark-openapi-explorer`

Purpose:

- Reuse discovery discipline for future Tool Gateway expansion.
- It must never become permission for Agent to call external provider APIs directly.

Business scenarios:

- Future recharge provider adapter needs official API research.
- Future Meta/BM invite adapter needs controlled API mapping.
- A missing internal service tool must be specified before implementation.

Triggers:

- Existing Tool Gateway cannot satisfy an approved business requirement.
- A future stage explicitly authorizes provider execution design.
- A developer needs to map external API concepts into controlled backend tools.

Solved flows:

```text
approved requirement
-> research official API docs
-> design backend service/tool contract
-> security review
-> tests
-> controlled adapter implementation
```

Must not solve:

- Runtime raw OpenAPI calls by LLM.
- Provider writes in Stage05.
- Bypassing execution tickets, confirmation or audit.

## 6. P2 Reference Skills

| Official Skill | Keep What | Do Not Bring Now |
| --- | --- | --- |
| `lark-doc` | Document read/edit boundary, embedded resource routing, attachment caution | Runtime document editing, customer-facing docs, Feishu doc semantics |
| `lark-drive` | File evidence lifecycle, import/export separation, permissions | Cloud drive implementation, arbitrary file upload/download in Agent |
| `lark-markdown` | Diff/patch discipline for docs | Business runtime skill |
| `lark-wiki` | Knowledge-space organization and node/member boundaries | SOP wiki or RAG runtime in Stage05 |
| `lark-apps` | Deployment/env/log/trace guardrails | Miaoda/Spark app hosting or app-generation workflow |
| `lark-mail` | Channel-specific send/read safety, untrusted external content warning | Email channel in current product |
| `lark-calendar` | Time inference, schedule entity rules | Scheduling product surface |
| `lark-slides` | Structured report export patterns | Presentation generation in current runtime |
| `lark-whiteboard` | Diagram update workflow and reference file split | Whiteboard/diagram runtime |

## 7. P3 Excluded Skills

| Official Skill | Exclusion Reason |
| --- | --- |
| `lark-attendance` | Attendance is unrelated to Telegram advertising agency service workflows. |
| `lark-okr` | OKR management would create non-core collaboration scope. |
| `lark-vc` | Historical meeting records are outside Stage05 business flows. |
| `lark-vc-agent` | Real meeting participation is unrelated and operationally high-risk. |
| `lark-minutes` | Audio/video transcription is outside current workflow and evidence model. |
| `lark-note` | Note lookup is not a current business endpoint. |

If any P3 domain becomes a real product requirement later, it must enter as a new stage candidate with its own table endpoint, source of truth, security design and acceptance plan.

## 8. Proposed Project Skill Layers

### L0 Governance Skills

Responsibilities:

- Define skill metadata, trigger description rules and non-use rules.
- Define actor identity, permission snapshot, confirmation and audit.
- Define stage gates and forbidden actions.

Examples:

- `project-skill-maker`
- `project-shared-policy`

Boundary:

- L0 does not produce business drafts.
- L0 decides whether other skills are allowed to run.

### L1 Channel And Event Skills

Responsibilities:

- Normalize external input.
- Bind source identity to customer/operator context.
- Consume events and enqueue work safely.
- Create outbound send requests only through policy.

Examples:

- `project-telegram-channel`
- `project-event-consumer`
- `project-contact-binding`

Boundary:

- L1 does not decide business intent alone.
- L1 does not execute provider operations.

### L2 Bitable Data Skills

Responsibilities:

- Resolve table/view/record context.
- Persist drafts, reviews, account events and service records.
- Enforce field/view masking and status transitions.

Examples:

- `project-bitable-base`
- `project-tabular-analysis`

Boundary:

- L2 writes business state only through service APIs.
- L2 does not invent facts missing from source records.

### L3 Business Atomic Skills

Responsibilities:

- Solve one business intent at a time.
- Produce one typed output schema.
- Land output in one primary Bitable endpoint.

Initial project skills:

- `recharge-draft`
- `card-binding-draft`
- `bm-invite-draft`
- `customer-reply-draft`
- `account-assignment-draft`
- `account-exception-marking`

Boundary:

- L3 creates drafts, review items or permitted account exception events.
- L3 does not confirm its own output.
- L3 does not call provider APIs.

### L4 Workflow Skills

Responsibilities:

- Compose L1/L2/L3 skills into end-to-end flows.
- Handle multi-intent messages.
- Route ambiguous cases to manual review.
- Produce daily/period summaries.

Examples:

- `telegram-message-business-workflow`
- `daily-operations-report`
- `period-summary-report`
- `confirmation-approval-workflow`

Boundary:

- L4 orchestrates.
- L4 does not bypass lower-level skill permission checks.

### L5 Controlled Execution Skills

Responsibilities:

- Later-stage provider execution after human confirmation and execution ticket.
- Readback, reconciliation, execution logs and rollback/escalation evidence.

Future examples:

- `execute-recharge-provider`
- `execute-card-binding-provider`
- `execute-bm-invite-provider`
- `readback-account-balance`

Boundary:

- L5 is not active in Stage05.
- L5 requires explicit future-stage approval, execution ticket, provider adapter tests and staging acceptance.

## 9. Skill Matching And Hit Rate Design

### 9.1 Matching Pipeline

```text
raw Telegram message
-> normalize text and source metadata
-> resolve customer binding
-> deterministic stage/domain guard
-> candidate skill retrieval from manifest
-> LLM or semantic router ranks candidates
-> context and permission gate
-> skill-specific schema validation
-> Bitable endpoint write
-> audit hit/miss evidence
```

### 9.2 Skill Manifest Fields

Each project skill should expose a compact manifest before its full instructions are loaded:

```text
skill_id:
priority:
layer:
owning_agent:
description:
positive_triggers:
negative_triggers:
required_entities:
optional_entities:
stage_allowed:
allowed_tools:
forbidden_actions:
primary_endpoint:
output_schema:
confidence_threshold:
fallback:
```

Important rule:

- `description` must describe when to use the skill, not summarize the workflow.
- Detailed workflow lives in the skill body or reference docs.
- Negative triggers are mandatory for skills whose names are semantically close.

### 9.3 Candidate Retrieval

Use three passes:

1. Deterministic lexical pass:
   - Match strong terms like `充值`, `充`, `U`, `USDT`, `绑卡`, `卡`, `BM`, `invite`, `回复客户`, `封号`, `风控`, `余额`, `消耗`.
   - Match source context like Telegram message, inbox row, pending confirmation, send request.

2. Structured entity pass:
   - Extract amount, currency, account hint, BM hint, invitee email, card/payment profile hint, customer reply request, account exception phrase.
   - Remove candidates whose required entities cannot be satisfied unless they support `needs_more_info`.

3. Semantic/LLM router pass:
   - Rank top candidates.
   - Allow multi-label output.
   - Include explicit rejected candidate reasons.

### 9.4 Confidence And Fallback Rules

| Situation | Action |
| --- | --- |
| High confidence and required context complete | Run selected skill and persist output. |
| High confidence but missing fields | Create `needs_more_info` draft if the business intent is supported. |
| Medium confidence or conflicting candidates | Create `agent_review_queue` item. |
| Unsupported but business-relevant intent | Manual review with unsupported intent code. |
| Stage-forbidden intent | Block and audit, optionally create draft/no-op evidence if allowed. |
| Sensitive payment data | Block normal draft, create manual review/audit without storing raw sensitive value. |
| External provider execution request in Stage05 | Create draft/no-op evidence only; no provider call. |

### 9.5 Improving Hit Rate

Hit rate should be improved through evidence, not by broadening prompts blindly.

Required feedback records:

- input trace id
- candidate skills
- selected skills
- rejected skills
- confidence
- missing entities
- output schema validation result
- endpoint record ids
- manual review reason
- operator correction if any

Metrics:

- Top-1 accuracy for single-intent messages.
- Top-3 recall for ambiguous messages.
- Multi-intent recall for messages containing two or more business requests.
- False positive count for forbidden skills.
- Manual-review precision: whether review was actually needed.
- Missing-field correctness: whether `needs_more_info` asked for the right missing fields.

Test case families:

- Recharge only.
- Recharge plus customer reply.
- Card binding with safe tokenized card reference.
- Card binding with raw card/CVV, expected block.
- BM invite with email.
- Account blocked/risk-controlled with resolvable account.
- Account blocked with ambiguous account, expected manual review.
- Spend/balance query before supported skill, expected manual review.
- Unbound Telegram sender, expected no business draft.
- Customer asks for direct external execution, expected draft/no-op only.

## 10. Business Skill Entry Order

After P0 governance is documented and accepted, the first runtime registry should be static and should add skills in this order:

1. `recharge-draft`
   - Reason: Already verified in Stage05 real Telegram/OpenRouter flow.
   - Endpoint: `service_drafts.draft_type = recharge`.
   - Main triggers: `充值`, `充`, amount/currency, ad account hint.

2. `customer-reply-draft`
   - Reason: Already verified with allowlisted Telegram receipt.
   - Endpoint: `service_drafts.draft_type = customer_reply`, then linked `telegram_send_requests` after confirmation.
   - Main triggers: `回复客户`, `告诉客户`, `回他说`, `客户那边怎么回`.

3. `bm-invite-draft`
   - Reason: Already exercised in additional Stage05 Telegram test.
   - Endpoint: `service_drafts.draft_type = bm_invite`.
   - Main triggers: `BM`, `invite`, `邀请`, email/contact hint.

4. `card-binding-draft`
   - Reason: Core advertising account workflow, but payment sensitivity requires stronger negative triggers.
   - Endpoint: `service_drafts.draft_type = card_binding`.
   - Main triggers: `绑卡`, `换卡`, `卡`, tokenized payment profile.

5. `account-exception-marking`
   - Reason: Stage05 allows narrow automatic exception marking.
   - Endpoint: `account_inventory`, `account_status_events`, audit.
   - Main triggers: `封了`, `风控`, `disabled`, `blocked`, `不能用了`.

6. `account-assignment-draft`
   - Reason: Useful but must avoid automatic replacement and production confusion.
   - Endpoint: `service_drafts.draft_type = account_assignment`.
   - Main triggers: `给我一个户`, `分配账户`, `要新户`.

7. `spend-balance-query`
   - Reason: Gap found during Stage05 real test. Should be next-stage candidate, not retroactively claimed as Stage05 done.
   - Endpoint: future report/query view.
   - Main triggers: `余额`, `消耗`, `花了多少`, `还剩多少`.

## 11. Non-Negotiable Boundaries

The adapted project skills must preserve these boundaries:

- Every output lands in a Bitable-like endpoint.
- No skill can treat chat text as proof that provider action succeeded.
- No skill can call raw SQL.
- No skill can call provider APIs directly.
- No skill can access secrets.
- No skill can self-confirm.
- No skill can send to real customer chat or customer group in Stage05.
- No skill can produce account production, import, automatic replacement or automatic redistribution in Stage05.
- No skill can store raw card number, CVV or full payment credential.
- No runtime registry should become dynamic before the static registry passes real Telegram case tests.

## 12. Acceptance Criteria For Later Implementation

Before implementing runtime skill registry:

- This audit is linked from `STAGE_05_AGENT_SKILLS_AND_CAPABILITIES.md`.
- P0 and P1 adapter names are accepted by user.
- Each P0/P1 project skill has a manifest contract.
- Each business skill has positive and negative trigger tests.
- Each business skill has at least one realistic Telegram input fixture.
- Each business skill has endpoint assertions.
- Forbidden action tests exist for provider writes, real customer sends, raw SQL, self-confirmation and account replacement.
- A hit-rate evaluation report can show top candidates, selected candidates and correction outcomes.

## 13. Recommended Next Step

Use this document as the source for a small post-acceptance Stage05 skill-extension implementation plan:

1. Define static skill manifest schema.
2. Add P0 governance manifests.
3. Add P1 business manifests for already supported Stage05 draft flows.
4. Add router candidate logging and hit/miss evidence.
5. Add tests before wiring runtime selection.
6. Run local real Telegram-style cases before any staging redeploy.

