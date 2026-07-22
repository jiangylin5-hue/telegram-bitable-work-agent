# Stage07 Acceptance Evidence Matrix

## Status

- Ledger date: 2026-07-16.
- Scope: every original active acceptance ID in the V1, Template/Import, Governance Readback/Write, TD005, TD006, TD009, TD010 and TD011 BDDs.
- Current stage decision: `not accepted`. This is a requirement-ID execution ledger for the acceptance-evidence closure plan; it does not turn any historical aggregate test count, Browser fixture or provider smoke into Stage07 acceptance. The 2026-07-15 implementation/retry/real-local-PostgreSQL supplement is [Final Closure Validation](stage07-final-closure-validation-2026-07-15.md).
- Disposition vocabulary:
  - `evidenced-pending`: a named bounded test/evidence artifact exists, but Task 5 has not independently accepted the BDD row.
  - `blocked`: the BDD's named minimum evidence is missing or only a non-equivalent substitute exists. The explanation is explicit in the row.
  - `contract-gated`: only for an ID whose work itself needs a new approved contract. None of the active rows below is silently reclassified this way.
- External-operation rule: TD007/TD008 historical delivery and identity evidence is not replayed from this ledger. This document authorizes no Telegram send, OpenRouter call, deployment, SSH action or browser control.

## Command and Evidence Catalog

Commands are executed from the indicated package directory. A command label is evidence only when its linked artifact records a result; no row below infers success merely from a broader full-suite run.

