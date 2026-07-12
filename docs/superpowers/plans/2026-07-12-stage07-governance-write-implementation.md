# Stage07 Governance Write Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver approved S4: versioned, idempotent member-role and field-policy commands plus protected Mini App editing, while reusing the existing V1 view-grant command.

**Architecture:** Add two additive revisions to existing `WorkspaceMember` and `PlatformField`, then reuse Stage06 fixed RBAC, row locks, idempotency records, audit service and Pydantic safe projections. React receives closed DTOs only, performs no optimistic authorization mutation and rereads canonical safe state after every terminal outcome.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy 2.x, Alembic, PostgreSQL, React, TypeScript, TanStack Query and current CSS/lucide system.

## Global Constraints

- TD004 permits only active-member role changes, fixed field `hidden|read|write` policy replacement and existing V1 grant reuse.
- Keep five fixed roles. Do not add invitations, deactivation, owner transfer, custom roles/actions, group/per-user policy or a general authorization library.
- Add only `workspace_members.version` and `fields.permission_version`; no new policy table, index or dependency.
- Every write requires server authorization, `Idempotency-Key`, row-lock revision comparison, sanitized audit and no optimistic UI.
- Generic member/audit routes and `PUT /views/{view_id}/members` remain unchanged.
- Tests use only in-memory or disposable local PostgreSQL data. No Telegram, staging, production, push, PR or deployment.

## Execution Status (2026-07-12)

| Group | Status | Evidence / remaining condition |
| --- | --- | --- |
| G1 — revisions, commands and PostgreSQL safety | completed locally | additive migration, fixed actions, locked/idempotent/audited services/routes and real disposable PostgreSQL replay/stale/concurrency evidence are implemented. |
| G2 — protected Mini App editing | completed locally | closed transport, protected keys, no-optimistic role/policy workbench and existing V1 restricted-view reuse are implemented and built. |
| G3 Step 1 — focused verification | completed locally | focused backend `19 passed`, frontend `5 files / 23 tests`, production build, migration downgrade/upgrade and smoke passed. |
| G3 Step 2 — Browser matrix | partial-local | built synthetic client observed role/policy success, V1 reuse and `1440/1280/430/390` paths with console `[]`; stale/denied/retry/focus-return permutations remain open. |
| G3 Step 3 — cleanup/reconciliation | completed locally | temporary seed/proxy removed, services stopped and evidence matrix reconciled. |
| G3 Step 4 — evidence commit | completed locally | `56171d4` records the evidence after final diff/check and port-clean verification. |

---

## File Map

| File | Responsibility |
| --- | --- |
| `backend/alembic/versions/20260712_0023_stage07_governance_write_revisions.py` | additive revision columns and reversible migration |
| `backend/app/models/stage06_platform.py` | model defaults for revisions |
| `backend/app/services/stage06_authorization.py` | two fixed governance actions |
| `backend/app/services/stage06_platform.py` | lock methods, normalization, mutation services and closed projections |
| `backend/app/schemas/stage07_governance_write.py` | strict S4 models |
| `backend/app/api/routes/stage07_governance_write.py` | four Mini App routes and idempotency/error mapping |
| `backend/app/main.py` | router mount |
| `backend/tests/unit/test_stage07_governance_write_api.py` | route contract and negative matrix |
| `backend/tests/integration/test_stage07_governance_write_postgres.py` | local PostgreSQL transaction/enforcement proof |
| `mini-app/src/app/governance-write-types.ts` | closed browser DTO types |
| `mini-app/src/app/api.ts` | strict GET/PATCH/PUT transport |
| `mini-app/src/app/protectedQuery.ts` | exact governance-write keys/removal |
| `mini-app/src/app/GovernanceWriteWorkbench.tsx` | role/policy editor UI |
| `mini-app/src/app/App.tsx`, `AppShell.tsx`, `styles.css` | lifecycle and responsive integration |
| `mini-app/src/test/governance-write-*.test.tsx` | parser/query/component/App regressions |

## G1: Backend Contract, Revisions and Atomic Commands

### Task 1: Migration, models and action grants

**Files:** Create `backend/alembic/versions/20260712_0023_stage07_governance_write_revisions.py`; modify `backend/app/models/stage06_platform.py`, `backend/app/services/stage06_authorization.py`; test `backend/tests/unit/test_stage07_governance_write_api.py`.

**Produces:** default `WorkspaceMember.version=1`, `PlatformField.permission_version=1`; `member.manage` and `field.permission.manage` for owner/admin only.

