# Stage07 F2 Relation and Lookup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not start any task until the user separately gives explicit implementation approval for the proposed API/data/permission changes.

**Goal:** Deliver a safe, same-Base relation and nested/aggregated lookup slice that is persisted through records and visible in the Stage07 Mini App without exposing raw configuration, hidden data or client-side joins.

**Architecture:** Two dedicated F2 initializer routes create `linked_record` and `lookup` fields atomically using the existing table-lock/idempotency/audit pattern. Existing record create/PATCH routes remain the only relation write path and gain server-side target revalidation; safe read models project relations as `{ id, label }` and evaluate lookups on the server. The React Mini App adds protected candidate queries plus relation/lookup builder and picker components while retaining TD001 generation/cancellation boundaries.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, SQLAlchemy 2.x, PostgreSQL JSONB and Alembic baseline; React, TypeScript, Vite, TanStack Query v5, Tailwind-compatible CSS, lucide-react, Vitest and Testing Library. No new package, migration, role/capability, browser persistence or client-side data engine is authorized.

## Global Constraints

- Implement only the approved F2 design in `docs/superpowers/specs/2026-07-11-stage07-f2-relation-lookup-design.md`.
- Do not create reverse fields, cross-Base links, a third lookup level, arbitrary DSL, automatic unlink/cascade delete, field edit/delete UI, V1 views, imports, governance, Bot, Telegram or production work.
- F2 field initialization must use one transaction, source-table lock, server-generated key/order, server-only view updates, idempotency replay/conflict and sanitized audit.
- Browser requests/receipts/schema/form models must not contain raw relation/lookup configuration, policy, default values, roles, audit body or hidden data.
- Reuse existing `field.manage`, `table.read`, `record.read`, field-read and record create/update checks. Do not add capability names or role schema.
- Relation candidate/result/query keys always begin with verified `userId` and `workspaceId`; 401/403/session/workspace behavior must retain TD001 fail-closed semantics.
- No migration is planned. Stop work and request a new user decision if implementation requires a migration, package, permission capability, persistent cache or contract beyond the approved specification.
- Current backend has no public record/field delete route. F2 must not add one incidentally; it supplies testable dependency-guard helpers for future deletion paths and does not add delete UI.
- Every behavior change begins with a focused failing test, is implemented minimally, then verified before moving forward.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `backend/app/schemas/stage06_platform.py` | F2 Pydantic request/response models, candidate page and safe create-form field ID. |
| `backend/app/services/stage06_platform.py` | F2 domain validation, UoW helpers, atomic initializers, candidate projection, relation/lookup read projection, write rechecks and reusable deletion guards. |
| `backend/app/api/routes/stage06_platform.py` | Dedicated F2 routes, existing create/PATCH safe response projection and consistent HTTP/idempotency mapping. |
| `backend/tests/unit/test_stage07_relation_lookup.py` | In-memory domain/API boundary tests for all F2 behavior. |
| `backend/tests/unit/test_stage07_mini_app_api.py` | Safe Mini App response redaction tests extended for F2 projections. |
| `backend/tests/integration/test_stage07_relation_lookup_postgres.py` | Disposable PostgreSQL rollback, replay, lock/concurrency and guard evidence. |
| `mini-app/src/app/api.ts` | F2 transport types, safe code allowlist and API methods. |
| `mini-app/src/app/protectedQuery.ts` | Candidate query-key helper and exact F2 invalidation helper. |
| `mini-app/src/app/RelationLookupFieldBuilderPanel.tsx` | F2 relation/lookup field builder drawer/sheet with safe local validation/idempotency UI. |
| `mini-app/src/app/RelationPicker.tsx` | Shared protected server-search/cursor multi-select relation picker. |
| `mini-app/src/app/FieldBuilderPanel.tsx` | Launch path from the existing Add Field UI into F2 builder without changing F1 request semantics. |
| `mini-app/src/app/CreateRecordPanel.tsx` | Writable `linked_record` fields, required validation and shared Picker integration. |
| `mini-app/src/app/RecordDetail.tsx` | Relation chip display/edit and read-only lookup presentation. |
| `mini-app/src/app/BaseCanvas.tsx` | Safe relation chip and lookup-cell formatting in Grid/Kanban/Calendar/Form renderers. |
| `mini-app/src/app/App.tsx` | F2 builder mode, protected reread/invalidation and generation-safe callbacks. |
| `mini-app/src/styles.css` | Light desktop drawer/mobile sheet and accessible relation-chip/picker styles. |
| `mini-app/src/test/f2-field-builder-panel.test.tsx` | F2 field-builder UI and error-boundary tests. |
| `mini-app/src/test/relation-picker.test.tsx` | Candidate search/cursor/selection/cancellation tests. |
| `mini-app/src/test/relation-lookup-flow.test.tsx` | App integration: field receipt reread, record write, safe render, denial and scope switch. |
| Existing `mini-app/src/test/*` | Focused updates to create/detail/renderer/api/protected-query regressions. |
| Stage07 source documents | Contract, SDD, BDD, test plan, traceability, acceptance and handoff evidence after actual implementation. |

