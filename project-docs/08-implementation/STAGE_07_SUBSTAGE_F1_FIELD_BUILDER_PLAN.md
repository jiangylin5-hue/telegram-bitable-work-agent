# Stage07 F1 Independent Field Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a safe, atomic and responsive Mini App flow that creates independent typed fields and makes them immediately usable in authorised saved views and record forms.

**Architecture:** F1 adds a browser-safe field-initialization endpoint beside the retained Stage06 primitive API. The backend owns generated keys, select choices, field order, view visibility updates, audit and idempotency in one transaction; the Mini App submits only user-facing data and rereads protected schema/view/record models before rendering the new column.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, PostgreSQL, existing Stage06 UoW/idempotency/audit services, React, TypeScript, TanStack Query v5, Tailwind, lucide-react, Vitest and Testing Library.

## Global Constraints

- Implement only the user-approved F1 scope in `docs/superpowers/specs/2026-07-10-stage07-f1-field-builder-design.md`.
- Browser request models accept only `name`, `field_type`, `required` and allowed choice arrays. Never accept or return raw policy, technical key, raw view configuration, role claim, audit state or arbitrary options.
- Supported F1 types are exactly `text`, `number`, `date`, `status`, `single_select`, `multi_select`, `user`, `checkbox`, `url`, `email` and `phone`.
- Do not implement relationship/lookup/JSON Builder, field editing/reordering/deletion, additional views, default-view switching, governance, imports or Bots.
- Preserve server authority: `field.manage` is checked server-side; protected query keys remain user/workspace/table scoped; no optimistic column or local policy semantics are permitted.
- All durable F1 writes use `Idempotency-Key`, run through one transaction, write a sanitized audit event and roll back the whole graph on failure.
- Reuse the retained [Workspace Ledger visual reference](assets/stage07/workspace-ledger-reference.png) and compare at `1440px`, `1280px`, `430px` and `390px` before reporting the substage complete.
- Every task follows TDD: write one failing test, run it and record the failure, make the smallest implementation, rerun the focused test, then commit the coherent task.

---

## File Structure And Responsibility Map

| Path | Role in F1 |
| --- | --- |
| `backend/app/schemas/stage06_platform.py` | safe Canvas schema fields, F1 request/receipt Pydantic models and strict request rejection |
| `backend/app/services/stage06_platform.py` | supported-type constants, safe schema projection, table-row lock, field initialization transaction, choice value validation and view visibility update |
| `backend/app/api/routes/stage06_platform.py` | `POST /tables/{table_id}/field-initializations`, request fingerprint and safe HTTP mapping |
| `backend/tests/unit/test_stage07_field_builder.py` | deterministic service/route/security/rollback regression coverage |
| `backend/tests/integration/test_stage07_field_builder_postgres.py` | disposable real-PostgreSQL order/idempotency/rollback proof gated by `STAGE06_LOCAL_DATABASE_URL` |
| `mini-app/src/app/api.ts` | safe schema/receipt/type definitions and typed F1 transport |
| `mini-app/src/app/FieldBuilderPanel.tsx` | focused accessible desktop drawer/mobile sheet creation form |
| `mini-app/src/app/App.tsx` | field-init mutation owner, protected cache invalidation/re-read, receipt verification and error boundaries |
| `mini-app/src/app/BaseCanvas.tsx` | real Add Field entry and F1 empty-table entry; no inert action |
| `mini-app/src/app/CreateRecordPanel.tsx` | server-filtered `multi_select` input and choice payloads |
| `mini-app/src/app/RecordDetail.tsx` | choice-aware `status`/`single_select`/`multi_select` direct edits |
| `mini-app/src/styles.css` | Workspace-Ledger drawer/sheet, choice editor and responsive layout styles |
| `mini-app/src/test/field-builder-panel.test.tsx` | isolated form validation, accessibility, retry/409 tests |
| `mini-app/src/test/field-builder-flow.test.tsx` | protected App flow, exact receipt re-read, denial/stale-result tests |
| `mini-app/src/test/create-record.test.tsx`, `mini-app/src/test/record-detail.test.tsx` | choice/multi-select record interaction regressions |
| Stage07 documentation set | SDD, BDD, API/security contract, test plan, risk register, checklist, progress and traceability evidence |

---

### Task 1: Make F1 Documentation the Authoritative Implementation Boundary

**Files:**

- Create: `project-docs/08-implementation/STAGE_07_SUBSTAGE_F1_FIELD_BUILDER_PLAN.md`
- Modify: `project-docs/08-implementation/STAGE_07_SDD.md`
- Modify: `project-docs/08-implementation/STAGE_07_API_DATA_SECURITY_CONTRACT.md`
- Modify: `project-docs/08-implementation/STAGE_07_BDD_AND_ACCEPTANCE.md`
- Modify: `project-docs/08-implementation/STAGE_07_TEST_PLAN.md`
- Modify: `project-docs/08-implementation/STAGE_07_RISK_REGISTER.md`
- Modify: `project-docs/08-implementation/STAGE_07_ACCEPTANCE_CHECKLIST.md`
- Modify: `project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`
- Modify: `project-docs/08-implementation/STAGE_07_MODULE_INDEX.md`