- [ ] **Step 1: Write failing revision/action tests**

    def test_governance_actions_are_owner_admin_only() -> None:
        assert action_allowed_for_role("owner", "member.manage")
        assert action_allowed_for_role("admin", "field.permission.manage")
        assert not action_allowed_for_role("builder", "field.permission.manage")

    def test_governance_models_start_with_revision_one() -> None:
        member = WorkspaceMember(id=uuid4(), workspace_id=uuid4(), user_id="operator-1", role="operator", status="active")
        field = PlatformField(id=uuid4(), table_id=uuid4(), name="Internal", key="internal", field_type="text", required=False, unique=False, options={}, permission_policy={}, order_index=0, status="active")
        assert member.version == field.permission_version == 1

- [ ] **Step 2: Verify RED**

Run: `cd backend; python -m pytest -q tests/unit/test_stage07_governance_write_api.py -k "actions or revision"`

Expected: missing grants and attributes cause failure.

- [ ] **Step 3: Implement smallest additive change**

    # model fields
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    permission_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

Migration adds both non-null `INTEGER DEFAULT 1` columns and drops only them on downgrade. Add the two action strings only to owner/admin action sets.

- [ ] **Step 4: Verify GREEN and migration SQL**

Run: `cd backend; python -m pytest -q tests/unit/test_stage07_governance_write_api.py -k "actions or revision"; alembic upgrade head --sql`

Expected: tests pass; revision chain ends at `20260712_0023`.

- [ ] **Step 5: Commit**

Run: `git add backend/alembic/versions/20260712_0023_stage07_governance_write_revisions.py backend/app/models/stage06_platform.py backend/app/services/stage06_authorization.py backend/tests/unit/test_stage07_governance_write_api.py; git commit -m "feat(stage07): add governance write revisions"`

### Task 2: Locked services and safe FastAPI routes

**Files:** Modify `backend/app/services/stage06_platform.py`, `backend/app/main.py`; create `backend/app/schemas/stage07_governance_write.py`, `backend/app/api/routes/stage07_governance_write.py`; extend the same unit test.

**Consumes:** Task 1 revisions/actions plus existing `begin_idempotent_operation`, `complete_idempotent_operation`, audit writer and Stage06 authorization.

**Produces:**

    GET   /mini-app/workspaces/{workspace_id}/governance/member-editor
    PATCH /mini-app/workspaces/{workspace_id}/governance/members/{member_id}/role
    GET   /mini-app/tables/{table_id}/governance/field-permissions
    PUT   /mini-app/tables/{table_id}/governance/fields/{field_id}/permission-policy

- [ ] **Step 1: Write failing route/invariant tests**

    def test_admin_changes_operator_but_cannot_promote_or_modify_admin(client, seed):
        allowed = client.patch(seed.role_path, headers=seed.key(), json={"role": "builder", "expected_version": 1})
        forbidden = client.patch(seed.admin_path, headers=seed.key("other"), json={"role": "admin", "expected_version": 1})
        assert allowed.status_code == 200
        assert forbidden.status_code == 422

    def test_policy_is_complete_closed_and_idempotent(client, seed):
        payload = {"expected_permission_version": 1, "policy": {"owner": "write", "admin": "write", "builder": "write", "operator": "read", "viewer": "hidden"}}
        assert client.put(seed.policy_path, headers=seed.key(), json=payload).status_code == 200
        assert client.put(seed.policy_path, headers=seed.key(), json=payload).status_code == 200

- [ ] **Step 2: Verify RED**

Run: `cd backend; python -m pytest -q tests/unit/test_stage07_governance_write_api.py`

Expected: routes/schemas/services do not exist.

- [ ] **Step 3: Implement strict services and routes**

Add `lock_workspace_member_for_mutation` and `lock_field_for_mutation` to both UOWs; SQLAlchemy uses `with_for_update`. Implement `change_workspace_member_role` and `replace_field_permission_policy`. Each locks, rechecks scope/actor matrix, compares revision, updates only the approved column(s), increments once, writes sanitized audit and returns closed DTO data. Policy accepts exactly five role keys with `hidden|read|write`; owner must be `write`. New routes use strict Pydantic schemas, current idempotency ledger and fixed `403|404|409|422` mappings.

- [ ] **Step 4: Verify GREEN and regression isolation**

Run: `cd backend; python -m pytest -q tests/unit/test_stage07_governance_write_api.py tests/unit/test_stage07_governance_api.py tests/unit/test_stage06_authorization.py tests/unit/test_stage06_audit_redaction.py`

