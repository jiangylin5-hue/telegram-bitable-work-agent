# Stage07 Template And Import SDD

## Status

- Document status: approved-scope technical design awaiting user review
- Scope: Mini App consumption of existing Stage06 template/import contracts only
- Architectural decision: reuse React/Vite/TypeScript, TanStack Query, FastAPI, SQLAlchemy and PostgreSQL; no dependency or backend-contract expansion

## 1. Design Constraints

1. Frontend submits no role/action claim. Existing bootstrap identity fills legacy required `installed_by_user_id`/`created_by_user_id` request members only; FastAPI identity is authoritative.
2. Client permits only read-safe response shapes and fixed error-code copy. It must not deserialize manifest/audit/raw exception content into UI state.
3. File content exists only during a create-preview request and is neither persisted nor included in query keys/logs/telemetry.
4. Existing server action names remain unchanged: `template.install`, `template.save`, `import.create`, `import.read`, `import.commit`.
5. Existing endpoint idempotency is required on install/create/commit. Save-template has no idempotency contract and the UI locks its single submit locally.

## 2. Existing Contract Inventory

| Endpoint | Request used by UI | Safe response consumed | Authority and client rule |
| --- | --- | --- | --- |
| `GET /templates` | none | `templates[]:{id,name,category,description,version,status}` | identity is required; no manifest read |
| `POST /workspaces/{workspace_id}/template-installations` | `{template_id,installed_by_user_id}` + `Idempotency-Key` | `{id,workspace_id,base_id,template_id,template_version,resource_map}` | server checks `template.install`; client reads only `base_id` for reread navigation |
| `POST /bases/{base_id}/templates` | `{name,category,description,created_by_user_id}` | safe `TemplateResponse` | server checks `template.save`; `status=draft` is display only |
| `POST /workspaces/{workspace_id}/imports` | `{source_type,file_name,content,created_by_user_id,base_id?}` + `Idempotency-Key` | `ImportJobResponse` | server checks `import.create`, parses and persists preview |
| `GET /imports/{import_job_id}` | none | `ImportJobResponse` | server checks `import.read`; no list route is assumed |
| `POST /imports/{import_job_id}/commit` | `{base_name,table_name,table_key,field_mapping?}` + `Idempotency-Key` | `{import_job_id,status,resource_map}` | server checks `import.commit`; client reads Base/table IDs only to reread |

`resource_map` is server-safe persistence output but is not a generic browser data model. UI narrows it to validated string `base_id`/`table_id` for navigation after authoritative state refresh; unknown keys are discarded.

## 3. Frontend Units And Interfaces

| Unit | Responsibility | Inputs/outputs |
| --- | --- | --- |
| `template-import-types.ts` | Safe local types, scalar mapping union and allowlisted error codes | no raw JSONB/manifest types |
| `api.ts` extension | Typed list/install/save/create/read/commit methods; CSV/XLSX request serializers | `ApiError(status, code?)` only |
| `protectedQuery.ts` extension | `templateImportKeys` plus exact cleanup helpers | user/workspace/template/import/Base IDs; never file data |
| `TemplateImportHub.tsx` | Shelf, entry routing, empty/denied/retry states | safe template list and event callbacks |
| `TemplateInstallPanel.tsx` | One-card install pending/replay/reread UI | safe `TemplateSummary`, no manifest |
| `SaveTemplatePanel.tsx` | Base-derived metadata form | name/category/description only |
| `ImportWizard.tsx` | file intake, preview, scalar mapping and explicit commit | local `File` held outside Query cache |
| `App.tsx` integration | open/close generations, mutations, protected cleanup, authoritative reread/navigation | existing ready workspace/Home/Canvas state |

The actual file split may combine small presentation-only units if the existing Mini App pattern makes that clearer; it must preserve these responsibilities and not create a general client-side import engine.

## 4. Typed Data Boundary

```ts
type TemplateSummary = {
  id: string
  name: string
  category: string
  description: string
  version: string
  status: string
}

type ImportScalarFieldType = 'text' | 'number' | 'date' | 'checkbox'
type ImportSchemaField = { key: string; name: string; field_type: ImportScalarFieldType }
type ImportMapping = {
  source_key: string
  target_key: string
  field_type: ImportScalarFieldType
  name?: string
}
type ImportPreview = {
  id: string
  workspace_id: string
  base_id: string | null
  source_type: 'csv' | 'excel'
  detected_schema: ImportSchemaField[]
  preview_rows: Record<string, unknown>[]
  mapping: ImportMapping[]
  status: 'awaiting_confirmation' | 'committed'
  error_summary: string | null
}
```

Runtime guards reject malformed strings, arrays, unknown source/status/type values, mappings with non-scalar field types and preview rows that are not plain objects. Error summary is not rendered: it stays outside all typed UI models. `Record<string, unknown>` preview values are rendered through bounded scalar text formatting only—no HTML interpretation, nested object traversal or broad JSON dump.

## 5. File Encoding And Local Validation