| Label | Reproducible command / observation | Retained evidence |
| --- | --- | --- |
| `V1-U` | `backend: python -m pytest -q tests/unit/test_stage07_view_builder_migration.py tests/unit/test_stage07_view_builder_schemas.py tests/unit/test_stage07_view_builder_validation.py tests/unit/test_stage07_view_builder_access.py tests/unit/test_stage07_view_builder_query_execution.py tests/unit/test_stage07_view_builder_api.py` | [V1 verification](stage07-v1-view-builder-verification.md) |
| `V1-PG` | `backend: python -m pytest -q tests/integration/test_stage07_view_builder_postgres.py tests/integration/test_stage07_view_builder_security_postgres.py -m postgres` against an explicitly disposable local PostgreSQL target | [V1 PostgreSQL](stage07-v1-view-builder-postgres.md) |
| `V1-UI` | retained built Mini App observations at 1440/1280/430/390 and local FastAPI/disposable-PostgreSQL observations | [V1 Browser evidence](stage07-v1-view-builder-ui.md) |
| `TI-BE` | `backend: python -m pytest -q tests/unit/test_stage06_template_import.py tests/unit/test_stage06_template_import_api.py tests/unit/test_stage06_import_limits.py tests/unit/test_stage06_template_import_migration.py` | [Template/import evidence](stage07-template-import-ui.md) |
| `TI-FE` | `mini-app: npm.cmd test -- --run src/test/base-template-actions.test.tsx src/test/save-template-panel.test.tsx src/test/template-app-flow.test.tsx src/test/template-import-api.test.ts src/test/template-import-query.test.ts src/test/template-install-flow.test.tsx src/test/import-flow.test.tsx src/test/import-wizard.test.tsx` | [Template/import evidence](stage07-template-import-ui.md) |
| `TI-PG` | retained disposable PostgreSQL template/import integration result; rerun target must be recorded before final acceptance | [Template/import evidence](stage07-template-import-ui.md) |
| `TI-UI` | fresh local FastAPI/disposable-PostgreSQL Codex Browser observation: in-Base dialog and focus return at 1440/1280/430/390; no file chooser path was observed | [Template/import evidence](stage07-template-import-ui.md) |
| `GR-U` | `backend: python -m pytest -q tests/unit/test_stage07_governance_api.py` | [Governance readback evidence](stage07-governance-readback.md) |
| `GR-PG` | `backend: python -m pytest -q tests/integration/test_stage07_governance_postgres.py -m postgres` | [Governance readback evidence](stage07-governance-readback.md) |
| `GR-UI` | built-client Browser member/audit observation, including denial/retry/paging, is not yet retained | [Governance readback evidence](stage07-governance-readback.md) |
| `GW-U` | `backend: python -m pytest -q tests/unit/test_stage07_governance_write_api.py`; focused `mini-app` governance-write API/query/workbench/app-flow tests | [Governance write evidence](stage07-governance-write.md) |
| `GW-PG` | `backend: python -m pytest -q tests/integration/test_stage07_governance_write_postgres.py -m postgres` | [Governance write evidence](stage07-governance-write.md) |
| `GW-UI` | retained built Mini App synthetic fixture at four widths; stale/denied/retry terminal mutation permutations are absent | [Governance write evidence](stage07-governance-write.md) |
| `S5-U` | `backend: python -m pytest -q tests/unit/test_stage07_draft_employee_hub_api.py`; focused `mini-app` draft employee API/hub/query/app-flow tests | [S5 draft evidence](stage07-s5-draft-employee-hub.md) |
| `S5-PG` | `backend: python -m pytest -q tests/integration/test_stage07_draft_employee_hub_postgres.py -m postgres` | [S5 draft evidence](stage07-s5-draft-employee-hub.md) |
| `S5-UI` | a built-client fixture was refused by available Browser surfaces; no observation exists | [S5 draft evidence](stage07-s5-draft-employee-hub.md) |
| `S5-PROVIDER` | `STAGE06_ENV_FILE=<ignored local env>` with `stage06_live_openrouter_smoke.py`, run individually for `summarize_basic`, `hidden_field_guard`, `citations_required`, `draft_update_status` and `unsafe_commit_refusal` | [2026-07-16 real Provider validation](stage07-real-openrouter-provider-validation-2026-07-16.md) |
| `ACD-U` | `backend: python -m pytest -q tests/unit/test_stage07_assistant_context_api.py`; focused `mini-app` assistant-context workbench/app-flow tests | [TD009 BDD reconciliation](../STAGE_07_ASSISTANT_CONTEXT_DISCOVERY_BDD_AND_ACCEPTANCE.md) |
| `ACD-CLOSURE-20260716` | `mini-app: npm.cmd test -- --run src/test/assistant-context-app-flow.test.tsx` | [TD009 client closure evidence](stage07-td009-client-closure-2026-07-16.md) |
| `ACD-PG` | `backend: python -m pytest -q tests/integration/test_stage07_assistant_context_postgres.py::test_assistant_context_postgres_rechecks_employee_table_scope_after_catalog_selection` | [Final Closure Validation](stage07-final-closure-validation-2026-07-15.md) |
| `ACD-UI` | no retained built Mini App visual review for the complete TD009 matrix | [Final audit gap](../STAGE_07_FINAL_AUDIT_REPORT.md) |
| `DEM-U` | `backend: python -m pytest -q tests/unit/test_stage07_digital_employee_management_models.py tests/unit/test_stage07_digital_employee_management_service.py tests/unit/test_stage07_digital_employee_management_api.py tests/unit/test_stage07_digital_employee_assignment_api.py`; focused Mini App management tests | [TD010 BDD reconciliation](../STAGE_07_DIGITAL_EMPLOYEE_MANAGEMENT_BDD_AND_ACCEPTANCE.md) |
| `DEM-PG` | `backend: python -m pytest -q tests/integration/test_stage07_digital_employee_management_postgres.py -m postgres` | [TD010 BDD reconciliation](../STAGE_07_DIGITAL_EMPLOYEE_MANAGEMENT_BDD_AND_ACCEPTANCE.md) |
| `DEM-UI` | current local Codex in-app Browser observation of closed manager/member surfaces, `draft -> active -> paused -> active`, fixed `409` reread and desktop/mobile focus return, against a disposable loopback fixture | [TD010 Browser Lifecycle Evidence](stage07-td010-browser-lifecycle-2026-07-16.md) |
| `TBK-U` | `backend: python -m pytest -q tests/unit/test_stage07_team_bot_knowledge_service.py tests/unit/test_stage07_team_bot_knowledge_api.py`; focused Team Bot Mini App API/query/workbench/app-flow tests | [Team Bot evidence](stage07-s5-team-bot-knowledge.md) |
| `TBK-PG` | `backend: python -m pytest -q tests/integration/test_stage07_team_bot_knowledge_postgres.py -m postgres` | [Team Bot evidence](stage07-s5-team-bot-knowledge.md) |
| `TBK-UI` | retained synthetic built Mini App Team Bot selection/rendering observation; it did not invoke a provider | [R2 Team Bot observation](stage07-r2-governance-draft-employee.md) |
| `TBK-PROVIDER` | `backend: python backend/scripts/stage07_team_bot_live_openrouter_smoke.py` exercises the safe API route with synthetic data only; it is not literal Mini App UI transport | [2026-07-16 real Provider validation](stage07-real-openrouter-provider-validation-2026-07-16.md) |

