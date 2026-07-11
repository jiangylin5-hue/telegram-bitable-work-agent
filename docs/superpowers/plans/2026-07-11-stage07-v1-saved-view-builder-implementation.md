# Stage07 V1 Saved View Builder Implementation Plan

## Status

- Plan status: user-approved detailed TDD plan; execution in progress.
- Scope gate: the user approved the V1 design package and this implementation plan.
- Current Progress: Task 1 is complete locally: model/migration/UoW foundation exists; typed schema/API/ACL/query/UI work remains pending.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver durable Grid/Kanban/Calendar/Form saved views with private/restricted member access, server-only query semantics and a responsive Mini App Builder.

**Architecture:** Extend `PlatformView` with server-owned V1 owner/scope/version state and add narrow `ViewMemberGrant` rows. A dedicated V1 service validates typed presentation commands, intersects view ACL with existing authorization, applies canonical server filters/sorts before pagination and returns safe projections only. React reuses TD001 protected query keys and F1/F2 authoritative reread patterns.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL/JSONB, React, Vite, TypeScript, TanStack Query, Tailwind, shadcn/ui, lucide-react, pytest and Vitest.

## Global Constraints

- Implement only the approved V1 design and companion BDD/SDD/work-surface/index package.
- Reuse Stage06 authorization, P3/F1/F2 idempotency/audit and TD001 state. Do not create a permission engine, raw SQL executor, persistent browser cache, generic JSON Patch endpoint or expression DSL.
- Never expose/accept raw view `config`, `permission_policy`, `is_default`, owner identity, raw member role/status, hidden field metadata, audit body or arbitrary query text.
- Creation is private-only. Owner sharing happens only through a separate atomic member-replacement command after authoritative reread.
- Keep the existing system default Grid as the sole default. No public link, member group, delegation, default reassignment, delete UI, import/template, Bot, Telegram or production work.
- V1 creation uses `Idempotency-Key`; presentation/member mutations use `expected_version`; all route input is `extra="forbid"` and all browser error text is fixed-code allowlisted.
- Test red before implementation, then green. Atomic/concurrent/index claims require the authorised disposable PostgreSQL suite. UI changes require Browser evidence at 1440/1280/430/390 and fixture cleanup.

---

### Task 1: Add V1 persistence model and migration invariant

**Files:**

- Create: `backend/alembic/versions/20260711_0022_stage07_saved_view_builder.py`
- Modify: `backend/app/models/stage06_platform.py:186-229`
- Modify: `backend/app/services/stage06_platform.py:145-205`, `backend/app/services/stage06_platform.py:382-400`, `backend/app/services/stage06_platform.py:588-606`
- Create: `backend/tests/unit/test_stage07_view_builder_migration.py`
- Modify: `backend/tests/unit/test_stage06_builder_default_view_migration.py`

**Interfaces:**

- Consumes: `PlatformView`, existing `uq_views_one_default_per_table`, `SqlAlchemyStage06PlatformUnitOfWork`, `InMemoryStage06PlatformUnitOfWork`.
- Produces: `PlatformView.owner_user_id`, `PlatformView.scope`, `PlatformView.version`, `ViewMemberGrant`, UoW grant CRUD and locked view mutation access.

- [x] **Step 1: Write failing migration/model tests**

```python
def test_stage07_saved_view_builder_migration_adds_owner_scope_version_and_grants() -> None:
    module = importlib.import_module("alembic.versions.20260711_0022_stage07_saved_view_builder")
    assert module.revision == "20260711_0022"
    assert module.down_revision == "20260710_0021"
    assert "view_member_grants" in inspect.getsource(module.upgrade)

def test_platform_view_declares_v1_owner_scope_and_version() -> None:
    assert {"owner_user_id", "scope", "version"} <= set(PlatformView.__table__.c)
    assert ViewMemberGrant.__tablename__ == "view_member_grants"
```

- [x] **Step 2: Verify red test**

Run: `python -m pytest -q tests/unit/test_stage07_view_builder_migration.py`

Expected: FAIL because the revision/model/grant type is missing.

- [x] **Step 3: Add minimal durable model and migration**

```python
class ViewMemberGrant(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "view_member_grants"
    __table_args__ = (
        UniqueConstraint("view_id", "user_id", name="uq_view_member_grants_view_user"),
    )
    view_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("views.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(160), nullable=False)
    access_level: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
```

Add nullable `owner_user_id`, non-null `scope` default `system_default`, and non-null `version` default `1` to `PlatformView`. The Alembic migration backfills existing rows to `system_default`, preserves the partial default Grid index and creates `view_member_grants` with the correctness-critical unique grant constraint. Do not create `ix_view_member_grants_user_status` or `ix_views_table_scope_status` yet: Task 7 must first record the required disposable-PostgreSQL `EXPLAIN` evidence; without that evidence they remain deferred. Add UoW methods `lock_view_for_mutation`, `list_view_grants`, `replace_view_grants` and `list_views_accessible_to_user` to both in-memory and SQLAlchemy adapters.