## Task 1: Establish F2 schema and safe transport contracts

**Files:**

- Modify: `backend/app/schemas/stage06_platform.py`
- Modify: `mini-app/src/app/api.ts`
- Test: `backend/tests/unit/test_stage07_relation_lookup.py`
- Test: `mini-app/src/test/api.test.ts`

**Consumes:** Existing `FieldInitializationResponse`, `CreateFormResponse`, `SafeTableFieldResponse`, typed `api` transport and the approved F2 specification.

**Produces:** Stable safe request/receipt/candidate/form interfaces used by all following tasks.

- [ ] **Step 1: Write failing schema and transport tests.**

```python
def test_f2_initializer_models_forbid_raw_configuration_and_candidate_page_is_safe() -> None:
    assert InitializeRelationFieldRequest.model_validate({
        "name": "关联客户", "target_table_id": str(uuid4()), "required": True,
    }).required is True
    with pytest.raises(ValidationError):
        InitializeLookupFieldRequest.model_validate({
            "name": "金额", "source_relation_field_id": str(uuid4()),
            "target_field_id": str(uuid4()), "aggregation": "sum", "options": {},
        })
```

```ts
test('posts only approved F2 initializer keys and parses safe candidate records', async () => {
  // Mock fetch and assert no raw options/policy is sent or retained.
})
```

- [ ] **Step 2: Run focused tests and verify they fail because F2 models/methods do not exist.**

Run:

```powershell
cd backend; python -m pytest -q tests/unit/test_stage07_relation_lookup.py -k schema
cd ..\mini-app; npm.cmd test -- --run src/test/api.test.ts
```

Expected: import/type failures for `InitializeRelationFieldRequest`, `InitializeLookupFieldRequest` and F2 transport methods.

- [ ] **Step 3: Add exact safe Pydantic and TypeScript contracts.**

```python
class InitializeRelationFieldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    target_table_id: str
    required: bool = False

class InitializeLookupFieldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    source_relation_field_id: str
    target_field_id: str
    aggregation: Literal[
        "values", "count", "count_distinct", "sum", "average", "min", "max"
    ]

class RelationCandidateResponse(BaseModel):
    id: str
    label: str

class RelationCandidatePageResponse(BaseModel):
    field_id: str
    records: list[RelationCandidateResponse]
    next_cursor: str | None
    has_more: bool
```

Extend `CreateFormFieldResponse` with `id: str`. In `api.ts`, add `RelationCell`, `RelationCandidatePage`, `RelationFieldInitializationValues`, `LookupFieldInitializationValues`, both initializer methods and `relationCandidates(fieldId, query, cursor, init)`. Expand `SafeApiErrorCode` only with the approved F2 safe-code allowlist; never parse message text.

- [ ] **Step 4: Re-run focused tests.**

Run the Step 2 commands.

Expected: PASS; unsafe request extras and server detail remain unavailable to the typed browser transport.

- [ ] **Step 5: Commit the schema/transport contract.**

```powershell
git add backend/app/schemas/stage06_platform.py backend/tests/unit/test_stage07_relation_lookup.py mini-app/src/app/api.ts mini-app/src/test/api.test.ts
git commit -m "feat(stage07): define safe F2 transport contracts"
```

## Task 2: Add relation UoW helpers and atomic relation-field initializer

**Files:**

- Modify: `backend/app/services/stage06_platform.py`
- Modify: `backend/app/api/routes/stage06_platform.py`
- Test: `backend/tests/unit/test_stage07_relation_lookup.py`

**Consumes:** Task 1 models; existing `initialize_field`, `_run_atomic_builder_initialization`, `fingerprint_request`, table lock, authorization and audit patterns.

**Produces:** `initialize_relation_field(...) -> FieldInitializationResult` and its safe idempotent route.

- [ ] **Step 1: Write failing relation-initializer tests.**

