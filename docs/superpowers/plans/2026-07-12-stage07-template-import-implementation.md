# Stage07 Template And Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver one existing-contract Mini App package for template installation/save and CSV/XLSX import preview/mapping/commit, with authoritative rereads and no browser retention of raw file data.

**Architecture:** Extend existing `api.ts` safe transport and protected TanStack Query keys; render focused panels from `App.tsx`; make FastAPI/PostgreSQL authoritative for every mutation/navigation. Native `File` content is held only in component memory while create-preview is active.

**Tech Stack:** React 19, TypeScript, Vite, TanStack Query, Vitest/Testing Library, native File APIs, existing FastAPI/SQLAlchemy/PostgreSQL Stage06 template-import routes.

## Global Constraints

- Consume only existing `stage06_templates.py` routes; no backend code, migration, endpoint, action, capability, dependency or external storage.
- Legacy actor fields copy verified bootstrap identity; browser never sends a role/action claim.
- File bytes/base64, manifests, full rows, `error_summary`, raw response bodies and server messages never reach keys, localStorage, URLs, telemetry or rendered errors.
- Mapping allowlist: `text`, `number`, `date`, `checkbox`. Do not create relation/lookup/select/status/user/formula/options controls.
- Install/create-preview/commit use idempotency; 409 locks with no automatic retry; success rereads authorized resources before navigation.

---

### Task 1: Safe Template/Import Transport and Protected State

**Files:**

- Create: `mini-app/src/app/template-import-types.ts`
- Modify: `mini-app/src/app/api.ts`
- Modify: `mini-app/src/app/protectedQuery.ts`
- Test: `mini-app/src/test/template-import-api.test.ts`
- Test: `mini-app/src/test/template-import-query.test.ts`

**Interfaces:** consumes `getJson`, `postJson`, `ApiError`, `protectedQueryKey`; produces safe types/API methods and exact cleanup for Tasks 2–3.

- [ ] **Step 1: Write the failing transport/key tests**

