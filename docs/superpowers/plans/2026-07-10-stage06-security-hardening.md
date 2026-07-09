# Stage06 Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Stage06 backend enforce verified identity, active workspace membership, tenant/resource isolation, safe lookup/audit/notification behavior, bounded imports, pagination, idempotency and PostgreSQL concurrency constraints.

**Architecture:** Stage06 gains a replaceable identity dependency and a central authorization service that resolves every resource to a workspace before applying role/action and field/view policies. Existing platform/template/runtime services remain the write boundary; one additive migration supplies Telegram-member linkage, constraints, indexes and idempotency storage. Request policy may only narrow server safety policy.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic 2, SQLAlchemy 2.x, Alembic, PostgreSQL JSONB, pytest, LangGraph/OpenRouter runtime unchanged.

## Global Constraints

- Do not add a Clerk/Auth0/OIDC provider in Stage06.
- `local` and `test` may use `X-Stage06-User-Id`; `staging` and `production` fail with `401` without a verified adapter.
- Roles come only from active `workspace_members` records.
- Telegram identity is context and must resolve through a workspace-member binding.
- Empty digital employee table/view scope grants no access.
- Request notification policy cannot weaken server policy.
- Do not enable real notification/provider sends.
- Do not remove or rewrite Stage02-05 tables.
- Every behavior change follows red-green-refactor.
- Preserve unrelated user changes in the dirty worktree.

---

## File Structure

- Create `backend/app/services/stage06_identity.py`: request identity types, development adapter and environment fail-closed dependency helpers.
- Create `backend/app/services/stage06_authorization.py`: action matrix, resource-to-workspace resolution, membership checks and sanitized denials.
- Create `backend/app/services/stage06_pagination.py`: cursor encode/decode and bounded page size.
- Create `backend/app/services/stage06_idempotency.py`: request fingerprint and idempotency state transitions.
- Create `backend/app/models/stage06_hardening.py`: idempotency ORM model.
- Create `backend/alembic/versions/20260710_0020_stage06_security_hardening.py`: additive constraints, indexes, Telegram member FK and idempotency table.
- Modify Stage06 route modules to depend on identity and resolve authorized actors.
- Modify Stage06 platform/template/runtime services to enforce resource invariants, redaction, limits, pagination and idempotency.
- Add focused unit/API/migration tests and opt-in PostgreSQL security/concurrency tests.

---

### Task 1: Request Identity And Workspace Member Actor

**Files:**

- Create: `backend/app/services/stage06_identity.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/api/deps.py`
- Test: `backend/tests/unit/test_stage06_identity.py`

**Interfaces:**

- Produces `Stage06RequestIdentity(user_id: str, source: str, telegram_user_id: str | None = None)`.
- Produces `resolve_stage06_request_identity(settings: Settings, development_user_id: str | None, verified_user_id: str | None = None) -> Stage06RequestIdentity`.
- Produces FastAPI dependency `get_stage06_request_identity(settings: Settings, x_stage06_user_id: str | None) -> Stage06RequestIdentity`.
- Adds `Settings.stage06_identity_mode`, default `development` in local and `verified` in production-like environments.

- [ ] **Step 1: Write failing identity tests**

```python
def test_stage06_identity_requires_header_in_local():
    with pytest.raises(Stage06IdentityError) as denied:
        resolve_stage06_request_identity(Settings(environment="local"), None)
    assert denied.value.code == "stage06_identity_required"

def test_stage06_identity_rejects_development_header_in_production():
    with pytest.raises(Stage06IdentityError) as denied:
        resolve_stage06_request_identity(
            Settings(environment="production"),
            "owner-1",
        )
    assert denied.value.code == "stage06_verified_identity_required"
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/unit/test_stage06_identity.py -q`

Expected: import/behavior failure because `stage06_identity` does not exist.

- [ ] **Step 3: Implement the identity module and dependency**

