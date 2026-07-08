# Stage 05 Database And Migration Design

## Status

- Document status: active database design draft
- Scope: Stage05 schema changes for Agent evidence, draft metadata, customer reply send linkage, account status exceptions and views.
- Current Progress: 2026-07-07 Phase 05.1 Task 2 created `20260707_0012_stage05_agent_run_evidence.py` for additive AgentRun evidence columns. Phase 05.3 Task 5 created `20260707_0013_stage05_service_draft_metadata.py` for additive `service_drafts` metadata columns after user confirmation. Phase 05.4 Task 7 created `20260707_0015_stage05_account_status_event_metadata.py` for additive `account_status_events` confidence and risk flag metadata. Phase 05.5 Task 8 reused existing `service_records`, `execution_logs` and `telegram_send_requests` tables without a migration. Task9 created `20260707_0016_stage05_reply_send_link.py` for additive `telegram_send_requests` draft-link and purpose metadata. Task10 Bitable Views required no migration; it reuses existing fact tables and view-service aggregation.
- Current Progress Update: 2026-07-08 Staging migration verification passed: `alembic current` returned `20260707_0016 (head)`. The Stage05 no-op evidence hotfix added ORM relationship wiring for `ServiceRecord`/`ExecutionLog` without a schema change and was verified in staging.

## 1. Migration Principles

- Preserve Stage02-04 data.
- Prefer additive changes over destructive rewrites.
- Do not remove or rename existing columns in Stage05.
- Keep idempotency constraints explicit.
- Do not store raw secrets.
- Do not expose full prompt/raw LLM response in operational views.
- Every Stage05 output must be traceable by `trace_id`.

## 2. Existing Tables Reused

| Table | Stage05 role |
| --- | --- |
| `messages` | Source message and Agent status |
| `service_drafts` | Draft candidates from child agents |
| `agent_runs` | OpenRouter and graph evidence |
| `service_records` | Confirmed business draft evidence |
| `execution_logs` | No-op provider-disabled evidence |
| `telegram_send_requests` | Customer reply allowlisted test send |
| `account_inventory` | Inventory facts and status |
| `account_status_events` | Account risk/block/disabled transitions |
| `ops_audit_events` | Audit evidence |
| `outbox_events` | Runtime delivery |

## 3. `messages` Changes

No new column is strictly required if `intent_status`, `intent_type`, `last_error_code`, `processed_at` and `trace_id` are reused.

Stage05 allowed `intent_status` values:

- `intent_ready`
- `agent_running`
- `routed`
- `manual_review`
- `agent_failed`

Implementation may add tests that assert code recognizes these values. A database enum is not used currently; keep string values to match existing project style.

## 4. `service_drafts` Changes

Existing columns already cover much of Stage05:

- `draft_type`
- `status`
- `customer_id`
- `account_asset_id`
- `account_inventory_id`
- `source_message_id`
- `created_by_type`
- `created_by_id`
- `payload`
- `missing_fields`
- `risk_flags`
- `confidence`
- `trace_id`
- `idempotency_key`

Recommended additive columns:

| Column | Type | Nullable | Purpose |
| --- | --- | --- | --- |
| `source_agent_run_id` | UUID FK `agent_runs.id` | yes | Link draft to generating Agent run |
| `intent_index` | integer | yes | Multi-intent order from Router |
| `payload_summary` | JSONB | yes | Redacted operational summary for views |
| `review_reason` | String(500) | yes | Manual review reason |
| `confirmed_at` | timestamptz | yes | Optional direct evidence of confirmation |

Idempotency:

- Existing `uq_service_drafts_idempotency_key` remains.
- Stage05 keys use `draft:{message_id}:{draft_type}:{intent_index}`.

Draft type values in Stage05:

- `recharge`
- `card_binding`
- `bm_invite`
- `customer_reply`
- `account_assignment`
- `account_status_review`

`account_status_review` is used only for ambiguous or review-needed account status issues. High-confidence automatic block/disabled/risk-control writes `account_status_events` directly and may create audit/review evidence but does not need a draft unless human follow-up is needed.

Task 5 implementation note:

- `20260707_0013_stage05_service_draft_metadata.py` adds `source_agent_run_id`, `intent_index`, `payload_summary`, `review_reason` and `confirmed_at`.
- `intent_type` remains part of the Stage05 draft candidate/output contract and is retained in `payload_summary` and audit context; it was not added as a first-class `service_drafts` column in Task 5 because the confirmed approach avoided that schema expansion.

## 5. `agent_runs` Changes

Existing columns:

- `agent_name`
- `graph_name`
- `model_provider`
- `model_name`
- `prompt_version`
- `input_summary`
- `output_summary`
- `tool_calls`
- `status`
- `trace_id`
- `started_at`
- `completed_at`

Recommended additive columns:

| Column | Type | Nullable | Purpose |
| --- | --- | --- | --- |
| `message_id` | UUID FK `messages.id` | yes | Link run to source message |
| `usage_summary` | JSONB | yes | prompt/completion/total tokens |
| `cost_summary` | JSONB | yes | estimated cost and currency if available |
| `latency_ms` | integer | yes | external/model latency |
| `error_code` | String(120) | yes | safe error code |
| `error_message_redacted` | String(500) | yes | safe error text |
| `created_entity_refs` | JSONB | yes | draft/status/send ids created by run |
| `redaction_policy` | String(80) | yes | e.g. `summary_only` |

