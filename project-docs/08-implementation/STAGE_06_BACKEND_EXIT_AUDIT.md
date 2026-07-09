# Stage 06 Backend Exit Audit

## Status

- Document status: active backend-readiness exit audit
- Scope: Stage06 backend-only exit evidence for the generic Telegram-first multidimensional table and table-bound digital employee platform
- Current Progress: 2026-07-10 Package 6 security hardening passed. Replaceable identity, active membership, tenant/resource isolation, lookup/audit redaction, notification fail-closed, import limits, pagination, idempotency, additive database guards and real local PostgreSQL negative/concurrency evidence are complete. Stage06 backend-readiness is passed; launch/UI/remote deployment remain out of this audit boundary.

## 1. Audit Boundary

This audit verifies the current Stage06 backend-readiness pass against:

1. `AGENTS.md`
2. `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`
3. `project-docs/08-implementation/STAGE_06_SOURCE_OF_TRUTH.md`
4. `project-docs/08-implementation/STAGE_06_IMPLEMENTATION_PLAN.md`
5. `project-docs/08-implementation/STAGE_06_SDD.md`
6. `project-docs/08-implementation/STAGE_06_API_DATA_SECURITY_CONTRACT.md`
7. `project-docs/08-implementation/STAGE_06_BDD_AND_ACCEPTANCE.md`

It does not claim production launch readiness.

## 2. Backend Exit Matrix

| ID | Requirement | Evidence | Status |
| --- | --- | --- | --- |
| S6-01 | Active docs are platform-first and Telegram-ecosystem-first | `AGENTS.md`, `IMPLEMENTATION_SOURCE_OF_TRUTH.md`, Stage06 source docs rewritten | Passed |
| S6-02 | UI implementation is deferred | No frontend/Mini App implementation added; docs keep UI as separate confirmation gate | Passed |
| S6-03 | Generic workspace/base/table/field/record/view model works | `test_stage06_platform_core.py`, `test_stage06_platform_api.py`; full backend regression | Passed |
| S6-04 | JSONB record values validate through field metadata | Stage06 platform service tests cover type allowlist and value validation | Passed |
| S6-05 | CSV import preview and commit works | `test_stage06_template_import.py`, `test_stage06_template_import_api.py` | Passed |
| S6-06 | Excel import preview and commit works | `test_stage06_template_import.py`, `test_stage06_template_import_api.py` | Passed |
| S6-07 | Official generic templates install ordinary resources | Template service/API tests; advertising sample is ordered last | Passed |
| S6-08 | Advertising sample is not the default product path | Docs and template ordering | Passed |
| S6-09 | Digital employee creation works | Digital employee service/API tests | Passed |
| S6-10 | Telegram `@` invocation resolves context | Local API tests plus real Telegram `@ops` smoke | Passed |
| S6-11 | Effective permission intersection is enforced | Active membership authorization, resource resolvers, field/view permission, hidden lookup omission and Telegram-member scope tests | Passed |
| S6-12 | Deterministic digital employee summaries are permission-filtered | `test_stage06_digital_employee_runtime.py` | Passed |
| S6-13 | Live LangGraph/OpenRouter digital employee runtime works | Unit tests with injected client plus real OpenRouter summarize and draft-update smokes | Passed |
| S6-14 | Digital employee writes create drafts | Deterministic, injected live and real OpenRouter draft-update evidence | Passed |
| S6-15 | Draft confirmation commits records and audit | Service/API tests confirm draft with permission/version re-check | Passed |
| S6-16 | Controlled notifications obey safety switches | Server-controlled mode/allowlist tests and pilot API safety-close evidence | Passed |
| S6-17 | Local PostgreSQL migration smoke passes | `stage06_smoke` disposable local PostgreSQL database upgraded to Alembic head `20260710_0020` | Passed |
| S6-18 | Telegram backend entry smoke passes when configured | Real `@ops` Telegram update resolved to `summarize`; webhook restored; pending update cleared | Passed |
| S6-19 | Safety close is verified | Dry-run/allowlist notification tests; `PROVIDER_MODE=disabled`; no uncontrolled sends | Passed |
| S6-20 | LarkSuite-style skill evidence is produced | 27 manifests represented, 11 active core skills, response/AgentRun evidence and real 5-case smoke | Passed |
| S6-21 | Active-core skill routing meets deterministic gates | 118 cases; top-1 89.23%, top-3 100%, zero high-risk/unauthorized false routes | Passed |
| S6-22 | API identity and active membership are enforced | Identity and authorization unit/API tests | Passed |
| S6-23 | Tenant/resource combinations are isolated | Unit/API tests plus real PostgreSQL outsider denial | Passed |
| S6-24 | Lookup and audit do not leak hidden/raw values | Lookup permission, audit sanitization and real PostgreSQL evidence | Passed |
| S6-25 | Import limits and cursor pagination pass | Import-limit and pagination tests | Passed |
| S6-26 | Idempotency and PostgreSQL concurrency pass | Replay/conflict tests, migration guards and concurrent one-winner integration test | Passed |
| S6-27 | Sanitized hardening evidence is retained | `evidence/STAGE_06_SECURITY_HARDENING_EVIDENCE.json` | Passed |