```python
def test_initialize_relation_field_uses_same_base_target_and_appends_only_explicit_views() -> None:
    result = initialize_relation_field(
        uow, source.id, name="关联客户", target_table_id=target.id,
        required=True, actor=owner,
    )
    assert result.field.field_type == "linked_record"
    assert result.field.options == {"target_table_id": str(target.id)}
    assert explicit_view.config["fields"][-1] == result.field.key
    assert "target_table_id" not in safe_table_schema_field(result.field)["options"]

def test_relation_initializer_rejects_cross_base_target_before_durable_write() -> None:
    with pytest.raises(PlatformValidationError, match="resource_scope_mismatch"):
        initialize_relation_field(...)
```

Add route tests for first `201`, same-key `200`, changed payload `409`, missing `field.manage` generic denial and receipt redaction.

- [ ] **Step 2: Run focused tests and verify the initializer/route are missing.**

Run:

```powershell
cd backend; python -m pytest -q tests/unit/test_stage07_relation_lookup.py -k relation_initializer
```

Expected: FAIL because `initialize_relation_field` and the dedicated route are undefined.

- [ ] **Step 3: Implement minimal relation initialization.**

Add a dedicated service that locks the source table, resolves `target_table_id`, requires same Base and uses the existing duplicate-name/key/order/view/audit mechanics. Its only persisted `options` are:

```python
{"target_table_id": str(target_table.id)}
```

Add:

```python
@router.post(
    "/tables/{table_id}/relation-field-initializations",
    response_model=FieldInitializationResponse,
    status_code=status.HTTP_201_CREATED,
)
def initialize_relation_field_endpoint(...):
    workspace_id = workspace_id_for_table(uow, table_id)
    actor = authorize_workspace_action(uow, identity, workspace_id, "field.manage")
    # Build a stage07.relation_field.initialize fingerprint and safe receipt.
```

The route must independently check target-table readability without exposing a target table name/ID on 403/404. Reuse F1 `Idempotency-Key` and `FieldInitializationResponse`; do not extend F1's generic endpoint.

- [ ] **Step 4: Run focused tests.**

Run the Step 2 command.

Expected: PASS; one field/audit/view update survives a replay and no raw relation config reaches the receipt/schema.

- [ ] **Step 5: Commit the relation initializer.**

```powershell
git add backend/app/services/stage06_platform.py backend/app/api/routes/stage06_platform.py backend/tests/unit/test_stage07_relation_lookup.py
git commit -m "feat(stage07): add atomic relation field initializer"
```

## Task 3: Add lookup initializer, dependency graph and fixed aggregation validation

**Files:**

- Modify: `backend/app/services/stage06_platform.py`
- Modify: `backend/app/api/routes/stage06_platform.py`
- Test: `backend/tests/unit/test_stage07_relation_lookup.py`

**Consumes:** Task 2 relation config and atomic initializer pattern.

**Produces:** `initialize_lookup_field(...) -> FieldInitializationResult`, stable internal lookup config and dependency validation.

- [ ] **Step 1: Write failing lookup tests.**

```python
@pytest.mark.parametrize("aggregation", ["values", "count", "count_distinct", "sum", "average", "min", "max"])
def test_lookup_initializer_accepts_only_compatible_fixed_aggregations(aggregation: str) -> None:
    result = initialize_lookup_field(..., aggregation=aggregation, actor=owner)
    assert result.field.field_type == "lookup"

def test_lookup_initializer_rejects_cycle_and_third_lookup_level() -> None:
    with pytest.raises(PlatformValidationError) as cycle:
        initialize_lookup_field(...)
    assert cycle.value.code == "lookup_dependency_cycle"
```

Cover a relation source from another Base, source not `linked_record`, hidden target field, `sum` over text, `values` on permitted scalar/multi-select values, legacy key-config read compatibility and safe receipt redaction.

- [ ] **Step 2: Run tests and verify they fail.**

Run:

```powershell
cd backend; python -m pytest -q tests/unit/test_stage07_relation_lookup.py -k lookup_initializer
```

Expected: FAIL because `initialize_lookup_field` and graph helpers are absent.

- [ ] **Step 3: Implement fixed lookup configuration and graph helpers.**

Implement exact helpers with stable IDs:

```python
LOOKUP_AGGREGATIONS = frozenset({
    "values", "count", "count_distinct", "sum", "average", "min", "max",
})
NUMERIC_LOOKUP_AGGREGATIONS = frozenset({"sum", "average", "min", "max"})

def initialize_lookup_field(
    uow: Stage06PlatformUnitOfWork, table_id: UUID, *, name: str,
    source_relation_field_id: UUID, target_field_id: UUID,
    aggregation: str, actor: Actor,
) -> FieldInitializationResult: ...
```

Store only `source_field_id`, `target_field_id` and `aggregation`. Build the lookup dependency graph from F2 stable-ID configurations plus legacy key configurations; reject a cycle and a path with more than two lookup nodes. Numeric aggregate validation accepts only `number`; `linked_record`, `json` and formula are never target values. Use a separate `stage07.lookup_field.initialize` idempotency operation and sanitized audit event.

