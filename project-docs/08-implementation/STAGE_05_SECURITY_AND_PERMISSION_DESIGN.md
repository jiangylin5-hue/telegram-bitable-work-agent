# Stage 05 Security And Permission Design

## Status

- Document status: active security design draft
- Scope: Stage05 Agent authority, OpenRouter, account inventory mutation, draft confirmation, Telegram send and view permissions.
- Current Progress: 2026-07-07 Security design drafted before implementation. Task 7 implemented the narrow `auto_mark_account_exception` service guard for manager/admin and `actor_id=account_inventory_agent` only. Task 8 implemented Stage05 confirmation as manager/admin only, blocks agent confirmation, and preserves old Stage02 production confirmation only for non-Stage05 drafts. Task9 implemented customer reply send request linkage plus confirm-time and worker-time allowlist checks. Task10 implemented view-level row scope and scoped masking for Stage05 operational views, including account inventory external-id masking for non-global roles. Generic `agent` role actors are not granted inventory mutation, confirmation or send authority.

## 1. Security Goals

Stage05 gives Agents real LLM capability and limited automatic inventory exception marking, so its security posture is:

- Strong enough for staging real OpenRouter.
- Safe enough to prevent customer-facing or provider-facing accidental execution.
- Explicit about which actions an Agent may perform without human confirmation.
- Auditable for every mutation and external call.

## 2. Actor Model

| Actor | Meaning | Stage05 capabilities |
| --- | --- | --- |
| `agent:operations_supervisor` | Runtime graph coordinator | Route and persist Agent outputs through services |
| `agent:message_intake_router` | OpenRouter intent parser | Create AgentRun evidence only |
| `agent:account_inventory_agent` | Inventory manager | Create assignment drafts; auto-mark high-confidence abnormal statuses |
| `agent:*_draft_agent` | Draft generator | Create service drafts only |
| `system:worker` | Background worker | Trigger workflow and send allowlisted test messages |
| `user:sales` | Sales/operator | View scoped records, request more info, escalate |
| `user:manager` | Manager/operator | Confirm/reject drafts, manage staging validation |
| `user:admin` | Admin | Full internal staging permissions |

Agents do not inherit Telegram sender identity. A Telegram user being bound to a customer does not make the Telegram sender an authorized system actor.

## 3. Proposed Permission Actions

| Action | Allowed roles | Notes |
| --- | --- | --- |
| `run_stage05_agent_workflow` | manager, admin, system | Manual or worker trigger |
| `create_agent_service_draft` | agent, system | Service-only, not public |
| `auto_mark_account_exception` | account_inventory_agent, manager, admin | Agent allowed only for high-confidence abnormal statuses |
| `propose_account_assignment` | agent, sales, manager, admin | Proposal/draft only |
| `confirm_draft` | manager, admin | Existing action may be reused |
| `reject_draft` | sales, manager, admin | Scoped by record visibility |
| `request_more_info` | sales, manager, admin | Existing action may be reused |
| `escalate_review` | sales, manager, admin | Existing action may be reused |
| `request_customer_reply_test_send` | manager, admin | Only through draft confirmation |
| `confirm_customer_reply_test_send` | manager, admin | Only allowlisted staging target |
| `view_agent_runs` | manager, admin | Sales may see only derived draft/review views |

## 4. LLM Authority Boundary

LLM may:

- Classify intent.
- Extract entities.
- Generate draft payloads.
- Generate customer reply draft text.
- Generate missing-field suggestions.
- Explain risk flags.
- Suggest manual review reasons.

LLM may not:

- Confirm a draft.
- Send Telegram messages.
- Create execution tickets for real provider work.
- Execute Meta/BM/card/recharge operations.
- Mark an account abnormal unless the backend Account Inventory Agent policy accepts the evidence.
- Access secrets.
- Decide that a real external write succeeded without execution evidence.

## 5. Account Inventory Automatic Status Marking

Stage05 allows a narrow automatic mutation because the user explicitly stated accounts are unstable and often risk-controlled/blocked.

Allowed automatic statuses:

- `blocked`
- `disabled`
- `risk_controlled`

Required evidence:

- Resolved existing `account_inventory_id`.
- Source message or structured context linked by id.
- Confidence at or above configured threshold.
- Risk flag in allowed set, such as:
  - `account_blocked_reported`
  - `risk_control_confirmed`
  - `account_disabled_reported`
