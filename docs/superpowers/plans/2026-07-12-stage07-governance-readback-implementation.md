# Stage07 Governance Readback Implementation Plan

> **Execution status (2026-07-12):** G1 and G2 are implemented locally; G3 has focused automated, build and cleanup evidence. The Browser environment could not navigate to the local built client, so Browser acceptance is explicitly pending rather than passed.

**Goal:** Deliver the approved Package 3 read-only Governance workbench: safe paged member readback and Base audit timeline in the Stage07 Mini App.

**Architecture:** Add two narrow Mini App read projections without altering legacy generic management/audit endpoints. Reuse existing Stage06 identity, authorization, Base scoping, audit collection/sanitization and opaque cursor pagination; feed only closed DTOs through React/TanStack protected state.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy 2.x, PostgreSQL, React, Vite, TypeScript, TanStack Query and current lucide/CSS system.

## Global Constraints

- Technical Decision 003 authorizes only the two safe read routes and read-only UI.
- Do not change legacy /workspaces/{workspace_id}/members or /bases/{base_id}/audit-events contracts.
- No migration, dependency, persistent browser storage, telemetry, member/role/policy mutation, Bot, draft, Telegram, push, PR or deployment.
- Browser responses exclude trace_id, actor_id, entity_id, before_state, after_state and permission_snapshot.
- Reuse existing paginate_items, protected QueryClient, safe error boundaries and AbortSignal/request-generation patterns.

---

## One Stage, Three Continuous Substages

| Substage | Deliverable | Exit gate |
| --- | --- | --- |
| G1 Safe backend projections | strict DTOs plus authorised member/audit routes | unit and real disposable PostgreSQL evidence |
| G2 Protected workbench | typed transport, query cleanup and responsive read-only UI | focused frontend tests and production build |
| G3 Reconciliation | BDD-by-BDD evidence, focused Browser pass and cleanup | exact evidence document, no false claim |

## File Map

| File | Responsibility |
| --- | --- |
| backend/app/schemas/stage07_governance.py | closed Mini App member/audit DTOs |
| backend/app/api/routes/stage07_governance.py | two independently authorised safe GET projections |
| backend/app/main.py | mount the new router |
| backend/tests/unit/test_stage07_governance_api.py | route shape, denial, cursor and raw-field exclusion |
| backend/tests/integration/test_stage07_governance_postgres.py | disposable PostgreSQL scope/redaction/pagination proof |
| mini-app/src/app/governance-types.ts | closed browser DTO types |
| mini-app/src/app/GovernanceWorkbench.tsx | member/audit presentation and local read states |
| mini-app/src/app/api.ts | strict GET parsers |
| mini-app/src/app/protectedQuery.ts | governance keys and exact cleanup |
| mini-app/src/app/App.tsx / AppShell.tsx | opening, Base selection, scope lifecycle |
| mini-app/src/test/governance-*.test.tsx | parser, key, workbench and App regressions |

## G1: Safe Backend Projections

### Task 1: Strict schema, routes and fast unit proof

**Files:**

- Create: backend/app/schemas/stage07_governance.py
- Create: backend/app/api/routes/stage07_governance.py
- Modify: backend/app/main.py
- Test: backend/tests/unit/test_stage07_governance_api.py

**Interfaces:**

- Produces GET /mini-app/workspaces/{workspace_id}/governance/members?limit=1..100&cursor?
- Produces GET /mini-app/bases/{base_id}/governance/audit-events?limit=1..100&cursor?

- [x] **Step 1: Write failing tests**

~~~python
def test_governance_member_projection_is_paged_and_closed(client, workspace_id):
    response = client.get(f"/mini-app/workspaces/{workspace_id}/governance/members?limit=1")
    assert response.status_code == 200
    assert set(response.json()) == {"workspace_id", "members", "next_cursor", "has_more"}
    assert set(response.json()["members"][0]) == {"id", "user_id", "role", "status"}

