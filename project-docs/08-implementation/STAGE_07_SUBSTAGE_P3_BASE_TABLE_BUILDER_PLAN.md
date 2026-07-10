# Stage07 P3 Base/Table Atomic Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This repository is already in the isolated `codex/stage07-mini-app-ui` worktree; do not create a second worktree.

**Goal:** Let an authorized user create a blank Base plus first Grid table, or a Grid table inside an existing Base, with atomic persistence, safe idempotent retry and receipt-verified navigation.

**Architecture:** Add two narrow initialization endpoints above the stable Stage06 primitive creation APIs. They call project-native Base/table/view service functions in one SQLAlchemy transaction, use the existing idempotency record model without the template route's early reservation commit, and return only navigation summaries. The Mini App owns a small creation panel and reuses the protected query/cache, Base Canvas and fresh authorized resource reads before rendering the returned destination.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, SQLAlchemy 2.x, Alembic, PostgreSQL JSONB/partial indexes, pytest, React, TypeScript, TanStack Query v5, Vitest, Testing Library, Vite and the existing light Stage07 CSS system.

## Status

- Document status: detailed implementation plan derived from the user-reviewed P3 design; awaiting user approval before test or production-code changes.
- Scope: only Stage07 Package 2 Base/Table atomic Builder; Fields, additional views, imports/templates, governance and Package 4 remain outside this plan.
- Current Progress: 2026-07-10 Task 1 is implemented and locally verified: RED migration/model checks, GREEN `3 passed`, one Alembic head `20260710_0021`, and offline SQL containing only the additive default-view partial unique index. Task 2 has not started.
- Source alignment: `AGENTS.md`; `STAGE_07_SOURCE_OF_TRUTH.md`; `STAGE_07_SDD.md`; `modules/STAGE_07_BITABLE_WORK_SURFACE.md`; `STAGE_07_BDD_AND_ACCEPTANCE.md`; `STAGE_07_API_DATA_SECURITY_CONTRACT.md`; `STAGE_07_SUBSTAGE_P3_BASE_TABLE_BUILDER_DESIGN.md`.

## Global Constraints

- Follow [P3 Base/Table Atomic Builder Design](STAGE_07_SUBSTAGE_P3_BASE_TABLE_BUILDER_DESIGN.md) exactly; its API/schema/permission decisions are approved.
- The browser submits display names only. It never submits a table key, view configuration, permission policy, default flag, role/capability claim, audit data or raw field data.
- Keep primitive `POST /workspaces/{id}/bases`, `POST /bases/{id}/tables` and `POST /bases/{id}/views` compatible. The Mini App must not call them for this substage.
- Use existing server checks: Base initialization requires `base.create`, `table.create`, `view.manage`; table initialization requires `table.create`, `view.manage` after Base ownership is resolved.
- Use one SQLAlchemy transaction for a newly initiated receipt, its Base/table/view graph, granular/parent audit events and completed idempotency record. Roll back all of them on failure.
- The new default view is active `grid`, named `所有记录`, with `config={"fields": []}`, an empty policy and `is_default=True`. No field and no record are created.
- PostgreSQL must enforce at most one `is_default=true` view per table with `uq_views_one_default_per_table`; legacy data is never silently rewritten.
- Existing memory-only protected query rules remain: user/workspace-prefixed keys; no browser persistence; `401` clears all Stage07 queries; `403` clears the active workspace scope.
- Desktop uses a focused side drawer. Narrow mobile uses a full-height sheet. Both use real buttons, labels, keyboard focus and touch-safe targets; no hover-only creation path.
- Do not implement field/view editing, default-view reassignment, rename/delete/copy, templates/imports, governance, Bots, drafts or automatic first fields.
- Every changed behavior begins with a failing focused test, then the minimum implementation, then a green focused command. Commit each independently reviewable task; do not push without the user's instruction.
- Run backend `python` and `alembic` commands from `backend/`; run `npm.cmd` commands from `mini-app/`. The final full-gate command explicitly changes directories.

---

## Locked File Structure

