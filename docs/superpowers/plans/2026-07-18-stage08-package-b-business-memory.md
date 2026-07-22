# Stage08 Package B Business Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` task-by-task. Each task requires a fresh implementer, focused TDD, a task-scoped independent review, and a progress-ledger entry.

**Goal:** Build versioned, attributable, revocable business memory from confirmed table events and controlled Telegram group extraction candidates, while never retaining raw chat text, raw provider content, hidden fields, or unauthorized projections.

**Architecture:** PostgreSQL remains the source of truth. `Stage08MemoryItem` and `Stage08MemoryExtractionCandidate` persist only typed, projection-safe payloads and source references. Confirmed table mutations enqueue a non-content outbox job; a deterministic materializer derives the configured safe field projection, writes idempotent memory, and records a redacted audit. Telegram group processing creates candidates only; promotion requires the same scope, confidence, conflict and audit checks. Read paths synchronously revalidate current source and permission state before returning a memory projection.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL JSONB, existing `OutboxEvent`, existing Stage06 authorization/audit/UoW patterns. No vector database, provider call, Telegram send, Redis worker, external network call, or new permission role is added in Package B.

## Global Constraints

- The authoritative statuses are exactly `active`, `conflicted`, `superseded`, `revoked`, `expired`, `deleted` for memory and `candidate`, `accepted`, `rejected`, `expired` for extraction candidates.
- Scope always contains `workspace_id`; customer, project, group, base, table and view only narrow visibility and never enlarge it.
- `payload`, source references, audit records and outbox payloads must never contain full chat text, raw prompt/response, hidden field values, provider keys, Telegram user IDs, record values not named by a memory policy, or chain-of-thought.
- A table event is eligible only after its `RecordChangeDraft` has been confirmed. Pending/rejected drafts must never enqueue or materialize memory.
- The package reuses `OutboxEvent` with a reference-only payload; it does not create a parallel queue table or invoke Redis in this implementation.
- Read, revoke, expiry and deletion fail closed. A deleted/revoked/expired source, inactive workspace membership, inaccessible record or unreadable field means no projection is returned.
- No direct ORM write may occur from a digital employee, and no memory path may confirm a draft, modify a source record, send Telegram, call a provider, or bypass audit.
- Do not stage, commit, reset, checkout or clean the current dirty worktree.

## File Map

| File | Responsibility |
| --- | --- |
| `backend/app/models/stage08_memory.py` | Persistent memory/candidate models, JSONB and lifecycle constraints. |
| `backend/alembic/versions/20260718_0029_stage08_business_memory.py` | Schema migration following `20260717_0028`. |
| `backend/app/runtime/stage08_memory_contracts.py` | Strict typed source, scope, payload, policy and lifecycle contracts. |
| `backend/app/services/stage08_memory.py` | Policy parsing, outbox creation/materialization, conflict/version lifecycle and safe reads. |
| `backend/app/services/stage06_platform.py` | Package-B UoW methods for both in-memory and SQLAlchemy implementations. |
| `backend/app/services/stage06_digital_employees.py` | One post-confirmation hook that enqueues a reference-only memory event. |
| `backend/app/schemas/stage08_memory.py` | Strict revoke/list API DTOs without raw source payload. |
| `backend/app/api/routes/stage08_memory.py` | Memory list and candidate revoke endpoints using verified identity. |
| `backend/app/main.py` | Stage08 Memory router registration. |
| `backend/tests/unit/test_stage08_memory_contracts.py` | Contract and sensitive-key rejection tests. |
| `backend/tests/unit/test_stage08_memory_service.py` | In-memory materialization, conflict, lifecycle and no-raw tests. |
| `backend/tests/unit/test_stage08_memory_api.py` | Identity, scope, redacted response and revoke API tests. |
| `backend/tests/integration/test_stage08_memory_postgres.py` | Migration, JSONB/check, idempotency and read-fail-closed evidence. |
| `project-docs/08-implementation/STAGE_08_PACKAGE_B_MEMORY_BDD_AND_ACCEPTANCE.md` | BDD scenarios and requirement mapping. |
| `project-docs/08-implementation/evidence/stage08-package-b-memory.md` | RED/GREEN, PostgreSQL and no-external-call evidence. |

---

### Task B1: Persistent contracts, models, migration and UoW

**Files:** Create `backend/app/models/stage08_memory.py`, `backend/alembic/versions/20260718_0029_stage08_business_memory.py`, `backend/tests/unit/test_stage08_memory_contracts.py`, `backend/tests/integration/test_stage08_memory_postgres.py`; modify `backend/app/models/__init__.py`, `backend/app/services/stage06_platform.py`.

**Produces:**

