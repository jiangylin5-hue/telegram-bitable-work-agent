# Stage07 Personal Assistant Context Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax.

**Goal:** Allow an authorized Workspace Home member to select a safe existing digital employee and one permitted saved view, invoke only the existing summarize intent, and explicitly open the matching Base.

**Architecture:** Reuse S5 contacts/invocation, Stage06 employee/view authorization and TD001 protected QueryClient. Add a contact-specific permitted-view catalog plus a selected-view reread. A presentational workbench owns local selection/result; App owns query lifetime, failure cleanup and existing Base handoff.

**Tech Stack:** Existing Python/FastAPI/Pydantic/SQLAlchemy 2.x and React/TypeScript/TanStack Query/Vitest/Testing Library/Vite. No dependency, schema or migration change.

## Global Constraints

- Only TD009 Option B is in scope.
- Reuse DigitalEmployee Base/view scope and S5 summarize; do not create a permission engine.
- No migration, table, index, lifecycle state, permission action, URL persistence, LangGraph store/checkpointer, record picker, draft action, memory, knowledge, Telegram route, external operation or dependency.
- Browser DTOs contain only opaque IDs and approved display fields. No generic employee/view DTO, configuration, policy, field, record, runtime/provider/trace data or raw error.
- Every new key uses verified user/workspace scope. Contact/view/workspace/close replacements discard late results.
- Do not control the user's browser.

---

## File Structure