```python
@dataclass(frozen=True)
class Stage06RequestIdentity:
    user_id: str
    source: Literal["development_header", "verified_adapter", "telegram_binding"]
    telegram_user_id: str | None = None

def resolve_stage06_request_identity(settings, development_user_id, verified_user_id=None):
    if verified_user_id:
        return Stage06RequestIdentity(verified_user_id, "verified_adapter")
    if settings.environment in {"staging", "production"}:
        raise Stage06IdentityError("stage06_verified_identity_required")
    if not development_user_id or not development_user_id.strip():
        raise Stage06IdentityError("stage06_identity_required")
    return Stage06RequestIdentity(development_user_id.strip(), "development_header")
```

The FastAPI dependency reads `X-Stage06-User-Id`, maps identity errors to `401`, and never returns an `Actor` or role.

- [ ] **Step 4: Run GREEN and focused regression**

Run: `python -m pytest tests/unit/test_stage06_identity.py tests/unit/test_stage06_platform_api.py -q`

Expected: PASS after API tests are updated to send the development identity header.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/stage06_identity.py backend/app/core/config.py backend/app/api/deps.py backend/tests/unit/test_stage06_identity.py backend/tests/unit/test_stage06_platform_api.py
git commit -m "feat(stage06): require request identity"
```

### Task 2: Central Authorization And Stage06 Route Enforcement

**Files:**

- Create: `backend/app/services/stage06_authorization.py`
- Modify: `backend/app/services/stage06_platform.py`
- Modify: `backend/app/api/routes/stage06_platform.py`
- Modify: `backend/app/api/routes/stage06_templates.py`
- Modify: `backend/app/api/routes/stage06_runtime.py`
- Test: `backend/tests/unit/test_stage06_authorization.py`
- Test: `backend/tests/unit/test_stage06_authorization_api.py`

**Interfaces:**

- Produces `Stage06Action` string constants matching the permission model.
- Produces `authorize_workspace_action(uow, identity, workspace_id, action) -> Actor`.
- Produces `workspace_id_for_base/table/view/record/import/draft/employee/notification` resolvers.
- Produces sanitized `Stage06AuthorizationError(code, resource_type, action)` without protected values.

- [ ] **Step 1: Write failing membership/action tests**

```python
def test_viewer_cannot_create_base():
    uow, workspace = workspace_with_member("viewer-1", "viewer")
    with pytest.raises(Stage06AuthorizationError) as denied:
        authorize_workspace_action(
            uow,
            Stage06RequestIdentity("viewer-1", "development_header"),
            workspace.id,
            "base.create",
        )
    assert denied.value.code == "stage06_action_denied"

def test_member_cannot_read_another_workspace():
    uow, workspace_a, workspace_b = two_workspace_uow()
    add_member(uow, workspace_a.id, "viewer-1", "viewer")
    with pytest.raises(Stage06AuthorizationError) as denied:
        authorize_workspace_action(
            uow,
            Stage06RequestIdentity("viewer-1", "development_header"),
            workspace_b.id,
            "workspace.read",
        )
    assert denied.value.code == "stage06_membership_required"
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/unit/test_stage06_authorization.py tests/unit/test_stage06_authorization_api.py -q`

Expected: failures because authorization service and identity-protected routes are absent.

- [ ] **Step 3: Implement role/action matrix and resource resolvers**

```python
ROLE_ACTIONS = {
    "owner": {"*"},
    "admin": {"workspace.read", "member.read", "base.create", "base.read", "table.create", "field.manage", "view.manage", "record.create", "record.update", "import.create", "import.commit", "template.install", "template.save", "digital_employee.create", "digital_employee.invoke", "record_change_draft.confirm", "notification_request.create", "notification_request.confirm", "audit.read"},
    "builder": {"workspace.read", "base.create", "base.read", "table.create", "field.manage", "view.manage", "record.create", "record.update", "import.create", "import.commit", "template.install", "template.save", "digital_employee.create", "digital_employee.invoke"},
    "operator": {"workspace.read", "base.read", "record.read", "record.create", "record.update", "digital_employee.invoke", "record_change_draft.confirm", "notification_request.create", "notification_request.confirm"},
    "viewer": {"workspace.read", "base.read", "record.read", "digital_employee.invoke"},
}
```

Resolve the active membership by `(workspace_id, identity.user_id, status="active")`, derive `Actor(actor_type="user", actor_id=identity.user_id, role=member.role)`, and record only safe denial metadata.

Update every Stage06 route to depend on `get_stage06_request_identity`; workspace creation enforces `owner_user_id == identity.user_id`; all other routes authorize against their resolved workspace before service access.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/unit/test_stage06_authorization.py tests/unit/test_stage06_authorization_api.py tests/unit/test_stage06_platform_api.py tests/unit/test_stage06_template_import_api.py tests/unit/test_stage06_digital_employee_api.py -q`