## Boundary Legend

| Code | Safe-data and authority boundary |
| --- | --- |
| `B1` | Closed safe DTO only; no raw configuration, policy, owner/member identity, hidden field, audit body or provider/runtime detail enters the client. |
| `B2` | Server resolves active identity, workspace/Base/table/view/record intersection and field filtering before returning data or calling a runtime. |
| `B3` | Versioned/idempotent server transaction and redacted audit only; employee writes remain `draft -> confirmation -> record service`, never browser/Bot direct writes. |
| `B4` | Exact protected-query cancellation/removal, fixed error copy and authoritative reread; no raw `error.detail`, stale scope or optimistic success. |
| `B5` | Browser/PostgreSQL proof uses temporary synthetic data on an explicitly disposable local target only; it is not Telegram, staging or production evidence. |
| `B6` | Provider receives only a permission-filtered, fixed bounded view window; raw prompts/responses, real records and Telegram identifiers are not retained. |

## V1 Saved View Builder

Source: [V1 BDD](../STAGE_07_V1_VIEW_BUILDER_BDD_AND_ACCEPTANCE.md).

| Requirement ID | Required evidence from BDD | Command / retained evidence | Boundary | Current disposition |
| --- | --- | --- | --- | --- |
| V1-A01 | private initialization, replay and rollback in unit/API + real PostgreSQL | `V1-U`, `V1-PG` | B1, B3, B5 | evidenced-pending |
| V1-A02 | ACL intersection and denial in service/API + local PostgreSQL, including the denied UI state | `V1-U`, `V1-PG`, `V1-UI` | B1, B2, B4, B5 | blocked — required real denied-screen observation is absent |
| V1-A03 | owner/editor/viewer mutation separation in API and Mini App panel | `V1-U`, `V1-UI` | B1, B2, B4, B5 | evidenced-pending |
| V1-A04 | one existing default Grid invariant in migration/integration | `V1-U`, `V1-PG` | B2, B3, B5 | evidenced-pending |
| V1-A05 | typed configuration validation and safe projection, including invalid Browser payloads | `V1-U`, `V1-PG`, `V1-UI` | B1, B2, B4, B5 | blocked — every required invalid payload is not observed in the real Browser |
| V1-A06 | server filter/sort/group-before-pagination and client lifecycle | `V1-U`, `V1-PG`, `V1-UI` | B1, B2, B5 | evidenced-pending |
| V1-A07 | F2 relation/numeric lookup eligibility, numeric-filter mutation, invalid and stale paths | `V1-U`, `V1-UI` | B1, B2, B4, B5 | blocked — numeric lookup filter and invalid/stale Browser paths are absent |
| V1-A08 | Kanban/Calendar/Form configuration validation including type-invalid states | `V1-U`, `V1-UI` | B1, B2, B4, B5 | blocked — complete type-specific invalid Browser matrix is absent |
| V1-A09 | protected query cancellation, fixed errors and authoritative reread | `V1-U`, `V1-UI` | B1, B4, B5 | evidenced-pending |
| V1-A10 | actual Browser role/type/error matrix at 1440/1280/430/390 | `V1-UI` | B1, B2, B4, B5 | blocked — all widths against real backend, full role and F2/type-invalid matrix are absent |

## Template and Import

Source: [Template/Import BDD](../STAGE_07_TEMPLATE_IMPORT_BDD_AND_ACCEPTANCE.md).