| Path | Responsibility |
| --- | --- |
| `backend/app/models/stage06_platform.py` | ORM declaration of the partial unique default-view index. |
| `backend/alembic/versions/20260710_0021_stage07_builder_defaults.py` | Additive PostgreSQL index migration from `20260710_0020`; downgrade removes only that index. |
| `backend/app/schemas/stage06_platform.py` | Trimmed initialization request models and safe receipt response models. |
| `backend/app/services/stage06_platform.py` | Public domain functions that build Base/Table/View graphs, generate table keys and write parent audit events. |
| `backend/app/api/routes/stage06_platform.py` | Atomic initialization routes, independent authorization, transaction/replay/error mapping. |
| `backend/tests/unit/test_stage06_platform_core.py` | Domain graph/default/audit/no-field unit tests. |
| `backend/tests/unit/test_stage06_platform_api.py` | In-memory FastAPI happy-path, safe response, denial, validation and replay/conflict tests. |
| `backend/tests/unit/test_stage06_builder_default_view_migration.py` | Revision-chain, partial-index and downgrade source-level checks. |
| `backend/tests/integration/test_stage06_postgres_security.py` | Real PostgreSQL atomic rollback, idempotency race/replay and partial-index enforcement. |
| `mini-app/src/app/api.ts` | Typed receipts and explicit `Idempotency-Key` POST transport. |
| `mini-app/src/app/BuilderCreatePanel.tsx` | Focused Base/table name panel, retry-key lifetime, accessible pending/error/close states. |
| `mini-app/src/app/App.tsx` | Panel state, exact receipt navigation, Home refresh and stale-response generations. |
| `mini-app/src/app/WorkspaceHome.tsx` | Capability-gated `新建 Base` entry callback. |
| `mini-app/src/app/BaseCanvas.tsx` | Capability-gated `新建表`, zero-field Grid state and no fake record entry. |
| `mini-app/src/styles.css` | Light desktop drawer/mobile sheet and zero-field styles. |
| `mini-app/src/test/api.test.ts` | Typed mutation URL/header/body transport tests. |
| `mini-app/src/test/builder-create-panel.test.tsx` | Isolated panel visibility, validation, focus, pending/retry/error tests. |
| `mini-app/src/test/builder-create-flow.test.tsx` | App-level Base/Table receipt, exact navigation, cache/denial/stale response tests. |
| `project-docs/08-implementation/STAGE_07_*.md` | Progress, API contract, implementation plan and traceability update only after code evidence exists. |

## Task 1: Enforce the Default-View Database Invariant

**Files:**

- Modify: `backend/app/models/stage06_platform.py`
- Create: `backend/alembic/versions/20260710_0021_stage07_builder_defaults.py`
- Create: `backend/tests/unit/test_stage06_builder_default_view_migration.py`

**Interfaces:**

- Consumes: `PlatformView.table_id`, `PlatformView.is_default`, Alembic revision `20260710_0020`.
- Produces: model index `uq_views_one_default_per_table`; migration revision `20260710_0021`; SQL condition `is_default IS TRUE`.

- [x] **Step 1: Write the failing migration/model checks**

  Create `backend/tests/unit/test_stage06_builder_default_view_migration.py` with the following assertions:

  ```python
  from pathlib import Path

  from app.models.stage06_platform import PlatformView


  MIGRATION = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20260710_0021_stage07_builder_defaults.py"


  def test_builder_default_view_migration_has_linear_revision_chain() -> None:
      source = MIGRATION.read_text(encoding="utf-8")

      assert 'revision = "20260710_0021"' in source
      assert 'down_revision = "20260710_0020"' in source
      assert '"uq_views_one_default_per_table"' in source
      assert 'postgresql_where=sa.text("is_default IS TRUE")' in source


  def test_platform_view_declares_the_same_partial_unique_index() -> None:
      indexes = {index.name: index for index in PlatformView.__table__.indexes}

      assert indexes["uq_views_one_default_per_table"].unique is True
      assert "table_id" in [column.name for column in indexes["uq_views_one_default_per_table"].columns]
      assert str(indexes["uq_views_one_default_per_table"].dialect_options["postgresql"]["where"]) == "is_default IS TRUE"


  def test_builder_default_view_migration_downgrade_removes_only_the_new_index() -> None:
      upgrade, downgrade = MIGRATION.read_text(encoding="utf-8").split("def downgrade", 1)

      assert "drop_table" not in upgrade
      assert 'op.drop_index("uq_views_one_default_per_table", table_name="views")' in downgrade
  ```

- [x] **Step 2: Run the focused test and record the expected RED result**

  Run:

  ```powershell
  python -m pytest -q tests/unit/test_stage06_builder_default_view_migration.py
  ```

  Expected: collection or assertions fail because revision `20260710_0021` and the model index do not exist.

- [x] **Step 3: Add the ORM and Alembic index with no data mutation**

  In `PlatformView`, import `Index` and `text`, then set `__table_args__` to the equivalent of:

  ```python
  __table_args__ = (
      Index(
          "uq_views_one_default_per_table",
          "table_id",
          unique=True,
          postgresql_where=text("is_default IS TRUE"),
      ),
  )
  ```

  Create the Alembic revision using this exact additive shape:

  ```python
  revision = "20260710_0021"
  down_revision = "20260710_0020"


  def upgrade() -> None:
      op.create_index(
          "uq_views_one_default_per_table",
          "views",
          ["table_id"],
          unique=True,
          postgresql_where=sa.text("is_default IS TRUE"),
      )


  def downgrade() -> None:
      op.drop_index("uq_views_one_default_per_table", table_name="views")
  ```

  Do not add `UPDATE views`, do not set defaults at schema level, and do not alter primitive `create_form_view` behavior in this task.