def test_governance_audit_projection_excludes_legacy_audit_fields(client, base_id):
    response = client.get(f"/mini-app/bases/{base_id}/governance/audit-events")
    assert response.status_code == 200
    forbidden = {"trace_id", "actor_id", "entity_id", "before_state", "after_state", "permission_snapshot"}
    assert forbidden.isdisjoint(response.json()["events"][0])
~~~

- [x] **Step 2: Confirm red**

Run: cd backend; python -m pytest -q tests/unit/test_stage07_governance_api.py

Expected: FAIL because the safe route/schema does not exist.

- [x] **Step 3: Implement exact closed DTOs and route checks**

~~~python
class GovernanceAuditEventResponse(BaseModel):
    id: str
    occurred_at: datetime
    actor_type: Literal["user", "digital_employee", "system"]
    event_type: str
    entity_type: str

@router.get("/mini-app/bases/{base_id}/governance/audit-events")
def list_governance_audit_events(
    base_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    uow: Stage06RuntimeUnitOfWork = Depends(get_stage06_runtime_uow),
) -> GovernanceAuditPageResponse:
    workspace_id = workspace_id_for_base(uow, base_id)
    authorize_workspace_action(uow, identity, workspace_id, "audit.read")
    page = paginate_items(list_base_audit_events(uow, base_id), limit=limit, cursor=cursor)
    return GovernanceAuditPageResponse(
        base_id=str(base_id),
        events=[
            GovernanceAuditEventResponse(
                id=str(event.id),
                occurred_at=event.created_at,
                actor_type=_safe_governance_actor_type(event.actor_type),
                event_type=event.event_type,
                entity_type=event.entity_type,
            )
            for event in page.items
        ],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )
~~~

Member route independently requires member.read. Both use Query(default=50, ge=1, le=100). Construct audit DTOs from model fields only; never serialize or filter the legacy HTTP response.

- [x] **Step 4: Confirm green behavior**

Run: cd backend; python -m pytest -q tests/unit/test_stage07_governance_api.py

Expected: PASS for owner/admin success, viewer/cross-workspace/Base denial, invalid cursor fixed 422 and no raw fields.

- [x] **Step 5: Commit**

~~~bash
git add backend/app/schemas/stage07_governance.py backend/app/api/routes/stage07_governance.py backend/app/main.py backend/tests/unit/test_stage07_governance_api.py
git commit -m "feat(stage07): add safe governance read projections"
~~~

### Task 2: Real local PostgreSQL G1 proof

**Files:**

- Create: backend/tests/integration/test_stage07_governance_postgres.py

- [x] **Step 1: Write failing synthetic scope/redaction/pagination case**

~~~python
def test_governance_postgres_audit_is_scoped_paged_and_redacted(stage06_postgres):
    app, owner, outsider, base_id = governance_postgres_fixture(stage06_postgres)
    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner
        first = client.get(f"/mini-app/bases/{base_id}/governance/audit-events?limit=1")
        cursor = first.json()["next_cursor"]
        second = client.get(
            f"/mini-app/bases/{base_id}/governance/audit-events?limit=1&cursor={cursor}"
        )
    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = outsider
        denied = client.get(f"/mini-app/bases/{base_id}/governance/audit-events")
    assert first.status_code == second.status_code == 200
    assert denied.status_code == 403
    assert "legacy-hidden-value" not in first.text + second.text
~~~

- [x] **Step 2: Confirm red, then complete only compatibility required by Task 1**

Run: cd backend; $env:DATABASE_URL=$env:STAGE06_LOCAL_DATABASE_URL; python -m pytest -q tests/integration/test_stage07_governance_postgres.py

Expected: red before route completion; no migration, index or serializer expansion may be added.

- [x] **Step 3: Confirm green and migration smoke**

Run: cd backend; $env:DATABASE_URL=$env:STAGE06_LOCAL_DATABASE_URL; python scripts/stage06_local_postgres_migration_smoke.py; python -m pytest -q tests/integration/test_stage07_governance_postgres.py

Expected: current Alembic head and passing synthetic disposable proof.

- [x] **Step 4: Commit**