- Audit event and account status event written in the same logical operation.

Forbidden automatic statuses:

- `reserved`
- `allocated`
- `activated`
- `recycled`
- `archived`
- any state that assigns or reassigns customer ownership.

Replacement account handling:

- No automatic recommendation.
- No automatic reservation.
- No automatic assignment.
- Replacement request enters human handling or a later stage.

## 6. Telegram Send Boundary

Only `customer_reply` draft can lead to Telegram send in Stage05.

Rules:

- Target chat must be in server-side allowlist.
- Customer reply draft confirmation creates/reuses a send request and checks the current allowlist; non-allowlisted targets become blocked requests.
- Confirmation checks current allowlist.
- Worker re-checks allowlist immediately before sending.
- `send_purpose = customer_reply_rehearsal` distinguishes Stage05 reply sends from Stage04 generic test sends.
- `TELEGRAM_SEND_MODE` must be `restricted_test` during send rehearsal.
- After rehearsal, `TELEGRAM_SEND_MODE` returns to `dry_run` and allowlist is cleared/disabled.

Forbidden:

- Customer group send.
- Real customer chat send.
- Bulk send.
- Sending directly from LLM output without a draft and human confirmation.

## 7. OpenRouter Secret Handling

OpenRouter key:

- Server-side env only.
- Not committed.
- Not stored in docs.
- Not returned by health/config routes.
- Not logged.

Prompt data:

- Minimize context.
- Include only bound customer context.
- Do not include raw secrets, payment sensitive fields, raw card numbers, CVV or unredacted credentials.
- Use redacted summaries for persistent evidence.

Output data:

- Save structured result and redacted summary.
- Do not expose full raw LLM response in views.
- If temporary debugging ever stores raw data locally, it must be outside git and removed before acceptance; Stage05 default is no raw storage.

## 8. Provider Safety

Provider mode remains disabled.

Stage05 business draft confirmation may create:

- `service_records`
- no-op `execution_logs`
- audit

It must not create:

- real provider request
- provider write job
- fund movement
- live Meta/BM/card/recharge operation

If code reaches a provider adapter in Stage05 tests, that is a failure unless the adapter is an explicit no-op/fake and the test asserts no external call.

## 9. View Security

Views must apply:

- Row-level customer scope using existing `can_view_customer_record`.
- Sensitive field masking using existing `allowed_fields_for_actor`.
- Global operational fields visible to manager/admin only.

Sensitive fields:

- Telegram chat/user ids.
- Account external ids for non-global roles.
- Telegram response summaries where they reveal target chat/message id.
- LLM summaries that include customer-sensitive information.
- Account risk reason details for non-global roles.

Task10 implementation notes:

- `service_drafts`, `agent_review_queue`, `pending_confirmation` and `customer_reply_send_requests` reuse the existing application-level row scope guard.
- `customer_reply_send_requests` inherits customer scope from the linked `service_drafts` row before projection.
- `account_inventory.external_account_id` is visible to manager/admin for operational inventory handling and masked for customer-scoped actors.
- `telegram_inbox` derives Agent evidence fields but does not expose raw prompt, raw response or raw Telegram payload.

## 10. Audit Contract

Every Stage05 mutation writes audit:

| Event | Required |
| --- | --- |
| `agent.workflow_started` | message id, trace id |
| `agent.router_completed` | intent summary, confidence |
| `agent.router_failed` | safe error code |
| `agent.draft_created` | draft id/type/status |
| `agent.manual_review_requested` | reason |
| `account.exception_marked` | before/after status, confidence, source |
| `draft_confirmed` | actor and side effect |
| `draft_rejected` | reason |
| `draft_more_info_requested` | missing fields |
| `customer_reply_send_requested` | draft/request link |
| `customer_reply_send_confirmed` | send confirmation + outbox link |
| `customer_reply_send_sent` | response summary |
| `customer_reply_send_failed` | allowlist block or Telegram failure |
| `business_noop_evidence_created` | service/execution ids |

Audit must not include secrets.

## 11. Failure Security

Fail closed conditions:

- Missing OpenRouter key in real mode.
- Missing Telegram allowlist in restricted send mode.
- Provider mode not disabled during Stage05 staging.
- Non-allowlisted send target.
- LLM output invalid.
- Account exception evidence ambiguous.
- Confirming non-confirmable draft.

Fail closed means no external write and no provider call.