**Interfaces:**

- Consumes: the approved F1 design specification and existing Stage07 visual-reference manifest.
- Produces: one source-aligned documentation package that forbids browser raw-policy/config access and gives every later implementation task a named acceptance condition.

- [x] **Step 1: Write the documentation acceptance matrix before code**

Add this row to the traceability audit and checklist before touching a runtime file:

```md
| F1 independent Field Builder | F1 Design §2–§10 | `approved-design-unimplemented` | Design: safe types, generated keys, atomic view visibility, select validation, four-width visual baseline | Implement only through the F1 plan; retain F2/V1 exclusions. |
```

- [x] **Step 2: Verify the documentation is initially incomplete**

Run:

```powershell
rg -n "field-initializations|FieldBuilderPanel|multi_select.*create" backend mini-app
```

Expected: no F1 endpoint, panel or complete multi-select create path exists.

- [x] **Step 3: Add precise cross-document F1 contracts**

Add the following concrete material, with matching names in every document:

```md
POST /tables/{table_id}/field-initializations
request: { name, field_type, required, choices? }
receipt: { field: SafeTableField, affected_view_ids: string[] }
authorisation: active member + field.manage
forbidden: key, options, permission_policy, raw view config, role claim
```

SDD must describe the table-toolbar/drawer/sheet transition; BDD must include F1-1 through F1-7 from the approved design; test/risk/checklist documents must name choice validation, schema projection, table lock, rollback, idempotency, cross-workspace denial and four-width visual comparison.

- [x] **Step 4: Verify documentation consistency**

Run:

```powershell
rg -n "field-initializations|SafeTableField|F1-1|field.manage|multi_select" project-docs/08-implementation
git diff --check
```

Expected: every document uses the same endpoint, receipt and permission rule; `git diff --check` exits `0`.

- [x] **Step 5: Commit the documentation boundary**

```powershell
git add project-docs/08-implementation docs/superpowers/specs/2026-07-10-stage07-f1-field-builder-design.md
git commit -m "docs(stage07): plan F1 field builder"
```

---

### Task 2: Red-Test and Implement Safe Canvas Schema Projection

**Files:**

- Modify: `backend/app/schemas/stage06_platform.py`
- Modify: `backend/app/services/stage06_platform.py`
- Modify: `backend/app/api/routes/stage06_platform.py`
- Modify: `backend/tests/unit/test_stage07_mini_app_api.py`
- Modify: `mini-app/src/app/api.ts`
- Test: `backend/tests/unit/test_stage07_field_builder.py`

**Interfaces:**

- Consumes: current `PlatformField`, Stage06 field-read permission and `/tables/{table_id}/schema` ownership authorization.
- Produces: `SafeTableFieldResponse`, `safe_table_schema_field(field)` and a Canvas schema response which contains only allowed field metadata and validated `choices`.

- [x] **Step 1: Write failing schema-leak tests**

```python
def test_canvas_schema_removes_policy_and_non_choice_options(client, seeded_table):
    response = client.get(f"/tables/{seeded_table.id}/schema")
    assert response.status_code == 200
    field = response.json()["fields"][0]
    assert field["options"] == {"choices": ["new", "active"]}
    assert "permission_policy" not in field
    assert "internal_rule" not in response.text
```

Add a hidden-field counterpart asserting both its key and policy are absent for a reader without permission.

- [x] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
cd backend; python -m pytest -q tests/unit/test_stage07_mini_app_api.py -k "schema"
```

Expected: FAIL because the current `_field_to_schema` exposes `permission_policy` and raw `options`.

- [x] **Step 3: Define explicit safe response models and projection**

Implement the response model and helper with this complete boundary:

```python
class SafeTableFieldResponse(BaseModel):
    id: str
    table_id: str
    name: str
    key: str
    field_type: str
    required: bool
    options: dict[str, Any]
    order_index: int


def _safe_field_options(field: PlatformField) -> dict[str, Any]:
    if field.field_type not in {"status", "single_select", "multi_select"}:
        return {}
    choices = field.options.get("choices")
    if not isinstance(choices, list) or not all(isinstance(item, str) for item in choices):
        return {}
    return {"choices": list(choices)}


def safe_table_schema_field(field: PlatformField) -> dict[str, Any]:
    return {
        "id": str(field.id), "table_id": str(field.table_id), "name": field.name,
        "key": field.key, "field_type": field.field_type, "required": field.required,
        "options": _safe_field_options(field), "order_index": field.order_index,
    }