Indexes:

- `ix_agent_runs_trace_id` already exists or should remain.
- Add `ix_agent_runs_message_id_started_at`.
- Add `ix_agent_runs_status_started_at`.

Implementation note:

- The original draft used the phrase `message_id_created_at`, but the existing `agent_runs` table has `started_at` and `completed_at`, not `created_at`. Stage05 Task 2 therefore implemented `ix_agent_runs_message_id_started_at` to reuse the existing run-start timestamp instead of adding a duplicate `created_at` column.

No column should store raw API key. Full prompt/raw response columns are not added in Stage05.

## 6. `telegram_send_requests` Changes

Stage05 customer reply send should be linked to the originating draft.

Recommended additive columns:

| Column | Type | Nullable | Purpose |
| --- | --- | --- | --- |
| `source_service_draft_id` | UUID FK `service_drafts.id` | yes | Link send request to `customer_reply` draft |
| `send_purpose` | String(60) | no, default `test_send` | Distinguish Stage04 test send and Stage05 customer reply rehearsal |
| `message_text_summary` | JSONB | yes | Redacted summary for views |

Rules:

- Existing Stage04 rows remain valid with `source_service_draft_id = null`.
- For Stage05 reply sends, `send_purpose = customer_reply_rehearsal`.
- Unique idempotency can be enforced in service layer using `reply-send:{draft_id}`; a database unique column may be added if a persisted idempotency key column is introduced.
- Task9 persists the link columns above. `telegram_send_requests.trace_id = reply-send:{draft_id}` remains the service-level idempotency/reuse key, while `source_service_draft_id` is the Bitable/query linkage.

## 7. `account_inventory` Changes

Existing columns include:

- `platform`
- `external_account_id`
- `inventory_status`
- `assigned_customer_id`
- `assigned_user_id`
- `assigned_at`
- `status_reason`

Recommended status semantics:

- `blocked`
- `disabled`
- `risk_controlled`

If `risk_controlled` is new for data, no database enum change is required because status is a string. Code tests must assert the service accepts it only for high-confidence exception marking.

Recommended additive columns:

| Column | Type | Nullable | Purpose |
| --- | --- | --- | --- |
| `last_risk_signal_at` | timestamptz | yes | Latest high-confidence risk signal |
| `last_risk_source` | String(120) | yes | `stage05_agent`, provider readback, manual, etc. |

These columns are useful but not mandatory for Stage05 if `account_status_events` and audit are sufficient.

## 8. `account_status_events` Changes

Existing table is adequate:

- `account_inventory_id`
- `event_type`
- `before_status`
- `after_status`
- `reason`
- `source_entity_type`
- `source_entity_id`
- `actor_type`
- `actor_id`
- `created_at`

Stage05 event types:

- `risk_controlled`
- `blocked`
- `disabled`
- `manual_review_requested`
- `assignment_proposed`

Recommended additive columns:

| Column | Type | Nullable | Purpose |
| --- | --- | --- | --- |
| `confidence` | Numeric(5,4) | yes | Agent confidence for automatic status mark |
| `risk_flags` | JSONB | yes | Structured risk evidence |

Task 7 implementation note:

- `20260707_0015_stage05_account_status_event_metadata.py` adds `confidence` and `risk_flags`.
- No `account_inventory` columns were added in Task 7 because `account_status_events` and audit are sufficient for the Stage05 local acceptance path.

## 9. `service_records` And `execution_logs`

Existing tables can support business draft confirmation:

- `service_records.status = pending` or `recorded_noop`
- `execution_logs.provider = noop`
- `execution_logs.execution_status = skipped`
- `request_summary` describes disabled provider path
- `response_summary` records no external call occurred

If implementation needs clearer semantics, add allowed service statuses in code constants:

- `recorded`
- `recorded_noop`
- `blocked_provider_disabled`

No real provider execution rows should appear with external provider names during Stage05 staging.

## 10. Migration Order

Recommended Alembic revisions:

1. `20260707_0012_stage05_agent_run_evidence`
   - Extend `agent_runs`.
2. `20260707_0013_stage05_service_draft_metadata`
   - Extend `service_drafts`.
3. `20260707_0015_stage05_account_status_event_metadata`
   - Extend `account_status_events` with confidence/risk columns.
4. `20260707_0016_stage05_reply_send_link`
   - Extend `telegram_send_requests`.

Implementation order note:

- Task 7 was implemented before the later customer-reply send-link task, so Alembic currently advances from `20260707_0013` to `20260707_0015`.
- The reply-send migration uses `down_revision = "20260707_0015"` and advances the Stage05 head to `20260707_0016`; it did not create a second Alembic head.

If one revision is simpler, it must still keep changes additive and easy to audit.

## 11. Rollback Considerations

Stage05 migrations are additive. Rollback can drop new indexes/columns, but production rollback is out of Stage05 scope. Staging rollback must not delete Stage04 evidence tables.

Before staging migration:

- Record current Alembic revision.
- Confirm no secrets in migration scripts.
- Run offline SQL generation locally.

After migration:

- Verify `alembic current`.
- Verify Stage04 views still work.
- Verify `service_drafts`, `agent_runs`, `telegram_send_requests`, `account_status_events` can be queried.