- [x] **Step 4: Run the focused test and Alembic graph checks**

  Run:

  ```powershell
  python -m pytest -q tests/unit/test_stage06_builder_default_view_migration.py
  alembic heads
  alembic upgrade head --sql
  ```

  Expected: focused test passes; `alembic heads` reports only `20260710_0021`; offline SQL contains the partial unique index without any data update.

- [x] **Step 5: Commit the database guard**

  ```powershell
  git add backend/app/models/stage06_platform.py backend/alembic/versions/20260710_0021_stage07_builder_defaults.py backend/tests/unit/test_stage06_builder_default_view_migration.py
  git commit -m "feat(stage07): guard one default view per table"
  ```

## Task 2: Add Domain-Level Atomic Resource Graph Builders

**Files:**

- Modify: `backend/app/services/stage06_platform.py`
- Modify: `backend/tests/unit/test_stage06_platform_core.py`

**Interfaces:**

- Consumes: existing `create_base`, `create_table`, `create_form_view`, `_record_stage06_audit`, `Actor` and `Stage06PlatformUnitOfWork`.
- Produces:

  ```python
  @dataclass(frozen=True)
  class BaseInitializationResult:
      base: BitableBase
      table: PlatformTable
      default_view: PlatformView

  @dataclass(frozen=True)
  class TableInitializationResult:
      table: PlatformTable
      default_view: PlatformView

  def initialize_base(uow, workspace_id, *, base_name: str, table_name: str, actor: Actor) -> BaseInitializationResult: ...
  def initialize_table(uow, base_id, *, table_name: str, actor: Actor) -> TableInitializationResult: ...
  ```

- [ ] **Step 1: Write domain tests before adding the service functions**

  Append focused tests to `backend/tests/unit/test_stage06_platform_core.py`:

  ```python
  def test_initialize_base_creates_one_zero_field_default_grid_and_parent_audit() -> None:
      uow = InMemoryStage06PlatformUnitOfWork()
      workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
      actor = Actor(actor_type="user", actor_id="owner-1", role="owner")

      result = initialize_base(
          uow,
          workspace.id,
          base_name="客户运营",
          table_name="客户",
          actor=actor,
      )

      assert result.base.workspace_id == workspace.id
      assert result.table.base_id == result.base.id
      assert result.table.key.startswith("tbl_")
      assert uow.list_fields(result.table.id) == []
      assert result.default_view.table_id == result.table.id
      assert result.default_view.name == "所有记录"
      assert result.default_view.view_type == "grid"
      assert result.default_view.config == {"fields": []}
      assert result.default_view.permission_policy == {}
      assert result.default_view.is_default is True
      assert [event.event_type for event in uow.audit_events][-1] == "stage06.base_initialized"


  def test_initialize_table_adds_only_its_own_default_grid() -> None:
      uow = InMemoryStage06PlatformUnitOfWork()
      workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
      base = create_base(uow, workspace.id, name="CRM")
      actor = Actor(actor_type="user", actor_id="owner-1", role="owner")

      result = initialize_table(uow, base.id, table_name="待办", actor=actor)

      assert uow.list_tables(base.id) == [result.table]
      assert uow.list_views(result.table.id) == [result.default_view]
      assert result.default_view.is_default is True
      assert uow.list_fields(result.table.id) == []
      assert uow.audit_events[-1].event_type == "stage06.table_initialized"
  ```

- [ ] **Step 2: Run the new tests and record the expected RED result**

  Run:

  ```powershell
  python -m pytest -q tests/unit/test_stage06_platform_core.py -k "initialize_base or initialize_table"
  ```

  Expected: import/collection failure because the initialization result types and functions do not exist.

- [ ] **Step 3: Add the smallest domain implementation**

  In `backend/app/services/stage06_platform.py`:

  1. Add the two frozen result dataclasses.
  2. Add `_normalized_builder_name(value: str, *, label: str) -> str` that strips whitespace and raises `PlatformValidationError("invalid_builder_name", label)` for empty values or strings longer than 160 characters.
  3. Add `_generated_table_key() -> str` returning `f"tbl_{uuid4().hex}"`.
  4. Extend `create_form_view` with keyword-only `is_default: bool = False`, and set `PlatformView.is_default=is_default`; existing callers continue receiving `False`.
  5. Implement `initialize_base` by normalizing both names, calling `create_base`, then `initialize_table`, and emitting `stage06.base_initialized` with `after_state={"resource_map": {"base_id": str(base.id), "table_id": str(table.id), "view_id": str(view.id)}}`.
  6. Implement `initialize_table` by resolving the Base, normalizing the table name, calling `create_table` with `_generated_table_key()`, calling `create_form_view` with the fixed `所有记录` Grid values and `is_default=True`, then emitting `stage06.table_initialized` with only Base/table/view IDs in `resource_map`.

  Use the same supplied `actor` for every child creation/audit call. Never add a field, record, policy or client-derived key.