```

Make `get_table_schema(uow, table_id, actor=actor)` use this helper after the existing field-read filter, and make `TableSchemaResponse.fields` typed as `list[SafeTableFieldResponse]`. Do not alter primitive `FieldResponse` or its backend/admin endpoint.

- [x] **Step 4: Align the Mini App type**

Replace the current minimal `TableSchema` field type with:

```ts
export type SafeTableField = {
  id: string; table_id: string; name: string; key: string; field_type: string
  required: boolean; options: { choices?: string[] }; order_index: number
}
export type TableSchema = {
  table: { id: string; base_id: string; name: string; key: string; status: string }
  fields: SafeTableField[]
}
```

Only existing consumers that need choice rendering may read `options.choices`.

- [x] **Step 5: Run focused tests and type build**

Run:

```powershell
cd backend; python -m pytest -q tests/unit/test_stage07_mini_app_api.py -k "schema"
cd ..\mini-app; npm.cmd test -- --run; npm.cmd run build
```

Expected: schema tests pass; all current frontend tests and TypeScript build pass with the richer safe type.

- [x] **Step 6: Commit the safe read correction**

```powershell
git add backend/app/schemas/stage06_platform.py backend/app/services/stage06_platform.py backend/app/api/routes/stage06_platform.py backend/tests/unit/test_stage07_mini_app_api.py mini-app/src/app/api.ts
git commit -m "fix(stage07): project safe table schema"
```

---

### Task 3: Add Atomic Field Initialization Domain Service and Table Lock

**Files:**

- Modify: `backend/app/services/stage06_platform.py`
- Test: `backend/tests/unit/test_stage07_field_builder.py`

**Interfaces:**

- Consumes: `PlatformField`, `PlatformView`, `Actor`, `Stage06PlatformUnitOfWork`, existing audit helper and idempotency storage.
- Produces: `FieldInitializationResult`, `initialize_field(uow, table_id, name, field_type, required, choices, actor)`, `lock_table_for_schema_mutation(table_id)`, validated F1 choice helpers and a view-visibility update result.

- [x] **Step 1: Write failing service tests**

```python
def test_initialize_field_generates_key_default_policy_order_and_view_visibility():
    result = initialize_field(uow, table.id, name="Stage", field_type="status",
                              required=True, choices=["new", "active"], actor=actor)
    assert result.field.key.startswith("fld_")
    assert result.field.permission_policy == {}
    assert result.field.order_index == 0
    assert result.field.options == {"choices": ["new", "active"]}
    assert result.affected_view_ids == [view.id]
    assert view.config["fields"] == [result.field.key]
```

Add tests for rejected F2/JSON types, missing/duplicate choices, duplicate normalized names, one append only, untouched implicit field lists, sanitised audit payload and two distinct fields receiving orders `0` then `1`.

- [x] **Step 2: Run the service tests and verify they fail**

Run:

```powershell
cd backend; python -m pytest -q tests/unit/test_stage07_field_builder.py
```

Expected: FAIL because `initialize_field`, F1 type validation and table locking do not exist.

- [x] **Step 3: Extend the UoW with a table lock**

Add this protocol operation and matching implementations:

```python
def lock_table_for_schema_mutation(self, table_id: UUID) -> PlatformTable | None:
    raise NotImplementedError
```

```python
# InMemoryStage06PlatformUnitOfWork
def lock_table_for_schema_mutation(self, table_id: UUID) -> PlatformTable | None:
    return self.get_table(table_id)

# SqlAlchemyStage06PlatformUnitOfWork
def lock_table_for_schema_mutation(self, table_id: UUID) -> PlatformTable | None:
    return self.session.scalar(
        select(PlatformTable).where(PlatformTable.id == table_id).with_for_update()
    )
```

The production operation must run inside the route-owned transaction before computing `max(order_index) + 1`.

- [x] **Step 4: Implement F1 validation and initialization**

Add these stable constants/helpers and result shape:

```python
F1_FIELD_TYPES = frozenset({
    "text", "number", "date", "status", "single_select", "multi_select",
    "user", "checkbox", "url", "email", "phone",
})
F1_CHOICE_FIELD_TYPES = frozenset({"status", "single_select", "multi_select"})

@dataclass(frozen=True)
class FieldInitializationResult:
    field: PlatformField
    affected_view_ids: list[UUID]
