# Stage07 Template And Import BDD And Acceptance

## Status

- Document status: detailed implementation source, awaiting user review
- Scope: approved existing-contract template/install/save and CSV/XLSX import preview/commit UI
- Current Progress: design only; no Mini App template/import code, new API, migration or permission change is implemented by this document
- Design companion: `../../docs/superpowers/specs/2026-07-12-stage07-template-import-design.md`

## 1. Vocabulary And Authority

| Term | Meaning |
| --- | --- |
| template shelf | Safe `GET /templates` metadata list; never a manifest browser. |
| installation | Existing server transaction that creates a Base/resources and records `TemplateInstallation`. |
| custom template | Existing `POST /bases/{base_id}/templates` result with server status `draft`; not public publication. |
| import job | Existing persisted parse/preview record, initially `awaiting_confirmation`. |
| workspace import | Import with no `base_id`; commit creates a Base and one table. |
| in-Base import | Import carries only the already-open authorized `base_id`; commit creates one table in that Base. |
| safe mapping | `{source_key,target_key,field_type,name?}` with scalar field types only. |
| durable success | Authoritative reread finds the installed/committed resource; a receipt alone is not success UI. |

Effective authority is always:

```text
existing UI capability hint -> authenticated identity -> workspace/Base authorization -> endpoint-specific action -> server transaction -> safe reread
```

## 2. BDD Scenarios

### TI-01 Template shelf is safe metadata only

Given an authenticated Mini App session
When it opens Templates & Imports
Then it requests `GET /templates` and renders only `id`, `name`, `category`, `description`, `version` and `status`
And it never renders template `manifest`, resource map, template creator, audit state or hidden Base data.

### TI-02 Only existing authorized management entry starts a mutation

Given the selected workspace lacks the existing `can_manage_schema` hint
When the user opens a Home or Base Canvas
Then install/import/save-template entries are absent.
Given an entry is visible but FastAPI rejects its action
Then the UI moves to denied without exposing a template/import/resource name from an error.
The hint is only UX; server `template.install`, `template.save`, `import.create`, `import.read` and `import.commit` remain authority.

### TI-03 Template install is idempotent and reread-gated

Given a visible template and an authorized workspace
When user installs it with one idempotency key
Then the UI locks that card until a safe response returns.
When the response is replayed or newly successful
Then it refreshes Workspace Home and authorized Base state
And opens only the receipt `base_id` that appears in the refreshed safe result.
When the same key conflicts or remains in progress
Then it shows fixed local conflict copy, performs no automatic retry and creates no local Base placeholder.

### TI-04 Save current authorized Base as a draft custom template

Given an authorized open Base and management entry
When user submits non-empty name, category and description
Then the existing Base template endpoint creates a server-owned template and returns safe metadata.
Then the UI displays returned name/category/version/status only.
It never allows browser editing of manifest, publisher, status transition, sharing, deletion or versioning.

### TI-05 File selection is bounded before upload but server decides

Given an authorized import entry
When user selects a file
Then client accepts only `.csv` and `.xlsx`, reads only one file in memory and explains server limits.
When extension/type, local read or client size preflight fails
Then no request is sent and local fixed copy is displayed.
When server returns any payload/row/column/cell/header/sheet limit error
Then no preview or commit action becomes available; server detail is not rendered.

### TI-06 CSV and XLSX use the existing payload encoding

Given a UTF-8 CSV
When create-preview is submitted
Then request `content` is decoded text.
Given an XLSX
When create-preview is submitted
Then request `content` is base64 of the file bytes.
In both cases `created_by_user_id` is copied only from bootstrap identity because the legacy request field is required; it is never user-editable or treated as authority.

### TI-07 Preview is persisted but not committed

Given `POST /imports` returns an import job
Then UI shows server `detected_schema`, maximum returned 20 `preview_rows`, safe status and mapping editor.
And it labels the state as preview awaiting explicit commit.
When the dialog closes before commit
Then it clears browser-local file/preview state but does not claim the server job was deleted or resources were created.

### TI-08 Mapping is scalar and explicit

Given a returned inferred schema
When user edits mapping
Then each source key has at most one target key, target keys are non-empty/unique and type is one of `text`, `number`, `date`, `checkbox`.
Relation, lookup, select/status, user, formula and arbitrary options cannot be authored in this surface.
When local mapping is invalid
Then commit is disabled with local fixed feedback.
When the backend rejects mapping or field type
Then draft remains safe and the error contains no raw server detail.