- [ ] **Step 4: Run focused unit tests and the existing platform-core suite**

  Run:

  ```powershell
  python -m pytest -q tests/unit/test_stage06_platform_core.py
  ```

  Expected: all platform-core tests, including the two new graph tests, pass; existing primitive views remain `is_default=False` unless explicitly initialized.

- [ ] **Step 5: Commit the domain graph**

  ```powershell
  git add backend/app/services/stage06_platform.py backend/tests/unit/test_stage06_platform_core.py
  git commit -m "feat(stage07): initialize Base and table resource graphs"
  ```

## Task 3: Expose Safe, Atomic Initialization Receipts

**Files:**

- Modify: `backend/app/schemas/stage06_platform.py`
- Modify: `backend/app/api/routes/stage06_platform.py`
- Modify: `backend/tests/unit/test_stage06_platform_api.py`
- Modify: `backend/tests/unit/test_stage07_mini_app_api.py`
- Modify: `backend/tests/integration/test_stage06_postgres_security.py`

**Interfaces:**

- Consumes: Task 2 initialization functions; `begin_idempotent_operation`, `complete_idempotent_operation`, `fingerprint_request`; existing Stage06 auth/UoW/session.
- Produces:

  ```python
  class InitializeBaseRequest(BaseModel):
      base_name: str
      table_name: str

  class InitializeTableRequest(BaseModel):
      table_name: str

  class BuilderInitializationResponse(BaseModel):
      base: BaseSummaryResponse
      table: TableResponse
      default_view: ViewSummaryResponse
  ```

  ```text
  POST /workspaces/{workspace_id}/base-initializations
  POST /bases/{base_id}/table-initializations
  ```

- [ ] **Step 1: Write failing API/security tests**

  Add API tests with the existing `TestClient` plus `InMemoryStage06PlatformUnitOfWork` override. Each test uses a real `Idempotency-Key` header:

  ```python
  def test_base_initialization_returns_only_navigation_receipt_and_replays_same_key() -> None:
      # create owner workspace, POST the endpoint twice with the same key/payload
      # assert first status is 201, second is 200 and JSON bodies match
      # assert base/table/default_view have only safe summary keys
      # assert exactly one Base, one table, one view and one parent event exist

  def test_table_initialization_requires_server_authorization_and_returns_no_partial_resource() -> None:
      # create owner Base; switch request header to viewer
      # assert 403 and list_tables(base.id) stays unchanged

  def test_base_initialization_rejects_same_key_with_different_payload() -> None:
      # first successful post, then same key with a different table_name
      # assert 409 and one resource graph remains
  ```

  In `test_stage07_mini_app_api.py`, assert the response never serializes `config`, `permission_policy`, `is_default`, `role`, `capabilities`, `trace_id`, `request_fingerprint` or `idempotency_key`.

  In the PostgreSQL integration file, add three real-DB tests gated by existing `stage06_postgres`:

  1. inject a failure after Base/table construction and assert the transaction leaves no `BitableBase`, `PlatformTable`, `PlatformView`, parent audit or idempotency row;
  2. run two threads with identical Base-initialization payload/key and assert both responses are `201`/`200`, then one graph/one idempotency row exists;
  3. create one `is_default=True` view and assert a second default for the same table raises `IntegrityError` on commit while the first stays default.

- [ ] **Step 2: Run focused commands and record the expected RED result**

  Run:

  ```powershell
  python -m pytest -q tests/unit/test_stage06_platform_api.py tests/unit/test_stage07_mini_app_api.py -k "initialization"
  python -m pytest -q tests/integration/test_stage06_postgres_security.py -k "initialization or default_view"
  ```

  Expected: unit tests fail with `404`/missing schema and integration tests are either failing or skipped only when `STAGE06_LOCAL_DATABASE_URL` is unavailable.