## 3. Real LLM Evidence

### 3.1 Real OpenRouter Summarize Smoke

Command:

```powershell
$env:STAGE06_ENV_FILE='D:\telegram多维表格和工作智能体的开发\.local\stage05-real-workflow.env'; python scripts\stage06_live_openrouter_smoke.py
```

Result:

- `status = passed`
- `model_provider = openrouter`
- `model_name = openrouter/auto`
- `prompt_version = stage06-live-digital-employee-v1`
- `total_tokens = 1017`
- `record_count = 1`
- `draft_count = 0`
- `raw_prompt_persisted = false`
- `raw_response_persisted = false`

LLM output preview:

```text
There is one open task from the product-team chat: Follow up on the Telegram launch checklist.
```

### 3.2 Real OpenRouter Draft-Update Smoke

Command:

```powershell
$env:STAGE06_ENV_FILE='D:\telegram多维表格和工作智能体的开发\.local\stage05-real-workflow.env'; $env:STAGE06_OPENROUTER_SMOKE_ACTION='draft_update'; python scripts\stage06_live_openrouter_smoke.py
```

Result:

- `status = passed`
- `action = draft_update`
- `model_provider = openrouter`
- `model_name = openrouter/auto`
- `prompt_version = stage06-live-digital-employee-v1`
- `total_tokens = 596`
- `record_count = 1`
- `draft_count = 1`
- `draft_status = pending_confirmation`
- `draft_proposed_values = {"status": "in_progress"}`
- `record_values_unchanged_before_confirmation = true`
- `raw_prompt_persisted = false`
- `raw_response_persisted = false`

LLM output preview:

```text
Draft update prepared for the visible Telegram task to change its status from open to in_progress.
```

Acceptance interpretation:

- Real LLM output is not treated as committed business state.
- The generated write-like result becomes a `record_change_draft`.
- The original record remains unchanged until confirmation.
- Raw prompt/response persistence remains disabled.

## 4. Real Telegram Evidence

Command:

```powershell
$env:STAGE06_ENV_FILE='D:\telegram多维表格和工作智能体的开发\.local\stage05-real-workflow.env'; $env:STAGE06_TELEGRAM_AUTO_DISCOVER='true'; $env:STAGE06_TELEGRAM_TEMPORARY_POLLING='true'; $env:STAGE06_TELEGRAM_DROP_PENDING_UPDATES='false'; $env:STAGE06_TELEGRAM_POLL_TIMEOUT_SECONDS='15'; python scripts\stage06_telegram_entry_smoke.py
```

Result:

- `status = passed`
- `action = summarize`
- `record_count = 1`
- `send_mode = dry_run`
- `provider_mode = disabled`
- `temporary_polling.webhook_restore_status = restored`
- Post-smoke webhook readback showed `pending_update_count = 0`

The temporary polling path is explicit and reversible. It is not a production webhook ingress claim.

## 5. Migration Evidence

Local PostgreSQL migration smoke used a disposable local database:

```text
postgresql+psycopg://ads_agent:***@127.0.0.1:5432/stage06_smoke?connect_timeout=3
```

Result:

- `status = passed`
- `alembic_version = 20260710_0020`
- Required Stage06 tables present

This is real local PostgreSQL evidence, not remote staging or production evidence.

## 6. Verification Commands

Latest verification:

```powershell
python -m pytest tests\unit\test_stage06_backend_smoke_scripts.py -q
```

Result:

```text
18 passed
```

