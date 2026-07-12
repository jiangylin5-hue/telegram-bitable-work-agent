# Stage07 Template And Import UI Design

## Status

- Document status: user-selected Package 2 design, awaiting written-spec review
- Scope: existing Stage06 template list/install, Base-to-template save, CSV/XLSX create-preview-commit import
- Decision: option A — complete existing contract surface in one coherent desktop-first package
- Non-goal: no schema, backend endpoint, permission, upload-storage, asynchronous queue, template publication or external file-provider change

## 1. Product Outcome

Builders can start a workspace from an existing official/custom template, save an accessible Base as a draft custom template, or turn one CSV/XLSX file into a durable Base/table after a server-created preview and explicit commit. The durable outcome is always an existing `TemplateInstallation`, `PlatformTemplate`, `ImportJob`, Base/table/field/record set and audit event; a browser-local parsed file is never treated as completion.

Desktop is the primary management surface. Mobile keeps complete entry, preview and commit capability in a full-screen sheet, but does not add a separate mobile-only contract.

## 2. Selected Architecture

The implementation reuses the mature project baseline already used by P3/F1/F2/V1:

```text
React + TypeScript panel
-> existing typed api.ts transport
-> existing FastAPI Stage06 template/import routes
-> existing SQLAlchemy/PostgreSQL idempotency, authorization, transaction and audit
-> authoritative Workspace Home/Base Canvas reread
```

No new dependency is introduced. Native browser `File`/`FileReader`/`ArrayBuffer` APIs produce request content: UTF-8 text for CSV and base64 ASCII for XLSX. TanStack Query remains memory-only and is keyed by authenticated user/workspace/resource; file bytes, raw rows and preview state are not persisted to browser storage.

## 3. Explicit Boundary Decisions

| Topic | Selected rule | Reason |
| --- | --- | --- |
| Template discovery | `GET /templates` returns only safe list metadata: name/category/description/version/status. | The existing endpoint never exposes manifests to the Mini App. |
| Template install | Available where existing `can_manage_schema` hint is true; FastAPI `template.install` remains final authority. | No new capability field or client role reconstruction. |
| Save as template | Available only from an already authorized open Base and the same capability hint; endpoint stores a server-owned draft template. | The UI cannot enumerate or reveal inaccessible Bases. |
| Workspace import target | Workspace entry imports into a **new Base** (`base_id` omitted). | No safe full Base picker contract is added. |
| In-Base import target | An authorized open Base can open `Import into this Base`; its existing `base_id` is submitted and commit creates one new table in that Base. | Reuses the open safe resource instead of probing for Bases. |
| File types | CSV and `.xlsx` only. Client extension/MIME/size checks are advisory; server parsing and limits decide. | Existing server supports only CSV/XLSX. |
| Mapping | Browser permits only server-inferred scalar `text`, `number`, `date`, `checkbox`; unique source/target keys are required locally. | Existing import has no safe options contract for relation/select/user/formula configuration. |
| Commit | Preview creates persistent `ImportJob(status=awaiting_confirmation)`; explicit commit creates resources atomically. | Browser never treats preview or upload as durable success. |
| Replay/conflict | Each mutation receives a fresh action-scoped idempotency key; same action retry reuses it only while request state remains pending/retryable. | Reuses existing idempotency records and prevents accidental duplicate Base/table creation. |

## 4. User Flows

### 4.1 Template shelf and installation

`Workspace Home -> Templates & Imports -> Template shelf -> Install -> authoritative Home reread -> open installed Base`.

The shelf groups only by returned `category`, preserves server order and labels official/custom/draft using `status`, not a guessed manifest. Install has `idle`, `pending`, `replayed`, `success-awaiting-reread`, `denied`, `validation`, `conflict-locked`, `network-retryable` and `scope-invalidated` states. A successful receipt is insufficient by itself: the client clears exact Home/Base list state and opens the returned `base_id` only after the refreshed authorized list contains it.

### 4.2 Save current Base as template

`Authorized Base Canvas -> More Base actions -> Save as template -> name/category/description -> POST -> safe template receipt`.

The panel never shows the manifest, record payload or audit body. `draft` means the server saved a custom reusable template; it does not mean it is publicly published. No edit, publish, delete, visibility, version or template-member UI is in this package.

### 4.3 Import create-preview-commit

`Workspace Home -> Import new Base` or `Base Canvas -> Import into this Base`:

1. User selects one CSV/XLSX file.
2. Client checks extension, decodes once in memory and submits `POST /workspaces/{workspace_id}/imports` with an idempotency key.
3. Server persists the bounded parsed rows and returns only `id`, inferred schema, first 20 preview rows, empty mapping and `awaiting_confirmation`.
4. User supplies Base/table names and edits only the scalar mapping.
5. User explicitly commits `POST /imports/{id}/commit` with a second idempotency key.
6. The client refreshes the safe workspace/Base state. For a new Base it opens the committed `base_id`; for an existing Base it rereads that Base and selects the returned table only if it is present in the authorized result.

Closing before commit does not cancel or delete the server `ImportJob`; no delete/cancel contract exists. The UI explains that the preview can be reopened only when a future approved import-job list/read-entry contract exists; this package does not invent one.

## 5. Safety, Error and Data Rules

- Never render, cache, log or put in query keys raw file bytes, full rows, template manifests, `resource_map` internals beyond navigation IDs, actor role claims, audit body or server exception text.
- Map only known error codes to fixed Chinese copy. Unknown `4xx/5xx`, malformed payload and decode failures use generic local copy.
- Existing authoritative limits are CSV 5 MiB decoded, XLSX 10 MiB decoded, 10,000 rows, 200 columns, 64 KiB cell text and 20 preview rows. The UI displays them as server rules, not independently enforced policy.
- `401` clears all protected state; `403` removes the active workspace and returns to the generic denied boundary; `404` removes only the exact template/import/Base state; delayed responses after close/workspace/Base replacement are discarded by request generation and cancelled queries.
- A `409` never retries automatically. Existing idempotency conflict/in-progress locks the relevant panel and asks the user to close/reload; commit-invalid-state retains the safe draft inputs but cannot claim an import occurred.

## 6. Out of Scope

No drag-and-drop provider upload, resumable upload, ZIP/ODS/Google Sheet, multiple worksheets selection, row-by-row repair, import overwrite/upsert, append to an existing table, async polling, import deletion/cancellation, template manifest editor, template publication, sharing, delete/versioning, public marketplace, Telegram upload/deep link, Bot-mediated import or new storage backend is authorized.

## 7. Acceptance Shape

The implementation must add typed transport redaction, panel/unit/application tests, focused backend regression use, local disposable PostgreSQL commit/replay/rollback evidence, and a small Browser main-path check at desktop plus mobile sheet reachability. It must update the BDD, SDD, work-surface, complex-index, progress and traceability documents with actual—not aspirational—results. This design itself makes no implementation-complete claim.