Expected: PASS with explicit identity headers and negative 401/403 coverage.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/stage06_authorization.py backend/app/services/stage06_platform.py backend/app/api/routes/stage06_platform.py backend/app/api/routes/stage06_templates.py backend/app/api/routes/stage06_runtime.py backend/tests/unit/test_stage06_authorization.py backend/tests/unit/test_stage06_authorization_api.py backend/tests/unit/test_stage06_*_api.py
git commit -m "feat(stage06): enforce workspace authorization"
```

### Task 3: Tenant Invariants, Telegram Member Scope And Lookup Safety

**Files:**

- Modify: `backend/app/models/stage06_platform.py`
- Modify: `backend/app/schemas/stage06_runtime.py`
- Modify: `backend/app/services/stage06_platform.py`
- Modify: `backend/app/services/stage06_templates.py`
- Modify: `backend/app/services/stage06_digital_employees.py`
- Test: `backend/tests/unit/test_stage06_tenant_isolation.py`
- Test: `backend/tests/unit/test_stage06_lookup_permissions.py`
- Test: `backend/tests/unit/test_stage06_telegram_member_scope.py`

**Interfaces:**

- Telegram binding accepts `workspace_member_id: UUID` and validates it belongs to the binding workspace.
- `assert_same_base(base_id, table_id/view_id/record_id)` and import/employee scope validators raise stable `resource_scope_mismatch` errors.
- `_assert_table_in_scope` and `_assert_view_in_scope` deny empty scopes.
- Lookup resolution receives `actor` and checks target field permission before returning a value.

- [ ] **Step 1: Write failing cross-boundary and lookup tests**

```python
def test_view_rejects_table_from_another_base():
    uow, base_a, base_b, table_b = two_base_fixture()
    with pytest.raises(PlatformValidationError) as denied:
        create_form_view(uow, base_a.id, table_b.id, name="Cross", view_type="grid", config={})
    assert denied.value.code == "resource_scope_mismatch"

def test_import_rejects_base_from_another_workspace():
    uow, workspace_a, workspace_b, base_b = two_workspace_base_fixture()
    with pytest.raises(PlatformValidationError) as denied:
        create_import_job_from_csv(uow, workspace_a.id, file_name="x.csv", content="name\nAda", created_by_user_id="owner-a", base_id=base_b.id)
    assert denied.value.code == "resource_scope_mismatch"

def test_employee_rejects_view_from_another_base():
    uow, base_a, _base_b, _table_b, view_b = cross_base_view_fixture()
    with pytest.raises(PlatformValidationError) as denied:
        create_digital_employee(uow, base_a.id, name="Ops", description="Ops", telegram_alias="ops", accessible_tables=[], accessible_views=[str(view_b.id)], allowed_actions=["summarize"], actor=owner_actor())
    assert denied.value.code == "resource_scope_mismatch"

def test_empty_employee_scope_denies_record_access():
    uow, employee, record = empty_scope_employee_fixture()
    with pytest.raises(PlatformValidationError) as denied:
        invoke_digital_employee(uow, employee.id, action="draft_update", record_id=record.id, proposed_values={"status": "done"}, actor=operator_actor())
    assert denied.value.code == "digital_employee_scope_denied"