Expected: all pass and S3 read contracts stay unchanged.

- [ ] **Step 5: Commit**

Run: `git add backend/app/services/stage06_platform.py backend/app/schemas/stage07_governance_write.py backend/app/api/routes/stage07_governance_write.py backend/app/main.py backend/tests/unit/test_stage07_governance_write_api.py; git commit -m "feat(stage07): add governed role and field commands"`

### Task 3: Real PostgreSQL proof

**Files:** Create `backend/tests/integration/test_stage07_governance_write_postgres.py`.

- [ ] **Step 1: Write failing transaction/enforcement cases**

    def test_replay_once_and_stale_role_never_overwrites(stage06_postgres):
        first, replay, stale = mutate_member_through_real_app(stage06_postgres)
        assert first.status_code == replay.status_code == 200
        assert stale.status_code == 409
        assert one_audit_and_version_two(stage06_postgres)

    def test_hidden_field_omits_everywhere_and_write_mode_cannot_grant_viewer_update(stage06_postgres):
        set_hidden_policy(stage06_postgres)
        assert hidden_field_absent_from_schema_presentation_detail(stage06_postgres)
        assert viewer_update_attempt(stage06_postgres).status_code == 403

- [ ] **Step 2: Verify RED and migration smoke**

Run: `cd backend; $env:DATABASE_URL=$env:STAGE06_LOCAL_DATABASE_URL; python scripts/stage06_local_postgres_migration_smoke.py; python -m pytest -q tests/integration/test_stage07_governance_write_postgres.py`

Expected: red before Task 2; the migration reaches the S4 head.

- [ ] **Step 3: Verify GREEN with concurrent command contention**

Run the same command after Task 2. Add concurrent distinct role/policy requests and assert one winner, one version increment and one audit mutation.

- [ ] **Step 4: Commit**

Run: `git add backend/tests/integration/test_stage07_governance_write_postgres.py; git commit -m "test(stage07): prove governance write postgres safety"`

## G2: Protected Mini App Editing

### Task 4: Closed transport and exact query keys

**Files:** Create `mini-app/src/app/governance-write-types.ts`; modify `mini-app/src/app/api.ts`, `mini-app/src/app/protectedQuery.ts`; test `mini-app/src/test/governance-write-api.test.ts`, `mini-app/src/test/governance-write-query.test.ts`.

- [ ] **Step 1: Write failing parser/key tests**

    expect(await api.listGovernanceEditableMembers("workspace-1")).toEqual(expect.objectContaining({ workspaceId: "workspace-1" }))
    expect(() => parseFieldPolicy({ owner: "read" })).toThrow("Invalid governance write response")
    expect(governanceWriteKeys.fieldPolicy(scope, "table-1")).toEqual(expect.arrayContaining(["governance-write", "field-policy", "table-1"]))

- [ ] **Step 2: Verify RED**

Run: `cd mini-app; npm.cmd test -- --run src/test/governance-write-api.test.ts src/test/governance-write-query.test.ts`

Expected: types/calls/keys do not exist.

- [ ] **Step 3: Implement allowlisted transport and no-optimistic helpers**

Use `URLSearchParams`, `encodeURIComponent`, strict role/mode/parser checks and PATCH/PUT `Idempotency-Key`. Add exact workspace/table/target removal. On success, cancel/remove S4 plus bootstrap/schema/presentation/detail keys and reread; on `409|422`, retain only local typed draft; unknown/server body is never rendered.

- [ ] **Step 4: Verify GREEN and commit**

Run: `npm.cmd test -- --run src/test/governance-write-api.test.ts src/test/governance-write-query.test.ts; git add mini-app/src/app/governance-write-types.ts mini-app/src/app/api.ts mini-app/src/app/protectedQuery.ts mini-app/src/test/governance-write-api.test.ts mini-app/src/test/governance-write-query.test.ts; git commit -m "feat(stage07): add protected governance write transport"`

### Task 5: Responsive role and field workbench

**Files:** Create `mini-app/src/app/GovernanceWriteWorkbench.tsx`; modify `mini-app/src/app/App.tsx`, `mini-app/src/app/AppShell.tsx`, `mini-app/src/styles.css`; test `mini-app/src/test/governance-write-workbench.test.tsx`, `mini-app/src/test/governance-write-app-flow.test.tsx`.

