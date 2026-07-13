# Stage07 S5.3 Team Bot Knowledge Entry — Local Evidence

## Scope

This note records only local implementation evidence for TD011/S5.3. It does not claim browser-controlled visual QA, a real OpenRouter call, Telegram behavior, staging, production, or whole-Stage07 acceptance.

## Implemented Local Surface

- Four closed Team Bot routes: safe contacts, permitted knowledge contexts, selected-view reread, and idempotent summaries.
- Existing active employee, member eligibility, digital_employee.invoke, Base/table/view scope and current saved-view authorization are re-evaluated server-side.
- The selected view is read with a 101 record probe; at most the first 100 field-filtered records are passed through a server-only runtime override. Record 101 becomes only the truncation boolean.
- Empty context creates a redacted audit receipt without provider execution. Successful summary receipts retain answer, opaque citation IDs, truncation and audit ID for identical idempotency replay.
- Home contains a separate Team Bot entry/workbench, strict DTO parser, separate team-bot protected-query subtree, exact selected-view reread, explicit Base handoff and no record picker/direct write/chat history.
- No migration, table, index, RBAC action, provider configuration, vector/RAG/file/memory/Telegram surface or browser persistence was added.

## Automated Evidence

| Check | Actual result |
| --- | --- |
| Focused backend unit regression | python -m pytest -q tests/unit/test_stage07_team_bot_knowledge_service.py tests/unit/test_stage07_team_bot_knowledge_api.py tests/unit/test_stage07_draft_employee_hub_api.py tests/unit/test_stage07_assistant_context_api.py → 23 passed |
| Disposable local PostgreSQL | python -m pytest -q tests/integration/test_stage07_team_bot_knowledge_postgres.py -m postgres → 1 passed |
| Full Mini App suite | npm.cmd test -- --run → 60 files / 221 tests passed |
| Production build | npm.cmd run build → passed |
| Diff whitespace | git diff --check → passed before documentation reconciliation |

The local PostgreSQL test uses the existing disposable Stage06 database fixture. It proves empty-context summary replay and one redacted Team Bot audit/idempotency record through real PostgreSQL; it is not staging or production evidence.

## Acceptance Reconciliation

| BDD IDs | Status | Direct evidence | Still open |
| --- | --- | --- | --- |
| TBK-A01 | implemented-local | safe active/eligible/summary-capable contact route, strict DTO/API tests, PostgreSQL contact projection | lifecycle/grant-change observation in a separate real session |
| TBK-A02 | partial-local | separate Home entry, component and team-bot query-key tests | user-controlled desktop/mobile visual review |
| TBK-A03 | implemented-local | dedicated context resolver filters Base/table/view/current access and supported types | grant/view-revocation PostgreSQL matrix |
| TBK-A04--A05 | partial-local | selected-view reread, strict extra-forbid request, <=600 client/server boundary and Home flow | dedicated revoked/paused/cross-Base command tests |
| TBK-A06 | implemented-local | captured live runtime input has 100 records; 101st record is excluded; citation guard covers the window | provider configured smoke |
| TBK-A07 | implemented-local | empty no-provider audit path, truncation signal and local PostgreSQL empty replay | user-controlled UI observation |
| TBK-A08 | partial-local | identical-key summary receipt replay and citation/audit safe projection | changed-payload conflict and configured-provider error evidence |
| TBK-A09 | partial-local | separate cleanup functions, request-generation guards and parser/component/app-flow coverage | delayed 401/403/404/409/422 replacement matrix and visual focus return |
| TBK-A10--A11 | implemented-local | source inventory, workbench/API tests, no model/migration/dependency additions | later product-boundary review |

## Open Risks And Cleanup

- Manual browser testing is intentionally not performed because the user prohibited browser control.
- Runtime provider failures are mapped through the existing safe API error path; real OpenRouter invocation and a failure-audit observation are not claimed by this local evidence.
- No temporary files, seed data or artifacts were added by S5.3. The local PostgreSQL fixture resets its disposable schema.