| File | Responsibility |
| --- | --- |
| backend/app/schemas/stage07_draft_employee_hub.py | closed catalog/selected-view DTOs |
| backend/app/api/routes/stage07_draft_employee_hub.py | authorization-backed catalog/reread routes |
| backend/tests/unit/test_stage07_draft_employee_hub_api.py | intersection, redaction, empty, denial tests |
| mini-app/src/app/draft-employee-types.ts | safe context types |
| mini-app/src/app/api.ts | strict parsers and read methods |
| mini-app/src/app/protectedQuery.ts | scoped context keys and cleanup |
| mini-app/src/app/AssistantContextWorkbench.tsx | safe Home assistant UI |
| mini-app/src/app/WorkspaceHome.tsx | explicit assistant callback |
| mini-app/src/app/App.tsx | lifecycle, summary and Base handoff |
| mini-app/src/styles.css | scoped responsive layout |
| mini-app/src/test/*assistant-context*.test.tsx | UI/application tests |

### Task 1: Closed server contact-to-view projection

**Files:**
- Modify: backend/app/schemas/stage07_draft_employee_hub.py
- Modify: backend/app/api/routes/stage07_draft_employee_hub.py
- Modify: backend/tests/unit/test_stage07_draft_employee_hub_api.py

**Produces:**

~~~
class SafeAssistantContextEmployeeResponse(BaseModel):
    id: str
    name: str
    description: str
    base_id: str

class SafeAssistantContextViewResponse(BaseModel):
    id: str
    name: str
    view_type: Literal["grid", "kanban", "calendar", "form"]

class SafeAssistantContextPageResponse(BaseModel):
    employee: SafeAssistantContextEmployeeResponse
    views: list[SafeAssistantContextViewResponse]
    next_cursor: str | None = None
    has_more: bool = False

class SafeAssistantSelectedViewResponse(BaseModel):
    id: str
    name: str
    view_type: Literal["grid", "kanban", "calendar", "form"]
    base_id: str
~~~

Routes:

~~~
GET /mini-app/digital-employees/{employee_id}/assistant-context
GET /mini-app/digital-employees/{employee_id}/assistant-context/views/{view_id}
~~~

- [ ] **Step 1: Write failing projection tests**

Create one Base with one employee-allowed view, one same-Base view outside employee scope and one foreign-workspace view. Assert exactly the allowed id/name/view_type appears; scope arrays, table id, config, policy, field, record, runtime and trace are absent.

~~~
response = client.get(f"/mini-app/digital-employees/{employee.id}/assistant-context")
assert response.status_code == 200
assert response.json()["views"] == [{"id": str(allowed.id), "name": "待处理", "view_type": "grid"}]
assert "accessible_views" not in response.text
assert str(table.id) not in response.text
~~~

- [ ] **Step 2: Write failing re-read and denial tests**

Assert out-of-scope view is generic 404, caller without existing digital_employee.invoke is denied, and removing/revoking a view after catalog read makes selected-view reread 404.

- [ ] **Step 3: Run red test**

~~~powershell
python -m pytest -q backend/tests/unit/test_stage07_draft_employee_hub_api.py -k "assistant_context"
~~~

Expected: FAIL because DTOs/routes do not exist.

- [ ] **Step 4: Implement minimal shared resolver**

Load only active employee; authorize existing digital_employee.invoke; require caller-readable employee Base; enumerate views for employee Base; intersect exact ids with employee accessible_views; reapply current caller view access; stable sort name/id; paginate with existing helper. Selected-view route calls the same resolver and matches one exact id.

Do not call list_view_records, return generic view payload/configuration, or modify the existing invocation endpoint.

- [ ] **Step 5: Run green test**

Run the same command. Expected: PASS for safe intersection/redaction, empty result, selected reread and denied states.

- [ ] **Step 6: Commit**

~~~powershell
git add backend/app/schemas/stage07_draft_employee_hub.py backend/app/api/routes/stage07_draft_employee_hub.py backend/tests/unit/test_stage07_draft_employee_hub_api.py
git commit -m "feat(stage07): add safe assistant view context"
~~~

### Task 2: Strict client transport and protected keys

**Files:**
- Modify: mini-app/src/app/draft-employee-types.ts
- Modify: mini-app/src/app/api.ts
- Modify: mini-app/src/app/protectedQuery.ts
- Modify: mini-app/src/test/draft-employee-api.test.ts
- Modify: mini-app/src/test/draft-employee-query.test.ts

**Produces:**

~~~
export type AssistantContextView = {
  id: string
  name: string
  viewType: 'grid' | 'kanban' | 'calendar' | 'form'
}
export type AssistantContextPage = {
  employee: { id: string; name: string; description: string; baseId: string }
  views: AssistantContextView[]
  nextCursor: string | null
  hasMore: boolean
}
export type AssistantSelectedView = AssistantContextView & { baseId: string }
~~~

New keys:

~~~
assistantContext(scope, employeeId, cursor)
assistantView(scope, employeeId, viewId)
~~~

They resolve to the user/workspace-prefixed assistant-context namespace.

- [ ] **Step 1: Write failing parser/key tests**

Stub one allowed view plus forbidden config/scope fields and unknown view type. Assert parsed output contains only safe data, unknown type rejects and two workspace keys differ.

~~~
await expect(api.getAssistantContext('employee-1')).resolves.toEqual({
  employee: { id: 'employee-1', name: 'Ops', description: 'Safe', baseId: 'base-1' },
  views: [{ id: 'view-1', name: '待处理', viewType: 'grid' }],
  nextCursor: null, hasMore: false,
})
~~~

- [ ] **Step 2: Run red test**

~~~powershell
npm.cmd test -- --run src/test/draft-employee-api.test.ts src/test/draft-employee-query.test.ts
~~~

Expected: FAIL because context types, parser, methods and keys do not exist.

- [ ] **Step 3: Implement strict parser/methods**

Add safeAssistantContextPage, safeAssistantSelectedView, api.getAssistantContext, api.getAssistantSelectedView, two draftEmployeeKeys helpers and clearAssistantContextQueries. Reject unknown/missing roots/types, strip extra data and clear only assistant subtree.

- [ ] **Step 4: Run green test**

Run the same command. Expected: PASS with strict parsing and scope isolation.

- [ ] **Step 5: Commit**

~~~powershell
git add mini-app/src/app/draft-employee-types.ts mini-app/src/app/api.ts mini-app/src/app/protectedQuery.ts mini-app/src/test/draft-employee-api.test.ts mini-app/src/test/draft-employee-query.test.ts
git commit -m "feat(stage07): add protected assistant context transport"
~~~

### Task 3: Bounded assistant context workbench

**Files:**
- Create: mini-app/src/app/AssistantContextWorkbench.tsx
- Create: mini-app/src/test/assistant-context-workbench.test.tsx
- Modify: mini-app/src/styles.css

**Consumes:**

~~~
type AssistantContextWorkbenchProps = {
  contacts: S5Contact[]
  context: AssistantContextPage | null
  selectedView: AssistantSelectedView | null
  summary: { answer: string; citations: S5Citation[] } | null
  loading: boolean
  failed: boolean
  onSelectContact: (employeeId: string) => void
  onSelectView: (viewId: string) => void
  onSummarize: (instruction?: string) => Promise<void>
  onOpenBase: () => void
  onRetry: () => void
  onClose: () => void
}
~~~

- [ ] **Step 1: Write failing UI boundary tests**

Assert idle fixed copy, safe contact/view controls, summary enablement after selected-view reread, fixed empty/retry copy and no draft action, record label, scope id or memory/knowledge control.

~~~
expect(screen.getByText('请选择数字员工和可访问视图，再开始协作。')).toBeVisible()
fireEvent.click(screen.getByRole('button', { name: '选择数字员工 运营助理' }))
expect(screen.getByRole('button', { name: '选择视图 待处理' })).toBeVisible()
expect(screen.queryByRole('button', { name: '创建草稿' })).not.toBeInTheDocument()
~~~

- [ ] **Step 2: Run red test**

~~~powershell
npm.cmd test -- --run src/test/assistant-context-workbench.test.tsx
~~~

Expected: FAIL because component does not exist.

- [ ] **Step 3: Implement presentational workbench and CSS**

Use existing Draft Hub dialog/sheet language. Component receives safe props/callbacks only and fetches nothing. Flow is contact → view → optional instruction capped at 1000 chars → 执行摘要 → safe answer. Show 打开 Base 继续处理 only after selected-view reread. Clear instruction/answer/pending state whenever contact/view props change.

Add only assistant-context CSS using existing colors/radii/mobile conventions. Do not redesign AppShell.

- [ ] **Step 4: Run green test**

Run the same command. Expected: PASS for visible safe states and prohibited-action absence.

- [ ] **Step 5: Commit**

~~~powershell
git add mini-app/src/app/AssistantContextWorkbench.tsx mini-app/src/test/assistant-context-workbench.test.tsx mini-app/src/styles.css
git commit -m "feat(stage07): add bounded assistant context workbench"
~~~

### Task 4: Home lifecycle, fixed summary and Base handoff

**Files:**
- Modify: mini-app/src/app/WorkspaceHome.tsx
- Modify: mini-app/src/app/App.tsx
- Create: mini-app/src/test/assistant-context-app-flow.test.tsx

**Produces:**

~~~
async function openAssistantContextWorkbench(trigger?: HTMLElement): Promise<void>
async function selectAssistantContact(employeeId: string): Promise<void>
async function selectAssistantView(viewId: string): Promise<void>
async function summarizeAssistantContext(instruction?: string): Promise<void>
async function openAssistantContextBase(): Promise<void>
function closeAssistantContextWorkbench(): void
~~~

- [ ] **Step 1: Write failing App flow tests**

Mock bootstrap/Home/contact/catalog/selected-view/invocation/Base-list. Assert order: Home assistant → contact → catalog → selected-view reread → existing summary POST → explicit Base handoff. Assert no request body contains draft_update, record_id, runtime_mode, accessible_views or browser role.

Use deferred catalog/summary responses, replace workspace/contact/view before resolve and assert stale name/answer never renders. Add 401, 403, 404 and 503 fixtures that show existing generic cleanup or fixed retry without raw detail.

- [ ] **Step 2: Run red test**

~~~powershell
npm.cmd test -- --run src/test/assistant-context-app-flow.test.tsx
~~~

Expected: FAIL because Home has no assistant context lifecycle.

- [ ] **Step 3: Implement scoped App orchestration**

WorkspaceHome gains onOpenAssistant; only its existing 智能汇总 action invokes it. App has a separate AssistantContextPanel and generation. Contact selection fetches assistantContext; view selection fetches assistantView; summary posts only summarize with base/view/instruction after successful reread. Base continuation rereads existing safe workspaceBases, finds selected employee Base, then delegates to existing openBase.

Current request handling: 401 denyInvalidSession; 403 denyWorkspace; 404 clears exact selection/keys; 409/422 clears selected view but retains only typed instruction; malformed/network/5xx produces fixed retry. Stale results do nothing. Do not modify Canvas-only invokeS5Employee.

- [ ] **Step 4: Run green test**

Run the same command. Expected: PASS for request order, summary-only Home, explicit Base handoff and stale/error isolation.

- [ ] **Step 5: Run affected regression/build**

~~~powershell
npm.cmd test -- --run src/test/draft-employee-api.test.ts src/test/draft-employee-query.test.ts src/test/draft-employee-hub.test.tsx src/test/assistant-context-workbench.test.tsx src/test/assistant-context-app-flow.test.tsx
npm.cmd run build
~~~

Expected: all selected tests pass and Vite reports success.

- [ ] **Step 6: Commit**

~~~powershell
git add mini-app/src/app/WorkspaceHome.tsx mini-app/src/app/App.tsx mini-app/src/test/assistant-context-app-flow.test.tsx
git commit -m "feat(stage07): connect home assistant context discovery"
~~~

### Task 5: Evidence reconciliation and bounded verification

**Files:**
- Modify: TD009/design/BDD/SDD/work-surface/index and Stage07 source/roadmap/progress/traceability/acceptance docs.

- [ ] **Step 1: Run package regressions**

~~~powershell
python -m pytest -q backend/tests/unit/test_stage07_draft_employee_hub_api.py
npm.cmd test -- --run
npm.cmd run build
~~~

Expected: all pass. If an authorized disposable PostgreSQL URL is available, add/run dedicated context intersection/revocation; otherwise record no database claim.

- [ ] **Step 2: Reconcile ACD-A01 through ACD-A10**

Mark only evidenced local rows implemented-local. Keep manual visual review, external provider/Telegram proof and excluded Package4 capabilities pending. Record commands/counts, skipped database/browser evidence, no migration/dependency proof and cleanup.

- [ ] **Step 3: Run document checks and commit**

~~~powershell
git diff --check
rg -n "[T]ODO|[T]BD|place[h]older" project-docs/08-implementation/STAGE_07_TECHNICAL_DECISION_009_ASSISTANT_CONTEXT_DISCOVERY.md docs/superpowers/specs/2026-07-13-stage07-assistant-context-discovery-design.md project-docs/08-implementation/STAGE_07_ASSISTANT_CONTEXT_DISCOVERY_BDD_AND_ACCEPTANCE.md project-docs/08-implementation/STAGE_07_ASSISTANT_CONTEXT_DISCOVERY_SDD.md project-docs/03-modules/STAGE_07_ASSISTANT_CONTEXT_DISCOVERY_WORK_SURFACE.md project-docs/08-implementation/STAGE_07_ASSISTANT_CONTEXT_DISCOVERY_COMPLEX_FEATURE_INDEX.md
git add project-docs/08-implementation project-docs/03-modules docs/superpowers/specs/2026-07-13-stage07-assistant-context-discovery-design.md docs/superpowers/plans/2026-07-13-stage07-assistant-context-discovery-implementation.md
git commit -m "docs(stage07): reconcile assistant context evidence"
~~~

Expected: no whitespace errors, no prohibited markers and documentation records no broader acceptance.

## Plan Self-Review

| Approved requirement | Task |
| --- | --- |
| employee/caller/Base/view intersection | Task 1 |
| strict DTO/parser and protected cache isolation | Task 2 |
| Home contact/view/summary without draft/memory/knowledge | Task 3 |
| selected-view reread, stale generations, errors and Base handoff | Task 4 |
| every ACD acceptance row and honest evidence | Task 5 |

No task adds schema, lifecycle, memory, knowledge, record picker, Telegram or external action.