```python
class Stage08MemoryItem(Base):
    workspace_id: UUID
    memory_type: str
    status: str
    scope: dict
    payload: dict
    source_refs: list
    source_fingerprint: str
    version: int
    supersedes_id: UUID | None
    valid_until: datetime | None
    revoked_at: datetime | None
    deleted_at: datetime | None

class Stage08MemoryExtractionCandidate(Base):
    workspace_id: UUID
    candidate_type: str
    status: str
    confidence: Decimal
    scope: dict
    normalized_payload: dict
    source_refs: list
    source_fingerprint: str
    valid_until: datetime | None
```

`Stage06PlatformUnitOfWork` gains exact add/get/list/lock methods for both entities. The in-memory UoW stores lists; SQLAlchemy uses `session.add`, `session.get` and `select(...).with_for_update()` for lifecycle transitions.

- [ ] **Step 1: Write failing model/round-trip tests**

```python
def test_memory_models_reject_non_object_scope_payload_and_non_array_sources(postgres_uow):
    item = _memory_item(scope=[], payload={}, source_refs=[])
    postgres_uow.add_memory_item(item)
    with pytest.raises(IntegrityError):
        postgres_uow.session.commit()

def test_memory_source_fingerprint_is_unique_per_workspace_and_memory_type(postgres_uow):
    postgres_uow.add_memory_item(_memory_item(source_fingerprint="f" * 64))
    postgres_uow.add_memory_item(_memory_item(source_fingerprint="f" * 64))
    with pytest.raises(IntegrityError):
        postgres_uow.session.commit()
```

- [ ] **Step 2: Verify RED**

Run: `Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/integration/test_stage08_memory_postgres.py -k "memory"; Pop-Location`  
Expected: import/model/table failure before implementation.

- [ ] **Step 3: Implement minimal persistent model**

Create checks for canonical statuses, `jsonb_typeof(scope) = 'object'`, `jsonb_typeof(payload/normalized_payload) = 'object'`, `jsonb_typeof(source_refs) = 'array'`, positive version and confidence in `[0,1]`. Add a unique `(workspace_id, memory_type, source_fingerprint)` index for items and `(workspace_id, candidate_type, source_fingerprint)` for candidates. Add lifecycle/read indexes `(workspace_id, status, valid_until)`.

- [ ] **Step 4: Implement migration and UoW parity**

Migration revision must depend on `20260717_0028`. The SQL UoW must expose only model-oriented methods, never raw SQL helpers. In-memory and SQL return the same ordering: newest `created_at`, then `id` descending.

- [ ] **Step 5: Verify GREEN**

Run: `Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/integration/test_stage08_memory_postgres.py -k "memory"; Pop-Location`  
Expected: PASS; PostgreSQL evidence covers constraints, unique fingerprints and lock acquisition.

---

### Task B2: Typed projections and safe-memory lifecycle service

**Files:** Create `backend/app/runtime/stage08_memory_contracts.py`, `backend/app/services/stage08_memory.py`, `backend/tests/unit/test_stage08_memory_service.py`.

**Consumes:** B1 models/UoW and existing Stage06 actor, field permission and audit services.

**Produces:**

```python
class MemorySourceRef(BaseModel):
    source_kind: Literal["platform_record", "record_change_draft", "telegram_message"]
    source_id: UUID
    source_version: int | None
    field_keys: tuple[str, ...]

class MemoryScopeProjection(BaseModel):
    workspace_id: UUID
    base_id: UUID | None = None
    table_id: UUID | None = None
    customer_record_id: UUID | None = None
    project_record_id: UUID | None = None
    group_chat_ref: str | None = None

def materialize_memory_from_projection(uow, projection, *, actor, now) -> Stage08MemoryItem: ...
def read_memory_projection(uow, item_id, *, actor, now) -> dict[str, object] | None: ...
def revoke_memory_candidate(uow, candidate_id, *, actor, expected_version, now) -> Stage08MemoryExtractionCandidate: ...
```

- [ ] **Step 1: Write failing lifecycle tests**

```python
def test_conflicting_fact_creates_new_conflicted_version_without_overwriting_active_item():
    active = materialize_memory_from_projection(uow, _fact("customer", "A"), actor=owner, now=NOW)
    conflict = materialize_memory_from_projection(uow, _fact("customer", "B"), actor=owner, now=NOW)
    assert active.status == "active"
    assert conflict.status == "conflicted"
    assert conflict.supersedes_id is None

def test_expired_or_revoked_source_returns_none_even_when_item_is_active():
    item = materialize_memory_from_projection(uow, _fact(), actor=owner, now=NOW)
    item.valid_until = NOW - timedelta(seconds=1)
    assert read_memory_projection(uow, item.id, actor=owner, now=NOW) is None
```