~~~bash
git add backend/tests/integration/test_stage07_governance_postgres.py
git commit -m "test(stage07): cover governance readback postgres boundary"
~~~

## G2: Protected Mini App Workbench

### Task 3: Closed transport and exact query removal

**Files:**

- Create: mini-app/src/app/governance-types.ts
- Modify: mini-app/src/app/api.ts
- Modify: mini-app/src/app/protectedQuery.ts
- Test: mini-app/src/test/governance-api.test.ts
- Test: mini-app/src/test/governance-query.test.ts

**Interfaces:**

- Produces api.listGovernanceMembers, api.listGovernanceAuditEvents, governanceKeys and clearGovernanceQueries.

- [x] **Step 1: Write failing parser/key tests**

~~~ts
expect(await api.listGovernanceAuditEvents("base-1")).toEqual(expect.objectContaining({ baseId: "base-1" }))
expect(fetchMock).toHaveBeenCalledWith("/mini-app/bases/base-1/governance/audit-events?limit=50", expect.anything())
expect(JSON.stringify(parsed)).not.toContain("trace-secret")
~~~

- [x] **Step 2: Confirm red**

Run: cd mini-app; npm.cmd test -- --run src/test/governance-api.test.ts src/test/governance-query.test.ts

Expected: FAIL because types, parsers and governance keys do not exist.

- [x] **Step 3: Implement closed types, URL creation and cleanup**

~~~ts
export type GovernanceAuditEvent = {
  id: string; occurredAt: string; actorType: "user" | "digital_employee" | "system"; eventType: string; entityType: string
}
export const governanceKeys = {
  members: (scope: ProtectedScope, cursor: string | null) => protectedQueryKey(scope, "governance", "members", cursor),
  audit: (scope: ProtectedScope, baseId: string, cursor: string | null) => protectedQueryKey(scope, "governance", "audit", baseId, cursor),
}
~~~

Use URLSearchParams, encodeURIComponent and exact allowlisted parsers. Exact Base removal clears its audit subtree; close/403/workspace replacement clears the Governance workspace subtree.

- [x] **Step 4: Confirm green and commit**

Run: cd mini-app; npm.cmd test -- --run src/test/governance-api.test.ts src/test/governance-query.test.ts

Expected: PASS; parsed values and query keys contain no raw audit field.

~~~bash
git add mini-app/src/app/governance-types.ts mini-app/src/app/api.ts mini-app/src/app/protectedQuery.ts mini-app/src/test/governance-api.test.ts mini-app/src/test/governance-query.test.ts
git commit -m "feat(stage07): add protected governance transport"
~~~

### Task 4: Read-only workbench and App lifecycle

**Files:**

- Create: mini-app/src/app/GovernanceWorkbench.tsx
- Modify: mini-app/src/app/App.tsx
- Modify: mini-app/src/app/AppShell.tsx
- Modify: mini-app/src/styles.css
- Test: mini-app/src/test/governance-workbench.test.tsx
- Test: mini-app/src/test/governance-app-flow.test.tsx

- [x] **Step 1: Write failing panel/lifecycle tests**

~~~tsx
test("shows safe members then selected Base audit only", async () => {
  render(<GovernanceWorkbench members={page} bases={[base]} onLoadMembers={loadMembers} onLoadAudit={loadAudit} />)
  expect(screen.queryByText("trace-secret")).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText("选择 Base"), { target: { value: base.id } })
  expect(loadAudit).toHaveBeenCalledWith(base.id, null)
})
~~~

Also test 401 global denial, 403 workspace denial, 404 exact Base clear, failed next page preserves first rows, and delayed Workspace A response cannot render in Workspace B.

- [x] **Step 2: Confirm red**

Run: cd mini-app; npm.cmd test -- --run src/test/governance-workbench.test.tsx src/test/governance-app-flow.test.tsx

Expected: FAIL because the workbench and lifecycle are absent.

- [x] **Step 3: Implement minimal read-only UI**