- [ ] **Step 1: Write failing component/Application tests**

    test("confirms role only after safe receipt reread", async () => {
      render(<GovernanceWriteWorkbench members={members} fields={fields} onChangeRole={changeRole} onReplacePolicy={replacePolicy} onClose={close} />)
      await user.selectOptions(screen.getByLabelText("成员 operator 的角色"), "builder")
      await user.click(screen.getByRole("button", { name: "确认改为 builder" }))
      expect(changeRole).toHaveBeenCalledWith("member-1", "builder", 1)
      expect(screen.queryByText("raw-server-detail")).not.toBeInTheDocument()
    })

    test("keeps typed policy on 409 and discards old scope response", async () => {
      render(<App />)
      await forcePolicyConflictAfterWorkspaceReplacement()
      expect(screen.getByText("数据已更新，请重新读取后再提交。")).toBeVisible()
      expect(screen.queryByText("old-workspace-field")).not.toBeInTheDocument()
    })

- [ ] **Step 2: Verify RED**

Run: `cd mini-app; npm.cmd test -- --run src/test/governance-write-workbench.test.tsx src/test/governance-write-app-flow.test.tsx`

Expected: editor/lifecycle do not exist.

- [ ] **Step 3: Implement read-before-write UI**

Only render selector values from `assignable_roles`; noneditable rows have no mutation control. Render the five-role matrix with owner fixed `write`; explicit confirmation disables only its pending command. Success invokes exact removal and authoritative reread before close. Map all terminal HTTP/network outcomes to SDD fixed UI states. Link View access only to the existing V1 control.

- [ ] **Step 4: Add mobile/focus behavior**

Use labelled full-height sheet at 430/390, 44px controls, independent content scroll, status/alert regions and exact opener focus return. Test no desktop-only write path and no raw response disclosure.

- [ ] **Step 5: Verify GREEN, build and commit**

Run: `npm.cmd test -- --run src/test/governance-write-workbench.test.tsx src/test/governance-write-app-flow.test.tsx; npm.cmd run build; git add mini-app/src/app/GovernanceWriteWorkbench.tsx mini-app/src/app/App.tsx mini-app/src/app/AppShell.tsx mini-app/src/styles.css mini-app/src/test/governance-write-workbench.test.tsx mini-app/src/test/governance-write-app-flow.test.tsx; git commit -m "feat(stage07): add governance write workbench"`

## G3: Evidence, Browser and Cleanup

### Task 6: Reconcile BDD-by-BDD

**Files:** Create `project-docs/08-implementation/evidence/stage07-governance-write.md`; modify `STAGE_07_PROGRESS.md`, `STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`, `STAGE_07_GOVERNANCE_WRITE_BDD_AND_ACCEPTANCE.md`, `STAGE_07_TEST_PLAN.md`.

- [ ] **Step 1: Run focused tests**

Run backend route/legacy tests, migration smoke and PostgreSQL suite from Tasks 1–3; then the four frontend files from Tasks 4–5 and `npm.cmd run build`. Record actual counts only.

- [ ] **Step 2: Run built-client Browser matrix**

Use synthetic owner/admin/viewer data only. Observe role success, field-policy success, stale conflict, denied/retry, focus return and console scan at 1440/1280/430/390. If local Browser navigation is unavailable, record its exact limitation and leave GW-A07 pending.

- [ ] **Step 3: Cleanup and acceptance reconciliation**

Remove temporary fixture/proxy/logs with `apply_patch`, stop local services, prove ports closed, update only evidence-supported GW-A01..GW-A08 rows and run `git diff --check`.

- [ ] **Step 4: Commit evidence**

Run: `git add project-docs/08-implementation/evidence/stage07-governance-write.md project-docs/08-implementation/STAGE_07_PROGRESS.md project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md project-docs/08-implementation/STAGE_07_GOVERNANCE_WRITE_BDD_AND_ACCEPTANCE.md project-docs/08-implementation/STAGE_07_TEST_PLAN.md; git commit -m "docs(stage07): record governance write evidence"`

## Plan Self-Review

- GW-A01/GW-A02 map to Tasks 1–3; GW-A03/GW-A04 to Tasks 2–3; GW-A05 to Task 5; GW-A06 to Tasks 4–5; GW-A07/GW-A08 to Task 6.
- No task permits invitation, deactivation, owner transfer, custom RBAC or a general policy engine.
- Every write uses the exact action, revision, idempotency, audit and protected-state rules from TD004.

## Execution Handoff

Execute inline in this existing Stage07 worktree as G1 → G2 → G3. Do not dispatch subagents, push, create a PR or deploy.