- [x] **Step 4: Verify migration/model tests green**

Run: `python -m pytest -q tests/unit/test_stage07_view_builder_migration.py tests/unit/test_stage06_builder_default_view_migration.py`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/alembic/versions/20260711_0022_stage07_saved_view_builder.py backend/app/models/stage06_platform.py backend/app/services/stage06_platform.py backend/tests/unit/test_stage07_view_builder_migration.py backend/tests/unit/test_stage06_builder_default_view_migration.py
git commit -m "feat(stage07): add saved view ownership persistence"
```

---

### Task 2: Define strict V1 command and response schemas

**Files:**

- Modify: `backend/app/schemas/stage06_platform.py:267-365`
- Create: `backend/tests/unit/test_stage07_view_builder_schemas.py`

**Interfaces:**

- Consumes: bearer actor, existing table/view identifiers and V1 JSON payloads.
- Produces: `ViewInitializationRequest`, `ViewPresentationPatchRequest`, `ViewMemberReplaceRequest`, `ViewBuilderResponse` and fixed-code API errors.

- [ ] **Step 1: Write failing schema boundary tests**

```python
def test_view_initialization_is_private_and_rejects_acl_fields() -> None:
    payload = {"name": "Mine", "view_type": "grid", "members": [{"user_id": "u2"}]}
    with pytest.raises(ValidationError):
        ViewInitializationRequest.model_validate(payload)

def test_presentation_patch_requires_version_and_rejects_raw_config() -> None:
    with pytest.raises(ValidationError):
        ViewPresentationPatchRequest.model_validate({"expected_version": 1, "config": {}})
```

- [ ] **Step 2: Verify red test**

Run: `python -m pytest -q tests/unit/test_stage07_view_builder_schemas.py`

Expected: FAIL because typed V1 commands do not exist.

- [ ] **Step 3: Add allowlisted Pydantic v2 models**

```python
class ViewInitializationRequest(StrictStage06Model):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    view_type: Literal["grid", "kanban", "calendar", "form"]
    presentation: ViewPresentationCommand

class ViewMemberReplaceRequest(StrictStage06Model):
    expected_version: Annotated[int, Field(ge=1)]
    members: list[ViewMemberCommand] = Field(default_factory=list, max_length=100)
```

Use a shared strict base with `extra="forbid"`; define typed operators, sort directions, a single group, field-order items, Kanban/Calendar/Form settings and allowed member access levels (`editor`, `viewer`). Do not use `dict[str, Any]` for V1 browser input. Define response schemas that expose only readable field keys/labels, canonical query summary, caller capability flags, `scope`, `version`, owner-self indicator and active grant display rows.

- [ ] **Step 4: Verify green and regression schemas**

Run: `python -m pytest -q tests/unit/test_stage07_view_builder_schemas.py tests/unit/test_stage06_platform_api.py`

Expected: PASS; legacy schemas still parse unchanged.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/stage06_platform.py backend/tests/unit/test_stage07_view_builder_schemas.py
git commit -m "feat(stage07): define strict saved view commands"
```

---

### Task 3: Canonicalize and validate presentation commands server-side

**Files:**

- Modify: `backend/app/services/stage06_platform.py:1337-1538`
- Create: `backend/tests/unit/test_stage07_view_builder_validation.py`

**Interfaces:**

- Consumes: typed V1 command, table field metadata and caller field visibility.
- Produces: canonical stored V1 presentation, a safe builder projection, and fixed validation codes.

- [ ] **Step 1: Write failing validation and projection tests**

```python
def test_grid_query_rejects_more_than_twelve_filters() -> None:
    with pytest.raises(Stage06PlatformError, match="view_filter_limit"):
        service.canonicalize_v1_presentation(table, actor, grid_with_filters(13))

def test_hidden_or_unauthorized_field_never_enters_builder_projection() -> None:
    projection = service.build_v1_builder_projection(view, actor_without_sensitive_field)
    assert "sensitive_field" not in json.dumps(projection)
```

- [ ] **Step 2: Verify red test**

Run: `python -m pytest -q tests/unit/test_stage07_view_builder_validation.py`

Expected: FAIL because V1 canonicalization is absent.

- [ ] **Step 3: Implement one service-owned canonicalization path**

```python
def canonicalize_v1_presentation(
    self, *, table: PlatformTable, actor: ActorScope, command: ViewPresentationCommand
) -> CanonicalViewPresentation:
    readable = self._readable_field_map(table=table, actor=actor)
    return self._validate_and_normalize(command=command, fields=readable)
```

Enforce A01--A07 exactly: Grid field order only from readable fields; at most 12 flat AND clauses; at most three stable sorts; one group; only enumerated operators per field type; no relation/lookup grouping; relation filters use candidate IDs from the safe picker; lookup filter/sort only for numeric lookup values; Kanban, Calendar and Form accept only their documented typed settings. Persist the canonical result in the existing JSONB `config` only as server-owned data and return an independently constructed safe projection. Reject unsupported nested lookup depth, formula text, free expressions and client-supplied policy.