| File | Browser read | API `source_type` | API content |
| --- | --- | --- | --- |
| `.csv` | `await file.text()` | `csv` | UTF-8 string |
| `.xlsx` | `await file.arrayBuffer()` | `excel` | base64 ASCII of bytes |

Client preflight rules are UX only: one file, extension exactly CSV/XLSX (case-insensitive), CSV no larger than 5 MiB and XLSX no larger than 10 MiB according to `File.size`. CSV text is not parsed/retyped client-side; XLSX is never unzipped client-side. Server is final for UTF-8, extension deception, zip safety, headers, rows, columns, cell size, inference and limits.

`File` and generated base64 are kept in a component ref/local state during `createPreview`; success/failure/close/scope change clears them. Neither is passed to TanStack Query, App route state, localStorage, URL, error object or test snapshot fixture beyond an explicit mock request assertion.

## 6. Import State Machine

```text
closed
  -> intake(empty | selected | local-invalid | reading)
  -> creating-preview(pending)
  -> preview(awaiting_confirmation, default-mapping | dirty-mapping | invalid-mapping)
  -> committing(pending)
  -> committed-awaiting-reread
  -> opened-authoritative-resource

any active state -> denied | missing | conflict-locked | retryable | scope-invalidated | closed
```

- `preview` is valid only when response status is exactly `awaiting_confirmation`; `committed` response from create replay is handled as commit result and goes straight to safe reread, not a second commit.
- Commit is enabled only for valid scalar mapping, Base/table names and a table key accepted by local format guard. Format guard prevents accidental whitespace/empty values but does not replace server validation.
- `import_job_invalid_state` means job cannot transition; it locks commit and exposes a close/reload action, never a fabricated cancel/retry.
- Dialog close discards local draft. Because there is no import-job discovery/list UI, the user is not promised recovery of an uncommitted closed job.

## 7. Protected Query And Mutation Rules

```ts
templateImportKeys = {
  templates: (scope) => protectedQueryKey(scope, 'templates'),
  importJob: (scope, importJobId) => protectedQueryKey(scope, 'import', importJobId),
}
```

- Scope includes bootstrap `user_id` and active `workspace_id`.
- Install success cancels/removes `templates` only if needed, then invalidates/reloads existing Home/Base list and opens the returned Base only after list membership confirmation.
- Create-preview cache may retain only typed safe `ImportPreview` under exact job ID while wizard stays open. Close, workspace switch, 401/403, Base close/unmount remove it.
- Commit success removes exact import key, current Home key and affected Base safe keys, then calls existing authoritative Base-open flow.
- Late completion is guarded by monotonically increasing request generation, current active workspace/Base equality and panel identity. It cannot overwrite a newer panel or navigate a replacement workspace.

## 8. Error Allowlist And Copy Policy

| Code/status | Fixed local copy / state |
| --- | --- |
| `import_payload_limit_exceeded` | 文件超过服务器允许大小。 |
| `import_row_limit_exceeded` | 行数超过服务器允许上限。 |
| `import_column_limit_exceeded` | 列数超过服务器允许上限。 |
| `import_cell_limit_exceeded` | 存在超过服务器允许长度的单元格。 |
| `import_has_no_rows` | 文件没有可导入的数据行。 |
| `import_missing_header` | 文件缺少可用表头。 |
| `import_missing_sheet` | Excel 文件缺少可读取工作表。 |
| `unsupported_import_source` | 仅支持 CSV 或 XLSX 文件。 |
| `invalid_import_mapping` / `unsupported_field_type` | 字段映射不符合当前导入规则。 |
| `resource_scope_mismatch` | 当前 Base 不属于所选工作区。 |
| `import_job_invalid_state` | 此导入任务当前不能提交，请重新打开工作区后检查。 |
| `template_not_found` | 模板当前不可用，请刷新后重试。 |
| `idempotency_conflict` / `idempotency_in_progress` / HTTP 409 | 本次操作状态已变化，请刷新后重试。 |
| 401/403/404 | existing expired/denied/missing boundary; no detail copy |
| unknown 422/5xx/network/decode | 操作未完成，请稍后重试。 |

No server message, `error_summary`, request file content, response body dump or unknown error code is displayed.

## 9. Responsive, Accessibility And Audit

- Desktop: fixed-width workbench with explicit stepper and preview table horizontal scroll.
- Mobile 430/390: labelled full-screen dialog, sticky primary action, focus returns to trigger on close; preview table preserves columns through horizontal scroll rather than drops data silently.
- Every pending mutation disables duplicate submit and close only when it would orphan active in-memory file encoding; explicit accessible status announces parsing, preview ready, committing and authoritative refresh.
- Browser writes no audit record directly. Existing server transactions write template-install/import-commit audits; the UI consumes no audit event payload.

## 10. Non-Expansion Check

This SDD authorizes no migration, endpoint, schema model, capability boolean, role action, upload storage, queue, template publication, import cancel/delete or Bot/Telegram work. Any need for safe full Base picker, import-job recovery list, table append/overwrite, mapping option configuration or cloud file upload is a separate contract decision and user approval gate.
