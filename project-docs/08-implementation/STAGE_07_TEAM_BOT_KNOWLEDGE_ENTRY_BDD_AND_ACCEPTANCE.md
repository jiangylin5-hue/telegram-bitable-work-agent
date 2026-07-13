# Stage07 Team Bot Knowledge Entry BDD And Acceptance

## Status

- Status: TD011 is partial-local after backend/frontend delivery and proportional evidence reconciliation on 2026-07-14. See evidence/stage07-s5-team-bot-knowledge.md; browser, real provider, Telegram, staging, production and whole-Stage07 acceptance remain open.
- Scope: S5.3 Team Bot entry, one selected saved-view knowledge window and one-shot safe summary only.

## BDD Scenarios

### TBK-A01 Team contact directory is server-authorized

Given an active workspace member opens the Team Bot entry
When the Team Bot contact page is read
Then it contains only active employees in the workspace for which the caller retains `digital_employee.invoke`, member-use eligibility and the fixed `summarize` action
And it contains no policy, scope array, member identity, runtime/provider or Telegram data.

### TBK-A02 Personal and Team entry are separate states

Given a member can use both Personal Assistant and Team Bot
When either entry is opened, closed or changed
Then it uses a distinct labelled workbench and distinct protected-query subtree
And no selected contact, view, instruction or result is copied between the two entries.

### TBK-A03 Knowledge catalog is the live authorization intersection

Given a Team Bot contact is selected
When the knowledge catalog is read
Then it contains only saved views in that employee's one Base, `accessible_views`, selected-table scope and the caller's currently readable views
And every returned view has a safe supported type and no table/field/configuration payload.

### TBK-A04 Selection is reread immediately before use

Given a caller selected a catalog view
When they submit a Team Bot summary
Then the server rereads employee lifecycle/member eligibility/Base/view membership and current view authorization
And a revoked, paused, deleted, cross-Base or out-of-scope view is an indistinguishable unavailable/reselect result.

### TBK-A05 Summary input is closed and bounded

Given an eligible Team Bot contact and selected view
When the caller submits a summary request
Then the request contains only `base_id`, `view_id` and an optional <=600-character instruction plus an idempotency key
And browser-supplied rows, fields, query rules, tools, model, runtime mode, provider options, records and draft values are rejected without a provider call.

### TBK-A06 Knowledge window is deterministic and permission-filtered

Given the summary request passed authorization
When the server assembles knowledge
Then it uses the selected saved view's stored order/filter and at most the first 100 rows currently permitted to the caller
And hidden fields, inaccessible records and values outside that view never reach the runtime, browser or audit payload.

### TBK-A07 Empty and truncated knowledge are honest

Given the selected view has no permitted rows
When a summary is requested
Then the response is a fixed empty-context result, no provider is called and a redacted audit event records the outcome
And when the 100-row limit truncates permitted data, the response exposes only a boolean truncation marker.

### TBK-A08 Provider result is safe and replayable

Given the server invokes the existing configured summary runtime
When it succeeds or the same idempotency key is replayed with the identical request
Then the caller receives the same safe answer, opaque visible-record citations, truncation marker and audit reference
And a changed-payload reuse conflicts without a second provider invocation or raw error.

### TBK-A09 Failures clear only the correct protected state

Given catalog, selection or summary requests are pending
When session, workspace, contact or selected view changes, or the server returns `401`, `403`, `404`, `409`, `422`, malformed response, network or `5xx`
Then the client applies the documented scoped cleanup and fixed retry/reselect copy
And late responses cannot restore a previous workspace/contact/view/result.

### TBK-A10 Draft writing remains the existing controlled path

Given a Team Bot summary identifies a record change
When the caller wants to draft an update
Then they explicitly open the authorized Base and use existing TD006 Canvas-record-only `draft_update`
And S5.3 creates no record picker, direct record write or Home `draft_update` command.

### TBK-A11 No knowledge/memory/Telegram expansion

Given the S5.3 source inventory is inspected
When models, migrations, routes, runtime inputs, UI and client persistence are reviewed
Then no knowledge-source table, vector query, file/URL ingestion, memory/thread store, chat history, Telegram route or external send exists.

## State Matrix

| Surface | Allowed state | Required behavior | Forbidden behavior |
| --- | --- | --- | --- |
| Home entry | loading / no contact / contact page / denied | fixed loading, empty and denied states | inferred employee or cached old contact |
| selected contact | active/eligible / revoked/paused/ineligible | catalog or generic unavailable result | assignment-state disclosure |
| catalog | loading / empty / safe views / selected view lost | safe view list, reselect on loss | generic view/table/record API fallback |
| summary | ready / running / empty context / answer / retry | one current request, fixed result/error copy | persisted chat or optimistic answer |
| Base handoff | explicit user action | existing authorized Base open only | record preselection or direct draft/write |

## Acceptance Matrix

| ID | Automated evidence required | Manual/local evidence | Does not accept |
| --- | --- | --- | --- |
| TBK-A01--A03 | route/DTO negative tests; active/grant/Base/view/field intersection matrix | Team/Personal visual distinction | generic runtime projection |
| TBK-A04--A06 | post-selection revocation, cross-Base, hidden-field, request-extra and fixed-window tests | safe loading/empty/reselect states | client query construction or raw data |
| TBK-A07--A08 | empty/no-provider, truncation, idempotency replay/conflict, citation/audit redaction tests | result/retry/handoff observation | provider success claim without configured smoke |
| TBK-A09 | deferred replacement, exact cleanup and malformed/error parser tests | desktop/mobile focus return | persistent cache evidence |
| TBK-A10--A11 | route/model/migration/dependency/source inventory | product-boundary review | memory, retrieval or Telegram expansion |

## Local Evidence Reconciliation

| BDD IDs | Local status | Evidence | Remaining gate |
| --- | --- | --- | --- |
| TBK-A01 | implemented-local | contact route/DTO tests and disposable PostgreSQL contact projection | lifecycle/grant-change observation |
| TBK-A02 | partial-local | separate Home entry/workbench and team-bot protected-query subtree tests | user-controlled desktop/mobile visual review |
| TBK-A03 | implemented-local | current Base/table/view/saved-view intersection service and safe context routes | revoke/grant PostgreSQL matrix |
| TBK-A04--A05 | partial-local | command-time selected-view reread, closed request models and <=600 bound | paused/revoked/cross-Base command matrix |
| TBK-A06--A07 | implemented-local | captured 101/100 window, citation guard, empty/no-provider audit and truncation tests | configured-provider/UI observation |
| TBK-A08--A09 | partial-local | same-key replay, safe receipt/parser, scoped cleanup and request generations | changed-key conflict and delayed-error replacement matrix |
| TBK-A10--A11 | implemented-local | source inventory confirms no direct write, RAG/memory/files/Telegram/model/migration expansion | later product-boundary review |

Focused backend result: 23 passed; disposable local PostgreSQL result: 1 passed; full Mini App: 60 files / 221 tests; production build passed. These are local-only results.

## Explicitly Deferred

- durable knowledge source management, file/URL ingestion, embeddings/vector retrieval and cross-Base discovery;
- personal/team memory, chat history and retention/deletion controls;
- real OpenRouter and Telegram smoke, staging/production and Stage07 final acceptance.