- [ ] **Step 4: Verify green plus F1/F2 regression**

Run: `python -m pytest -q tests/unit/test_stage07_view_builder_validation.py tests/unit/test_stage06_platform_api.py tests/unit/test_stage07_relation_lookup.py`

Expected: PASS; legacy safe presentation and F2 relation/lookup guards remain intact.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/stage06_platform.py backend/tests/unit/test_stage07_view_builder_validation.py
git commit -m "feat(stage07): validate canonical view presentation"
```

---

### Task 4: Implement view ACL, versioning and idempotent initialization

**Files:**

- Modify: `backend/app/services/stage06_platform.py:145-205`, `backend/app/services/stage06_platform.py:1337-1538`
- Create: `backend/tests/unit/test_stage07_view_builder_access.py`
- Create: `backend/tests/integration/test_stage07_view_builder_postgres.py`

**Interfaces:**

- Consumes: authenticated caller, table permission result, `Idempotency-Key`, `expected_version` and member-replacement command.
- Produces: a private V1 view, owner/editor/viewer effective capabilities, atomic grant replacement and version conflict errors.

- [ ] **Step 1: Write failing access-control tests**

```python
def test_new_v1_view_is_private_even_when_creator_can_read_entire_base(client) -> None:
    created = create_view(client, idempotency_key="new-private")
    assert created["scope"] == "private"
    assert read_as("another-base-member", created["id"]).status_code == 404

def test_editor_cannot_replace_members_and_viewer_cannot_patch_presentation() -> None:
    assert replace_members_as("editor").status_code == 403
    assert patch_presentation_as("viewer").status_code == 403
```

- [ ] **Step 2: Verify red test**

Run: `python -m pytest -q tests/unit/test_stage07_view_builder_access.py`

Expected: FAIL because V1 ACL behavior is absent.

- [ ] **Step 3: Add narrow effective-access service methods**

```python
def resolve_view_access(self, *, view: PlatformView, actor: ActorScope) -> ViewAccess:
    base_access = self._require_table_read_scope(view.table_id, actor)
    role = self._view_role_from_owner_or_active_grant(view, actor.user_id)
    return ViewAccess.intersect(base_access=base_access, view_role=role)
```

Implement initialization as private-only and idempotent through the existing Stage06 idempotency store. Lock the view row before `PATCH` or `PUT members`, compare `expected_version`, update canonical state and increment `version` exactly once on success. The owner may change presentation and replace active editor/viewer grants; editors may change presentation only; viewers read only. Grant replacement is atomic, may not grant an unknown/disabled Base member, preserves owner authority outside the grant rows and recomputes `scope` as `private` or `restricted`. Underlying Base/Table/Field authorization is always intersected and must return not-found-safe denial where existing routes do so.

- [ ] **Step 4: Run unit and disposable PostgreSQL concurrency coverage**

Run: `python -m pytest -q tests/unit/test_stage07_view_builder_access.py`

Run: `python -m pytest -q tests/integration/test_stage07_view_builder_postgres.py -m postgres`

Expected: PASS, including duplicate initialization idempotency, stale `expected_version`, concurrent grant replacement and unique grant/index behavior against PostgreSQL.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/stage06_platform.py backend/tests/unit/test_stage07_view_builder_access.py backend/tests/integration/test_stage07_view_builder_postgres.py
git commit -m "feat(stage07): enforce saved view member access"
```

---

### Task 5: Apply canonical Grid query semantics before pagination

**Files:**

- Modify: `backend/app/services/stage06_platform.py:1659-1765`
- Modify: `backend/tests/unit/test_stage06_pagination.py`
- Create: `backend/tests/unit/test_stage07_view_builder_query_execution.py`
- Modify: `backend/tests/integration/test_stage07_view_builder_postgres.py`

**Interfaces:**

- Consumes: a readable Grid view's canonical filters/sorts/group and existing record-list pagination cursor.
- Produces: server-filtered, stable-sorted record rows and permitted single-group metadata, with no client predicate authority.

- [ ] **Step 1: Write failing query-order tests**

```python
def test_filter_and_stable_sorts_happen_before_limit_and_cursor() -> None:
    page = list_records_for_view(grid_with_two_sorts_and_filter, limit=2)
    assert page["rows"] == ["r3", "r1"]
    assert page["next_cursor"] is not None

def test_relation_and_lookup_fields_cannot_be_used_as_group_keys() -> None:
    assert patch_view(group_by="related_record").status_code == 422
```

- [ ] **Step 2: Verify red test**

Run: `python -m pytest -q tests/unit/test_stage07_view_builder_query_execution.py`

Expected: FAIL because list logic currently pages raw records before V1 execution.

- [ ] **Step 3: Introduce a service-owned execution pipeline**

```python
records = self._load_visible_records(table_id=table_id, actor=actor)
matched = self._apply_v1_filters(records=records, query=canonical_query)
ordered = self._stable_sort_v1_records(records=matched, sorts=canonical_query.sorts)
page = self._paginate_records(records=ordered, cursor=cursor, limit=limit)
```

