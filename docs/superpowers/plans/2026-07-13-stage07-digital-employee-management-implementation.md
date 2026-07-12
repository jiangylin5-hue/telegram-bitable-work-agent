# Stage07 Digital Employee Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` task-by-task. Each task requires RED, minimal GREEN, focused regression and a commit.

**Goal:** Deliver TD010 Option A: Base-bound versioned digital employee configuration, optional member-use eligibility, explicit activation/pause, and no general agent framework.

**Architecture:** Extend existing `DigitalEmployee`, Stage06 authorization and S4 row-lock/version/idempotency/audit conventions. A new strict Stage07 management adapter owns browser-safe configuration; existing S5/TD009 consumer routes retain their current Base/view/field/record checks and add only assigned-member eligibility.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, current Stage06 UoW/authorization, React, Vite, TypeScript, TanStack Query and Vitest.

## Global Constraints

- One immutable Base per employee; no multi-Base, reassignment, archive/delete, clone, import/export or marketplace.
- Existing action strings only: `digital_employee.create`, `digital_employee.update`, `digital_employee.read`, `digital_employee.invoke`.
- UI actions are exactly `summarize` and `draft_update`; TD009 Home stays summary-only and TD006 remains Canvas-record-only.
- Lifecycle: `draft -> active -> paused -> active`; scopes/grants change only in `draft` or `paused`.
- `assigned` grants discovery/use eligibility only, never resource or management authority.
- Strict DTOs exclude policy JSON, prompt/provider/runtime/trace, Telegram identity and record/field values.
- Mutations use expected version, idempotency and a row lock. No optimistic or persistent browser state.
- All changes use `apply_patch`; no browser control, external provider, Telegram or deployment work.

---

### Task 1: Add additive persistence and migration

**Files:**

- Create `backend/alembic/versions/20260713_0027_stage07_digital_employee_management.py`.
- Modify `backend/app/models/stage06_runtime.py` and `backend/app/services/stage06_platform.py`.
- Modify `backend/tests/unit/test_model_metadata.py`.
- Create `backend/tests/unit/test_stage07_digital_employee_management_models.py`.
- Create `backend/tests/integration/test_stage07_digital_employee_management_postgres.py`.

**Interfaces produced:**

```python
class DigitalEmployeeMemberGrant(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "digital_employee_member_grants"
    employee_id: Mapped[UUID]
    workspace_member_id: Mapped[UUID]

# DigitalEmployee additions
version: Mapped[int]       # default=1; positive
access_mode: Mapped[str]   # workspace | assigned; legacy default=workspace
```

**RED test:** assert default version/access mode, table metadata, unique `(employee_id, workspace_member_id)`, manager-directory index, migration upgrade/downgrade/replay and legacy active employee `workspace` behavior. Run `python -m pytest -q backend/tests/unit/test_stage07_digital_employee_management_models.py backend/tests/integration/test_stage07_digital_employee_management_postgres.py -m postgres`; expect missing model/migration failures.

**GREEN implementation:** add grant UoW methods `add_digital_employee_member_grant`, `list_digital_employee_member_grants`, `replace_digital_employee_member_grants` in protocol, in-memory and SQLAlchemy UoWs. Migration adds positive-version/access-mode checks and `ix_stage07_digital_employee_management_base_updated(base_id, updated_at DESC, id DESC)`. Existing rows become `version=1`, `access_mode=workspace`; status/Base/policy/records/drafts remain untouched.

**Verify:** run `python -m pytest -q backend/tests/unit/test_model_metadata.py backend/tests/unit/test_stage07_digital_employee_management_models.py backend/tests/integration/test_stage07_digital_employee_management_postgres.py -m postgres`; expect pass. Commit `feat(stage07): add digital employee management persistence`.

### Task 2: Implement closed configuration, grants and lifecycle service

**Files:**

- Create `backend/app/services/stage07_digital_employee_management.py`.
- Modify `backend/app/services/stage06_digital_employees.py` and `backend/app/services/stage06_platform.py`.
- Create `backend/tests/unit/test_stage07_digital_employee_management_service.py`.

**Interfaces produced:**