- [ ] **Step 3: Add narrow schemas, routes and transaction/replay handling**

  Add the request and response models in `stage06_platform.py` schemas. The response must be composed manually from safe summary fields, not from primitive `ViewResponse`.

  In the route module:

  1. import `Header`, `Response`, `status`, `IntegrityError`, the Task 2 domain functions and idempotency helpers;
  2. authorize all required actions before calling `begin_idempotent_operation`;
  3. fingerprint exactly `{workspace_id, operation, actor_user_id, normalized request values}`;
  4. call `begin_idempotent_operation` directly and deliberately do **not** call template route helper `_begin_and_reserve`, because that helper commits early;
  5. on `replay`, assign `response.status_code = status.HTTP_200_OK` and return the stored safe receipt;
  6. on a started operation, call the Task 2 builder, create `BuilderInitializationResponse`, call `complete_idempotent_operation`, then commit once;
  7. catch `IntegrityError`, roll back the SQLAlchemy session, reread the idempotency record and replay a matching completed response; if the stored fingerprint differs, map to `409`;
  8. on every non-replay exception, call `session.rollback()` when a SQLAlchemy session exists before mapping the safe error;
  9. extend `_http_error` so `idempotency_conflict` and `idempotency_in_progress` map to `409`, while invalid names remain `422`.

  Use the following response construction pattern in both route handlers:

  ```python
  BuilderInitializationResponse(
      base=BaseSummaryResponse(
          id=str(result.base.id),
          name=result.base.name,
          source_type=result.base.source_type,
          status=result.base.status,
      ),
      table=TableResponse(
          id=str(result.table.id),
          base_id=str(result.table.base_id),
          name=result.table.name,
          key=result.table.key,
          status=result.table.status,
      ),
      default_view=ViewSummaryResponse(
          id=str(result.default_view.id),
          base_id=str(result.default_view.base_id),
          table_id=str(result.default_view.table_id),
          name=result.default_view.name,
          view_type=result.default_view.view_type,
          status=result.default_view.status,
      ),
  )
  ```

- [ ] **Step 4: Run focused API and real-PostgreSQL verification**

  Run:

  ```powershell
  python -m pytest -q tests/unit/test_stage06_platform_api.py tests/unit/test_stage07_mini_app_api.py -k "initialization"
  python -m pytest -q tests/integration/test_stage06_postgres_security.py -k "initialization or default_view"
  ```

  Expected: all focused unit tests pass. If `STAGE06_LOCAL_DATABASE_URL` is configured, the three integration tests pass against real PostgreSQL; otherwise pytest explicitly reports the environment-bound skip and it is recorded in progress, not treated as proof.

- [ ] **Step 5: Commit the safe HTTP contract**

  ```powershell
  git add backend/app/schemas/stage06_platform.py backend/app/api/routes/stage06_platform.py backend/tests/unit/test_stage06_platform_api.py backend/tests/unit/test_stage07_mini_app_api.py backend/tests/integration/test_stage06_postgres_security.py
  git commit -m "feat(stage07): add atomic Builder initialization api"
  ```

## Task 4: Add Typed Mini App Transport And an Accessible Creation Panel

**Files:**

- Modify: `mini-app/src/app/api.ts`
- Create: `mini-app/src/app/BuilderCreatePanel.tsx`
- Modify: `mini-app/src/app/WorkspaceHome.tsx`
- Modify: `mini-app/src/app/BaseCanvas.tsx`
- Modify: `mini-app/src/styles.css`
- Modify: `mini-app/src/test/api.test.ts`
- Create: `mini-app/src/test/builder-create-panel.test.tsx`

**Interfaces:**

- Consumes: `Workspace.capabilities.can_manage_schema`, safe receipt types and existing BaseCanvas table toolbar.
- Produces:

  ```ts
  export type BuilderInitializationReceipt = {
    base: BaseSummary
    table: PlatformTable
    default_view: ViewSummary
  }

  api.initializeBase(workspaceId, { baseName, tableName }, idempotencyKey): Promise<BuilderInitializationReceipt>
  api.initializeTable(baseId, { tableName }, idempotencyKey): Promise<BuilderInitializationReceipt>
  ```

  ```tsx
  <BuilderCreatePanel
    mode="base" | "table"
    onSubmit={(values, idempotencyKey) => Promise<void>}
    onClose={() => void}
  />
  ```

- [ ] **Step 1: Write failing API/panel/component tests**

  In `api.test.ts`, add a request assertion:

  ```ts
  await api.initializeBase('workspace-1', { baseName: '客户运营', tableName: '客户' }, 'idempotency-1')

  expect(fetchMock).toHaveBeenCalledWith(
    '/workspaces/workspace-1/base-initializations',
    expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({
        Accept: 'application/json',
        'Content-Type': 'application/json',
        'Idempotency-Key': 'idempotency-1',
      }),
      body: JSON.stringify({ base_name: '客户运营', table_name: '客户' }),
    }),
  )
  ```

  In `builder-create-panel.test.tsx`, test all of these separately:

  1. Base mode labels both inputs, defaults the first table to `数据表`, and cannot submit a whitespace-only Base name.
  2. Table mode has no Base-name input and defaults table name to `数据表`.
  3. the initial focus is the first name field; closing calls `onClose` and does not submit.
  4. a pending submission disables the submit button; a rejected promise shows generic `创建失败，请稍后重试。` and a second submit retains the exact idempotency key.
  5. `WorkspaceHome` has no `新建 Base` button when `can_manage_schema=false`; `BaseCanvas` has no `新建表` button under the same condition.

- [ ] **Step 2: Run focused frontend tests and record the expected RED result**

  Run:

  ```powershell
  npm.cmd test -- --run src/test/api.test.ts src/test/builder-create-panel.test.tsx
  ```

  Expected: import/render failures because the receipt transport and panel do not exist; existing canvas still exposes the plus button unconditionally.