Ensure the pipeline reads only already-authorized field values; does not emit hidden values through predicates, sort keys, counts or grouping metadata; provides deterministic record-ID tie-break behavior; uses the documented numeric lookup treatment; and does not let browser query parameters override saved view semantics. Use SQLAlchemy/JSONB operators where that preserves semantics and use bounded, covered fallback only if the existing generic record architecture requires it. Do not add free-text formula evaluation, search DSL, multi-group or client-side filtering.

- [ ] **Step 4: Verify green unit, regression and PostgreSQL tests**

Run: `python -m pytest -q tests/unit/test_stage07_view_builder_query_execution.py tests/unit/test_stage06_pagination.py`

Run: `python -m pytest -q tests/integration/test_stage07_view_builder_postgres.py -m postgres`

Expected: PASS, with ordering/pagination parity under actual PostgreSQL.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/stage06_platform.py backend/tests/unit/test_stage06_pagination.py backend/tests/unit/test_stage07_view_builder_query_execution.py backend/tests/integration/test_stage07_view_builder_postgres.py
git commit -m "feat(stage07): execute saved grid query server-side"
```

---

### Task 6: Expose only the approved V1 HTTP surface

**Files:**

- Modify: `backend/app/api/routes/stage06_platform.py:472-535`, `backend/app/api/routes/stage06_platform.py:830-910`
- Modify: `backend/app/schemas/stage06_platform.py:267-365`
- Create: `backend/tests/unit/test_stage07_view_builder_api.py`
- Modify: `backend/tests/unit/test_stage06_platform_api.py`

**Interfaces:**

- Consumes: existing Stage06 bearer authentication, Idempotency-Key and typed V1 route payloads.
- Produces: only the five approved endpoints, safe response bodies, fixed security error codes and compatible legacy routes.

- [ ] **Step 1: Write failing contract tests**

```python
def test_v1_routes_require_authorized_actor_and_never_return_raw_policy(client) -> None:
    view = initialize_private_view(client)
    response = client.get(f"/views/{view['id']}/builder", headers=actor_headers())
    assert response.status_code == 200
    assert {"permission_policy", "owner_user_id", "config"}.isdisjoint(response.json())

def test_unapproved_create_view_route_cannot_create_restricted_v1_view(client) -> None:
    response = client.post("/tables/table-1/views", json={"scope": "restricted"})
    assert response.status_code in {400, 422}
```

- [ ] **Step 2: Verify red test**

Run: `python -m pytest -q tests/unit/test_stage07_view_builder_api.py`

Expected: FAIL because V1 endpoints and response projection do not exist.

- [ ] **Step 3: Add explicit V1 routes; retain legacy surface untouched**

```python
@router.post("/tables/{table_id}/view-initializations", status_code=status.HTTP_201_CREATED)
async def initialize_view(...): ...

@router.patch("/views/{view_id}/presentation")
async def patch_view_presentation(...): ...

@router.put("/views/{view_id}/members")
async def replace_view_members(...): ...
```

Also implement `GET /tables/{table_id}/view-builder-context` and `GET /views/{view_id}/builder`, and wire the existing safe record-list endpoint to V1 execution when the selected view is a V1 Grid. Parse `Idempotency-Key` only for initialization and `expected_version` only from the typed body for mutations. Translate service errors to the SDD's allowlisted codes (`view_not_found`, `view_access_denied`, `view_version_conflict`, `view_filter_limit`, `view_query_unsupported`, etc.); do not reflect exception strings. Do not widen the existing raw create/view response routes as a shortcut.

- [ ] **Step 4: Verify route contract and compatibility**

Run: `python -m pytest -q tests/unit/test_stage07_view_builder_api.py tests/unit/test_stage06_platform_api.py`

Expected: PASS; no route returns raw configuration/policy or bypasses ACL.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/stage06_platform.py backend/app/schemas/stage06_platform.py backend/tests/unit/test_stage07_view_builder_api.py backend/tests/unit/test_stage06_platform_api.py
git commit -m "feat(stage07): expose safe saved view builder routes"
```

---

### Task 7: Prove schema, index and security invariants on disposable PostgreSQL

**Files:**

- Modify: `backend/tests/integration/test_stage07_view_builder_postgres.py`
- Create: `backend/tests/integration/test_stage07_view_builder_security_postgres.py`
- Create: `project-docs/08-implementation/evidence/stage07-v1-view-builder-postgres.md`

**Interfaces:**

- Consumes: disposable local PostgreSQL fixture, migration chain and authorised API/service surface.
- Produces: evidence for migration head, partial/default index preservation, grant uniqueness, concurrent conflict behavior, non-disclosure and a measured decision to add or defer optional non-unique indexes.

- [ ] **Step 1: Write failing integration scenarios**

```python
def test_migration_keeps_one_system_default_grid_and_private_v1_rows_are_not_defaults(pg_session) -> None:
    ...

def test_denied_user_cannot_learn_hidden_field_from_builder_filter_sort_group_or_record_page(pg_client) -> None:
    ...
```