| Requirement ID | Required evidence from BDD | Command / retained evidence | Boundary | Current disposition |
| --- | --- | --- | --- | --- |
| TI-A01 | safe template metadata and capability-gated entry | `TI-BE`, `TI-FE` | B1, B2, B4 | evidenced-pending |
| TI-A02 | install replay/idempotency and authoritative Base reread | `TI-BE`, `TI-FE`, `TI-PG` | B1, B2, B3, B4, B5 | evidenced-pending |
| TI-A03 | safe custom-template save | `TI-BE`, `TI-FE` | B1, B2, B3 | evidenced-pending |
| TI-A04 | CSV/XLSX bounded intake and safe preview, including Browser main file path | `TI-BE`, `TI-FE`, `TI-UI` | B1, B2, B4, B5 | blocked — the Browser could not select a local CSV/XLSX file |
| TI-A05 | scalar mapping validation/allowlist | `TI-BE`, `TI-FE` | B1, B2, B4 | evidenced-pending |
| TI-A06 | explicit commit, rollback/replay, navigation reread and Browser main file path | `TI-FE`, `TI-PG`, `TI-UI` | B1, B2, B3, B4, B5 | blocked — Browser upload/preview/commit was not observed |
| TI-A07 | denial/scope cancellation and no file/content retention | `TI-FE` | B1, B4 | evidenced-pending |
| TI-A08 | reachable management path at 1440/1280/430/390 | `TI-UI` | B1, B4, B5 | evidenced-pending — literal local Browser dialog and focus-return observation now exists at all four widths; file upload remains a separate blocked requirement |

## Governance Readback and Write

Sources: [Readback BDD](../STAGE_07_GOVERNANCE_READBACK_BDD_AND_ACCEPTANCE.md), [Write BDD](../STAGE_07_GOVERNANCE_WRITE_BDD_AND_ACCEPTANCE.md).

| Requirement ID | Required evidence from BDD | Command / retained evidence | Boundary | Current disposition |
| --- | --- | --- | --- | --- |
| GR-A01 | server-authorised paginated safe member read model | `GR-U`, `GR-PG` | B1, B2, B5 | evidenced-pending |
| GR-A02 | server-authorised redacted Base-audit read model | `GR-U`, `GR-PG` | B1, B2, B5 | evidenced-pending |
| GR-A03 | exact protected query cleanup/race containment | `GR-U`; `GR-UI` is absent | B1, B4 | blocked — owning BDD still records partial cleanup/replacement evidence |
| GR-A04 | raw governance/audit data excluded from UI state | `GR-U` | B1, B4 | evidenced-pending |
| GR-A05 | disposable PostgreSQL authorization and cursor path | `GR-PG` | B1, B2, B5 | evidenced-pending |
| GR-A06 | built Browser reachability and console scan | `GR-UI` | B1, B4, B5 | blocked — no retained compliant Browser observation |
| GW-A01 | independently authorised role command and protected-role invariants | `GW-U`, `GW-PG` | B1, B2, B3, B5 | evidenced-pending |
| GW-A02 | membership lock/version/idempotency atomicity | `GW-PG` | B1, B2, B3, B5 | evidenced-pending |
| GW-A03 | fixed, versioned field policy cannot alter field/record data | `GW-U`, `GW-PG` | B1, B2, B3, B5 | evidenced-pending |
| GW-A04 | field read/write intersection remains effective | `GW-U`, `GW-PG` | B1, B2, B5 | evidenced-pending |
| GW-A05 | V1 grant replacement reused; no broader policy route | `GW-U`, `GW-UI` | B1, B2, B3, B5 | evidenced-pending |
| GW-A06 | exact cleanup and explicit canonical reread | `GW-U` | B1, B4 | evidenced-pending |
| GW-A07 | four-width built UI including stale/denied/retry terminal mutation states | `GW-UI` | B1, B3, B4, B5 | blocked — retained success/width observation omits those terminal permutations |
| GW-A08 | redacted audit and temporary cleanup reconciliation | `GW-U`, `GW-PG`, `GW-UI` | B1, B3, B5 | evidenced-pending |

## TD005 Draft Employee Hub and TD006 Context Binding

Sources: [TD005 BDD](../STAGE_07_DRAFT_EMPLOYEE_HUB_BDD_AND_ACCEPTANCE.md), [TD006 BDD](../STAGE_07_S5_CONTEXT_BINDING_BDD_AND_ACCEPTANCE.md).