```powershell
python -m pytest tests\unit\test_stage06_live_digital_employee_runtime.py tests\unit\test_stage06_backend_smoke_scripts.py tests\unit\test_stage06_digital_employee_runtime.py tests\unit\test_stage06_digital_employee_api.py tests\unit\test_stage06_runtime_api_contract.py tests\unit\test_stage06_pilot_acceptance_api.py -q
```

```text
28 passed
```

```powershell
python -m pytest tests -q
```

```text
401 passed, 17 skipped
```

Skipped tests require `STAGE02_ONLINE_DATABASE_URL` and belong to old online PostgreSQL smoke coverage.

## 7. What This Backend Exit Implements

Package 6 changed-file groups:

- Identity/authorization: `backend/app/services/stage06_identity.py`, `stage06_authorization.py`, `backend/app/api/deps.py` and Stage06 route modules.
- Tenant/audit/notification: Stage06 platform, template and digital-employee services plus runtime schemas/config.
- Operational guards: `stage06_pagination.py`, `stage06_idempotency.py`, `stage06_hardening.py` and migration `20260710_0020`.
- Verification: focused Stage06 unit/API tests, `test_stage06_postgres_security.py`, `stage06_security_hardening_smoke.py` and the sanitized evidence artifact.

Skipped tests and cleanup:

- The 17 skipped tests are historical Stage02 online tests requiring `STAGE02_ONLINE_DATABASE_URL`; the new Stage06 PostgreSQL tests ran and passed.
- The smoke uses the explicitly disposable local `stage06_smoke` database and resets its schema before migration/testing.
- No temporary source/test file is retained. The sanitized JSON is intentionally retained as audit evidence.

- Generic workspace/base/table/field/record/view backend.
- JSONB record storage with typed field validation.
- Linked-record and lookup metadata/read behavior.
- CSV/Excel import preview and commit.
- Official generic templates plus advertising sample as a weak optional template.
- Table-bound digital employee configuration.
- Deterministic and live OpenRouter runtime modes.
- Real LLM summarize and draft-update smoke.
- Draft-first write behavior with confirmation gate.
- Telegram `@` mention backend entry smoke.
- Controlled notification safety close.
- Audit evidence for material actions, denials, drafts, confirmations and notification blocks.

## 8. What This Backend Exit Does Not Implement

- Mini App frontend.
- Desktop-browser frontend.
- Production webhook-to-backend deployment path.
- Remote staging/production PostgreSQL smoke.
- Feishu/Lark API integration or API compatibility.
- Full formula engine.
- Full attachment storage/preview.
- Full workflow builder.
- Full dashboard builder.
- Digital clone/persona runtime.
- Real provider writes, funds movement or irreversible external operations.
- Broad uncontrolled Telegram sends.

## 9. Remaining Risks

| Risk | Status | Recommendation |
| --- | --- | --- |
| Workspace/base/table RBAC administration is not complete | Active | Harden in UI/permission phase before production launch |
| Production Telegram ingress is not proven | Active | Add deployment-specific webhook smoke after topology is finalized |
| Remote staging PostgreSQL smoke is absent | Active | Add when a disposable staging database is provided |
| Mini App is deferred | Accepted | Start only after separate user confirmation |
| Full Feishu-like formula/workflow/dashboard breadth is deferred | Accepted | Keep as Stage07+ candidates |
| Stage06 LarkSuite-style skill breadth is partial | Active | Keep the implemented 27-manifest/11-active-core evidence distinct from executable backend tool coverage |
| Real LLM prompt coverage is still narrow | Improved | Real post-skill OpenRouter multi-case smoke passed with 5 cases; broader prompt-evaluation corpus remains a later hardening task |
| Production verified identity adapter is not connected | Active | Select and implement an external identity provider in a separately confirmed deployment phase |
| Stale `in_progress` idempotency recovery is not automated | Active | Add expiry/recovery runbook and monitoring before production traffic |

## 10. Exit Decision

Stage06 backend-readiness is passed. Package 6 identity, authorization, tenant isolation, audit redaction, notification fail-closed, import limit, pagination, idempotency, database constraint and real local PostgreSQL security/concurrency gates all have current evidence.

It should not be treated as full Stage06 launch-like completion until the user confirms and completes the separate Mini App/frontend phase and production-style deployment evidence.

For the current unresolved tasks, risks, LarkSuite skills status and recommended LLM multi-case smoke, see [Stage 06 Remaining Risks And Next Cases](STAGE_06_REMAINING_RISKS_AND_NEXT_CASES.md).