```

`initialize_field` must normalize a `1..160` display name, validate the exact F1 set, require/order-safe choices for the three choice types, reject all choices for other types, call `lock_table_for_schema_mutation`, reject a normalized duplicate display name, generate an opaque `fld_` key, write `{}` policy, append once to each active explicit `config.fields` list and record a sanitized `stage07.field_initialized` event. It must not call the raw `create_field` endpoint or accept a client key/policy.

- [x] **Step 5: Run service tests and platform regression**

Run:

```powershell
cd backend; python -m pytest -q tests/unit/test_stage07_field_builder.py tests/unit/test_stage06_platform_core.py
```

Expected: F1 service tests and existing platform core tests pass.

- [ ] **Step 6: Commit the domain transaction**

```powershell
git add backend/app/services/stage06_platform.py backend/tests/unit/test_stage07_field_builder.py
git commit -m "feat(stage07): initialize fields atomically"
```

---

### Task 4: Expose the Safe Idempotent Field-Initialization Endpoint

**Files:**

- Modify: `backend/app/schemas/stage06_platform.py`
- Modify: `backend/app/api/routes/stage06_platform.py`
- Modify: `backend/app/services/stage06_platform.py`
- Test: `backend/tests/unit/test_stage07_field_builder.py`

**Interfaces:**

- Consumes: `initialize_field`, `workspace_id_for_table`, `authorize_workspace_action`, P3 fingerprint/idempotency helper and `safe_table_schema_field`.
- Produces: `POST /tables/{table_id}/field-initializations` returning `FieldInitializationResponse`.

- [x] **Step 1: Write failing route tests**

```python
def test_field_initialization_replays_same_key_and_rejects_payload_change(client, table_id):
    headers = {"Idempotency-Key": "field-key-1"}
    payload = {"name": "Stage", "field_type": "status", "required": False,
               "choices": ["new", "active"]}
    first = client.post(f"/tables/{table_id}/field-initializations", json=payload, headers=headers)
    replay = client.post(f"/tables/{table_id}/field-initializations", json=payload, headers=headers)
    conflict = client.post(f"/tables/{table_id}/field-initializations",
                           json={**payload, "name": "Priority"}, headers=headers)
    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert conflict.status_code == 409
```

Add tests for `403` before write, cross-workspace denial, `extra` raw keys rejected with `422`, receipt contains no policy/raw config, and a forced view-update failure rolls back field/audit/idempotency.

- [x] **Step 2: Run the route tests and verify they fail**

Run:

```powershell
cd backend; python -m pytest -q tests/unit/test_stage07_field_builder.py -k "endpoint or idempotency or rollback"
```

Expected: FAIL with `404` because the endpoint has not been registered.

- [x] **Step 3: Define strict request and receipt models**

```python
class InitializeFieldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    field_type: str
    required: bool = False
    choices: list[str] | None = None

class FieldInitializationResponse(BaseModel):
    field: SafeTableFieldResponse
    affected_view_ids: list[str]
```

No fallback `dict[str, Any]` is allowed in either F1 browser model.

- [x] **Step 4: Register the route using the P3 idempotency discipline**

Implement the route with this shape:

```python
@router.post("/tables/{table_id}/field-initializations",
             response_model=FieldInitializationResponse,
             status_code=status.HTTP_201_CREATED)
