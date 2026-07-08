# Stage 05 Account Inventory Agent

## Status

- Document status: active module design draft
- Scope: Account distribution drafts, inventory state visibility, high-confidence exception marking and manual review boundary.
- Current Progress: 2026-07-07 Task 7 implemented locally after user confirmed the existing documented plan. Account Inventory Agent now uses deterministic policy logic, creates `account_assignment` drafts only for human review, and may auto-mark high-confidence `blocked`, `disabled` and `risk_controlled` exceptions through a narrow service guard. The implementation writes `account_status_events` and audit evidence, and does not produce accounts, recommend/reserve replacements, confirm assignments, call providers or execute staging actions.
- Current Progress Update: 2026-07-08 Controlled Tencent Cloud staging fixture verified the account exception boundary: account `24eb5124-80ab-438f-a4cd-b427a76345a0` produced status event `fcd2db3c-d26e-47ba-86dc-528656d685f2`, `after_status=risk_controlled`, audit evidence, `replacement_action=none` and zero assignments.

## 1. Purpose

The Account Inventory Agent manages account distribution and inventory stability. In this business, accounts are not stable: they may be risk-controlled, blocked, disabled or otherwise unusable. Stage05 therefore gives this Agent a narrow automatic mutation ability for high-confidence abnormal states.

The Agent exists to keep `account_inventory` and `account_status_events` current enough that later service drafts and human operators do not rely on stale account availability.

## 2. Explicit Non-Goals

The Agent does not:

- Produce new accounts.
- Import account production batches.
- Create inventory accounts from production messages.
- Automatically recommend replacement accounts after a block.
- Automatically reserve replacement accounts.
- Automatically assign replacement accounts.
- Execute Meta/BM/provider actions.
- Treat Telegram sender identity as permission to assign accounts.

If a message asks to produce new accounts, Stage05 records manual review or a future-stage note.

## 3. Business Inputs

The Agent may use:

- Router intent `account_assignment`.
- Router intent `account_status_exception`.
- Existing `account_inventory` rows.
- Existing `account_assignments`.
- Existing `account_status_events`.
- Customer binding from Stage04.
- Structured account hints from the message.
- Recent customer messages as redacted context.

The Agent may not use:

- raw provider credentials.
- raw card data.
- unverified Telegram claims as final account ownership proof.

## 4. Outputs

| Output | Condition | Table/view |
| --- | --- | --- |
| Account assignment draft | Customer asks for an account and context is enough to propose human-reviewed assignment | `service_drafts.draft_type = account_assignment` |
| Account status event | High-confidence risk/block/disabled evidence exists | `account_status_events` |
| Inventory status mutation | Same high-confidence abnormal evidence | `account_inventory.inventory_status` |
| Manual review | Evidence is ambiguous or action is out of scope | `agent_review_queue` |
| Audit event | Every mutation and review decision | `ops_audit_events` |

## 5. Status Policy

### 5.1 Allowed Automatic Statuses

| After status | Example evidence | Required confidence |
| --- | --- | --- |
| `blocked` | Message clearly says account is封号/blocked/disabled by platform and account id resolves | high |
| `disabled` | Message clearly says account is disabled/unusable and account id resolves | high |
| `risk_controlled` | Message clearly says account is under risk control / 风控 and account id resolves | high |

### 5.2 Forbidden Automatic Statuses

| Status | Reason |
| --- | --- |
| `reserved` | Would pre-allocate inventory and affect future distribution |
| `allocated` | Assigns customer ownership and requires human confirmation |
| `activated` | Implies operational activation outside Stage05 |
| `recycled` | Requires operational recovery policy |
| `archived` | Lifecycle terminal state requiring human/process decision |

## 6. Account Assignment Draft

The Agent may create a draft when:

- Customer is bound.
- Intent is account distribution/request.
- There is enough information to identify request type.
- Candidate account selection is safe enough for human review.

Draft payload may include:

```json
{
  "request_type": "account_assignment",
  "customer_id": "uuid",
  "candidate_account_inventory_ids": ["uuid"],
  "selection_reason": "unused account with matching platform",
  "requires_human_confirmation": true
}
```

If candidate selection is uncertain, use:

- `status = needs_more_info` when request is clear but fields are missing.
- `status = manual_review` when candidate quality/risk is unclear.

Stage05 confirmation of `account_assignment` creates no-op service evidence unless a separate existing account assignment service is explicitly wired and confirmed by user in implementation. It does not automatically allocate replacement accounts.

## 7. Exception Marking Flow

```text
Router detects account_status_exception
-> Account Inventory Agent resolves account hint
-> check current inventory row
-> classify evidence
-> if high-confidence abnormal:
     update account_inventory.inventory_status
     create account_status_events
     write audit
     do not recommend replacement
   else:
     create manual review evidence
```

## 8. Edge Cases

| Case | Handling |
| --- | --- |
| Account hint not found | Manual review, no mutation |
| Multiple accounts match hint | Manual review, no mutation |
| Account already blocked | Idempotent status event/no duplicate mutation |
| Account assigned to another customer | Manual review unless same customer is verified |
| Message asks for replacement | Manual review or future-stage note; no replacement recommendation |
| Message asks to produce accounts | Out of scope manual review |
| Ambiguous "not stable" wording | Manual review |
| Low-confidence LLM output | Manual review |

## 9. Permission Boundary

Agent action:

- `auto_mark_account_exception` only.
- Allowed only for `blocked`, `disabled`, `risk_controlled`.

Task 7 implemented permission boundary:

- Do not grant `auto_mark_account_exception` to the generic `agent` role in a way that lets all child Agents mutate inventory.
- Service-level guard allows:
  - manager/admin human actors,
  - `actor_type = agent` with `actor_id = account_inventory_agent` only.
- Successful mutation remains behind resolved existing inventory id, high confidence and allowed risk flag.
- Confidence/risk evidence is stored on `account_status_events` via additive nullable metadata.
- Use audit `account.exception_marked` for every automatic abnormal mark.

Human action:

- Confirm account assignment.
- Replace account.
- Reserve account.
- Recycle account.
- Reopen account.

## 10. Audit Contract

Automatic status mark audit:

```json
{
  "event_type": "account.exception_marked",
  "actor_type": "agent",
  "actor_id": "account_inventory_agent",
  "entity_type": "account_inventory",
  "before_state": {"inventory_status": "allocated"},
  "after_state": {
    "inventory_status": "blocked",
    "confidence": "0.9400",
    "source_message_id": "uuid",
    "replacement_action": "none"
  }
}
```

Manual review audit:

```json
{
  "event_type": "agent.manual_review_requested",
  "reason": "ambiguous_account_risk",
  "entity_type": "message"
}
```

## 11. Tests

Required tests:

- Agent does not call `create_inventory_account`.
- High-confidence blocked message updates status and event.
- High-confidence risk-control message updates status and event.
- Ambiguous risk creates manual review.
- Replacement request does not create candidate/reservation/assignment.
- Forbidden status transition is rejected.
- Duplicate risk signal does not create duplicate mutation.

## 12. Staging Evidence

Stage05 staging should include either:

- A controlled message that marks a staging test account abnormal, or
- A controlled API/fixture workflow that proves high-confidence abnormal marking while no real customer account is affected.

Evidence must include:

- account id redacted or staging-only id.
- before/after inventory status.
- account status event id.
- audit event.
- proof no replacement was created.
