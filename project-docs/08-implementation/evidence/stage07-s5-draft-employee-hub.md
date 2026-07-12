# Stage07 S5 Draft and Digital Employee Hub Local Evidence

## Status

- Status: `partial-local`; this is an implementation/evidence checkpoint, not S5 or Stage07 acceptance.
- Scope: approved TD005 safe contact/draft adapter and approved TD006 Option A current-Canvas invocation bridge.
- Environment: disposable local PostgreSQL for backend tests; built Mini App for client verification; no production, staging, Telegram identity, real provider credential or external-send operation.

## Implemented Functionality

| Surface | Implemented behavior | Safety boundary retained |
| --- | --- | --- |
| safe contacts and draft review | Home loads only safe contacts; queue opens only safe draft detail; confirm/reject reread the authoritative safe detail | generic runtime and draft DTOs do not enter browser state |
| terminal draft transition | versioned/idempotent confirm or reject locks the draft, writes a sanitized audit receipt and uses record service only for confirm | reject does not write the record; terminal commands remain server-authorized |
| safe summary result | server filters citations against the current authorized view, deduplicates IDs and emits only `{record_id}`; client parses only `{recordId}` | no record arrays, fields, trace, model/provider/runtime metadata or raw server error is rendered |
| TD006 Option A bridge | Base Canvas toolbar opens the Hub; App root supplies only transient `{baseId, viewId, recordId?}`; Hub selects an existing safe contact | no Base/view/record picker, generic context request, URL/localStorage persistence or browser authorization claim |
| fixed invocation controls | `summarize` requires current Base/view; `draft_update` remains disabled without an open record and submits a fresh idempotency key when enabled | intent cannot be arbitrary; a result draft pointer is reread through the existing safe draft route |
| stale/failure boundary | Canvas identity is checked before and after invocation; replaced context discards stale result; `401`/`403` retain existing protected-state cleanup | no automatic re-submit or inferred local success |
| pending draft queue | the safe Base queue returns pending drafts only, newest-first, through a bounded keyset cursor | terminal drafts are read only through their explicit safe detail pointer; no general queue/filter/search is added |

## Fresh Automated Evidence

| Command | Result | What it proves |
| --- | --- | --- |
| `pytest tests/unit/test_stage07_draft_employee_hub_api.py tests/integration/test_stage07_draft_employee_hub_postgres.py -q` | `16 passed` | safe citation projection/cross-Base denial, pending-only newest-first keyset queue, confirm replay, reject no-record-write, concurrent terminal lock/loser-ledger rollback, and fresh revoked-field reread that suppresses the diff/value and disables confirmation |
| `npm.cmd test -- --run src/test/draft-employee-api.test.ts src/test/draft-employee-hub.test.tsx src/test/draft-employee-query.test.ts src/test/draft-employee-app-flow.test.tsx` | `4 files / 18 tests` | strict transport, current-Canvas summary body, disabled no-record draft control, fresh draft idempotency key, stale Canvas-result discard, safe queue/terminal reread flows, and delayed terminal `401/403` isolation across a workspace replacement |
| `npm.cmd run build` | completed | TypeScript compile and production Vite bundle include the current-Canvas Hub bridge |
| disposable local PostgreSQL `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` | `512` pending + `1,536` terminal drafts; `Limit -> Sort -> Bitmap Heap Scan -> ix_stage06_drafts_base_status`; `0.913 ms`, `0` shared reads | I-A is sufficient at this documented fixture: the optional S5 partial index is not created; this is not a production performance claim |

## Built UI Attempt and Cleanup

1. A temporary, synthetic local fixture was created only to serve the built client and its allowlisted safe responses. It contained no real user data, credentials, PostgreSQL connection, provider key or production URL.
2. The built Mini App was served at loopback `127.0.0.1:4179`. The in-app browser and the available Chrome browser each refused that loopback connection. This is recorded as a Browser environment limitation, not a successful UI observation.
3. The temporary fixture source was deleted and its background process stopped. Port `4179` was confirmed closed.

Therefore this document does **not** claim Browser interaction, screenshot inspection, console cleanliness, responsive `1440/1280/430/390` acceptance, real provider execution, Telegram handoff, staging, production, S5 completion or Stage07 completion.

## Remaining Acceptance Work

- Browser-capable environment: observe the approved summary, draft creation, confirm/reject, denied/stale path and four target widths with synthetic data.
- Real LangGraph/OpenRouter evidence when a configured non-production credential is available.
- Complete DE-A01--DE-A10 and CB-A01--CB-A06 reconciliation; Telegram/S6 and all Stage07 exit gates remain separate.