| Function | Exact parameters | Return |
| --- | --- | --- |
| `create_managed_employee` | `uow, base_id, actor, ManagedEmployeeCreateCommand, idempotency_key` | `DigitalEmployee` |
| `update_managed_employee` | `uow, employee_id, actor, ManagedEmployeeUpdateCommand, expected_version` | `DigitalEmployee` |
| `replace_managed_employee_grants` | `uow, employee_id, actor, member_ids, expected_version, idempotency_key` | `DigitalEmployee` |
| `activate_managed_employee` | `uow, employee_id, actor, expected_version, idempotency_key` | `ManagedEmployeeLifecycleReceipt` |
| `pause_managed_employee` | `uow, employee_id, actor, expected_version, idempotency_key` | `ManagedEmployeeLifecycleReceipt` |
| `is_member_eligible_for_employee` | `uow, employee, actor_user_id` | `bool` |

The module defines `MANAGED_ACTIONS={summarize,draft_update}`, `MANAGED_STATUSES={draft,active,paused}` and `MANAGED_ACCESS_MODES={workspace,assigned}` as closed frozensets.

**RED test:** create draft, configure scopes, replace grants, activate/pause; assert active scope change raises `digital_employee_active_requires_pause`, assigned activation without active grant raises `digital_employee_member_grant_required`, and workspace legacy mode requires no grant.

Also cover unknown action, table/view outside Base, view outside selected table, inactive/wrong-workspace member, stale version, idempotency changed-payload collision, pause leaves drafts/records unchanged, active-alias collision and redacted audit. Run `python -m pytest -q backend/tests/unit/test_stage07_digital_employee_management_service.py`; expect service import/behavior failure.

**GREEN implementation:** use existing `FOR UPDATE`, `begin_idempotent_operation`, `complete_idempotent_operation`, `fingerprint_request`, Base/view helpers and audit service. Activation validates non-empty views, mandatory summarize, scope intersections, grants and alias uniqueness in one transaction. Audits contain IDs/counts/status/actions/version only. Verify with `python -m pytest -q backend/tests/unit/test_stage07_digital_employee_management_service.py backend/tests/unit/test_stage07_draft_employee_hub_api.py`; commit `feat(stage07): add managed employee lifecycle service`.

### Task 3: Add safe management routes, schemas and capability hint

**Files:**

- Create `backend/app/schemas/stage07_digital_employee_management.py`.
- Create `backend/app/api/routes/stage07_digital_employee_management.py`.
- Modify `backend/app/main.py`, `backend/app/services/stage07_mini_app.py`, `backend/app/schemas/stage06_platform.py`.
- Create `backend/tests/unit/test_stage07_digital_employee_management_api.py`.

**Routes:**

```text
GET  /mini-app/bases/{base_id}/digital-employee-management-context
GET  /mini-app/bases/{base_id}/digital-employees/management?cursor=&limit=
POST /mini-app/bases/{base_id}/digital-employees/management
GET  /mini-app/digital-employees/{employee_id}/management
PATCH /mini-app/digital-employees/{employee_id}/management
PUT  /mini-app/digital-employees/{employee_id}/member-grants
POST /mini-app/digital-employees/{employee_id}/activate
POST /mini-app/digital-employees/{employee_id}/pause
```

**RED test:** create a manager fixture and assert exact response keys, `ConfigDict(extra="forbid")`, current Base authorization, expected version, idempotency replay/collision, 401/403/404/409/422 handling and no policy/runtime raw content. Assert an operator retains contact read but cannot access management detail.

Run `python -m pytest -q backend/tests/unit/test_stage07_digital_employee_management_api.py`; expect absent routes and capability.

**GREEN implementation:** context/create uses existing create or update action; directory/detail/mutations use existing update action plus current Base access. Add `can_manage_digital_employees` only as a Bootstrap visibility hint derived from current role actions. It is never authorization. Verify with `python -m pytest -q backend/tests/unit/test_stage07_digital_employee_management_api.py backend/tests/unit/test_stage07_mini_app_api.py backend/tests/unit/test_stage07_draft_employee_hub_api.py`; commit `feat(stage07): add safe employee management api`.

### Task 4: Apply member eligibility to safe S5 and TD009 consumers

**Files:**

