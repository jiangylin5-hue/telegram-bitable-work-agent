# Stage08 Package B — Task B3 SDD Brief

## Status

- Status: approved / ready for task-level TDD
- Scope: confirmed `RecordChangeDraft` creates a reference-only Memory outbox event; its materializer rebuilds a permitted projection and delegates to Task B2.
- Confirmed inputs: `PlatformTable.settings["memory_policy"]` version 1 mapping; Task B4 minimum candidate confidence `0.85`.
- Out of scope: Telegram send/read, LLM/Provider calls, Redis, new public API, permission-role change, vector/RAG, deployment.

## Preconditions and source of truth

- Read `project-docs/08-implementation/STAGE_08_DATA_API_SECURITY_CONTRACT.md` section 7 before implementation.
- Reuse `confirm_record_change_draft` only after it has created/updated its record and emitted the existing confirmation audit event.
- Reuse B2 `materialize_memory_from_projection`; never write `Stage08MemoryItem` directly from this task.
- Outbox storage reuses `OutboxEvent`; no queue table or migration is permitted.

## Reconciliation gate

The confirmed policy includes `identity_field_keys`, but B2 currently derives same-identity only from scope. The user approved the internal field below:

```python
class MemoryScopeProjection(_StrictMemoryModel):
    # existing public scope fields...
    identity_token: str | None = None  # server generated only; HMAC-SHA256 hex
```

The materializer must compute `identity_token` from canonical `{policy_version, table_id, memory_type, identity_field_values}` using the dedicated server-owned `STAGE08_MEMORY_IDENTITY_HMAC_KEY`; it must not store, return, log, accept, or include raw values in events. Safe read projections exclude `identity_token`. This changes an internal typed projection and deployment configuration, but not database schema, public request schema, or permissions. Tests inject a fixed test key; the key must not reuse Telegram, provider or webhook secrets.

## Required interfaces

```python
def enqueue_confirmed_record_memory_event(
    uow: Stage06RuntimeUnitOfWork,
    draft: RecordChangeDraft,
    record: PlatformRecord,
    *,
    confirmation_actor: Actor,
    now: datetime,
) -> OutboxEvent | None: ...

def materialize_stage08_memory_outbox_event(
    uow: Stage06PlatformUnitOfWork,
    event_id: UUID,
    *,
    actor: Actor,
    now: datetime,
) -> Stage08MemoryItem | None: ...
```

Payload exact keys are `workspace_id`, `table_id`, `record_id`, `record_version`, `policy_version`, and `rule_index`. It is reference-only. Idempotency covers the same six values. The illustrative older plan assertion that omitted `table_id` is superseded by BDD B-02 and the current data/security contract.

The approved B3 enqueue interface is singular. A `memory_policy.rules` list must therefore contain exactly one valid rule; zero or multiple rules fail closed with no event. Multi-rule materialization requires a separately approved multi-event contract.

## TDD cases required before implementation

1. A confirmed create and update draft on a configured active table enqueues exactly one reference-only event after the existing audit; materialization writes the B2-derived decision Memory with only policy-listed readable payload fields.
2. A pending/rejected/failed draft, unconfigured table, invalid policy, unreadable policy field, stale record version, invalid scope reference, or inactive resource yields no Memory and no terminal success.
3. Event payload has exactly the six reference keys and no value, field key, HMAC token, raw chat, prompt/response, provider or Telegram content.
4. `identity_field_keys` changes same-identity behavior: same customer + subject compares into one lifecycle chain; a different subject does not conflict merely because table/customer/project scope is the same.
5. The safe reader never returns `identity_token`; no client entry point can supply it.
6. Replaying the same confirmation/event is idempotent. Adapter makes no `create_record`, `update_record`, Telegram, Provider or direct ORM write.

## Required task report

Write `.superpowers/sdd/stage08-package-b-task-b3-report.md` with changed files, test RED/GREEN evidence, exact commands/results, exclusions, risk notes, and no-external-call statement. Do not stage, commit, reset, checkout, clean, or modify unrelated Stage07/user changes.