AppShell accepts onOpenGovernance and exposes it only behind existing can_manage_workspace. App owns a governance request generation. Selecting a Base clears previous audit state before a new request. The panel maps known role/status/event values to fixed labels, maps unknown values to fixed generic labels, supports load-more/retry, and has no mutation control.

- [x] **Step 4: Add responsive/accessibility contract**

Desktop has labelled members/audit panes. Mobile has one labelled full-height dialog/sheet. Base selector, retry and continuation are keyboard reachable at 390px. Close returns focus to the opening entry; no horizontal scroll is necessary to identify role/status/event.

- [x] **Step 5: Confirm green/build and commit**

Run: cd mini-app; npm.cmd test -- --run src/test/governance-workbench.test.tsx src/test/governance-app-flow.test.tsx; npm.cmd run build

Expected: focused tests pass and production build exits 0.

~~~bash
git add mini-app/src/app/GovernanceWorkbench.tsx mini-app/src/app/App.tsx mini-app/src/app/AppShell.tsx mini-app/src/styles.css mini-app/src/test/governance-workbench.test.tsx mini-app/src/test/governance-app-flow.test.tsx
git commit -m "feat(stage07): add governance readback workbench"
~~~

## G3: Reconciliation, Browser Evidence and Cleanup

### Task 5: Execute exact acceptance evidence

**Files:**

- Create: project-docs/08-implementation/evidence/stage07-governance-readback.md
- Modify: project-docs/08-implementation/STAGE_07_PROGRESS.md
- Modify: project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md
- Modify: project-docs/08-implementation/STAGE_07_GOVERNANCE_READBACK_BDD_AND_ACCEPTANCE.md
- Modify: project-docs/08-implementation/STAGE_07_TEST_PLAN.md

- [x] **Step 1: Run focused verification**

~~~powershell
cd backend
python -m pytest -q tests/unit/test_stage07_governance_api.py
$env:DATABASE_URL=$env:STAGE06_LOCAL_DATABASE_URL
python scripts/stage06_local_postgres_migration_smoke.py
python -m pytest -q tests/integration/test_stage07_governance_postgres.py
cd ../mini-app
npm.cmd test -- --run src/test/governance-api.test.ts src/test/governance-query.test.ts src/test/governance-workbench.test.tsx src/test/governance-app-flow.test.tsx
npm.cmd run build
~~~

Expected: record actual counts only.

- [ ] **Step 2: Focused Browser path (blocked by Browser local-origin navigation policy; no pass claimed)**

Use synthetic local data only. Observe desktop/mobile entry, safe member rows, selected Base timeline, one continuation or empty state, one denial/retry state and final console error/warn scan. Do not claim any unexecuted width, raw audit inspection, Telegram, staging or production flow.

- [x] **Step 3: Clean temporary material**

Finalize Browser, stop local services, delete temporary fixture/proxy/logs with apply_patch, rerun the disposable migration smoke if it owns the test DB, and prove temporary ports are closed.

- [x] **Step 4: Reconcile BDD row-by-row and commit**

Mark only observed/tested GR-A rows implemented-local. Retain unexecuted Browser widths or negatives as partial-local.

~~~bash
git diff --check
git add project-docs/08-implementation/evidence/stage07-governance-readback.md project-docs/08-implementation/STAGE_07_PROGRESS.md project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md project-docs/08-implementation/STAGE_07_GOVERNANCE_READBACK_BDD_AND_ACCEPTANCE.md project-docs/08-implementation/STAGE_07_TEST_PLAN.md
git commit -m "docs(stage07): record governance readback evidence"
~~~

## Plan Self-Review

- G1 implements Technical Decision 003 without changing generic endpoints.
- G2 implements every design UI/cache/error invariant but no governance write.
- G3 maps GR-A01 through GR-A06 to actual commands and Browser evidence.
- The plan introduces no migration, dependency, raw-audit browser path, Bot/Telegram work or placeholder scope.

## Execution Handoff

Execute inline in this worktree as G1 → G2 → G3. Do not dispatch subagents, push, create a PR or deploy.