- [ ] **Step 2: Verify RED**

Run: `Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_service.py; Pop-Location`  
Expected: missing contract/service failure.

- [ ] **Step 3: Implement strict contracts and service**

Contract validators reject any recursive key in `{prompt,response,raw_text,normalized_text,api_key,token,telegram_user_id}` and require source IDs, scope IDs and field keys to be typed. A materialization accepts only `decision`, `preference`, `risk`, `customer_fact`, `project_fact`; it computes a deterministic source fingerprint from the safe typed projection. Same fingerprint is idempotent. Same identity key with equivalent payload supersedes the old active version; a different payload produces `conflicted`, never overwrites. All creates/transitions emit redacted audit events.

- [ ] **Step 4: Implement fail-closed read and lifecycle**

Read re-checks active workspace membership, scope narrowing, `valid_until`, item status, every source reference existence/version and named source field visibility. Revocation sets candidate/item status without deleting source facts; deletion marks `deleted` and returns no payload. No service return may include `source_refs` internals beyond permitted identifiers.

- [ ] **Step 5: Verify GREEN**

Run: `Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py; Pop-Location`  
Expected: PASS for idempotency, conflict, supersede, TTL, revoke, cross-workspace denial and raw-content rejection.

---

### Task B3: Confirmed-table event adapter and reference-only outbox

**Files:** Modify `backend/app/services/stage06_digital_employees.py`, `backend/app/services/stage06_platform.py`, `backend/app/services/stage08_memory.py`; create `backend/tests/unit/test_stage08_memory_confirmed_record.py`.

**Consumes:** `confirm_record_change_draft`, B1/B2 UoW/service, existing `OutboxEvent`.

**Produces:**

```python
def enqueue_confirmed_record_memory_event(uow, draft, record, *, confirmation_actor, now) -> OutboxEvent | None: ...
def materialize_stage08_memory_outbox_event(uow, event_id, *, actor, now) -> Stage08MemoryItem | None: ...
```

Table configuration uses the existing `PlatformTable.settings["memory_policy"]` shape below; unconfigured tables return `None` and create no event:

```json
{
  "version": 1,
  "rules": [{
    "memory_type": "decision",
    "identity_field_keys": ["customer", "subject"],
    "payload_field_keys": ["decision", "status"],
    "scope_field_keys": {"customer_record_id": "customer", "project_record_id": "project"},
    "valid_for_days": 90
  }]
}
```

- [ ] **Step 1: Write failing event tests**

```python
def test_confirmed_draft_enqueues_reference_only_memory_event_then_materializes_one_item():
    draft = _confirm_memory_enabled_draft()
    event = enqueue_confirmed_record_memory_event(uow, draft, record, confirmation_actor=owner, now=NOW)
    assert event.payload == {"workspace_id": str(workspace.id), "record_id": str(record.id), "record_version": record.version, "policy_version": 1}
    item = materialize_stage08_memory_outbox_event(uow, event.id, actor=owner, now=NOW)
    assert item.payload == {"decision": "approved", "status": "open"}

def test_pending_or_rejected_draft_never_enqueues_memory_event():
    assert enqueue_confirmed_record_memory_event(uow, _pending_draft(), record, confirmation_actor=owner, now=NOW) is None
```

- [ ] **Step 2: Verify RED**

Run: `Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_confirmed_record.py; Pop-Location`  
Expected: missing adapter failure.

- [ ] **Step 3: Implement reference-only outbox**

Only the existing post-confirmation service calls the adapter after record creation/update and its audit. The outbox payload contains workspace/table/record IDs, record version, rule/policy version and no field values. Its idempotency key uses workspace, record, record version and policy version. The materializer rereads the current record, accepts only policy-listed readable fields, constructs B2’s projection and marks the outbox terminal only after the memory/audit transition succeeds.

- [ ] **Step 4: Verify no confirmation/write bypass**

Run: `Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_confirmed_record.py tests/unit/test_stage08_tool_gateway.py; Pop-Location`  
Expected: PASS; pending/rejected drafts create neither event nor item; the adapter never calls `create_record`, `update_record`, Telegram or a provider.

---

### Task B4: Controlled group candidate extraction, conflict decision and APIs

**Files:** Create `backend/app/schemas/stage08_memory.py`, `backend/app/api/routes/stage08_memory.py`, `backend/tests/unit/test_stage08_memory_api.py`, `project-docs/08-implementation/STAGE_08_PACKAGE_B_MEMORY_BDD_AND_ACCEPTANCE.md`; modify `backend/app/main.py`, `backend/app/services/stage08_memory.py`.

**Consumes:** B1/B2 memory lifecycle; a source adapter that resolves an already-authorized `telegram_message` to a short-lived in-process projection. It must never persist the raw message or add a provider call.