def test_lookup_omits_hidden_target_field():
    payload = read_lookup_fixture(actor=viewer_actor(), target_policy={"viewer": "hidden"})
    assert "private_note_lookup" not in payload["records"][0]["fields"]
    assert "hidden-value" not in str(payload)

def test_telegram_mention_uses_bound_viewer_role():
    response, run = invoke_bound_telegram_viewer_fixture()
    assert response["action"] == "summarize"
    assert run.input_summary["actor_role"] == "viewer"
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/unit/test_stage06_tenant_isolation.py tests/unit/test_stage06_lookup_permissions.py tests/unit/test_stage06_telegram_member_scope.py -q`

Expected: current code accepts cross-boundary resources, empty table scope, or hidden lookup output.

- [ ] **Step 3: Implement invariant checks**

Validate the complete ownership chain before creating views/imports/employees/drafts/bindings. Resolve Telegram caller `Actor` from the binding member instead of the API dependency. Lookup returns `_MISSING` when the target field is unreadable and never includes the target value in denial audit.

- [ ] **Step 4: Run GREEN and runtime regression**

Run: `python -m pytest tests/unit/test_stage06_tenant_isolation.py tests/unit/test_stage06_lookup_permissions.py tests/unit/test_stage06_telegram_member_scope.py tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage06_live_digital_employee_runtime.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/models/stage06_platform.py backend/app/schemas/stage06_runtime.py backend/app/services/stage06_platform.py backend/app/services/stage06_templates.py backend/app/services/stage06_digital_employees.py backend/tests/unit/test_stage06_tenant_isolation.py backend/tests/unit/test_stage06_lookup_permissions.py backend/tests/unit/test_stage06_telegram_member_scope.py
git commit -m "fix(stage06): enforce tenant and lookup boundaries"
```

### Task 4: Audit Redaction And Server Notification Safety

**Files:**

- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/stage06_platform.py`
- Modify: `backend/app/services/stage06_digital_employees.py`
- Modify: `backend/app/api/routes/stage06_runtime.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/unit/test_stage06_audit_redaction.py`
- Test: `backend/tests/unit/test_stage06_notification_safety.py`

**Interfaces:**

- Produces `sanitize_stage06_audit_state(value: object) -> object`.
- Adds `Settings.stage06_notification_mode` and `Settings.stage06_notification_allowed_chat_ids`.
- Changes `create_notification_request(uow, *, workspace_id, base_id, source_record_id, channel, target, message_payload, send_policy, actor, server_mode: str, server_allowlist: Sequence[str])` and confirmation to recompute the effective policy.

- [ ] **Step 1: Write failing redaction/fail-closed tests**

```python
def test_record_audit_stores_changed_keys_not_raw_values():
    event = create_record_and_return_audit(values={"secret": "hidden-value"})
    assert event.after_state["field_keys"] == ["secret"]
    assert "hidden-value" not in str(event.after_state)

def test_audit_readback_requires_owner_or_admin():
    response = audit_api_response(identity="viewer-1", role="viewer")
    assert response.status_code == 403

def test_audit_readback_never_contains_hidden_value():
    response = audit_api_response(identity="owner-1", role="owner", seeded_value="hidden-value")
    assert response.status_code == 200
    assert "hidden-value" not in response.text

def test_empty_request_policy_is_blocked_when_server_disabled():
    request = create_notification_fixture(send_policy={}, server_mode="disabled", server_allowlist=())
    assert request.status == "blocked"

def test_confirmation_cannot_bypass_server_allowlist():
    request = pending_notification_fixture(target_chat_id="chat-2")
    confirmed = confirm_notification_request_fixture(request, server_mode="restricted_test", server_allowlist=("chat-1",))
    assert confirmed.status == "blocked"
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/unit/test_stage06_audit_redaction.py tests/unit/test_stage06_notification_safety.py -q`

Expected: raw values are present and empty request policy can become queued.

- [ ] **Step 3: Implement safe state and effective notification policy**