- [ ] **Step 3: Implement only typed transport and presentational behavior**

  In `api.ts`, preserve the existing `getJson` transport but add an explicit `postJson<T>` helper that merges headers via `new Headers(init.headers)`, then sets `Accept`, `Content-Type` and `Idempotency-Key`. Do not let a passed `headers` object erase `Accept`.

  Implement the two calls exactly as:

  ```ts
  initializeBase: (workspaceId, values, key) => postJson<BuilderInitializationReceipt>(
    `/workspaces/${workspaceId}/base-initializations`,
    { base_name: values.baseName, table_name: values.tableName },
    key,
  ),
  initializeTable: (baseId, values, key) => postJson<BuilderInitializationReceipt>(
    `/bases/${baseId}/table-initializations`,
    { table_name: values.tableName },
    key,
  ),
  ```

  `BuilderCreatePanel` keeps its generated key in component state from first submit until close or successful parent resolution. Use `crypto.randomUUID()` only when the first submission starts. Keep form values on a rejected request. Use semantic `<aside aria-label="创建 Base">` or `<aside aria-label="创建数据表">`, visible labels, a `role="alert"` error, `disabled={saving}` and explicit cancel/close buttons.

  Extend `WorkspaceHomeProps` with optional `onCreateBase`; render the button only when `workspace.capabilities.can_manage_schema` and the callback both exist. Extend `BaseCanvasProps` with `canManageSchema` and optional `onCreateTable`; render the existing plus only when both are true. No new field/view action is added.

  Add light CSS classes `builder-create-panel`, `builder-create-backdrop`, `builder-create-form` and a `max-width: 900px` rule that makes the panel full width/full height above the mobile navigation. Reuse existing light borders, azure active color and current detail form controls; do not add dark fills, glow effects or card stacks.

- [ ] **Step 4: Run focused component/API tests**

  Run:

  ```powershell
  npm.cmd test -- --run src/test/api.test.ts src/test/builder-create-panel.test.tsx
  ```

  Expected: API body/header test and all five panel/visibility/focus/retry tests pass.

- [ ] **Step 5: Commit the typed UI boundary**

  ```powershell
  git add mini-app/src/app/api.ts mini-app/src/app/BuilderCreatePanel.tsx mini-app/src/app/WorkspaceHome.tsx mini-app/src/app/BaseCanvas.tsx mini-app/src/styles.css mini-app/src/test/api.test.ts mini-app/src/test/builder-create-panel.test.tsx
  git commit -m "feat(stage07): add Builder creation panel"
  ```

## Task 5: Wire Receipt-Verified Navigation And Empty-Field State

**Files:**

- Modify: `mini-app/src/app/App.tsx`
- Modify: `mini-app/src/app/BaseCanvas.tsx`
- Create: `mini-app/src/test/builder-create-flow.test.tsx`
- Modify: `mini-app/src/test/app-shell.test.tsx`

**Interfaces:**

- Consumes: Task 4 panel callbacks, `BuilderInitializationReceipt`, existing `loadWorkspaceHome`, protected query helpers and `openBase` fetch chain.
- Produces:

  ```ts
  type CanvasTarget = { tableId: string; viewId: string }
  async function openBase(base: BaseSummary, target?: CanvasTarget, homeOverride?: WorkspaceHome): Promise<void>
  async function createBase(values: { baseName: string; tableName: string }, key: string): Promise<void>
  async function createTable(values: { tableName: string }, key: string): Promise<void>
  ```

- [ ] **Step 1: Write failing application tests for success, exactness and stale state**

  Create `builder-create-flow.test.tsx` with mocked fetch sequences that prove:

  1. Home with `can_manage_schema=true` opens `创建 Base`; a successful Base receipt sends the exact POST/header/body, refetches Home and then requests only receipt Base tables/views, receipt table schema and receipt view presentation/records. The rendered Grid names the receipt Base/table/view and shows the zero-field message.
  2. An open authorized Base can create a table. The next canvas is the receipt table/view, even when the freshly returned lists put a pre-existing table/view first.
  3. If the receipt table/view is missing from the fresh authorized lists, the app renders the existing safe empty/denied boundary and makes no schema/presentation/record request for an unrelated first resource.
  4. A `403` creation response clears the protected workspace and does not leave the drawer, optimistic Base or receipt title visible.
  5. Resolve a delayed creation receipt after the user changes workspace; assert it cannot open the old workspace/Base.

  Add a renderer test in `app-shell.test.tsx` or `builder-create-flow.test.tsx` asserting a zero-field Grid shows the exact helper message and does not render `新建记录`.

- [ ] **Step 2: Run focused application tests and record the expected RED result**

  Run:

  ```powershell
  npm.cmd test -- --run src/test/builder-create-flow.test.tsx
  ```

  Expected: failure because Home/BaseCanvas cannot open the panel, no mutation exists and `openBase` always chooses the first list entry.