- [ ] **Step 4: Run focused tests.**

Run the Step 2 command.

Expected: PASS; all enum/type/depth/cycle decisions are enforced before a field, audit or view update persists.

- [ ] **Step 5: Commit lookup initialization.**

```powershell
git add backend/app/services/stage06_platform.py backend/app/api/routes/stage06_platform.py backend/tests/unit/test_stage07_relation_lookup.py
git commit -m "feat(stage07): add bounded lookup field initializer"
```

## Task 4: Implement safe relation/lookup projections, Candidate Picker and write rechecks

**Files:**

- Modify: `backend/app/services/stage06_platform.py`
- Modify: `backend/app/api/routes/stage06_platform.py`
- Modify: `backend/app/schemas/stage06_platform.py`
- Modify: `backend/tests/unit/test_stage07_relation_lookup.py`
- Modify: `backend/tests/unit/test_stage07_mini_app_api.py`

**Consumes:** Tasks 1–3 F2 contracts/configuration.

**Produces:** Server-only projection and read/write enforcement used by view, detail, create form and existing record mutations.

- [ ] **Step 1: Write failing security/read/write tests.**

```python
def test_relation_candidates_return_only_safe_readable_label_and_cursor() -> None:
    page = list_relation_candidates(uow, relation_field.id, actor=viewer, query="ac", cursor=None, limit=1)
    assert page["records"] == [{"id": str(readable.id), "label": "Acme"}]
    assert "secret" not in repr(page)

def test_lookup_omits_entire_value_when_any_hop_is_unreadable() -> None:
    response = list_view_records(uow, view.id, actor=viewer, limit=50, cursor=None)
    assert "customer_total" not in response["records"][0]["fields"]

def test_patch_rejects_wrong_table_unreadable_or_self_relation_target() -> None:
    with pytest.raises(PlatformValidationError) as error:
        update_record(...)
    assert error.value.code == "invalid_link_target"
```

Add tests for `{id,label}` relation projection, primary/fallback label, missing safe label omission, all aggregation results, required relation create/explicit empty PATCH, create-form field ID, self reference, target readability recheck, stale link synchronization and reusable incoming-link/dependent-field guard functions. Assert generic errors never include target resource detail.

- [ ] **Step 2: Run tests and verify they fail.**

Run:

```powershell
cd backend; python -m pytest -q tests/unit/test_stage07_relation_lookup.py -k "candidate or projection or relation_write or delete_guard"
```

Expected: FAIL because the candidate route, safe relation projection, target actor recheck and guards do not exist.

- [ ] **Step 3: Extend UoW and service logic minimally.**

Add UoW methods for incoming record links and F2 field dependency inspection in both in-memory and SQLAlchemy implementations. Implement:

```python
def list_relation_candidates(
    uow: Stage06PlatformUnitOfWork, field_id: UUID, *, actor: Actor,
    query: str | None, cursor: str | None, limit: int,
) -> dict[str, Any]: ...

def _safe_relation_cells(... ) -> list[dict[str, str]]: ...
def _lookup_field_value(... ) -> list[Any] | int | float | None | object: ...
def assert_record_has_no_incoming_relation_links(... ) -> None: ...
def assert_field_has_no_relation_lookup_dependents(... ) -> None: ...
```

Pass `actor` and, where applicable, the source record ID through relation validation. Reject an explicit empty/null required relation value; allow an omitted field in a partial legacy PATCH. Project safe relation cells and lookup values in `list_view_records` and `read_record_for_actor`; existing create/PATCH HTTP responses must call the safe actor read projection before serialization. Add `id` to safe create-form fields and allow `linked_record` only when writable and picker-safe.

Add the candidate route:

```python
@router.get("/fields/{field_id}/relation-candidates", response_model=RelationCandidatePageResponse)
def list_relation_candidates_endpoint(field_id: UUID, q: str | None = None, cursor: str | None = None, ...): ...
```

No record or field DELETE route is added. The reusable guards are covered at service level for future deletion paths.

- [ ] **Step 4: Run focused tests.**

Run the Step 2 command plus:

```powershell
cd backend; python -m pytest -q tests/unit/test_stage07_mini_app_api.py
```

Expected: PASS; only safe labels/projections appear, hidden hops fail closed and existing record writes cannot bypass target visibility.

- [ ] **Step 5: Commit safe reads/writes and candidate endpoint.**