Record `{field_keys, version, record_count, status}` instead of raw values. Sanitize legacy-shaped audit state on readback. Compute notification state with server mode first; `disabled`/`dry_run` always block, `restricted_test` requires a non-empty server allowlist and matching target, and request allowlists only narrow the server set.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/unit/test_stage06_audit_redaction.py tests/unit/test_stage06_notification_safety.py tests/unit/test_stage06_pilot_acceptance_api.py tests/unit/test_stage06_runtime_api_contract.py -q`

Expected: PASS with updated controlled-notification expectations.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/core/config.py backend/app/services/stage06_platform.py backend/app/services/stage06_digital_employees.py backend/app/api/routes/stage06_runtime.py backend/.env.example backend/tests/unit/test_stage06_audit_redaction.py backend/tests/unit/test_stage06_notification_safety.py backend/tests/unit/test_stage06_pilot_acceptance_api.py backend/tests/unit/test_stage06_runtime_api_contract.py
git commit -m "fix(stage06): redact audit and fail notifications closed"
```

### Task 5: Bounded Import And Cursor Pagination

**Files:**

- Create: `backend/app/services/stage06_pagination.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/stage06_templates.py`
- Modify: `backend/app/services/stage06_platform.py`
- Modify: `backend/app/services/stage06_digital_employees.py`
- Modify: `backend/app/schemas/stage06_platform.py`
- Modify: `backend/app/schemas/stage06_runtime.py`
- Modify: `backend/app/api/routes/stage06_platform.py`
- Modify: `backend/app/api/routes/stage06_runtime.py`
- Test: `backend/tests/unit/test_stage06_import_limits.py`
- Test: `backend/tests/unit/test_stage06_pagination.py`

**Interfaces:**

- `ImportLimits(csv_bytes=5*1024*1024, excel_bytes=10*1024*1024, rows=10000, columns=200, cell_chars=65536, preview_rows=20)`.
- `bounded_page_size(limit: int | None) -> int` rejects values outside 1..200.
- `encode_cursor(created_at, id) -> str` and `decode_cursor(value) -> Cursor` use URL-safe base64 JSON without secrets.
- List responses add `next_cursor: str | None` and `has_more: bool`.

- [ ] **Step 1: Write failing import-limit and pagination tests**

```python
def test_csv_payload_over_five_mib_is_rejected_before_parse():
    content = "x" * (5 * 1024 * 1024 + 1)
    with pytest.raises(PlatformValidationError) as denied:
        create_import_job_from_csv(import_uow(), workspace_id(), file_name="large.csv", content=content, created_by_user_id="owner-1")
    assert denied.value.code == "import_payload_limit_exceeded"

def test_import_over_row_column_or_cell_limit_is_rejected():
    limits = ImportLimits(rows=1, columns=1, cell_chars=3)
    with pytest.raises(PlatformValidationError) as denied:
        validate_import_rows([{"a": "long", "b": "x"}, {"a": "x"}], limits)
    assert denied.value.code in {"import_row_limit_exceeded", "import_column_limit_exceeded", "import_cell_limit_exceeded"}

def test_page_limit_above_200_is_rejected():
    with pytest.raises(PlatformValidationError) as denied:
        bounded_page_size(201)
    assert denied.value.code == "page_limit_exceeded"

def test_cursor_pages_have_no_duplicates():
    first = paginate_items(ordered_items(75), limit=50, cursor=None)
    second = paginate_items(ordered_items(75), limit=50, cursor=first.next_cursor)
    assert set(first.item_ids).isdisjoint(second.item_ids)
    assert first.item_ids + second.item_ids == [str(item.id) for item in ordered_items(75)]
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/unit/test_stage06_import_limits.py tests/unit/test_stage06_pagination.py -q`

Expected: imports are unbounded and cursor helpers are missing.

- [ ] **Step 3: Implement bounded parsing and pagination**