### TI-09 New-Base and in-Base imports preserve scope

Given import starts from Workspace Home
Then request omits `base_id`; commit requires new Base name and creates one imported table.
Given import starts from an authorized Base Canvas
Then request contains exactly that Canvas `base_id`; commit creates a new table in that Base and does not offer a Base picker.
Workspace/Base changes while preview or commit is pending invalidate the old generation; late results cannot open a resource in the new scope.

### TI-10 Commit is explicit, idempotent and authoritative

Given an `awaiting_confirmation` job, valid names/key and mapping
When user presses Commit Import
Then one `POST /imports/{id}/commit` is issued with a distinct commit idempotency key.
When status is `committed`
Then the UI rereads only safe Home/Base/table/view resources before navigation.
When `import_job_invalid_state`, `409`, `401`, `403`, `404`, malformed response or network failure occurs
Then no local table/record is inserted and no blind retry occurs.

### TI-11 Browser state does not leak file or prior workspace data

Given a workspace switch, 401, Base close, dialog close or unmount
When a template/import request is pending or cached
Then exact protected queries are cancelled and removed, local file bytes are dereferenced and prior mapping/preview cannot reappear.
No URL, localStorage, telemetry or query key contains file content, preview values or manifest.

### TI-12 Responsive completeness retains one command path

Given desktop 1440/1280 or mobile 430/390
When an authorized user opens template/import work
Then desktop uses a management workbench and mobile uses labelled full-screen sheets.
Both invoke the same typed existing endpoints and retain loading, empty, denied, validation, conflict, retryable and success-awaiting-reread states.

## 3. State And Error Matrix

| Surface | States | Terminal rule |
| --- | --- | --- |
| template shelf | loading, ready, empty, denied, retryable, scope-invalidated | safe list only; no manifest fallback |
| template card install | idle, pending, replayed, success-awaiting-reread, conflict-locked, denied, validation, retryable, cancelled | only refreshed authorized Base opens |
| save template | idle, locally-invalid, pending, saved, denied, validation, retryable, cancelled | safe metadata receipt only |
| file intake | empty, selected, local-invalid, reading, ready-to-preview, create-pending, preview-ready, denied, validation, retryable, cancelled | preview never means committed |
| mapping | server-default, dirty-valid, dirty-invalid, commit-pending, commit-conflict, commit-invalid-state, committed-awaiting-reread, scope-invalidated | server commit/reread owns result |
| navigation | idle, rereading-home, rereading-base, opened, denied, missing, stale-response-discarded | no receipt-only optimistic navigation |

| HTTP/status class | Fixed UI behavior |
| --- | --- |
| 200 new/replay | parse exact safe schema; progress to reread or preview state |
| 401 | clear all Stage07 protected state and use expired-session boundary |
| 403 | clear active workspace state and use denied boundary |
| 404 | clear exact template/import/Base state; no existence disclosure |
| 409 | lock current action; no automatic retry or duplicate mutation |
| 422 allowlisted import/template code | retain safe editable input where meaningful; fixed local copy only |
| other 4xx/5xx/network/malformed body | generic retryable failure; no raw detail |

## 4. Acceptance Matrix

| ID | Requirement | Minimum evidence | Current status |
| --- | --- | --- | --- |
| TI-A01 | safe template metadata and capability-gated entry | API transport/component tests | specified-awaiting-review |
| TI-A02 | install idempotency and Base reread | API/client lifecycle + PostgreSQL replay | specified-awaiting-review |
| TI-A03 | safe custom template save | API/component tests | specified-awaiting-review |
| TI-A04 | CSV/XLSX intake and bounded safe preview | API/client tests + Browser main path | specified-awaiting-review |
| TI-A05 | scalar mapping and validation/allowlist | unit/component tests | specified-awaiting-review |
| TI-A06 | explicit commit, rollback/replay and navigation reread | PostgreSQL/client lifecycle + Browser main path | specified-awaiting-review |
| TI-A07 | denial/scope cancellation/no content retention | application/transport negative tests | specified-awaiting-review |
| TI-A08 | desktop/mobile reachability | four-width Browser evidence | specified-awaiting-review |

## 5. Prohibited Claims

No acceptance report may call this Package 2, Stage07, Telegram, staging or production complete solely because these documents exist, a preview renders, a response receipt is returned or a local file is parsed.