```powershell
git add backend/app/services/stage06_platform.py backend/app/api/routes/stage06_platform.py backend/app/schemas/stage06_platform.py backend/tests/unit/test_stage07_relation_lookup.py backend/tests/unit/test_stage07_mini_app_api.py
git commit -m "feat(stage07): enforce safe relation lookup reads and writes"
```

## Task 5: Prove transactional and concurrency behavior on disposable PostgreSQL

**Files:**

- Create: `backend/tests/integration/test_stage07_relation_lookup_postgres.py`
- Modify: `backend/tests/integration/test_stage07_field_builder_postgres.py` only if its reusable fixture needs a general name; otherwise leave it unchanged.

**Consumes:** Tasks 2–4 plus existing Stage07 disposable PostgreSQL fixture conventions.

**Produces:** Real database evidence for F2's transaction and concurrency claims.

- [ ] **Step 1: Write PostgreSQL tests before implementation-specific fixes.**

```python
def test_relation_initializer_rolls_back_field_view_audit_and_idempotency(...): ...
def test_lookup_initializer_same_key_replays_one_field_and_audit(...): ...
def test_concurrent_f2_initializers_receive_consecutive_order(...): ...
def test_relation_lookup_dependency_guard_survives_real_postgres(...): ...
```

Each test must require the existing authorised disposable `STAGE06_LOCAL_DATABASE_URL`, reset only the approved smoke database through the existing fixture and assert committed rows/audit/idempotency counts directly.

- [ ] **Step 2: Run the new test selection and verify it fails before any fixture/service correction.**

Run:

```powershell
cd backend; python -m pytest -q tests/integration/test_stage07_relation_lookup_postgres.py
```

Expected: FAIL before the F2 service is complete, or SKIP only when the authorised disposable URL is absent. A skip is not success evidence.

- [ ] **Step 3: Make only database-specific correctness repairs exposed by the tests.**

Use existing SQLAlchemy UoW patterns (`flush` after new staged objects where same-transaction rereads require it; row lock for schema mutation). Do not add a migration unless the user has separately approved it.

- [ ] **Step 4: Re-run the matrix.**

Run the Step 2 command.

Expected: all F2 PostgreSQL cases PASS; no test uses a development, staging or production database.

- [ ] **Step 5: Commit the real-database proof.**

```powershell
git add backend/tests/integration/test_stage07_relation_lookup_postgres.py backend/app/services/stage06_platform.py
git commit -m "test(stage07): prove F2 relation lookup postgres invariants"
```

## Task 6: Add protected F2 browser transport and query helpers

**Files:**

- Modify: `mini-app/src/app/api.ts`
- Modify: `mini-app/src/app/protectedQuery.ts`
- Test: `mini-app/src/test/api.test.ts`
- Test: `mini-app/src/test/protected-query-state.test.ts`

**Consumes:** Task 1's exact HTTP contracts and TD001 behavior.

**Produces:** Typed safe API calls and user/workspace-scoped candidate query helpers.

- [ ] **Step 1: Write failing TypeScript tests.**

```ts
test('relation candidate transport encodes only query and cursor and receives safe id label items', async () => {
  await api.relationCandidates('field-1', 'acme', undefined)
  expect(fetch).toHaveBeenCalledWith(
    '/fields/field-1/relation-candidates?q=acme',
    expect.objectContaining({ headers: { Accept: 'application/json' } }),
  )
})

test('relation candidate keys are isolated by verified user workspace field query and cursor', () => {
  expect(protectedRelationCandidateKey(scope, 'field-1', 'acme', null)).toEqual([...])
})
```

- [ ] **Step 2: Run tests and verify they fail.**

Run:

```powershell
cd mini-app; npm.cmd test -- --run src/test/api.test.ts src/test/protected-query-state.test.ts
```

Expected: missing API method/key helper failures.

- [ ] **Step 3: Implement minimal transport and protected-key helpers.**

```ts
export function protectedRelationCandidateKey(
  scope: ProtectedScope, fieldId: string, query: string, cursor: string | null,
): QueryKey {
  return protectedQueryKey(scope, 'relation-candidates', fieldId, query, cursor)
}
```

`api.relationCandidates` URL-encodes only `q` and `cursor`; it has no target-table/config/label-field argument. Extend error-code parsing only for the fixed allowlist from the specification.

- [ ] **Step 4: Run focused tests.**

Run the Step 2 command.

Expected: PASS; no candidate key lacks user/workspace scope or exposes raw configuration.

- [ ] **Step 5: Commit protected F2 transport.**

```powershell
git add mini-app/src/app/api.ts mini-app/src/app/protectedQuery.ts mini-app/src/test/api.test.ts mini-app/src/test/protected-query-state.test.ts
git commit -m "feat(stage07): add protected relation candidate transport"
```