Check decoded payload size before ZIP/XML parsing, bound required XLSX entry sizes, validate normalized rows/cells, and keep only the configured preview slice. Fetch `limit + 1`, return the first `limit`, and derive `next_cursor` from the last returned item.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/unit/test_stage06_import_limits.py tests/unit/test_stage06_pagination.py tests/unit/test_stage06_template_import.py tests/unit/test_stage06_platform_api.py tests/unit/test_stage06_runtime_api_contract.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/stage06_pagination.py backend/app/core/config.py backend/app/services/stage06_templates.py backend/app/services/stage06_platform.py backend/app/services/stage06_digital_employees.py backend/app/schemas/stage06_platform.py backend/app/schemas/stage06_runtime.py backend/app/api/routes/stage06_platform.py backend/app/api/routes/stage06_runtime.py backend/tests/unit/test_stage06_import_limits.py backend/tests/unit/test_stage06_pagination.py
git commit -m "feat(stage06): bound imports and paginate reads"
```

### Task 6: Idempotency Model, Migration And PostgreSQL Concurrency

**Files:**

- Create: `backend/app/models/stage06_hardening.py`
- Create: `backend/app/services/stage06_idempotency.py`
- Create: `backend/alembic/versions/20260710_0020_stage06_security_hardening.py`
- Modify: `backend/app/models/__init__.py`
- Modify: Stage06 template/runtime routes and services for idempotency keys and row locking
- Test: `backend/tests/unit/test_stage06_hardening_migration.py`
- Test: `backend/tests/unit/test_stage06_idempotency.py`
- Test: `backend/tests/integration/test_stage06_postgres_security.py`

**Interfaces:**

- ORM `Stage06IdempotencyRecord(workspace_id, operation, idempotency_key, request_fingerprint, status, response_ref, trace_id)`.
- `fingerprint_request(payload: Mapping[str, object]) -> str` uses canonical JSON and SHA-256.
- `begin_idempotent_operation(uow, *, workspace_id: UUID, operation: str, idempotency_key: str, request_fingerprint: str, trace_id: str) -> IdempotencyDecision` returns `started`, `replay` or raises `idempotency_conflict`.
- SQLAlchemy UoW methods used for commit/confirm select pending rows with `FOR UPDATE`.

- [ ] **Step 1: Write failing migration/idempotency tests**

```python
def test_same_idempotency_key_and_fingerprint_replays_result():
    uow = InMemoryStage06IdempotencyUnitOfWork()
    first = begin_idempotent_operation(uow, workspace_id=workspace_id(), operation="import.commit", idempotency_key="key-1", request_fingerprint="sha-a", trace_id="trace-1")
    complete_idempotent_operation(uow, first.record, response_ref={"import_job_id": "job-1"})
    replay = begin_idempotent_operation(uow, workspace_id=workspace_id(), operation="import.commit", idempotency_key="key-1", request_fingerprint="sha-a", trace_id="trace-2")
    assert replay.status == "replay"
    assert replay.response_ref == {"import_job_id": "job-1"}

def test_same_key_with_different_fingerprint_conflicts():
    uow = idempotency_uow_with_key("key-1", "sha-a")
    with pytest.raises(PlatformValidationError) as denied:
        begin_idempotent_operation(uow, workspace_id=workspace_id(), operation="import.commit", idempotency_key="key-1", request_fingerprint="sha-b", trace_id="trace-2")
    assert denied.value.code == "idempotency_conflict"

def test_security_migration_adds_member_fk_indexes_constraints_and_idempotency_table():
    migration = Path("alembic/versions/20260710_0020_stage06_security_hardening.py").read_text(encoding="utf-8")
    assert '"stage06_idempotency_records"' in migration
    assert '"workspace_member_id"' in migration
    assert "create_index" in migration
    assert "create_check_constraint" in migration
```

The opt-in PostgreSQL test starts two sessions against the same draft/import and asserts one committed transition and one replay/conflict.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/unit/test_stage06_hardening_migration.py tests/unit/test_stage06_idempotency.py -q`

Expected: missing model, migration and service failures.