- [ ] **Step 2: Verify red test at the target migration**

Run: `python -m pytest -q tests/integration/test_stage07_view_builder_security_postgres.py -m postgres`

Expected: FAIL before Task 1--6 behavior exists.

- [ ] **Step 3: Close gaps exposed only by real PostgreSQL**

Do not alter product scope. If the fixture exposes a migration/default/transaction mismatch, fix the smallest model, migration, UoW or query implementation defect and add a regression test. Run and record the SDD-required `EXPLAIN (ANALYZE, BUFFERS)` evaluation before creating either optional access/list index. Add a follow-up migration only when the measured query shape justifies it; otherwise document both as explicitly deferred. Record database version, migration head, executed commands, sanitized test identifiers and pass/fail result in the evidence file. Do not include credentials, full record values, raw request bodies or sensitive field names.

- [ ] **Step 4: Verify the real database suite**

Run: `python -m pytest -q tests/integration/test_stage07_view_builder_postgres.py tests/integration/test_stage07_view_builder_security_postgres.py -m postgres`

Expected: PASS against a disposable real PostgreSQL database at Alembic head `20260711_0022`.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/integration/test_stage07_view_builder_postgres.py backend/tests/integration/test_stage07_view_builder_security_postgres.py project-docs/08-implementation/evidence/stage07-v1-view-builder-postgres.md
git commit -m "test(stage07): prove saved view PostgreSQL invariants"
```

---

### Task 8: Add Mini App V1 transport, protected query keys and error mapping

**Files:**

- Modify: `mini-app/src/app/api.ts:71-210`
- Modify: `mini-app/src/app/protectedQuery.ts`
- Create: `mini-app/src/app/view-builder-types.ts`
- Modify: `mini-app/src/test/api.test.ts`
- Create: `mini-app/src/test/view-builder-api.test.ts`

**Interfaces:**

- Consumes: the five V1 safe endpoints and authenticated Mini App transport.
- Produces: typed browser client methods, cache keys namespaced by table/view/version, safe error labels and no raw configuration transport type.

- [ ] **Step 1: Write failing transport tests**

```tsx
it("sends Idempotency-Key only when initializing a private view", async () => {
  await initializeView("table-1", command, "idempotency-1")
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/view-initializations"),
    expect.objectContaining({ headers: expect.objectContaining({ "Idempotency-Key": "idempotency-1" }) }),
  )
})

it("maps an allowlisted version conflict without rendering server text", () => {
  expect(toSafeViewError({ code: "view_version_conflict", detail: "secret" })).toBe("此视图已被更新，请重新加载后再试。")
})
```

- [ ] **Step 2: Verify red test**

Run: `npm run test -- --run src/test/view-builder-api.test.ts`

Expected: FAIL because V1 client functions/types are missing.

- [ ] **Step 3: Add typed requests and protected transport helpers**

```ts
export const viewBuilderKeys = {
  context: (tableId: string) => ["stage07", "view-builder-context", tableId] as const,
  builder: (viewId: string, version?: number) => ["stage07", "view-builder", viewId, version ?? "current"] as const,
}

export async function patchViewPresentation(
  viewId: string, command: ViewPresentationPatchRequest,
): Promise<ViewBuilderResponse> {
  return requestJson(`/views/${encodeURIComponent(viewId)}/presentation`, { method: "PATCH", body: command })
}
```

Model only safe V1 response fields; use `encodeURIComponent` for every path parameter; send exactly the server's documented JSON; keep credentials/auth behavior consistent with F1/F2. Use the existing query client's optimistic-update policy only if its rollback/invalidate pattern is already proven; otherwise invalidate and authoritative reread after each successful mutation. Map only documented codes to fixed Chinese labels and log no raw payload/error body.

- [ ] **Step 4: Verify green and previous transport tests**

Run: `npm run test -- --run src/test/view-builder-api.test.ts src/test/api.test.ts`

Expected: PASS; F2 transport remains unchanged.

- [ ] **Step 5: Commit**

```bash
git add mini-app/src/app/api.ts mini-app/src/app/protectedQuery.ts mini-app/src/app/view-builder-types.ts mini-app/src/test/api.test.ts mini-app/src/test/view-builder-api.test.ts
git commit -m "feat(stage07): add typed view builder transport"
```

---

### Task 9: Build the accessible View Builder and owner-only Access panels

**Files:**

- Create: `mini-app/src/app/ViewBuilderPanel.tsx`
- Create: `mini-app/src/app/ViewAccessPanel.tsx`
- Create: `mini-app/src/app/ViewQueryControls.tsx`
- Modify: `mini-app/src/app/App.tsx:15-900`
- Create: `mini-app/src/test/view-builder-panel.test.tsx`
- Create: `mini-app/src/test/view-access-panel.test.tsx`

**Interfaces:**

- Consumes: safe builder/context projections and V1 mutation callbacks.
- Produces: create-private-view flow, type-specific editing, flat query controls, owner access management and deterministic focus/live feedback.

- [ ] **Step 1: Write failing interaction/accessibility tests**

```tsx
it("creates a private view before rendering its Access panel", async () => {
  render(<ViewBuilderPanel tableId="t1" />)
  await user.click(screen.getByRole("button", { name: "新建视图" }))
  await user.click(screen.getByRole("button", { name: "创建私有视图" }))
  expect(await screen.findByRole("heading", { name: "访问权限" })).toBeVisible()
})