## Task 7: Build the F2 relation/lookup field builder UI

**Files:**

- Create: `mini-app/src/app/RelationLookupFieldBuilderPanel.tsx`
- Modify: `mini-app/src/app/FieldBuilderPanel.tsx`
- Modify: `mini-app/src/app/App.tsx`
- Modify: `mini-app/src/styles.css`
- Test: `mini-app/src/test/f2-field-builder-panel.test.tsx`
- Test: `mini-app/src/test/app-shell.test.tsx`

**Consumes:** Tasks 1–3 and existing F1 drawer/sheet patterns.

**Produces:** A capability-gated F2 panel that submits exactly one approved initializer shape with idempotency/retry/409 behavior.

- [ ] **Step 1: Write failing UI tests.**

```tsx
test('relation builder submits name target table and required without raw configuration', async () => {
  render(<RelationLookupFieldBuilderPanel tables={[source, target]} schemas={...} onSubmit={onSubmit} onClose={close} />)
  // Select 关联记录, target table and required, then assert exact payload.
})

test('lookup builder offers only allowed source relations and compatible aggregations', async () => {
  // Assert sum is hidden/disabled for text and cycle/depth errors use fixed local copy.
})
```

- [ ] **Step 2: Run tests and verify they fail.**

Run:

```powershell
cd mini-app; npm.cmd test -- --run src/test/f2-field-builder-panel.test.tsx src/test/app-shell.test.tsx
```

Expected: missing panel and F2 App mode failures.

- [ ] **Step 3: Implement the focused panel and App callbacks.**

Use a discriminated value union:

```ts
type F2FieldBuilderValues =
  | { kind: 'relation'; name: string; targetTableId: string; required: boolean }
  | { kind: 'lookup'; name: string; sourceRelationFieldId: string; targetFieldId: string; aggregation: LookupAggregation }
```

Keep F1 request semantics unchanged. `FieldBuilderPanel` only exposes an explicit route into the new F2 panel; `App.tsx` fetches permitted target table schemas through existing protected reads, captures workspace/canvas/builder generations, invokes the matching API initializer, clears the exact table schema/affected presentation/record/create-form keys, rereads and verifies `receipt.field.id` before closing. Reuse current 401/403 fail-closed behavior and the fresh-key/explicit-retry/409-lock model.

Add only light existing-grammar CSS: white panel/sheet, compact labeled selects, visible focus rings, no dark surface, gradient, glow or card-wall. Mobile uses full height above bottom navigation.

- [ ] **Step 4: Run focused tests.**

Run the Step 2 command.

Expected: PASS; both builder modes have safe payloads, local error mapping and no optimistic field.

- [ ] **Step 5: Commit F2 builder UI.**

```powershell
git add mini-app/src/app/RelationLookupFieldBuilderPanel.tsx mini-app/src/app/FieldBuilderPanel.tsx mini-app/src/app/App.tsx mini-app/src/styles.css mini-app/src/test/f2-field-builder-panel.test.tsx mini-app/src/test/app-shell.test.tsx
git commit -m "feat(stage07): add relation lookup field builder"
```

## Task 8: Build the shared Relation Picker and relation/lookup renderers

**Files:**

- Create: `mini-app/src/app/RelationPicker.tsx`
- Modify: `mini-app/src/app/CreateRecordPanel.tsx`
- Modify: `mini-app/src/app/RecordDetail.tsx`
- Modify: `mini-app/src/app/BaseCanvas.tsx`
- Modify: `mini-app/src/styles.css`
- Test: `mini-app/src/test/relation-picker.test.tsx`
- Modify: `mini-app/src/test/create-record-panel.test.tsx`
- Modify: `mini-app/src/test/record-detail.test.tsx`
- Modify: `mini-app/src/test/view-renderers.test.tsx`

**Consumes:** Tasks 4 and 6 safe cells/candidate API.

**Produces:** Searchable paged relation editing in create/detail plus relation chips and read-only lookup displays in all current view renderers.

- [ ] **Step 1: Write failing component tests.**

```tsx
test('relation picker searches server candidates, appends the next cursor page and preserves ordered selected IDs', async () => {
  // Verify calls include only fieldId/q/cursor and selected values are opaque IDs.
})

test('create form blocks a required empty relation and submits selected IDs through existing create callback', async () => {
  // Assert selected {id,label} becomes ['record-1'] under the safe field key.
})

test('record detail renders relation chips and never makes lookup editable', () => {
  // Assert lookup has output text and no editable input.
})
```

- [ ] **Step 2: Run tests and verify they fail.**

Run:

```powershell
cd mini-app; npm.cmd test -- --run src/test/relation-picker.test.tsx src/test/create-record-panel.test.tsx src/test/record-detail.test.tsx src/test/view-renderers.test.tsx
```

Expected: missing picker/component behavior and existing unsupported-field assertions fail.

- [ ] **Step 3: Implement picker and field-type presentation.**

`RelationPicker` accepts `scope`, `fieldId`, selected `RelationCell[]`, `onChange`, `disabled` and optional `excludeRecordId`. It uses TanStack protected keys, debounced local search input without client filtering, an explicit load-more button and ordered chips. It never fetches arbitrary tables or persists candidates.

Extend Create/Detail forms to support `linked_record`; map selected chips to ID arrays only at submit. Detail excludes `lookup` from editable field types. Add a shared formatter in `BaseCanvas.tsx` that renders relation labels/chips and lookup output without JSON raw IDs. Keep Calendar/Kanban/Form renderers within their existing shapes.

- [ ] **Step 4: Run focused tests.**

Run the Step 2 command.

Expected: PASS; required relation validation, candidate paging and read-only lookup behavior are proven.

- [ ] **Step 5: Commit picker and renderers.**

```powershell
git add mini-app/src/app/RelationPicker.tsx mini-app/src/app/CreateRecordPanel.tsx mini-app/src/app/RecordDetail.tsx mini-app/src/app/BaseCanvas.tsx mini-app/src/styles.css mini-app/src/test/relation-picker.test.tsx mini-app/src/test/create-record-panel.test.tsx mini-app/src/test/record-detail.test.tsx mini-app/src/test/view-renderers.test.tsx
git commit -m "feat(stage07): support relation picker and lookup rendering"
```

## Task 9: Prove end-to-end scope safety, build and browser behavior

**Files:**

- Create: `mini-app/src/test/relation-lookup-flow.test.tsx`
- Modify: `mini-app/src/test/record-mutation-safety.test.tsx`
- Modify: `project-docs/08-implementation/STAGE_07_TEST_PLAN.md`
- Modify: `project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`
- Modify: `project-docs/08-implementation/STAGE_07_PROGRESS.md`

**Consumes:** Tasks 1–8.

**Produces:** F2 local automated/browser evidence and accurate current-stage status.

- [ ] **Step 1: Write end-to-end failing application tests.**

```tsx
test('a delayed relation candidate or field receipt cannot restore a previous workspace', async () => {
  // Start F2 action in workspace-1, switch to workspace-2, resolve old request,
  // and assert workspace-2 remains rendered with no old labels.
})

test('relation write 401/403/404 follows TD001 cleanup without retaining labels or IDs', async () => {
  // Exercise create/PATCH failure and assert generic safe boundary only.
})
```

Add flow fixtures for relation builder -> schema reread -> picker -> record create/edit -> nested lookup/aggregate render. Include each allowlisted error and an unknown error that remains generic.

- [ ] **Step 2: Run the F2 frontend selection and verify it fails before integration is complete.**

Run:

```powershell
cd mini-app; npm.cmd test -- --run src/test/relation-lookup-flow.test.tsx src/test/record-mutation-safety.test.tsx
```

Expected: FAIL before the complete App/query integration exists.

- [ ] **Step 3: Make only integration fixes identified by the tests.**

Ensure builder/candidate/create/detail transitions increment the relevant existing request generation and cancel exact F2 queries on close/view/table/workspace replacement. Do not broaden cache removal beyond the verified workspace/resource prefix.

- [ ] **Step 4: Run full automated verification.**

Run:

```powershell
cd backend; python -m pytest -q tests/unit/test_stage07_relation_lookup.py tests/unit/test_stage07_mini_app_api.py
python -m pytest -q tests/integration/test_stage07_relation_lookup_postgres.py
cd ..\mini-app; npm.cmd test -- --run
npm.cmd run build
```

Expected: all selected unit/integration tests PASS; PostgreSQL result is recorded as pass or explicitly skipped only for absent authorised disposable configuration; Mini App suite and build PASS.

- [ ] **Step 5: Perform actual Mini App Browser QA before documentation claims.**

Use a disposable local fixture/proxy that serves only synthetic data. At 1440, 1280, 430 and 390 widths verify: relation field creation; lookup creation; target search/cursor page; relation create/edit; same-table self candidate exclusion; two-level lookup; each aggregation family; generic denial; validation; stale-workspace response rejection; desktop drawer/mobile sheet; empty final console error/warning list. Stop servers, remove temporary fixture/proxy source and retain only explicitly sanitised evidence.

- [ ] **Step 6: Update Stage07 evidence documents only with actual result values.**