| Requirement ID | Required evidence from BDD | Command / retained evidence | Boundary | Current disposition |
| --- | --- | --- | --- | --- |
| DE-A01 | safe contacts and cross-workspace omission in API/unit/PostgreSQL | `S5-U`, `S5-PG` | B1, B2, B5 | evidenced-pending |
| DE-A02 | Base/view/record intersection before runtime | `S5-U`, `S5-PG` | B1, B2, B3, B5 | evidenced-pending |
| DE-A03 | fixed intents and safe results with a real provider proof | `S5-U`, `S5-PROVIDER` | B1, B2, B6 | evidenced-pending — shared live runtime has real Provider results; literal Hub Browser proof remains separate |
| DE-A04 | non-mutating draft creation with real runtime or injected LangGraph proof | `S5-U`, `S5-PG`, `S5-PROVIDER` | B1, B2, B3, B6 | evidenced-pending — real runtime produces a pending draft only; no Hub Browser acceptance is implied |
| DE-A05 | field-filtered immutable diff and Browser inspection after revocation | `S5-U`, `S5-PG`; `S5-UI` absent | B1, B2, B3, B5 | blocked — field-filtered Browser detail is not observed |
| DE-A06 | confirm lock/revision/replay/audit reference | `S5-PG` | B1, B2, B3, B5 | evidenced-pending |
| DE-A07 | replay-safe reject with no record write | `S5-U`, `S5-PG` | B1, B2, B3, B5 | evidenced-pending |
| DE-A08 | full protected client failure/cleanup matrix | `S5-U`; `S5-UI` absent | B1, B4 | blocked — only selected delayed `401/403` paths are covered |
| DE-A09 | four-width accessible Hub/draft terminal review | `S5-UI` | B1, B3, B4, B5 | blocked — no compliant Browser observation exists |
| DE-A10 | no S6 capability leak | `S5-U`, source/route inventory in [S5 evidence](stage07-s5-draft-employee-hub.md) | B1, B3 | evidenced-pending |
| CB-A01 | no generic object/client persistence enters Hub | `S5-U` | B1, B4 | evidenced-pending |
| CB-A02 | summary sends only current Canvas Base/view | `S5-U` | B1, B2, B4 | evidenced-pending |
| CB-A03 | draft update needs the open record and a fresh idempotency key | `S5-U`, `S5-PG` | B1, B2, B3 | evidenced-pending |
| CB-A04 | server rejects cross-Base, stale and hidden context | `S5-U`, `S5-PG` | B1, B2, B3, B5 | evidenced-pending |
| CB-A05 | result surface excludes runtime metadata/raw content | `S5-U` | B1, B4, B6 | evidenced-pending |
| CB-A06 | responsive/focus/failure lifecycle | `S5-U`; `S5-UI` absent | B1, B4, B5 | blocked — required Browser width/focus observation is unavailable |

## TD009 Personal Assistant Context Discovery

Source: [TD009 BDD](../STAGE_07_ASSISTANT_CONTEXT_DISCOVERY_BDD_AND_ACCEPTANCE.md).

| Requirement ID | Required evidence from BDD | Command / retained evidence | Boundary | Current disposition |
| --- | --- | --- | --- | --- |
| ACD-A01 | Home starts without default/inferred context | `ACD-U` | B1, B4 | evidenced-pending |
| ACD-A02 | contacts exclude configuration/raw metadata | `ACD-U` | B1, B2 | evidenced-pending |
| ACD-A03 | catalog employee/caller/Base/view intersection plus PostgreSQL authorization | `ACD-U`, `ACD-PG` | B1, B2, B5 | evidenced-pending |
| ACD-A04 | summary re-read uses only fixed existing intent | `ACD-U` | B1, B2, B4 | evidenced-pending |
| ACD-A05 | Home contains no draft-update/record-create fallback | `ACD-U` | B1, B3, B4 | evidenced-pending |
| ACD-A06 | empty/retryable/raw-error suppression error matrix | `ACD-U`, `ACD-CLOSURE-20260716` | B1, B4 | evidenced-pending — dedicated network failure, fixed retry copy and raw-error suppression now exist; empty/malformed variants remain covered by the pre-existing parser/workbench suites and require BDD reconciliation |
| ACD-A07 | `401`/`403`/`404` cleanup fails closed | `ACD-U`, `ACD-CLOSURE-20260716` | B1, B2, B4 | evidenced-pending — selected-view `404` cleanup/redaction is directly covered; authorization-specific backend coverage remains separate |
| ACD-A08 | workspace/contact/view/close replacement discards late result | `ACD-U`, `ACD-CLOSURE-20260716` | B1, B4 | evidenced-pending — deferred old-contact response cannot replace newer selection; other replacement permutations require BDD reconciliation |
| ACD-A09 | no Package4 lifecycle/memory/knowledge/Telegram expansion | `ACD-U`, source inventory in BDD | B1, B3 | evidenced-pending |
| ACD-A10 | production build and reviewed visual flow | production build is historical; `ACD-UI` absent | B1, B4, B5 | blocked — requested visual review is not retained |