it("does not render grant controls for editor and viewer capabilities", () => {
  render(<ViewAccessPanel capability="editor" />)
  expect(screen.queryByRole("button", { name: "保存成员权限" })).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Verify red test**

Run: `npm run test -- --run src/test/view-builder-panel.test.tsx src/test/view-access-panel.test.tsx`

Expected: FAIL because the V1 panels do not exist.

- [ ] **Step 3: Implement components by reusing existing F1/F2 panel patterns**

```tsx
<Dialog open={open} onOpenChange={setOpen}>
  <DialogContent aria-describedby={undefined}>
    <ViewQueryControls value={draft.presentation.query} onChange={updateQuery} fields={builder.fields} />
  </DialogContent>
</Dialog>
```

Use shadcn/ui Dialog, Sheet, Select, Checkbox, Button and existing form/error primitives rather than custom modal, state machine or permission UI. The create flow has name/type/presentation only and clearly labels the result as private. Render Grid controls: ordered visible fields, flat AND filters (max 12), max-three sorts and one group. Render Kanban/Calendar/Form only using the settings supplied by safe context; unsupported field/type combinations are disabled with the fixed product explanation. Relation filters invoke the existing F2 safe candidate picker; numeric lookup controls use typed numeric values; no relation/lookup group control is rendered. Owner sees active member list and editor/viewer grant choices; editor/viewer never see mutation controls. Implement keyboard focus return, `aria-live` mutation state, labels, Escape close and fixed safe errors.

- [ ] **Step 4: Verify green and F1/F2 panel regression**

Run: `npm run test -- --run src/test/view-builder-panel.test.tsx src/test/view-access-panel.test.tsx src/test/builder-create-panel.test.tsx src/test/f2-field-builder-panel.test.tsx`

Expected: PASS; prior builder/field flows retain their behavior.

- [ ] **Step 5: Commit**

```bash
git add mini-app/src/app/ViewBuilderPanel.tsx mini-app/src/app/ViewAccessPanel.tsx mini-app/src/app/ViewQueryControls.tsx mini-app/src/app/App.tsx mini-app/src/test/view-builder-panel.test.tsx mini-app/src/test/view-access-panel.test.tsx
git commit -m "feat(stage07): add saved view builder panels"
```

---

### Task 10: Wire selected views into the Mini App canvas and renderers

**Files:**

- Modify: `mini-app/src/app/App.tsx:15-900`
- Modify: `mini-app/src/app/BaseCanvas.tsx:6-180`
- Modify: `mini-app/src/app/App.tsx:15-900`
- Create: `mini-app/src/test/view-builder-lifecycle.test.tsx`
- Modify: `mini-app/src/test/view-renderers.test.tsx`

**Interfaces:**

- Consumes: selected view safe builder response, record list response and typed V1 capabilities.
- Produces: authoritative selected-view lifecycle, Grid/Kanban/Calendar/Form rendering, safe query summaries and no locally authoritative view state.

- [ ] **Step 1: Write failing lifecycle/rendering tests**

```tsx
it("invalidates then re-reads builder and records after a versioned presentation save", async () => {
  render(<App />)
  await saveViewPresentation()
  expect(fetchBuilder).toHaveBeenCalledTimes(2)
  expect(fetchRecords).toHaveBeenCalledTimes(2)
})

it("renders each allowed view type without client-side filter execution", () => {
  for (const viewType of ["grid", "kanban", "calendar", "form"] as const) {
    render(<BaseCanvas {...canvasFixture(viewType, serverFilteredRows)} />)
    expect(screen.getByTestId(`view-${viewType}`)).toBeVisible()
  }
})
```

- [ ] **Step 2: Verify red test**

Run: `npm run test -- --run src/test/view-builder-lifecycle.test.tsx src/test/view-renderers.test.tsx`

Expected: FAIL because the canvas does not yet own V1 selected-view lifecycle.

- [ ] **Step 3: Use a single selected-view state and authoritative rereads**

```tsx
const selectedViewQuery = useQuery({
  queryKey: viewBuilderKeys.builder(selectedViewId),
  queryFn: () => getViewBuilder(selectedViewId),
  enabled: Boolean(selectedViewId),
})
```

Replace inert toolbar placeholders only where the selected view reports the matching capability. Save paths must await the server mutation, invalidate builder/context/records keys and render the reread canonical data. Grid shows the server's applied filter/sort/group summary rather than computing predicates locally. Kanban groups only by the server-approved field/settings, Calendar uses the approved date field and Form exposes only its configured readable fields; all three use the existing safe record/detail entry path. Preserve Record Detail relation edit/safe rendering from F2. Do not add drag-and-drop mutation, delete view, default reassignment or client-managed ACL shadow state.

- [ ] **Step 4: Verify green lifecycle and renderer suite**

Run: `npm run test -- --run src/test/view-builder-lifecycle.test.tsx src/test/view-renderers.test.tsx src/test/record-mutation-safety.test.tsx`

Expected: PASS; selected view state is coherent after create, patch and member changes.

- [ ] **Step 5: Commit**

```bash
git add mini-app/src/app/App.tsx mini-app/src/app/BaseCanvas.tsx mini-app/src/test/view-builder-lifecycle.test.tsx mini-app/src/test/view-renderers.test.tsx
git commit -m "feat(stage07): render selected saved views"
```

---

### Task 11: Cover failure, responsive and no-disclosure edge cases

**Files:**

- Modify: `mini-app/src/app/ViewBuilderPanel.tsx`
- Modify: `mini-app/src/app/ViewAccessPanel.tsx`
- Modify: `mini-app/src/app/App.tsx`
- Create: `mini-app/src/test/view-builder-errors.test.tsx`
- Create: `mini-app/src/test/view-builder-responsive.test.tsx`

**Interfaces:**

- Consumes: version conflict, access denial, unsupported query, network failure and narrow viewport states.
- Produces: safe recovery paths, no raw data disclosure, usable mobile layout and tested keyboard behavior.

- [ ] **Step 1: Write failing edge-case tests**

```tsx
it("reloads canonical state after a version conflict and keeps no stale grant controls", async () => {
  mockPatchFailure("view_version_conflict")
  render(<ViewBuilderPanel viewId="v1" />)
  await user.click(screen.getByRole("button", { name: "保存" }))
  expect(await screen.findByText("此视图已被更新，请重新加载后再试。")).toBeVisible()
})

it("keeps panel actions reachable at 390px and sends focus back to the trigger on close", async () => {
  setViewport(390, 844)
  render(<ViewBuilderPanel viewId="v1" />)
  // interaction assertion uses the existing project resize helper
})
```

- [ ] **Step 2: Verify red test**

Run: `npm run test -- --run src/test/view-builder-errors.test.tsx src/test/view-builder-responsive.test.tsx`

Expected: FAIL until error recovery and responsive behavior are implemented.

- [ ] **Step 3: Implement bounded recovery and responsive layout**

Handle 401/403/404/409/422/5xx only through fixed user messages. On conflict/denial, clear incompatible local draft, invalidate protected keys and re-read when the current identity still has access. Retain draft only for validation errors when the safe response permits it; never render hidden member/field data. Ensure builder and access panels use scroll-safe content, sticky action bar when needed, minimum 44px targets, no horizontal overflow at 390px, and desktop two-column composition only where space permits. Keep mutation controls disabled while pending; do not retry non-idempotent create automatically.

- [ ] **Step 4: Verify green and production type/build gate**

Run: `npm run test -- --run src/test/view-builder-errors.test.tsx src/test/view-builder-responsive.test.tsx`

Run: `npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mini-app/src/app/App.tsx mini-app/src/app/ViewBuilderPanel.tsx mini-app/src/app/ViewAccessPanel.tsx mini-app/src/test/view-builder-errors.test.tsx mini-app/src/test/view-builder-responsive.test.tsx
git commit -m "test(stage07): cover saved view safety and responsive states"
```

---

### Task 12: Run end-to-end verification, perform UI acceptance and update stage evidence

**Files:**

- Modify: `project-docs/08-implementation/STAGE_07_PROGRESS.md`
- Modify: `project-docs/08-implementation/STAGE_07_BDD_AND_ACCEPTANCE.md`
- Modify: `project-docs/08-implementation/STAGE_07_TEST_PLAN.md`
- Modify: `project-docs/08-implementation/STAGE_07_ACCEPTANCE_CHECKLIST.md`
- Modify: `project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`
- Modify: `HANDOFF.md`
- Modify: `project-docs/08-implementation/STAGE_07_V1_VIEW_BUILDER_BDD_AND_ACCEPTANCE.md`
- Modify: `project-docs/08-implementation/STAGE_07_V1_VIEW_BUILDER_SDD.md`
- Modify: `project-docs/08-implementation/modules/STAGE_07_V1_VIEW_BUILDER_WORK_SURFACE.md`
- Modify: `project-docs/08-implementation/modules/STAGE_07_V1_VIEW_BUILDER_COMPLEX_FEATURE_INDEX.md`
- Create: `project-docs/08-implementation/evidence/stage07-v1-view-builder-ui.md`
- Create: `project-docs/08-implementation/evidence/stage07-v1-view-builder-verification.md`

**Interfaces:**

- Consumes: completed implementation, real disposable PostgreSQL result, Mini App dev server and the approved requirement documents.
- Produces: evidence-backed acceptance status for each V1 requirement, UI screenshots/observations and an accurate handoff without production claims.

- [ ] **Step 1: Run focused and full automated verification**

```bash
cd backend
python -m pytest -q tests/unit/test_stage07_view_builder_migration.py tests/unit/test_stage07_view_builder_schemas.py tests/unit/test_stage07_view_builder_validation.py tests/unit/test_stage07_view_builder_access.py tests/unit/test_stage07_view_builder_query_execution.py tests/unit/test_stage07_view_builder_api.py
python -m pytest -q tests/integration/test_stage07_view_builder_postgres.py tests/integration/test_stage07_view_builder_security_postgres.py -m postgres
python -m pytest -q
cd ../mini-app
npm run test -- --run
npm run build
```

Expected: every command passes except explicitly documented historical skips; capture exact counts and skip reasons without inventing production/staging evidence.

- [ ] **Step 2: Perform manual UI acceptance in a real browser**

Start the existing Mini App development command and use the browser-control verification workflow. Test with controlled fixtures at 1440px, 1280px, 430px and 390px:

1. Create Grid, Kanban, Calendar and Form views; confirm each begins private and default Grid remains unchanged.
2. Configure Grid field order, flat filter, three sorts and one group; confirm result changes only after server response and pagination remains stable.
3. Attempt a thirteenth filter, unsupported operator, relation/lookup group and stale version save; confirm fixed safe errors and canonical reread.
4. Grant editor then viewer; verify owner/editor/viewer UI capability differences and Base/Table/Field intersection.
5. Exercise relation candidate filtering, numeric lookup filter/sort and Record Detail relation edit to ensure F2 behavior is retained.
6. Inspect browser console/network only for expected safe endpoint traffic; confirm no raw config, policy, hidden field or member data appears.
7. Check keyboard Dialog/Sheet focus, Escape, live status, touch targets and no horizontal overflow on narrow viewports.

Save sanitized screenshots/observations and browser console result in the UI evidence document. End the browser-control session after evidence is captured; do not issue further browser actions in that session.

- [ ] **Step 3: Reconcile every requirement and state boundary**

For A01--A10 and every BDD scenario, mark `pass`, `blocked` or `not implemented` only with linked test/UI evidence. Update `Current Progress` and handoff with actual test counts, migration head, browser matrix, retained temporary artifacts and the explicit non-goals: no public link/group/delegation, no delete/default reassignment, no import/template/Telegram/Bot/production work, no expression DSL and no Stage08 scope. If any required check fails, leave the status unaccepted, document the failing behavior and return to the smallest owning task; do not call Stage07 complete.

- [ ] **Step 4: Verify documentation integrity and clean working state**

Run: `git diff --check`

Run: `rg -n "A0[1-9]|A10|Current Progress|implemented-local|not implemented|blocked" project-docs/08-implementation/STAGE_07_V1_VIEW_BUILDER_BDD_AND_ACCEPTANCE.md project-docs/08-implementation/STAGE_07_V1_VIEW_BUILDER_SDD.md project-docs/08-implementation/evidence/stage07-v1-view-builder-*.md`

Run: `git status --short`

Expected: no whitespace errors; every requirement has an evidence-backed state; only intentional, tracked files remain.

- [ ] **Step 5: Commit evidence-only closure candidate**

```bash
git add project-docs/08-implementation
git commit -m "docs(stage07): record V1 saved view verification evidence"
```

Do not merge, deploy, push or claim Stage07/production completion from this task. Those remain separate user-authorized gates.

---

## Final Review Checklist

- [ ] The migration is additive, backs existing views to `system_default`, keeps the original default Grid invariant and sets `owner_user_id` only for V1 views.
- [ ] New V1 views are always private at creation; restricted sharing occurs only through atomic owner-only replacement of editor/viewer grants.
- [ ] Every view access result is intersected with existing Base/Table/Field authorization, including builder context, query execution, member visibility and record details.
- [ ] All browser-originated V1 mutations are typed, allowlisted, idempotent/versioned as approved and reject unknown keys.
- [ ] No raw config/policy, hidden field, raw error, arbitrary expression, raw member state or client-side authoritative filtering leaks through any endpoint or UI state.
- [ ] Grid constraints are exactly enforced: field order, flat AND-only filters (max 12), stable sort (max 3), one group; relation/lookup grouping is forbidden; lookup filtering/sorting is numeric-only; relation filter uses safe candidates.
- [ ] Kanban, Calendar and Form only render/configure fields and settings supported by canonical safe context.
- [ ] Presentation changes, ACL changes and version conflict recovery always follow invalidation plus authoritative reread.
- [ ] PostgreSQL evidence proves migration/index/atomicity/non-disclosure; UI evidence proves the 1440/1280/430/390 matrix, keyboard behavior and clean console.
- [ ] Full backend and Mini App verification output is recorded truthfully with historical skips and any remaining risks.
- [ ] No unapproved scope has entered the diff: public link, member group, delegation/inheritance, view delete/default reassignment, import/template, Telegram/Bot, production or Stage08 work.