Update the files listed above plus `STAGE_07_API_DATA_SECURITY_CONTRACT.md`, `STAGE_07_SDD.md`, `STAGE_07_BDD_AND_ACCEPTANCE.md`, `STAGE_07_ACCEPTANCE_CHECKLIST.md`, `modules/STAGE_07_BITABLE_WORK_SURFACE.md` and `HANDOFF.md`. Mark F2 `implemented-local` only if all approved boundaries and evidence pass. Otherwise state the exact missing test, UI state or external evidence; do not claim V1 or full Stage07 acceptance.

- [ ] **Step 7: Commit verified F2 evidence.**

```powershell
git add mini-app/src/test/relation-lookup-flow.test.tsx mini-app/src/test/record-mutation-safety.test.tsx project-docs/08-implementation docs/superpowers/specs HANDOFF.md
git commit -m "test(stage07): verify F2 relation lookup flow"
```

## Task 10: Final requirement-by-requirement acceptance audit

**Files:**

- Modify: `project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`
- Modify: `project-docs/08-implementation/STAGE_07_ACCEPTANCE_CHECKLIST.md`
- Modify: `HANDOFF.md`

**Consumes:** All completed F2 tasks and fresh command/browser output.

**Produces:** A bounded F2 acceptance statement with no unsupported whole-stage claim.

- [ ] **Step 1: Build a traceability table from the approved F2 specification.**

List each confirmed decision: same-Base/self relation; dedicated routes; idempotency/rollback; safe candidate labels; two-level/cycle checks; all fixed aggregates; complete fail-closed lookup; PATCH rechecks; required semantics; view append; safe errors; protected cache; PostgreSQL; four-width browser QA; no delete route/UI; no migration/dependency/capability.

- [ ] **Step 2: Attach only direct evidence.**

For each row, cite the exact test name, command result and, for UI rows, actual browser observation. Mark evidence absent, skipped or external-pending rather than extrapolating from a component test.

- [ ] **Step 3: Run final read-only consistency checks.**

Run:

```powershell
git diff --check
git status --short
rg -n "TODO|TBD|F2 relation/lookup.*unimplemented" project-docs/08-implementation docs/superpowers
```

Expected: no whitespace error; clean tree after commit; stale F2 status is either corrected with evidence or explicitly preserved as incomplete.

- [ ] **Step 4: Commit final audit.**

```powershell
git add project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md project-docs/08-implementation/STAGE_07_ACCEPTANCE_CHECKLIST.md HANDOFF.md
git commit -m "docs(stage07): audit F2 relation lookup acceptance"
```

## Plan Self-Review

### Specification coverage

| Specification requirement | Planned tasks |
| --- | --- |
| Dedicated safe F2 contracts and no raw configuration | 1, 2, 3, 4, 6, 7 |
| Same-Base/self relation, required semantics and versioned writes | 2, 4, 8, 9 |
| Two-level nested lookup and fixed aggregates | 3, 4, 8, 9 |
| Permission rechecks and fail-closed result behavior | 2, 3, 4, 6, 9 |
| Candidate picker and safe `{id,label}` values | 1, 4, 6, 8 |
| View append/audit/idempotency/transaction evidence | 2, 3, 5, 9 |
| Delete/dependency policy without scope-expanding delete API | 4, 5, 10 |
| Four-width live UI evidence and cleanup | 9, 10 |
| Stage documents remain accurate and F2 is not confused with V1/Stage07 completion | 9, 10 |

### Placeholder scan

The plan contains no implementation placeholders. The phrase “future deletion paths” is an explicit non-scope boundary: the repository currently has no public delete route, and F2 does not add one. The reusable guard and its tests are the approved policy evidence without an unapproved API expansion.

### Type consistency

- Both F2 initializer routes return the existing `FieldInitializationResponse` and use `FieldInitializationResult`.
- `RelationCandidatePageResponse` is the backend counterpart of `RelationCandidatePage` in `mini-app/src/app/api.ts`.
- `protectedRelationCandidateKey` is the only candidate cache-key factory and includes user/workspace/field/query/cursor.
- Relation writes remain `Record<string, unknown>` values carrying an array of opaque record IDs under the existing field key; rendered values are server-projected `RelationCell[]`.
- Lookup remains a server-projected read-only value and never enters create/PATCH payloads.

## Execution Gate

This plan is complete but does not authorize implementation. Before Task 1, obtain a separate explicit user confirmation that authorizes the proposed API/read-model/permission-enforcement changes in the approved F2 design and this plan. After F2 is accepted locally, begin a new V1 design discussion; do not combine V1 implementation with this plan.