- [ ] **Step 3: Add generation-safe mutation/navigation code**

  In `App.tsx`:

  1. Add a `builderRequestVersion` ref and increment it on workspace change, Base/back transitions and panel close.
  2. Store `builderPanel` as `undefined | { mode: "base" } | { mode: "table"; base: BaseSummary }` only in the ready state.
  3. Pass `canManageSchema={selectedWorkspace.capabilities.can_manage_schema}`, `onCreateTable` and `onCreateBase` into current presentational components.
  4. Add `createBase` and `createTable` callbacks that capture the active workspace/Base and builder generation, call Task 4 transport, remove/invalidate the protected Home/base-table/base-view keys, fetch a current authorized Home record, and then call `openBase(receipt.base, { tableId: receipt.table.id, viewId: receipt.default_view.id }, refreshedHome)`.
  5. Change `openBase` so an omitted target retains today's first-authorized behavior, while a supplied target uses only an exact `table.id` and exact `view.id` belonging to that table. If either is absent after the fresh lists, commit the safe empty canvas and return before schema/presentation/records reads.
  6. At every async boundary, verify workspace ID, canvas generation and builder generation before committing state. Reuse existing `ApiError` branches: `401` calls `clearAllProtectedQueries`; `403` calls `clearProtectedWorkspace`; `404`/other errors enter the generic safe error boundary. Never place the receipt itself in a persistent cache or render it before list verification.
  7. Render `BuilderCreatePanel` beside current Home/Canvas/record drawer content only while `builderPanel` is present. Its successful promise closes only after receipt-verified navigation succeeds.

  In `BaseCanvas`, when the active Grid has `schema.fields.length === 0`, render:

  ```tsx
  <div className="grid-empty" role="status">此数据表尚未添加字段。字段配置将在 Builder 的下一子阶段提供。</div>
  ```

  and omit the record-create callback/button for that canvas. Preserve the separate generic no-table/no-view state.

- [ ] **Step 4: Run focused application and legacy regression tests**

  Run:

  ```powershell
  npm.cmd test -- --run src/test/builder-create-flow.test.tsx src/test/app-shell.test.tsx src/test/table-switch.test.tsx src/test/create-record-flow.test.tsx
  ```

  Expected: new success/table/exactness/denial/stale-state tests pass; existing table switching and scalar record-create tests remain green.

- [ ] **Step 5: Commit the application transition**

  ```powershell
  git add mini-app/src/app/App.tsx mini-app/src/app/BaseCanvas.tsx mini-app/src/test/builder-create-flow.test.tsx mini-app/src/test/app-shell.test.tsx
  git commit -m "feat(stage07): navigate from Builder receipts safely"
  ```

## Task 6: Perform Browser QA, Full Verification And Stage Documentation Update

**Files:**

- Modify: `project-docs/08-implementation/STAGE_07_API_DATA_SECURITY_CONTRACT.md`
- Modify: `project-docs/08-implementation/STAGE_07_IMPLEMENTATION_PLAN.md`
- Modify: `project-docs/08-implementation/STAGE_07_PROGRESS.md`
- Modify: `project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`
- Modify: `project-docs/08-implementation/STAGE_07_ACCEPTANCE_CHECKLIST.md`
- Temporary Create/Delete: `mini-app/qa_base_table_builder_fixture.py` or an equivalent disposable local fixture.

**Interfaces:**

- Consumes: Tasks 1–5, local FastAPI/fixture data and Browser capability.
- Produces: sanitized evidence for the P3 bounded substage only; no Stage07-wide completion claim.

- [ ] **Step 1: Add a disposable Browser fixture before using it**

  Create a fixture that returns only synthetic resource names and demonstrates all five visual cases:

  1. authorized Desktop New Base → `客户运营` / `客户` / `所有记录` → zero-field Grid;
  2. authorized Desktop New Table in an existing Base → exact new `待办` Grid while older tables remain;
  3. mobile sheet on a real narrow browser/emulator viewport with labelled controls and visible submit/cancel;
  4. required-name validation and a simulated safe error/retry state;
  5. denied mutation with no optimistic Base/table preview.

  The fixture must never include real tokens, raw policies, audit bodies, user names, record values or production URLs.

- [ ] **Step 2: Run the full automated gates before browser claims**

  Run:

  ```powershell
  Push-Location backend; python -m pytest -q; Pop-Location
  Push-Location mini-app; npm.cmd test -- --run; npm.cmd run build; Pop-Location
  git diff --check
  ```

  Also run the migration checks from Task 1 and, if `STAGE06_LOCAL_DATABASE_URL` is configured, the exact PostgreSQL integration command from Task 3. Record real pass/fail/skip counts; do not use earlier counts.