- [ ] **Step 3: Implement additive migration and idempotency service**

Migration `20260710_0020` adds the idempotency table, binding member/employee FKs, partial uniqueness for aliases/bindings, Stage06 FK/list indexes, unique trace constraints and positive-version/status checks without dropping Stage02-05 data.

Service code reserves a key in the same transaction as the operation, compares fingerprints, stores only safe response references, and locks pending resource rows before transitions.

- [ ] **Step 4: Run GREEN and optional PostgreSQL test**

Run: `python -m pytest tests/unit/test_stage06_hardening_migration.py tests/unit/test_stage06_idempotency.py -q`

Run when configured: `python -m pytest tests/integration/test_stage06_postgres_security.py -q`

Expected: unit PASS; PostgreSQL PASS or explicit skip only when `STAGE06_LOCAL_DATABASE_URL` is absent.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/models/stage06_hardening.py backend/app/services/stage06_idempotency.py backend/alembic/versions/20260710_0020_stage06_security_hardening.py backend/app/models/__init__.py backend/app/api/routes/stage06_templates.py backend/app/api/routes/stage06_runtime.py backend/app/services/stage06_templates.py backend/app/services/stage06_digital_employees.py backend/tests/unit/test_stage06_hardening_migration.py backend/tests/unit/test_stage06_idempotency.py backend/tests/integration/test_stage06_postgres_security.py
git commit -m "feat(stage06): add idempotency and database guards"
```

### Task 7: Sanitized Evidence And Exit Reconciliation

**Files:**

- Create: `backend/scripts/stage06_security_hardening_smoke.py`
- Create after successful run: `project-docs/08-implementation/evidence/STAGE_06_SECURITY_HARDENING_EVIDENCE.json`
- Modify: Stage06 source, SDD, contract, BDD, progress, risk and exit documents
- Test: `backend/tests/unit/test_stage06_security_hardening_smoke.py`

**Interfaces:**

- Smoke output contains only status, migration head, test case ids, counts, safe error codes and booleans.
- Artifact schema excludes database URLs, tokens, raw user ids, record values, Telegram text and LLM payloads.

- [ ] **Step 1: Write failing artifact-redaction test**

```python
def test_security_hardening_artifact_contains_no_secret_or_raw_value_keys():
    payload = build_security_hardening_evidence(sample_security_results())
    serialized = json.dumps(payload, sort_keys=True)
    for forbidden in ("database_url", "token", "raw_text", "record_values", "prompt", "response_body"):
        assert forbidden not in serialized.lower()
    assert payload["status"] in {"passed", "blocked"}
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/unit/test_stage06_security_hardening_smoke.py -q`

Expected: smoke module absent.

- [ ] **Step 3: Implement smoke and evidence writer**

The script runs preflight, selected identity/tenant/audit/notification/import/idempotency checks, migration head readback and optional PostgreSQL concurrency checks; it writes JSON only when all required local gates pass.

- [ ] **Step 4: Run verification**

Run:

```powershell
python -m pytest tests/unit/test_stage06_*.py -q
python -m pytest tests -q
python -m compileall -q app scripts
python -m alembic heads
python scripts/stage06_security_hardening_smoke.py
git diff --check
```

Expected: all Stage06/full tests pass with only documented environment skips; compile succeeds; one Alembic head is `20260710_0020`; smoke passes or reports an explicit PostgreSQL environment blocker; diff check is clean.

- [ ] **Step 5: Update Stage06 documents and commit**

Record changed files, verification, skipped tests, remaining risks and temporary cleanup. Do not restore a passed exit decision unless every required Package 6 gate has evidence.

```powershell
git add backend/scripts/stage06_security_hardening_smoke.py backend/tests/unit/test_stage06_security_hardening_smoke.py project-docs/08-implementation/evidence project-docs/08-implementation/STAGE_06_*.md docs/superpowers/plans/2026-07-10-stage06-security-hardening.md
git commit -m "docs(stage06): record security hardening evidence"
```