**Produces:**

```python
GET  /api/stage08/memory?workspace_id=<uuid>&status=active
POST /api/stage08/memory/extractions/{candidate_id}/revoke

def create_group_memory_candidate(uow, projection, *, actor, now) -> Stage08MemoryExtractionCandidate: ...
def resolve_group_candidate(uow, candidate_id, *, actor, now) -> Stage08MemoryItem | None: ...
```

- [ ] **Step 1: Write failing API/candidate tests**

```python
def test_group_candidate_keeps_only_normalized_payload_and_message_reference():
    candidate = create_group_memory_candidate(uow, _high_confidence_group_projection(), actor=owner, now=NOW)
    assert "raw_text" not in candidate.normalized_payload
    assert candidate.status == "candidate"

def test_memory_api_denies_foreign_workspace_and_revoke_requires_expected_version(client):
    assert client.get(f"/api/stage08/memory?workspace_id={foreign_workspace.id}").status_code == 403
    assert client.post(f"/api/stage08/memory/extractions/{candidate.id}/revoke", json={"expected_version": 99}).status_code == 409
```

- [ ] **Step 2: Verify RED**

Run: `Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_api.py -q; Pop-Location`  
Expected: route/schema/service missing.

- [ ] **Step 3: Implement candidate decision and API**

Candidate creation accepts only structured safe projection with a trusted message reference, allowed type, confidence at or above the deployment configuration threshold, and a chat binding that narrows to the workspace. It persists `candidate` first. The conflict detector then promotes to an `active` memory only when there is no unequal active fact for the same identity key; otherwise it sets `conflicted`. `GET` calls existing verified identity and `workspace.read`, then B2 safe read. Revoke uses the existing `member.manage` workspace action (therefore owner/admin only), requires expected version and writes a redacted audit. Both responses contain status, type, version and permitted payload projection only.

- [ ] **Step 4: Verify GREEN**

Run: `Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_api.py tests/unit/test_stage08_memory_service.py; Pop-Location`  
Expected: PASS; no raw chat text, unauthorized source or stale candidate is readable.

---

### Task B5: PostgreSQL lifecycle evidence and Package-B closure record

**Files:** Modify `backend/tests/integration/test_stage08_memory_postgres.py`; create `project-docs/08-implementation/evidence/stage08-package-b-memory.md`; update `.superpowers/sdd/progress.md` and `project-docs/08-implementation/STAGE_08_IMPLEMENTATION_PLAN.md` after clean review.

- [ ] **Step 1: Add PostgreSQL acceptance tests**

```python
@pytest.mark.postgres
def test_postgres_memory_revocation_and_source_invalidation_fail_closed(stage06_postgres):
    item = _materialized_memory(stage06_postgres)
    revoke_memory_item(stage06_postgres, item.id, actor=owner, now=NOW)
    assert read_memory_projection(stage06_postgres, item.id, actor=owner, now=NOW) is None
```

- [ ] **Step 2: Verify RED**

Run: `Push-Location backend; python -m pytest -q tests/integration/test_stage08_memory_postgres.py -m postgres; Pop-Location`  
Expected: new lifecycle assertion fails before the final persistence repair.

- [ ] **Step 3: Close constraints and local evidence**

Record exact migration head, JSONB/status/index evidence, event idempotency proof, cross-workspace denial, TTL/delete/revoke fail-closed proof, audit redaction scan and explicit statement that no real Provider/Telegram/deployment call ran.

- [ ] **Step 4: Verify Package B module suite**

Run: `Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_memory_confirmed_record.py tests/unit/test_stage08_memory_api.py tests/integration/test_stage08_memory_postgres.py; Pop-Location`  
Expected: PASS, subject to configured local PostgreSQL availability.

## Pre-execution decision gate

Task B3 uses the existing generic `PlatformTable.settings["memory_policy"]` JSONB as the only table-to-memory mapping. This is an implementation detail not yet enumerated in the Stage08 API contract, although it realizes the confirmed rule that *confirmed table events automatically write structured memory*. Before B3 code begins, record the user’s acceptance of this policy shape or replace it with an approved equivalent. Tasks B1/B2 remain schema-contract work directly derived from the approved Stage08 Memory objects and can proceed independently.

## Self-review

- Source/version/conflict/TTL/delete/revoke requirements map to B1, B2 and B5.
- Confirmed table event, controlled group candidate, audit and safe read requirements map to B3 and B4.
- The plan contains no vector indexing, file-to-memory automation, external provider, Telegram sending, broad acceptance sweep or new permission role.
- All write paths use existing services/outbox/audit and retain the draft-confirmation boundary.