- Modify `backend/app/api/routes/stage07_draft_employee_hub.py`.
- Modify `backend/tests/unit/test_stage07_draft_employee_hub_api.py`.
- Modify `backend/tests/unit/test_stage07_assistant_context_api.py`.
- Modify `backend/tests/integration/test_stage07_draft_employee_hub_postgres.py`.

**RED test:** an active `assigned` employee with one operator grant must be absent for viewer contact listing and return generic unavailable/denied results for viewer context/invocation. A `workspace` employee with no grants remains available to the same authorized viewer. Run `python -m pytest -q backend/tests/unit/test_stage07_draft_employee_hub_api.py backend/tests/unit/test_stage07_assistant_context_api.py`; expect unassigned caller remains accepted before the gate.

**GREEN implementation:** invoke `is_member_eligible_for_employee` after active-status check and before employee output/use. Contacts omit ineligible users; direct context/invoke does not reveal assignment state. Do not change generic Stage06 runtime or existing Base/view/field/record checks. Verify `python -m pytest -q backend/tests/unit/test_stage07_draft_employee_hub_api.py backend/tests/unit/test_stage07_assistant_context_api.py backend/tests/integration/test_stage07_draft_employee_hub_postgres.py -m postgres`; commit `feat(stage07): gate employee use by assignment`.

### Task 5: Add strict Mini App transport and scoped management cache

**Files:**

- Create `mini-app/src/app/digital-employee-management-types.ts`.
- Modify `mini-app/src/app/api.ts` and `mini-app/src/app/protectedQuery.ts`.
- Create `mini-app/src/test/digital-employee-management-api.test.ts` and `mini-app/src/test/digital-employee-management-query.test.ts`.

**Interfaces:**

```ts
api.getDigitalEmployeeManagementContext(baseId)
api.listManagedDigitalEmployees(baseId, cursor?)
api.createManagedDigitalEmployee(baseId, values, idempotencyKey)
api.getManagedDigitalEmployee(employeeId)
api.updateManagedDigitalEmployee(employeeId, values, expectedVersion)
api.replaceManagedDigitalEmployeeGrants(employeeId, memberIds, expectedVersion, idempotencyKey)
api.activateManagedDigitalEmployee(employeeId, expectedVersion, idempotencyKey)
api.pauseManagedDigitalEmployee(employeeId, expectedVersion, idempotencyKey)
```

**RED test:** parser rejects extra `field_policy`, `runtime` and `trace` roots; management cleanup for workspace A does not remove workspace B. Run `npm.cmd test -- --run src/test/digital-employee-management-api.test.ts src/test/digital-employee-management-query.test.ts`; expect absent imports/helpers.

**GREEN implementation:** require exact roots, non-empty IDs, positive version and known status/access/action/view literals. Mutation payloads only send documented snake-case properties and `Idempotency-Key`. Keys use `['stage07', userId, workspaceId, 'digital-employee-management', baseIdOrEmployeeId]`; cleanup only removes that subtree. Verify with `npm.cmd test -- --run src/test/digital-employee-management-api.test.ts src/test/digital-employee-management-query.test.ts src/test/draft-employee-api.test.ts`; commit `feat(stage07): add protected employee management transport`.

### Task 6: Build bounded management workbench and Base entry

**Files:**

- Create `mini-app/src/app/DigitalEmployeeManagementWorkbench.tsx`.
- Modify `mini-app/src/app/BaseCanvas.tsx` and `mini-app/src/styles.css`.
- Create `mini-app/src/test/digital-employee-management-workbench.test.tsx`.
- Modify `mini-app/src/test/base-canvas.test.tsx`.

**RED test:** render a labelled `数字员工管理` dialog. It contains only name, description, alias, table/view scope, fixed intent, access mode and member assignment controls. It has no model/provider/prompt/memory/knowledge/record-search control, and activation is disabled until valid safe input exists. Also test table-to-view filtering, active read-only behavior, paused edit behavior, retry/conflict copy, no raw error and close focus return.

Run `npm.cmd test -- --run src/test/digital-employee-management-workbench.test.tsx src/test/base-canvas.test.tsx`; expect absent workbench/entry.

**GREEN implementation:** `BaseCanvas` receives `canManageDigitalEmployees` and `onOpenDigitalEmployeeManagement(trigger)`. Reuse current workbench/backdrop/mobile-sheet CSS grammar and accessible controls. Do not add a chat, raw JSON editor, action/provider selector, second sidebar route or record picker. Bound all text input lengths. Verify the focused tests and commit `feat(stage07): add employee management workbench`.