- [ ] **Step 3: Execute desktop/mobile Browser QA and inspect runtime state**

  Start the disposable fixture only through the approved local workflow. In the in-app Browser:

  1. execute the five flows from Step 1;
  2. inspect visible button labels, selected table/view, zero-field message and denied/error state;
  3. inspect console output for errors/warnings attributable to the feature;
  4. capture only sanitized local evidence at desktop plus the actual narrow viewport used; and
  5. report the real viewport if the Browser ignores a requested mobile size instead of calling it mobile evidence.

- [ ] **Step 4: Delete temporary artifacts and update evidence documents**

  Stop the fixture process and delete the fixture file. Update documentation only with observed evidence:

  - API contract §5 gets the two endpoint request/receipt boundaries, auth, idempotency and raw-data exclusions.
  - implementation plan Package 2 links P3 as an implemented bounded substage only after the tests pass.
  - progress records commands/results, browser flows, viewport facts, cleanup and remaining limits.
  - traceability changes Desktop builder Base/Table from `approved-contract-unimplemented` to `implemented-local` only if every listed acceptance criterion has evidence; field/view/import builder rows stay incomplete.
  - acceptance checklist marks only verifiably covered Base/Table builder items, never the whole Builder/import/template package.

- [ ] **Step 5: Final review and coherent substage commit**

  Re-read the P3 design's §12 checklist line by line against concrete tests/command output/browser evidence. Then run:

  ```powershell
  git status --short
  git diff --check
  ```

  Commit documentation/evidence only when the working tree contains no fixture or generated artifact:

  ```powershell
  git add project-docs/08-implementation/STAGE_07_API_DATA_SECURITY_CONTRACT.md project-docs/08-implementation/STAGE_07_IMPLEMENTATION_PLAN.md project-docs/08-implementation/STAGE_07_PROGRESS.md project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md project-docs/08-implementation/STAGE_07_ACCEPTANCE_CHECKLIST.md
  git commit -m "docs(stage07): record Base table Builder evidence"
  ```

## Execution Exit Criteria

This plan is executed only when all six tasks have their own RED/GREEN evidence and commits. P3 is accepted locally only when every item below is backed by fresh output:

- [ ] `20260710_0021` is the single Alembic head and the PostgreSQL partial index exists.
- [ ] Domain creation produces exactly the specified Base/table/default Grid graph, no fields and the correct granular plus parent audit events.
- [ ] Both endpoints independently authorize, validate, replay safely and return only the defined receipt model.
- [ ] In-memory and real-PostgreSQL tests cover denial, conflict, transaction rollback, same-key concurrency and default-view uniqueness; unavailable local PostgreSQL is reported as a remaining evidence gap.
- [ ] The Mini App has capability-gated desktop/mobile entry, labelled panel, same-key retry and `401`/`403` safe cleanup.
- [ ] Receipt navigation uses fresh authorized lists and cannot select another table/view by list order or stale response.
- [ ] Zero-field Grid state is honest and has no fake record/field mutation affordance.
- [ ] Full backend/frontend/build/migration checks, sanitized Browser QA and artifact cleanup are recorded.
- [ ] P3 documentation describes only verified Base/Table Builder progress; Stage07, Field/View Builder, imports/templates, governance and Digital Employee work remain unclaimed.

## Plan Self-Review

| Approved design requirement | Plan coverage | Review result |
| --- | --- | --- |
| Two distinct atomic initialization endpoints and safe receipts | Tasks 2–3 define domain graph, typed request/response, status/replay mapping and response exclusions. | Covered; no primitive UI POST is introduced. |
| One default Grid and database uniqueness | Task 1 creates the partial index; Task 2 creates fixed Grid resources; Task 3 and real-PostgreSQL tests cover the invariant. | Covered; legacy data is not rewritten. |
| One transaction and retry safety | Task 3 calls the existing idempotency service without template early-commit behavior and covers rollback/race/replay. | Covered; a failed operation cannot leave a business graph or idempotency record. |
| Existing authorization and audit boundaries | Tasks 2–3 pass actor through granular events, add sanitized parent events and test denial before durable writes. | Covered; capability is presentation-only. |
| Desktop/mobile panel and no automatic field | Tasks 4–5 define the labelled responsive panel, zero-field state and removal of fake record creation. | Covered; Field Builder remains excluded. |
| Receipt-verified protected navigation | Task 5 refetches authorized lists, requires exact resource IDs and rejects stale responses/list-order fallback. | Covered; no optimistic resource surface is allowed. |
| Test, browser, cleanup and documentation evidence | Task 6 requires fresh full commands, actual viewport reporting, sanitized fixture evidence and artifact removal. | Covered; no Stage07-wide completion claim is authorized. |

The red-flag scan found no unresolved work marker, vague deferred handoff or undefined cross-task interface. Names in Task 3 (`BuilderInitializationResponse`, receipt routes) are reused unchanged by Tasks 4–5. No approved-design requirement lacks an implementation task.