## TD010 Digital Employee Management

Source: [TD010 BDD](../STAGE_07_DIGITAL_EMPLOYEE_MANAGEMENT_BDD_AND_ACCEPTANCE.md).

| Requirement ID | Required evidence from BDD | Command / retained evidence | Boundary | Current disposition |
| --- | --- | --- | --- | --- |
| DEM-A01 | safe manager DTO plus closed manager-editor controls | `DEM-U`, `DEM-UI` | B1, B2, B5 | evidenced-pending — current local Browser record confirms the closed editor; independent BDD review remains required |
| DEM-A02 | explicit idempotent draft creation plus closed editor controls | `DEM-U`, `DEM-UI` | B1, B2, B3, B5 | evidenced-pending — one visible draft creation complements automated idempotency evidence; independent BDD review remains required |
| DEM-A03 | authorised Base/table/view scope validation plus closed controls | `DEM-U`, `DEM-UI` | B1, B2, B5 | evidenced-pending — current Base table/view selections are observed; server intersection authority remains covered by automated evidence |
| DEM-A04 | fixed intent validation plus closed controls | `DEM-U`, `DEM-UI` | B1, B2, B3, B5 | evidenced-pending — only the two fixed intent controls render; independent BDD review remains required |
| DEM-A05 | assigned-member eligibility and manager/member UI separation | `DEM-U`, `DEM-PG`, `DEM-UI` | B1, B2, B5 | evidenced-pending — manager/member entry separation is observed; grant authority remains covered by service/PostgreSQL evidence |
| DEM-A06 | legacy workspace migration and member UI separation | `DEM-U`, `DEM-PG`, `DEM-UI` | B1, B2, B3, B5 | evidenced-pending — UI separation supplements legacy migration evidence; no broader member model is implied |
| DEM-A07 | activation row-lock/version/idempotency and responsive activation observation | `DEM-U`, `DEM-PG`, `DEM-UI` | B1, B2, B3, B5 | evidenced-pending — draft/paused activation and active read-only state are observed; transaction authority remains server evidence |
| DEM-A08 | immediate pause semantics and responsive pause observation | `DEM-U`, `DEM-PG`, `DEM-UI` | B1, B2, B3, B5 | evidenced-pending — active-to-paused editable transition is observed; service semantics remain server evidence |
| DEM-A09 | concurrent/stale/replayed command matrix and conflict reread observation | `DEM-U`, `DEM-PG`, `DEM-UI` | B1, B2, B3, B4, B5 | evidenced-pending — fixed `409` reread/retry is observed; concurrent and idempotency matrix remains automated evidence |
| DEM-A10 | exact scoped cleanup plus desktop/mobile focus return | `DEM-U`, `DEM-UI` | B1, B4, B5 | evidenced-pending — desktop and `390 × 844` close-focus return are observed; exact scoped cleanup remains protected-query test evidence |
| DEM-A11 | no prohibited Package4 expansion | source/model/route/migration inventory in TD010 BDD | B1, B3 | evidenced-pending |

## TD011 Team Bot Knowledge Entry

Source: [TD011 BDD](../STAGE_07_TEAM_BOT_KNOWLEDGE_ENTRY_BDD_AND_ACCEPTANCE.md).

