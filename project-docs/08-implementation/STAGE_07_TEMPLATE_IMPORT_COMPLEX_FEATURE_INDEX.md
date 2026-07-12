# Stage07 Template And Import Complex Feature Index

## Status

- Document status: implementation/risk index awaiting review
- Scope: high-risk behavior of the selected existing-contract template/import package
- Status convention: all TI-I items are `specified-awaiting-review`; none is implemented by this document

## 1. Index

| ID | Complex behavior | Primary source | Required proof | Current status |
| --- | --- | --- | --- | --- |
| TI-I01 | safe template projection and shelf ordering | BDD TI-01; SDD §2/4 | transport response scan + component render | specified-awaiting-review |
| TI-I02 | installation idempotency/replay and authoritative Base navigation | BDD TI-03; SDD §7 | API/client lifecycle + PostgreSQL replay | specified-awaiting-review |
| TI-I03 | Base-to-draft-template save without manifest disclosure | BDD TI-04; SDD §2/8 | API/component negative render tests | specified-awaiting-review |
| TI-I04 | CSV/XLSX encoding, file-memory lifecycle and server limits | BDD TI-05/06; SDD §5 | unit/API limit and client cleanup tests | specified-awaiting-review |
| TI-I05 | persisted preview/not-committed state | BDD TI-07; SDD §6 | API/application state tests | specified-awaiting-review |
| TI-I06 | scalar mapping validation and no complex field authoring | BDD TI-08; SDD §4/6/8 | component/API negative tests | specified-awaiting-review |
| TI-I07 | new-Base/in-Base target scope and commit transaction | BDD TI-09/10; SDD §2/6 | PostgreSQL rollback/replay + lifecycle tests | specified-awaiting-review |
| TI-I08 | protected query cancellation, no file/raw data retention | BDD TI-11; SDD §7 | application/transport tests | specified-awaiting-review |
| TI-I09 | responsive modal/sheet, focus and safe error feedback | BDD TI-12; Work Surface §5 | Browser 1440/1280/430/390 | specified-awaiting-review |

## 2. Implementation Dependencies

```text
TI-I01 typed transport
  -> TI-I02 shelf/install lifecycle
  -> TI-I03 current-Base save panel

TI-I04 file intake
  -> TI-I05 preview
  -> TI-I06 mapping
  -> TI-I07 commit/reread

TI-I08 protected cleanup applies to every mutation/read
TI-I09 validates the rendered combination after TI-I01..TI-I08
```

## 3. Risk Register And Fixed Decisions

| Risk | Required design defense | Forbidden shortcut |
| --- | --- | --- |
| File may contain private business data | memory-only `File`/base64, no query key/storage/log/error body | localStorage, URL payload, telemetry payload, raw console dump |
| Existing legacy request carries creator ID | copy bootstrap user ID into required field; server ignores it for authority and resolves request identity | editable actor input or client role claim |
| Preview response is persistent but uncommitted | explicit `awaiting_confirmation` state and separate commit key | preview-success navigation or local resource creation |
| Server accepts broad field types but UI lacks safe option config | scalar whitelist only | emit relation/lookup/select/user/formula mappings |
| Workspace changes during parsing/commit | generation guard + exact protected-query removal | leave old preview visible or open stale receipt Base |
| Resource map contains broader implementation metadata | validate only navigation IDs and discard other keys | render/retain generic map JSON |
| No import-job list/recovery contract | close clears local preview and UI states this honestly | invent a history route or fake cancellation |
| Mobile density hides mapping errors | labelled full-screen sheet and sticky commit action | desktop-only or hover-only errors |

## 4. Test Routing

| Test layer | Required TI IDs | Evidence expectation |
| --- | --- | --- |
| backend existing regression | TI-I02, I04, I05, I07 | focused Stage06 template/import API, limits, idempotency and PostgreSQL tests remain green |
| frontend unit/component | TI-I01, I03, I04, I05, I06 | safe decoders, file adapter, local mapping/error states |
| frontend application | TI-I02, I07, I08 | reread/navigation/cancellation/scope replacement |
| local PostgreSQL | TI-I02, I07 | explicit disposable target; replay/rollback/commit result |
| Browser | TI-I01, I02, I04, I07, I09 | real client main path and four-width reachability; cleanup recorded |

## 5. Schema And Index Gate

The existing `templates`, `template_installations` and `import_jobs` migration/data model is consumed as-is. This package may not add an index, migration, retention task, storage reference, queue status or template access policy. If measured import job listing/recovery needs an index or any new read contract, create a separate decision document with PostgreSQL plan, privacy analysis, migration/rollback and explicit user approval.