```ts
test('posts only approved XLSX preview fields and an idempotency key', async () => {
  await api.createImport('workspace-1', {
    sourceType: 'excel', fileName: 'tasks.xlsx', content: 'UEsDB...', createdByUserId: 'user-1', baseId: undefined,
  }, 'import-create-1')
  expect(fetchMock).toHaveBeenCalledWith('/workspaces/workspace-1/imports', expect.objectContaining({
    method: 'POST', body: JSON.stringify({ source_type: 'excel', file_name: 'tasks.xlsx', content: 'UEsDB...', created_by_user_id: 'user-1' }),
  }))
})

test('omits manifest, error_summary and unknown mapping types from a parsed import job', async () => {
  await expect(api.importJob('job-1')).resolves.toMatchObject({ id: 'job-1', status: 'awaiting_confirmation' })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `npm.cmd test -- --run src/test/template-import-api.test.ts src/test/template-import-query.test.ts`

Expected: FAIL because the types, methods and keys are absent.

- [ ] **Step 3: Implement closed safe types and methods**

```ts
export type ImportScalarFieldType = 'text' | 'number' | 'date' | 'checkbox'
export type ImportMapping = { source_key: string; target_key: string; field_type: ImportScalarFieldType; name?: string }
export type ImportPreview = {
  id: string; workspace_id: string; base_id: string | null; source_type: 'csv' | 'excel'
  detected_schema: { key: string; name: string; field_type: ImportScalarFieldType }[]
  preview_rows: Record<string, unknown>[]; mapping: ImportMapping[]; status: 'awaiting_confirmation' | 'committed'
}
```

Implement `listTemplates`, `installTemplate`, `saveBaseAsTemplate`, `createImport`, `importJob`, `commitImport`; paths use `encodeURIComponent`, idempotent writes use `postJson`, and runtime parsers retain allowlisted fields only. Extend `SafeApiErrorCode` only with SDD §8 codes.

- [ ] **Step 4: Implement exact protected cleanup**

```ts
export const templateImportKeys = {
  templates: (scope: ProtectedScope) => protectedQueryKey(scope, 'templates'),
  importJob: (scope: ProtectedScope, jobId: string) => protectedQueryKey(scope, 'import', jobId),
}
export async function clearTemplateImportQueries(queryClient: QueryClient, scope: ProtectedScope, jobId?: string) {
  const keys = [templateImportKeys.templates(scope), ...(jobId ? [templateImportKeys.importJob(scope, jobId)] : [])]
  await Promise.all(keys.map((queryKey) => queryClient.cancelQueries({ queryKey })))
  for (const queryKey of keys) queryClient.removeQueries({ queryKey })
}
```

Test workspace-scoped keys, exact import-job removal/cancellation and no file content in query keys.

- [ ] **Step 5: Run focused tests and commit**

Run: `npm.cmd test -- --run src/test/template-import-api.test.ts src/test/template-import-query.test.ts`

Expected: PASS with approved request fields, keys, headers and redaction. Then run: `git add mini-app/src/app/template-import-types.ts mini-app/src/app/api.ts mini-app/src/app/protectedQuery.ts mini-app/src/test/template-import-api.test.ts mini-app/src/test/template-import-query.test.ts; git commit -m "feat(stage07): add template import transport boundary"`.

### Task 2: Template Shelf, Installation and Current-Base Save

**Files:**

- Create: `mini-app/src/app/TemplateImportHub.tsx`
- Create: `mini-app/src/app/SaveTemplatePanel.tsx`
- Modify: `mini-app/src/app/App.tsx`
- Modify: `mini-app/src/app/WorkspaceHome.tsx`
- Modify: `mini-app/src/app/BaseCanvas.tsx`
- Modify: `mini-app/src/styles.css` (or current Stage07 dialog/sheet stylesheet)
- Test: `mini-app/src/test/template-install-flow.test.tsx`
- Test: `mini-app/src/test/save-template-panel.test.tsx`

**Interfaces:** consumes Task 1, `can_manage_schema`, current `openBase` and safe Home/Base reads; produces template management and import-entry callbacks for Task 3.

- [ ] **Step 1: Write failing template UI/lifecycle tests**

```tsx
test('installs only after refreshed Home contains receipt base', async () => {
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '模板与导入' }))
  fireEvent.click(await screen.findByRole('button', { name: '安装模板' }))
  expect(await screen.findByRole('heading', { name: 'CRM' })).toBeVisible()
  expect(homeReads).toBeGreaterThanOrEqual(2)
})
test('renders saved custom template metadata without a manifest', async () => {
  render(<SaveTemplatePanel base={base} onSave={onSave} onClose={onClose} />)
  fireEvent.click(screen.getByRole('button', { name: '保存为模板' }))
  expect(await screen.findByText('草稿模板')).toBeVisible()
  expect(screen.queryByText('manifest')).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run to verify failure**

Run: `npm.cmd test -- --run src/test/template-install-flow.test.tsx src/test/save-template-panel.test.tsx`

Expected: FAIL because panels and entry points are absent.

- [ ] **Step 3: Implement panels and accessible states**

`TemplateImportHub` owns safe shelf/loading/empty/denied/retry states and emits `onInstall(template)`, `onStartWorkspaceImport()` and close. It groups returned category but shows only safe metadata. `SaveTemplatePanel` owns name/category/description validation, pending lock, fixed error copy and focus return. It renders only safe receipt metadata and no manifest/publication/share/delete/version action.

- [ ] **Step 4: Integrate exact App lifecycle**

```ts
type TemplateImportPanel =
  | { mode: 'hub' }
  | { mode: 'save-template'; base: BaseSummary }
  | { mode: 'workspace-import' }
  | { mode: 'base-import'; base: BaseSummary }
```

Add `templateImportRequestVersion` to existing invalidation. Entries are visible only behind `can_manage_schema` as a non-authoritative hint. Install clears exact template/import state, rereads Home and safe Base data, and opens only the receipt Base found in refreshed authorized results. Reuse existing 401/403/404 boundaries.

- [ ] **Step 5: Run focused tests and commit**

Run: `npm.cmd test -- --run src/test/template-install-flow.test.tsx src/test/save-template-panel.test.tsx`

Expected: PASS for safe display, pending lock, reread-before-open, denial and focus return. Then run: `git add mini-app/src/app/TemplateImportHub.tsx mini-app/src/app/SaveTemplatePanel.tsx mini-app/src/app/App.tsx mini-app/src/app/WorkspaceHome.tsx mini-app/src/app/BaseCanvas.tsx mini-app/src/styles.css mini-app/src/test/template-install-flow.test.tsx mini-app/src/test/save-template-panel.test.tsx; git commit -m "feat(stage07): add template management surface"`.

### Task 3: CSV/XLSX Intake, Server Preview, Scalar Mapping and Commit

**Files:**

- Create: `mini-app/src/app/ImportWizard.tsx`
- Modify: `mini-app/src/app/App.tsx`
- Modify: `mini-app/src/styles.css` (or current Stage07 dialog/sheet stylesheet)
- Test: `mini-app/src/test/import-wizard.test.tsx`
- Test: `mini-app/src/test/import-flow.test.tsx`

**Interfaces:** consumes Task 1 transport, Task 2 panel state, bootstrap identity and existing Home/Base reads; produces memory-only file handling and authoritative import navigation.

- [ ] **Step 1: Write failing wizard/flow tests**

```tsx
test('sends CSV text, renders server preview and commits only scalar mapping', async () => {
  const file = new File(['Name,Score\nAda,10\n'], 'customers.csv', { type: 'text/csv' })
  render(<ImportWizard target={{ kind: 'workspace', workspaceId: 'workspace-1' }} onCreatePreview={createPreview} onCommit={commit} onClose={close} />)
  fireEvent.change(screen.getByLabelText('选择导入文件'), { target: { files: [file] } })
  fireEvent.click(screen.getByRole('button', { name: '生成预览' }))
  expect(await screen.findByText('Ada')).toBeVisible()
})
test('discards deferred preview after workspace replacement', async () => {
  // resolve an old request after scope switch; assert prior filename/row/receipt Base is absent
})
```

- [ ] **Step 2: Run to verify failure**

Run: `npm.cmd test -- --run src/test/import-wizard.test.tsx src/test/import-flow.test.tsx`

Expected: FAIL because ImportWizard and lifecycle are absent.

- [ ] **Step 3: Implement one-file adapter and safe preview**

```ts
async function payloadForFile(file: File): Promise<{ sourceType: 'csv' | 'excel'; content: string }> {
  const extension = file.name.split('.').pop()?.toLowerCase()
  if (extension === 'csv') return { sourceType: 'csv', content: await file.text() }
  if (extension === 'xlsx') return { sourceType: 'excel', content: bytesToBase64(new Uint8Array(await file.arrayBuffer())) }
  throw new LocalImportError('仅支持 CSV 或 XLSX 文件。')
}
```

Allow one CSV/XLSX, preflight documented 5/10 MiB `File.size`, never parse rows locally, and clear File/content in `finally`, close, target replacement and unmount. Start preview with fresh key and verified bootstrap identity; render server schema/rows only.

- [ ] **Step 4: Implement mapping/commit state machine**

Default mapping derives from safe schema. Reject blank/duplicate target key and non-scalar type. Workspace target requires Base/table/key; Base target has fixed authorized `base_id` and requires table/key. Commit uses fresh key. On `committed`, remove exact job cache and use Task 2 authoritative reread helper. Preserve safe fields on 422, lock 409/invalid state, never retry blindly and reuse App 401/403/404 boundaries.

- [ ] **Step 5: Run focused tests and commit**

Run: `npm.cmd test -- --run src/test/import-wizard.test.tsx src/test/import-flow.test.tsx`

Expected: PASS for file adapter, no raw retention, preview/mapping, distinct keys, reread, denial and stale-scope cases. Then run: `git add mini-app/src/app/ImportWizard.tsx mini-app/src/app/App.tsx mini-app/src/styles.css mini-app/src/test/import-wizard.test.tsx mini-app/src/test/import-flow.test.tsx; git commit -m "feat(stage07): add import preview and commit flow"`.

### Task 4: Whole-Package Regression, PostgreSQL and Focused Browser Evidence

**Files:**

- Create: `project-docs/08-implementation/evidence/stage07-template-import-ui.md`
- Modify: `project-docs/08-implementation/STAGE_07_PROGRESS.md`
- Modify: `project-docs/08-implementation/STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`
- Modify: `project-docs/08-implementation/STAGE_07_TEMPLATE_IMPORT_BDD_AND_ACCEPTANCE.md`
- Modify: `project-docs/08-implementation/STAGE_07_TEST_PLAN.md`

**Interfaces:** consumes Tasks 1–3 and existing backend tests; produces only actual evidence/status.

- [ ] **Step 1: Add final application regressions**

Cover no manifest/error summary/file in DOM/query keys; unknown error generic copy; idempotency headers; 401 global removal; 403 workspace removal; 404 exact import removal; delayed preview/commit discard after close/workspace/Base switch; and receipt ID presence in refreshed safe data before navigation.

- [ ] **Step 2: Run focused frontend/backend and build**

Run: `cd mini-app; npm.cmd test -- --run src/test/template-import-api.test.ts src/test/template-import-query.test.ts src/test/template-install-flow.test.tsx src/test/save-template-panel.test.tsx src/test/import-wizard.test.tsx src/test/import-flow.test.tsx; npm.cmd run build; cd ../backend; python -m pytest -q tests/unit/test_stage06_template_import.py tests/unit/test_stage06_template_import_api.py tests/unit/test_stage06_import_limits.py tests/unit/test_stage06_idempotency_api.py tests/unit/test_stage06_authorization_api.py`

Expected: selected tests pass/build exits `0`; record actual counts only.

- [ ] **Step 3: Run only disposable PostgreSQL evidence**

Run: `cd backend; $env:DATABASE_URL = $env:STAGE06_LOCAL_DATABASE_URL; python scripts/stage06_local_postgres_migration_smoke.py; python -m pytest -q tests/integration/test_stage06_postgres_security.py -m postgres`

Expected: only explicit local disposable database resets; capture replay/authorization/commit result.

- [ ] **Step 4: Run focused Browser main path, cleanup and evidence update**

Observe built client template shelf/install reread, CSV preview/mapping/commit to new Base, in-Base entry and 430/390 sheet reachability. Scan console; do not grow into a large manual matrix unless defect occurs. Stop services, finalize Browser, delete temporary material, rerun migration smoke, verify ports closed, update listed evidence documents with actual results only, run `git diff --check`, then commit `docs(stage07): record template import evidence`.

## Plan Self-Review

- TI-A01 through TI-A08 map to Tasks 1–4: transport, template UI, import lifecycle, then actual evidence.
- Four reviewer-level tasks keep the package coherent; no separate approvals or unrelated governance/Bot/import-history project is introduced.
- Endpoints, types, safe data boundary, error behavior, file ownership and exact verification commands are specified. No schema/API/permission change is hidden.

## Execution Handoff

Execute inline in this worktree after user approval, task by task with Tasks 1–4 checkpoints. No subagents, push or production deployment are authorized.