### Task 7: Wire App lifecycle, authoritative rereads and stale-result protection

**Files:**

- Modify `mini-app/src/app/App.tsx`, `mini-app/src/app/api.ts`, `mini-app/src/app/protectedQuery.ts`.
- Create `mini-app/src/test/digital-employee-management-app-flow.test.tsx`.
- Modify `mini-app/src/test/app-shell-navigation.test.tsx`.

**RED tests:** 

```tsx
test('creates configures assigns activates and pauses through authoritative rereads', async () => {
  // Assert only TD010 endpoint bodies/headers and no S5 invocation.
})

test.each([401, 403, 404, 409])('drops delayed old-workspace employee command on %s', async (status) => {
  // Defer mutation, switch workspace, resolve, assert replacement state remains intact.
})
```

Run `npm.cmd test -- --run src/test/digital-employee-management-app-flow.test.tsx`; expect panel lifecycle absence.

**GREEN implementation:** App state stores only safe directory/context/detail, Base ID, request generation and focus trigger. Every mutation cancels/removes exact management keys then rereads server state; no local patch of status/scopes/grants. Close/Base/workspace/session change invalidates generation. `409/422` retains only typed local values; 401/403/404 use current cleanup; malformed/network/5xx use fixed local copy. Bootstrap capability controls entry visibility only. Verify focused flow/workbench/protected-state tests and commit `feat(stage07): connect employee management lifecycle`.

### Task 8: Proportional acceptance and evidence reconciliation

**Files:**

- Modify TD010/design/BDD/SDD/work-surface/complex-index documents.
- Modify Stage07 source, roadmap, progress, traceability audit and acceptance checklist.

- [ ] **Step 1: Run verification**

Run backend focus: `python -m pytest -q backend/tests/unit/test_stage07_digital_employee_management_models.py backend/tests/unit/test_stage07_digital_employee_management_service.py backend/tests/unit/test_stage07_digital_employee_management_api.py backend/tests/unit/test_stage07_draft_employee_hub_api.py backend/tests/unit/test_stage07_assistant_context_api.py`.

Run PostgreSQL: `python -m pytest -q backend/tests/integration/test_stage07_digital_employee_management_postgres.py backend/tests/integration/test_stage07_draft_employee_hub_postgres.py -m postgres`.

Run Mini App focus/full/build: `npm.cmd test -- --run src/test/digital-employee-management-api.test.ts src/test/digital-employee-management-query.test.ts src/test/digital-employee-management-workbench.test.tsx src/test/digital-employee-management-app-flow.test.tsx`; `npm.cmd test -- --run`; `npm.cmd run build`.

Run full backend: `python -m pytest -q backend`.

- [ ] **Step 2: Inspect UI only when locally available without browser control**

Record actual manual desktop/mobile observations only. If no locally available fixture/application exists without browser control, leave visual acceptance open.

- [ ] **Step 3: Reconcile DEM-A01 through DEM-A11**

Promote only direct evidence to `implemented-local`. Record migration head/replay/downgrade, lock/idempotency, measured index plan if run, skipped database/browser checks and cleanup. Keep provider/Telegram/staging/production/excluded Package4 work open.

- [ ] **Step 4: Documentation check and commit**

Run `git diff --check` and forbidden-marker scan over TD010/design/BDD/SDD/work-surface/complex-index/plan. Commit `docs(stage07): reconcile employee management evidence` only after the evidence is truthful.

## Plan Self-Review

| TD010 requirement | Task |
| --- | --- |
| additive version/access-mode/grants and legacy compatibility | 1 |
| fixed configuration/lifecycle/member eligibility | 2 |
| safe API and existing action reuse | 3 |
| S5/TD009 assigned eligibility | 4 |
| strict transport/cache isolation | 5 |
| bounded Base workbench | 6 |
| reread/stale-result handling | 7 |
| every BDD row and evidence reconciliation | 8 |

No task adds multi-Base scope, Base reassignment, archive/delete, chat/memory/knowledge, record picker, Telegram routing, external action or a general agent/permission framework.