| Requirement ID | Required evidence from BDD | Command / retained evidence | Boundary | Current disposition |
| --- | --- | --- | --- | --- |
| TBK-A01 | authorised Team contact projection and active/grant matrix | `TBK-U`, `TBK-PG`, `TBK-UI` | B1, B2, B5 | evidenced-pending |
| TBK-A02 | separate Team/Personal state and protected query subtree | `TBK-U`, `TBK-UI` | B1, B4, B5 | evidenced-pending |
| TBK-A03 | live Base/table/view/field intersection catalog | `TBK-U`, `TBK-PG`, `TBK-UI` | B1, B2, B5 | evidenced-pending |
| TBK-A04 | command-time selected-view reread and unavailable/reselect terminal | `TBK-U`; `TBK-UI` is fixture-only | B1, B2, B4, B5 | blocked — literal UI -> API -> provider run and revoked/paused/reselect terminal are not evidenced together |
| TBK-A05 | closed <=600 input/no browser-supplied runtime data | `TBK-U`; `TBK-UI` is fixture-only | B1, B2, B4, B6 | blocked — required literal UI transport boundary is not observed |
| TBK-A06 | permission-filtered deterministic 100-row knowledge window | `TBK-U`; `TBK-PROVIDER` is API-route-only | B1, B2, B5, B6 | blocked — safe API provider smoke cannot substitute for literal Mini App UI transport |
| TBK-A07 | honest empty/truncation/no-provider and result/retry/handoff observation | `TBK-U`, `TBK-PG`, `TBK-UI` | B1, B2, B4, B5, B6 | blocked — synthetic UI result and separate provider smoke are non-equivalent evidence |
| TBK-A08 | safe/replayable provider result and changed-payload conflict | `TBK-U`, `TBK-PROVIDER` | B1, B2, B3, B4, B6 | blocked — no non-empty literal UI -> provider receipt is recorded |
| TBK-A09 | exact failure/replacement cleanup and desktop/mobile focus return | `TBK-U`; partial `TBK-UI` | B1, B4, B5 | blocked — full delayed failure/replacement and focus matrix is absent |
| TBK-A10 | no direct record write; Base handoff only | `TBK-U`, source inventory in [Team Bot evidence](stage07-s5-team-bot-knowledge.md) | B1, B2, B3 | evidenced-pending |
| TBK-A11 | no knowledge/memory/Telegram expansion | `TBK-U`, source inventory in [Team Bot evidence](stage07-s5-team-bot-knowledge.md) | B1, B3 | evidenced-pending |

## Explicit Unresolved IDs for the Closure Substage

The rows below are `blocked` by missing BDD-specific evidence, not by a newly proposed product feature or a request for production authority.

| Work package | Unresolved IDs | Exact closure needed |
| --- | --- | --- |
| V1 and Template | V1-A02, V1-A05, V1-A07, V1-A08, V1-A10; TI-A04, TI-A06 | Required real local Browser denied/invalid/stale/type/role paths; CSV/XLSX chooser path needs a browser-capable local setup or an explicitly approved equivalent. |
| Governance | GR-A03, GR-A06; GW-A07 | Built Mini App Browser authorized/denied/retry/paging and terminal mutation observations, preserving fixed-copy/redaction. |
| TD005/TD006 | DE-A05, DE-A08, DE-A09; CB-A06 | Real Provider evidence now exists for the shared S5 runtime. Remaining work is real local Browser field-filtered draft/failure/focus/four-width evidence; `DE-A03/A04` remain `evidenced-pending` until independent BDD reconciliation. |
| TD009 | ACD-A10 | Dedicated network/revocation/deferred-replacement client evidence now exists for ACD-A06/A07/A08; the outstanding strict item is the reviewed built-client visual flow. `ACD-A03` has direct local PostgreSQL evidence but remains `evidenced-pending` until independent BDD reconciliation. |
| TD010 | no currently `blocked` DEM row; `DEM-A01` through `DEM-A10` are `evidenced-pending` | Independent Task 5 acceptance/rejection of each owning BDD row; this does not request a new feature or any external operation. |
| TD011 | TBK-A04 through TBK-A09 | One safe non-empty literal Mini App UI -> local API -> existing provider execution plus required reselect/error/focus evidence; keep existing API-route smoke and fixture evidence separate. |

## Next Ledger Rule

Only the task that actually runs a listed command/observation may change its row. A later Task 5 may set an individual row to `accepted` only after direct evidence is linked, independently checked and reconciled back into its owning BDD. A full regression pass, a fixture result, an unrelated provider smoke or a prior aggregate reconciliation never closes a different row.