def initialize_field_endpoint(
    table_id: UUID,
    request: InitializeFieldRequest,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
) -> FieldInitializationResponse:
    workspace_id = workspace_id_for_table(uow, table_id)
    actor = authorize_workspace_action(uow, identity, workspace_id, "field.manage")
    name = _validated_field_name(request.name)
    choices = _validated_f1_choices(request.field_type, request.choices)
    result, replayed = _run_atomic_builder_initialization(
        uow, workspace_id=workspace_id, operation="stage07.field.initialize",
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint_request({
            "workspace_id": str(workspace_id), "operation": "stage07.field.initialize",
            "actor_user_id": identity.user_id, "table_id": str(table_id), "name": name,
            "field_type": request.field_type, "required": request.required, "choices": choices,
        }),
        build=lambda: _field_initialization_response(initialize_field(
            uow, table_id, name=name, field_type=request.field_type,
            required=request.required, choices=choices, actor=actor,
        )),
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
    return result
```

The fingerprint includes workspace, operation, actor user ID, table ID and normalized user-visible request values. Reuse `_commit_if_sqlalchemy` only through the atomic helper; no early commit is permitted.

- [x] **Step 5: Run focused route tests and full backend regression**

Run:

```powershell
cd backend; python -m pytest -q tests/unit/test_stage07_field_builder.py tests/unit/test_stage07_mini_app_api.py
python -m pytest -q
```

Expected: all focused tests pass; full-suite output reports only the documented environment-gated PostgreSQL skips.

- [ ] **Step 6: Commit the API boundary**

```powershell
git add backend/app/schemas/stage06_platform.py backend/app/api/routes/stage06_platform.py backend/app/services/stage06_platform.py backend/tests/unit/test_stage07_field_builder.py
git commit -m "feat(stage07): add safe field initialization api"
```

---

### Task 5: Enforce Choice Values and Make Multi-Select Creatable

**Files:**

- Modify: `backend/app/services/stage06_platform.py`
- Test: `backend/tests/unit/test_stage07_field_builder.py`
- Test: `backend/tests/unit/test_stage07_mini_app_api.py`

**Interfaces:**

- Consumes: `PlatformField.options.choices`, `get_create_form`, `_validate_record_values`, `create_record` and `update_record`.
- Produces: safe `multi_select` create-form metadata and configured-choice validation that preserves no-choice legacy fields.

- [ ] **Step 1: Write failing value-validation tests**

```python
def test_configured_multi_select_requires_distinct_allowed_choices():
    field = create_f1_choice_field("Tags", "multi_select", ["vip", "trial"])
    assert create_record(uow, table.id, values={field.key: ["vip", "trial"]})
    with raises(PlatformValidationError, match="invalid_field_choice"):
        create_record(uow, table.id, values={field.key: ["vip", "unknown"]})
    with raises(PlatformValidationError, match="invalid_field_choice"):
        create_record(uow, table.id, values={field.key: ["vip", "vip"]})
```

Add a legacy `status` field with `{}` options that accepts its historical string value, and assert the create-form response includes F1 `multi_select` choices only for a writable actor.

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
cd backend; python -m pytest -q tests/unit/test_stage07_field_builder.py -k "choice or multi_select"
```

Expected: FAIL because `multi_select` is excluded from `CREATE_FORM_SCALAR_FIELD_TYPES` and select membership is not validated.

- [ ] **Step 3: Implement explicit option membership validation**

Use the following helper from `_validate_record_values` after type validation:

```python
def _validate_configured_choice_value(field: PlatformField, value: Any) -> None:
    choices = _safe_field_options(field).get("choices")
    if choices is None or value is None:
        return
    values = value if field.field_type == "multi_select" else [value]
    if not isinstance(values, list) or len(values) != len(set(values)):
        raise PlatformValidationError("invalid_field_choice", field.key)
    if any(item not in choices for item in values):
        raise PlatformValidationError("invalid_field_choice", field.key)
```

Add `multi_select` to `CREATE_FORM_SCALAR_FIELD_TYPES`. Make `_create_form_options` call the same safe-options helper for the three choice types; do not expose raw options.

- [ ] **Step 4: Run record and API tests**

Run:

```powershell
cd backend; python -m pytest -q tests/unit/test_stage07_field_builder.py tests/unit/test_stage07_mini_app_api.py -k "choice or create_form or record"
```

Expected: configured choice constraints pass; legacy option-less fields retain existing behavior.

- [ ] **Step 5: Commit typed-value support**

```powershell
git add backend/app/services/stage06_platform.py backend/tests/unit/test_stage07_field_builder.py backend/tests/unit/test_stage07_mini_app_api.py
git commit -m "feat(stage07): validate builder choice values"
```

---

### Task 6: Build the Focused Field Creation Panel

**Files:**

- Create: `mini-app/src/app/FieldBuilderPanel.tsx`
- Modify: `mini-app/src/app/api.ts`
- Modify: `mini-app/src/styles.css`
- Test: `mini-app/src/test/field-builder-panel.test.tsx`

**Interfaces:**

- Consumes: `FieldInitializationReceipt`, `ApiError`, `crypto.randomUUID`, existing Builder drawer classes and `can_manage_schema` presentation hint.
- Produces: `FieldBuilderPanel` with `onSubmit(values, idempotencyKey)` and `onClose()`.

- [ ] **Step 1: Write failing panel tests**

```tsx
render(<FieldBuilderPanel onSubmit={onSubmit} onClose={onClose} />)
expect(screen.getByRole('dialog', { name: '添加字段' })).toBeInTheDocument()
fireEvent.click(screen.getByRole('button', { name: '创建字段' }))
expect(await screen.findByText('请输入字段名称')).toBeInTheDocument()
fireEvent.change(screen.getByLabelText('字段类型'), { target: { value: 'multi_select' } })
expect(screen.getByRole('button', { name: '添加选项' })).toBeInTheDocument()
```

Add tests for first-input focus, type-dependent choice editor, pending state, same key after `503`, `409` lock, Cancel/Close and no visible technical key/policy/JSON control.

- [ ] **Step 2: Run the panel test and verify it fails**

Run:

```powershell
cd mini-app; npm.cmd test -- --run src/test/field-builder-panel.test.tsx
```

Expected: FAIL because `FieldBuilderPanel` does not exist.

- [ ] **Step 3: Implement the focused controlled panel**

Define these public types and state rules:

```tsx
export type FieldBuilderValues = {
  name: string
  fieldType: 'text' | 'number' | 'date' | 'status' | 'single_select' |
    'multi_select' | 'user' | 'checkbox' | 'url' | 'email' | 'phone'
  required: boolean
  choices: string[]
}

type FieldBuilderPanelProps = {
  onSubmit: (values: FieldBuilderValues, idempotencyKey: string) => Promise<void>
  onClose: () => void
}
```

Generate a fresh key once per newly opened panel. Preserve it only for a network/5xx retry. Normalize duplicate local choices for feedback, but submit only after server-facing values are valid. Use semantic labels, native form controls and the existing light drawer/full-screen mobile sheet styling; do not add a package.

- [ ] **Step 4: Add typed transport**

Add to `api.ts`:

```ts
export type FieldInitializationReceipt = { field: SafeTableField; affected_view_ids: string[] }
initializeField: (tableId: string, values: FieldBuilderValues, idempotencyKey: string) =>
  postJson<FieldInitializationReceipt>(`/tables/${tableId}/field-initializations`, {
    name: values.name, field_type: values.fieldType, required: values.required,
    ...(choiceFieldTypes.has(values.fieldType) ? { choices: values.choices } : {}),
  }, idempotencyKey),
```

`choiceFieldTypes` must be a local immutable `Set` containing only `status`, `single_select` and `multi_select`.

- [ ] **Step 5: Run panel tests and production build**

Run:

```powershell
cd mini-app; npm.cmd test -- --run src/test/field-builder-panel.test.tsx
npm.cmd run build
```

Expected: panel tests pass and TypeScript/Vite build exits `0`.

- [ ] **Step 6: Commit panel and transport**

```powershell
git add mini-app/src/app/FieldBuilderPanel.tsx mini-app/src/app/api.ts mini-app/src/styles.css mini-app/src/test/field-builder-panel.test.tsx
git commit -m "feat(stage07): add field builder panel"
```

---

### Task 7: Connect Field Initialization to Protected App State and Canvas

**Files:**

- Modify: `mini-app/src/app/App.tsx`
- Modify: `mini-app/src/app/BaseCanvas.tsx`
- Modify: `mini-app/src/app/protectedQuery.ts`
- Test: `mini-app/src/test/field-builder-flow.test.tsx`

**Interfaces:**

- Consumes: `api.initializeField`, `FieldBuilderPanel`, `SafeTableField`, current `openTableView`/canvas generation logic and protected query keys.
- Produces: `onCreateField`, exact safe receipt verification and a real capability-gated `添加字段`/`添加第一个字段` surface.

- [ ] **Step 1: Write failing protected-flow tests**

```tsx
fireEvent.click(screen.getByRole('button', { name: '添加第一个字段' }))
fireEvent.change(screen.getByLabelText('字段名称'), { target: { value: '客户阶段' } })
fireEvent.click(screen.getByRole('button', { name: '创建字段' }))
await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
  '/tables/table-new/field-initializations', expect.objectContaining({ method: 'POST' })
))
expect(await screen.findByRole('columnheader', { name: '客户阶段' })).toBeInTheDocument()
```

Add tests that `403` clears the workspace scope and shows no field preview; a response whose field ID is absent from the fresh schema never renders; old workspace/view responses cannot restore the panel or column; and a successful receipt rereads schema, presentation, records and create form.

- [ ] **Step 2: Run the App-flow test and verify it fails**

Run:

```powershell
cd mini-app; npm.cmd test -- --run src/test/field-builder-flow.test.tsx
```

Expected: FAIL because there is no capability-gated field entry or initialization request.

- [ ] **Step 3: Add query keys and exact invalidation**

Use existing keys such as `protectedQueryKey(scope, 'table', table.id, 'schema')` and `protectedQueryKey(scope, 'view', view.id, 'presentation')`. On a safe receipt, cancel/remove the active table schema, every affected view presentation/record window, current table create form and open record details. Then reread the current authorised table/view through `openTableView`; independently fetch the safe schema and verify `receipt.field.id` is present before closing the panel.

The mutation owner must map errors exactly as P3: `401` calls full protected cleanup, `403` removes the current workspace scope, `409` is rethrown to lock the panel, and network/5xx is rethrown to preserve its key/values.

- [ ] **Step 4: Replace the inert F1 empty state**

Extend `BaseCanvasProps` with `onCreateField?: () => void`. Render a real button only when `canManageSchema` and the callback exist:

```tsx
if (presentation.view_type === 'grid' && schema.fields.length === 0) {
  return <div className="grid-empty" role="status">
    <p>此数据表尚未添加字段。</p>
    {canManageSchema && onCreateField && <button type="button" onClick={onCreateField}>添加第一个字段</button>}
  </div>
}
```

Pass the same callback to a table-toolbar `添加字段` action for nonempty tables. A viewer receives no disabled button or protected metadata.

- [ ] **Step 5: Run focused application tests and build**

Run:

```powershell
cd mini-app; npm.cmd test -- --run src/test/field-builder-flow.test.tsx src/test/app-shell.test.tsx src/test/table-switch.test.tsx
npm.cmd run build
```

Expected: exact receipt navigation, stale rejection and denial tests pass; build exits `0`.

- [ ] **Step 6: Commit protected integration**

```powershell
git add mini-app/src/app/App.tsx mini-app/src/app/BaseCanvas.tsx mini-app/src/app/protectedQuery.ts mini-app/src/test/field-builder-flow.test.tsx
git commit -m "feat(stage07): refresh canvas after field creation"
```

---

### Task 8: Make Choice Fields Usable in Create and Direct-Edit Flows

**Files:**

- Modify: `mini-app/src/app/CreateRecordPanel.tsx`
- Modify: `mini-app/src/app/RecordDetail.tsx`
- Modify: `mini-app/src/styles.css`
- Test: `mini-app/src/test/create-record.test.tsx`
- Test: `mini-app/src/test/record-detail.test.tsx`

**Interfaces:**

- Consumes: server-filtered `options.choices` in `CreateForm`/`SafeTableField`, existing record create/update callbacks and server value validation.
- Produces: choice-safe native controls that send only strings or distinct string arrays from returned choices.

- [ ] **Step 1: Write failing create/edit tests**

```tsx
render(<CreateRecordPanel form={{ table_id: 't1', can_create: true, fields: [
  { key: 'tags', name: '标签', field_type: 'multi_select', required: true,
    options: { choices: ['vip', 'trial'] }, order_index: 0 },
] }} onCreate={onCreate} onClose={onClose} />)
fireEvent.click(screen.getByRole('checkbox', { name: 'vip' }))
fireEvent.click(screen.getByRole('checkbox', { name: 'trial' }))
fireEvent.click(screen.getByRole('button', { name: '创建记录' }))
expect(onCreate).toHaveBeenCalledWith({ tags: ['vip', 'trial'] })
```

Add direct-detail tests showing single-choice selects and multi-choice checkboxes, changing only visible values and never rendering a choice not supplied by the safe schema.

- [ ] **Step 2: Run focused UI tests and verify they fail**

Run:

```powershell
cd mini-app; npm.cmd test -- --run src/test/create-record.test.tsx src/test/record-detail.test.tsx
```

Expected: FAIL because current supported field types omit `multi_select` and direct edit treats select-like values as plain text.

- [ ] **Step 3: Implement choice controls**

Add `multi_select` to the CreateRecordPanel support set. Use a checked-array update that is deterministic and distinct:

```tsx
function toggleChoice(values: string[], choice: string): string[] {
  return values.includes(choice) ? values.filter((item) => item !== choice) : [...values, choice]
}
```

For `status`/`single_select`, render a native `<select>` only from `options.choices`. For `multi_select`, render one labelled checkbox per choice. RecordDetail follows the same server-derived controls; it never constructs an option from current raw record text.

- [ ] **Step 4: Run UI tests, full Mini App suite and build**

Run:

```powershell
cd mini-app; npm.cmd test -- --run src/test/create-record.test.tsx src/test/record-detail.test.tsx
npm.cmd test -- --run
npm.cmd run build
```

Expected: focused and full frontend test suites pass; build exits `0`.

- [ ] **Step 5: Commit record usability support**

```powershell
git add mini-app/src/app/CreateRecordPanel.tsx mini-app/src/app/RecordDetail.tsx mini-app/src/styles.css mini-app/src/test/create-record.test.tsx mini-app/src/test/record-detail.test.tsx
git commit -m "feat(stage07): support builder choice fields"
```

---

### Task 9: Prove Atomicity and Concurrency on Real PostgreSQL

**Files:**

- Create: `backend/tests/integration/test_stage07_field_builder_postgres.py`
- Modify: `project-docs/08-implementation/STAGE_07_TEST_PLAN.md`
- Modify: `project-docs/08-implementation/STAGE_07_RISK_REGISTER.md`

**Interfaces:**

- Consumes: disposable `STAGE06_LOCAL_DATABASE_URL`, Alembic head, F1 endpoint and SQLAlchemy UoW.
- Produces: real database evidence for rollback, idempotent replay and table-lock ordering; it does not become staging/production evidence.

- [ ] **Step 1: Write the environment-gated integration tests**

```python
@pytest.mark.skipif(not os.getenv("STAGE06_LOCAL_DATABASE_URL"), reason="requires disposable local PostgreSQL")
def test_concurrent_distinct_field_initializations_receive_consecutive_order(postgres_factory, table_id):
    def submit(name: str, key: str) -> Response:
        with postgres_factory() as client:
            return client.post(
                f"/tables/{table_id}/field-initializations",
                json={"name": name, "field_type": "text", "required": False},
                headers={"Idempotency-Key": key},
            )
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda pair: submit(*pair), [("First", "f1-a"), ("Second", "f1-b")]))
    assert [item.status_code for item in (first, second)] == [201, 201]
    assert sorted(item.json()["field"]["order_index"] for item in (first, second)) == [0, 1]
```

Write three executable cases: a forced exception after field add leaves no field/view/audit/idempotency record; same-key replay produces one field and one audit; and distinct keys serialize order/append once. Use the local integration test fixture's schema reset and Alembic upgrade rather than an existing user database.

- [ ] **Step 2: Run tests without the local URL and record the expected skip**

Run:

```powershell
cd backend; python -m pytest -q tests/integration/test_stage07_field_builder_postgres.py
```

Expected: all three tests skip with the exact disposable-local-PostgreSQL reason when the URL is absent.

- [ ] **Step 3: Run tests with the authorised disposable URL when available**

Run:

```powershell
cd backend; $env:STAGE06_LOCAL_DATABASE_URL = '<authorised-disposable-url>'; python -m pytest -q tests/integration/test_stage07_field_builder_postgres.py
```

Expected: all real PostgreSQL cases pass. If no URL is authorised, retain the skipped result as an explicit acceptance gap; do not create, inspect or alter a user database.

- [ ] **Step 4: Commit the integration proof**

```powershell
git add backend/tests/integration/test_stage07_field_builder_postgres.py project-docs/08-implementation/STAGE_07_TEST_PLAN.md project-docs/08-implementation/STAGE_07_RISK_REGISTER.md
git commit -m "test(stage07): cover field builder postgres safety"
```

---

### Task 10: Run Full Evidence, Visual Comparison and Close the F1 Documentation Loop

**Files:**

- Modify: `project-docs/08-implementation/STAGE_07_PROGRESS.md`
- Modify: `project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`
- Modify: `project-docs/08-implementation/STAGE_07_ACCEPTANCE_CHECKLIST.md`
- Modify: `project-docs/08-implementation/STAGE_07_SUBSTAGE_F1_FIELD_BUILDER_PLAN.md`

**Interfaces:**

- Consumes: focused/full tests, browser screenshots, console output, PostgreSQL result/skip status and retained visual reference.
- Produces: evidence-backed F1 status only; it must not mark Package 2 or Stage07 complete.

- [ ] **Step 1: Run fresh complete automated gates**

Run:

```powershell
cd backend; python -m pytest -q
cd ..\mini-app; npm.cmd test -- --run; npm.cmd run build
cd ..\backend; alembic heads; alembic upgrade head --sql
cd ..; git diff --check
```

Expected: backend/frontend/build/migration commands report their actual result; any skipped PostgreSQL test count and reason are retained verbatim.

- [ ] **Step 2: Create and inspect the disposable browser fixture**

At `1440px`, `1280px`, `430px` and `390px`, run these real interactions against a disposable fixture:

1. fieldless Grid -> `添加第一个字段` -> first `status` field with choices -> exact new header;
2. nonempty Grid -> `multi_select` field -> create and direct-edit a record with two allowed choices;
3. blank/duplicate name and invalid choice feedback;
4. simulated `503` same-key explicit retry, simulated `409` lock and simulated `403` generic denial; and
5. workspace/view switch during a pending request, proving no stale field renders.

Capture the rendered screen beside `assets/stage07/workspace-ledger-reference.png` at the matching desktop widths. Inspect visible differences in shell proportions, dense toolbar placement, drawer/sheet spacing, type scale, borders/radii, selection blue and right-rail treatment. Stop/remove the fixture and delete unsanctioned test artifacts after inspection.

- [ ] **Step 3: Update evidence documents accurately**

Change the F1 traceability row to `implemented-local` only when all non-PostgreSQL requirements and browser cases have evidence. If the local URL is absent, keep F1 `partial-local` with the exact three real-PostgreSQL cases as a visible gap. State that F2, V1, imports, governance and Package 4 remain unimplemented/contract-gated.

- [ ] **Step 4: Re-run final checks after documentation updates**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace error; status contains only the intended final F1 evidence documents before staging.

- [ ] **Step 5: Commit final F1 evidence**

```powershell
git add project-docs/08-implementation/STAGE_07_PROGRESS.md project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md project-docs/08-implementation/STAGE_07_ACCEPTANCE_CHECKLIST.md project-docs/08-implementation/STAGE_07_SUBSTAGE_F1_FIELD_BUILDER_PLAN.md
git commit -m "docs(stage07): record F1 field builder evidence"
```

## Plan Self-Review

| F1 design requirement | Plan coverage |
| --- | --- |
| exact independent type allowlist and F2/V1 exclusion | Global constraints, Tasks 1, 3 and 6 |
| no raw policy/options/key/config in browser | Tasks 1, 2 and 4 |
| generated key/default policy/validated choices | Tasks 3–5 |
| atomic append-once saved-view visibility | Tasks 3, 4 and 9 |
| same-key replay, rollback and concurrency order | Tasks 3, 4 and 9 |
| safe empty-table and field panel UX | Tasks 6 and 7 |
| multi-select create/direct edit | Tasks 5 and 8 |
| protected reread, stale/denied state | Task 7 |
| desktop/mobile reference comparison | Task 10 |
| full tests, documentation evidence and explicit residual gaps | Tasks 9 and 10 |

Placeholder scan is negative except where this plan quotes the required environment variable placeholder (`<authorised-disposable-url>`), which is intentionally never a real connection string. Function/type names introduced by one task are named in the interface block before later tasks consume them.

## Execution Order

Execute Tasks 1 through 10 in order. A task cannot be marked complete from a planned code path or a mocked happy-path test; it requires the exact focused command recorded in that task. Do not start F2, V1 or another Stage07 package while any F1 task is in progress.
