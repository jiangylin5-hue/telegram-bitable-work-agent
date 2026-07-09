# Stage 06 Progress

## Status

- Document status: active Stage06 progress log
- Scope: Stage06 platform pivot progress, evidence and open risks
- Current Progress: 2026-07-10 Package 6 security hardening is complete. Backend verification passed with `401 passed, 17 skipped`; the 17 skips are historical Stage02 online tests requiring `STAGE02_ONLINE_DATABASE_URL`. Real local PostgreSQL migration, tenant denial, audit redaction and concurrent idempotency tests passed at head `20260710_0020`. Sanitized evidence is retained and backend-readiness is restored; Mini App and production deployment remain separate gates.

## Progress Log

### 2026-07-10: Package 6 Security Hardening Completed

Completed:

- Added replaceable Stage06 request identity; local/test may use the development header, while staging/production require a verified adapter.
- Centralized active workspace-member authorization and resource-to-workspace resolution across platform, template/import and runtime routes.
- Enforced cross-workspace/base/table/view/record scope, Telegram-member binding, empty employee scope denial and lookup target-field permission.
- Sanitized stored and returned audit state and restricted audit readback to owner/admin.
- Made notification safety server-controlled and fail-closed.
- Added CSV/Excel decoded-size, row, column and cell limits plus cursor pagination bounded to 200.
- Added required `Idempotency-Key` handling for template install, import create/commit, notification create and draft confirmation.
- Added migration `20260710_0020` with idempotency storage, FKs, positive-version checks, partial uniqueness and lookup indexes.
- Added real PostgreSQL tenant-denial, audit-leak and concurrent import one-winner tests.

Verification:

- `pytest tests -q` with disposable local Stage06 PostgreSQL: `401 passed, 17 skipped`.
- `python -m compileall -q app scripts`: passed.
- `python -m alembic heads`: `20260710_0020 (head)`.
- `python scripts/stage06_security_hardening_smoke.py`: passed all 4 checks; Stage06 unit count `128`, PostgreSQL security count `2`.
- `git diff --check`: passed; Windows line-ending warnings only.

Retained evidence:

- `project-docs/08-implementation/evidence/STAGE_06_SECURITY_HARDENING_EVIDENCE.json`.

Boundary:

- No external Auth provider, Mini App, real notification send or remote staging deployment was added.
- A production verified-identity adapter and stale `in_progress` idempotency recovery policy remain production-readiness work.

### 2026-07-10: Package 6 Security Hardening Design Approved

- User approved Option A: backend identity abstraction without choosing an external Auth provider.
- Stage06 backend exit was reopened because the existing permission/security contract is not fully implemented.
- Added the Stage06 security-hardening design and updated source, SDD, API/security contract, BDD, implementation plan and exit audit before code changes.
- Mini App UI, real sends and external Auth provider selection remain out of scope.
- Next gate: written-spec review, detailed TDD implementation plan, then red-green implementation.

### 2026-07-10: Skill Matching Hit-Rate Benchmark And Guardrail Hardening

Completed:

- Added a 118-case generic work-scenario corpus covering 11 active core skills, negative prompts, ambiguous prompts, high-risk bypass attempts, permission attacks, missing context and inactive skills.
- Added a repeatable local evaluator with explicit routing and safety gates.
- Hardened deterministic matching so generic `actor_user_id`/`workspace_id` context does not masquerade as domain intent.
- Added token-boundary matching so `view` no longer falsely matches `preview` or `review`.
- Preserved approval and shared-policy guardrails when prompts request `skip approval`, `ignore scope`, hidden fields or raw SQL.
- Blocked permission-denied data routes before any table-analysis skill is selected.

Verified benchmark result:

- `case_count=118`.
- `top1_accuracy=0.8923` against gate `>=0.85`.
- `top3_recall=1.0` against gate `>=0.95`.
- `high_risk_false_commit_routes=0`.
- `hidden_or_unauthorized_false_positive=0`.
- `missing_context_clarification_rate=1.0`.
- `evidence_presence_rate=1.0`.

Verification:

- `pytest tests/unit/test_stage06_skill_hit_rate_benchmark.py tests/unit/test_stage06_skill_matching.py tests/unit/test_stage06_skill_registry.py -q`: `15 passed`.
- `python scripts/stage06_skill_hit_rate_eval.py`: `ok=true`, `case_count=118`, no hard failures.
- `pytest -q`: `339 passed, 17 skipped`; skips are historical online PostgreSQL tests requiring `STAGE02_ONLINE_DATABASE_URL`.
- `git diff --check`: no whitespace errors; Windows line-ending warnings only.

Boundary:

- This is deterministic matcher evidence, not an LLM rerank benchmark.
- The existing real OpenRouter evidence remains a separate 5-case smoke.
- All 27 manifests are represented, but only the 11-skill generic core is active and manifest coverage does not imply full executable backend tools.

### 2026-07-10: LarkSuite Skills Runtime Connection

Completed:

- Added a project-native Stage06 static skill manifest registry covering all 27 official `larksuite/cli` skills.
- Activated only the generic Stage06 core subset:
  - `platform-shared-policy`
  - `platform-base`
  - `platform-telegram-im`
  - `platform-event`
  - `platform-contact`
  - `platform-file-import`
  - `platform-task`
  - `platform-approval`
  - `platform-tabular-analysis`
  - `platform-skill-maker`
  - `platform-tool-discovery`
- Added deterministic skill matching and `skill_evidence`.
- Added `skill_evidence` to deterministic and live digital employee responses.
- Added `skill_evidence` to AgentRun `output_summary`.
- Added selected skill context to live OpenRouter prompts without exposing hidden fields.
- Extended the OpenRouter smoke script so explicit multi-case runs can report `skill_evidence` and `selected_skill_ids`.

Verification:

- `pytest tests/unit/test_stage06_skill_registry.py tests/unit/test_stage06_skill_matching.py -q`: `8 passed`.
- `pytest tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage06_live_digital_employee_runtime.py -q`: `7 passed`.
- `pytest tests/unit/test_stage06_digital_employee_api.py tests/unit/test_stage06_pilot_acceptance_api.py -q`: `2 passed`.
- `python -m py_compile scripts/stage06_live_openrouter_smoke.py; pytest tests/unit/test_stage06_backend_smoke_scripts.py -q`: `19 passed`.
- `pytest tests/unit/test_stage06_skill_registry.py tests/unit/test_stage06_skill_matching.py tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage06_live_digital_employee_runtime.py tests/unit/test_stage06_digital_employee_api.py tests/unit/test_stage06_pilot_acceptance_api.py tests/unit/test_stage06_backend_smoke_scripts.py -q`: `36 passed`.
- `pytest tests/unit -k stage06 -q`: `59 passed, 173 deselected`.
- `pytest -q`: `330 passed, 17 skipped`; skipped tests require `STAGE02_ONLINE_DATABASE_URL` for historical online PostgreSQL smoke tests.
- Real OpenRouter multi-case smoke after skills connection:
  - Command: `STAGE06_OPENROUTER_SMOKE_CASES=summarize_basic,draft_update_status,hidden_field_guard,unsafe_commit_refusal,citations_required python scripts/stage06_live_openrouter_smoke.py`
  - Env: `STAGE06_ENV_FILE=.local/stage05-real-workflow.env`
  - Result: `ok=true`, `status=passed`, `case_count=5`, `draft_count=2`, `record_values_unchanged_before_confirmation=true`, `raw_prompt_persisted=false`, `raw_response_persisted=false`.

Not done:

- No Feishu/Lark API integration.
- No Feishu API compatibility.
- No copied official `SKILL.md` runtime files.
- No dynamic skill marketplace.
- No full executable backend implementation for all 27 skills.
- No full executable backend implementation for planned/future/reference skills.

### 2026-07-10: LarkSuite Skills Integration Design Draft

Completed:

- Retrieved and analyzed the 27 official `larksuite/cli` skills from <https://github.com/larksuite/cli/tree/main/skills>.
- Added [Stage 06 LarkSuite Skills Integration Design](STAGE_06_LARKSUITE_SKILLS_INTEGRATION_DESIGN.md).
- Added [Stage 06 LarkSuite Skills Runtime Implementation Plan](STAGE_06_LARKSUITE_SKILLS_RUNTIME_IMPLEMENTATION_PLAN.md) after user confirmed the design direction.
- Linked the design from [Stage 06 Source Of Truth](STAGE_06_SOURCE_OF_TRUTH.md) and the Stage06 implementation index.
- Reframed the skills plan away from Stage05 advertising-operation adapters and toward generic work scenarios.
- Added an explicit review and approval checklist so runtime connection does not begin without user approval.

Boundary at the time the design draft was created (later superseded by the runtime connection entry above):

- This is a documentation proposal only.
- It does not connect a Stage06 runtime skill registry.
- It does not run new OpenRouter multi-case smoke.
- It does not introduce Feishu/Lark API integration or API compatibility.

### 2026-07-09: Backend-First Replan After UI Deferral

User instruction:

- UI is not implemented in the current pass.
- Backend should be connected first.
- After backend readiness is complete, UI work should wait for separate user confirmation.

Updated direction:

- Stage06 remains a generic Telegram-first multidimensional table and table-bound digital employee platform.
- Pilot framing is Telegram ecosystem productivity, not advertising-agency operations.
- Local PostgreSQL is acceptable for current migration smoke if it is real PostgreSQL.
- Real LangGraph/OpenRouter invocation is required for backend readiness when credentials are configured.
- Deterministic backend tool gateway remains a test/fallback mode only.

Changed documentation:

- `AGENTS.md`
- `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`
- `project-docs/00-governance/TECHNICAL_DECISIONS.md`
- `project-docs/08-implementation/STAGE_06_SOURCE_OF_TRUTH.md`
- `project-docs/08-implementation/STAGE_06_IMPLEMENTATION_PLAN.md`
- `project-docs/08-implementation/STAGE_06_SDD.md`
- `project-docs/08-implementation/STAGE_06_API_DATA_SECURITY_CONTRACT.md`
- `project-docs/08-implementation/STAGE_06_BDD_AND_ACCEPTANCE.md`

Current remaining backend work:

- Implement live LangGraph/OpenRouter Stage06 runtime.
- Add local PostgreSQL migration smoke evidence.
- Add Telegram backend entry smoke evidence.
- Run focused and full backend verification.
- Update this progress document with final backend-readiness results.

What remains deferred:

- No Mini App frontend project.
- No UI smoke.
- No screenshots.
- No shadcn/Tailwind implementation until the user confirms the separate UI phase.

### 2026-07-09: Backend Readiness Live LLM And Smoke Evidence

Implemented:

- Added Stage06 live digital employee LangGraph runtime:
  - permission-filtered context preparation;
  - OpenRouter-compatible structured JSON call;
  - strict `answer`/`citations` validation;
  - draft proposal validation for `draft_update`;
  - AgentRun evidence with `model_provider`, `model_name`, usage summary and redaction policy.
- Extended digital employee invocation with explicit `runtime_mode = deterministic | live_openrouter`.
- Preserved deterministic gateway as test/fallback mode.
- Added Stage06 smoke scripts:
  - `scripts/stage06_live_openrouter_smoke.py`;
  - `scripts/stage06_local_postgres_migration_smoke.py`;
  - `scripts/stage06_telegram_entry_smoke.py`;
  - `scripts/stage06_env.py`.
- Added local env loading from `STAGE06_ENV_FILE` or `backend/.env`, with secret key names redacted from smoke output.
- Added local PostgreSQL smoke support for:
  - disposable local database;
  - fallback disposable schema when database creation is unavailable.

Changed backend files:

- `backend/.env.example`
- `backend/app/agents/stage06_live_digital_employee.py`
- `backend/app/api/routes/stage06_runtime.py`
- `backend/app/schemas/stage06_runtime.py`
- `backend/app/services/stage06_digital_employees.py`
- `backend/scripts/stage06_env.py`
- `backend/scripts/stage06_live_openrouter_smoke.py`
- `backend/scripts/stage06_local_postgres_migration_smoke.py`
- `backend/scripts/stage06_telegram_entry_smoke.py`
- `backend/tests/unit/test_stage06_backend_smoke_scripts.py`
- `backend/tests/unit/test_stage06_live_digital_employee_runtime.py`

Verification:

- RED live runtime test:
  - `python -m pytest tests/unit/test_stage06_live_digital_employee_runtime.py -q`
  - Result before implementation: failed because `invoke_digital_employee()` did not accept `runtime_mode`.
- GREEN live runtime tests:
  - `python -m pytest tests/unit/test_stage06_live_digital_employee_runtime.py tests/unit/test_stage06_backend_smoke_scripts.py -q`
  - Result: `7 passed`.
- Stage06 runtime/API neighbor tests:
  - `python -m pytest tests/unit/test_stage06_live_digital_employee_runtime.py tests/unit/test_stage06_backend_smoke_scripts.py tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage06_digital_employee_api.py tests/unit/test_stage06_runtime_api_contract.py tests/unit/test_stage06_pilot_acceptance_api.py -q`
  - Initial result: `13 passed`.
  - Latest result after formalizing temporary Telegram polling: `25 passed`.
  - Latest result after adding real draft-update smoke controls: `28 passed`.
- Local PostgreSQL disposable database smoke:
  - Created `stage06_smoke` database with local `postgres/postgres`, owned by `ads_agent`.
  - Ran `python scripts\stage06_local_postgres_migration_smoke.py` with `STAGE06_LOCAL_DATABASE_URL=postgresql+psycopg://ads_agent:***@127.0.0.1:5432/stage06_smoke?connect_timeout=3`.
  - Result: `status = passed`, `alembic_version = 20260709_0019`, required Stage06 tables present.
- Real OpenRouter smoke:
  - Ran `python scripts\stage06_live_openrouter_smoke.py` with `STAGE06_ENV_FILE=D:\telegram多维表格和工作智能体的开发\.local\stage05-real-workflow.env`.
  - First result: failed because the model returned JSON without `answer`.
  - Fix: injected explicit `response_schema` and output template into the live prompt.
  - Final result: `status = passed`, `model_provider = openrouter`, `model_name = openrouter/auto`, `prompt_version = stage06-live-digital-employee-v1`, `record_count = 1`, `draft_count = 0`, raw prompt/response persistence disabled.
  - Added explicit `STAGE06_OPENROUTER_SMOKE_ACTION=draft_update` support to the smoke script.
  - Ran real draft-update smoke with the same `.local` env file.
  - Result: `status = passed`, `action = draft_update`, `model_provider = openrouter`, `model_name = openrouter/auto`, `record_count = 1`, `draft_count = 1`, `draft_status = pending_confirmation`, `draft_proposed_values = {"status": "in_progress"}`, `record_values_unchanged_before_confirmation = true`, raw prompt/response persistence disabled.
- Telegram backend entry smoke:
  - Ran `python scripts\stage06_telegram_entry_smoke.py` with the same `.local` env file.
  - Result: `status = blocked`.
  - Reason: env file has non-empty `TELEGRAM_BOT_TOKEN`, but `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` is empty and `STAGE06_TELEGRAM_TEST_CHAT_ID` / `STAGE06_TELEGRAM_TEST_USER_ID` are missing.
  - After the user sent an `@ops` message to `BitableWorkAgentBot`, ran the smoke with `STAGE06_TELEGRAM_AUTO_DISCOVER=true`.
  - Result: `status = blocked`.
  - Reason: Telegram returned `409 Conflict`, indicating the bot likely has an active webhook or another polling consumer. Do not call `deleteWebhook` or change polling/webhook state without explicit user confirmation.
  - After explicit user confirmation, read the current webhook state, temporarily called `deleteWebhook` for a polling smoke, and restored the original webhook with its host, `max_connections` and `allowed_updates`.
  - Formalized this path in `scripts/stage06_telegram_entry_smoke.py` behind explicit `STAGE06_TELEGRAM_TEMPORARY_POLLING=true`.
  - Ran `python scripts\stage06_telegram_entry_smoke.py` with `STAGE06_TELEGRAM_AUTO_DISCOVER=true`, `STAGE06_TELEGRAM_TEMPORARY_POLLING=true`, `STAGE06_TELEGRAM_DROP_PENDING_UPDATES=false`, and `STAGE06_TELEGRAM_POLL_TIMEOUT_SECONDS=15`.
  - Result: `status = passed`, `action = summarize`, `record_count = 1`, `send_mode = dry_run`, `provider_mode = disabled`, `temporary_polling.webhook_restore_status = restored`.
  - Post-smoke webhook readback: original webhook is present and `pending_update_count = 0`.
- Full backend regression:
  - `python -m pytest tests -q`
  - Initial result: `310 passed, 17 skipped`.
  - Latest result after formalizing temporary Telegram polling: `318 passed, 17 skipped`.
  - Latest result after adding real draft-update smoke controls: `321 passed, 17 skipped`.
  - Skipped tests require `STAGE02_ONLINE_DATABASE_URL` for old online PostgreSQL smoke coverage.

What this implements:

- Stage06 backend can now run deterministic and live LLM digital employee flows.
- Live LLM calls use permission-filtered records and do not persist raw prompt/response.
- Local PostgreSQL migration smoke is proven against a real disposable local database.
- Smoke scripts provide concrete blocked states instead of pretending success when credentials/config are missing, and Telegram temporary polling is explicit, reversible and audited in smoke output.

What remains:

- Production-style Telegram webhook-to-backend entry can be added after deployment topology is finalized; current Stage06 backend entry smoke is proven through a controlled temporary polling window.
- Mini App UI remains deferred until separate user confirmation.

### 2026-07-09: API Contract Cleanup After Package 5 Backend Evidence

Implemented:

- Added `GET /workspaces/{workspace_id}/members`, matching the Stage06 API contract.
- Added API-level Excel import coverage for `POST /workspaces/{workspace_id}/imports` with `source_type = excel`.

Changed backend files:

- `backend/app/services/stage06_platform.py`
- `backend/app/schemas/stage06_platform.py`
- `backend/app/api/routes/stage06_platform.py`
- `backend/tests/unit/test_stage06_platform_api.py`
- `backend/tests/unit/test_stage06_template_import_api.py`

What this implements:

- Workspace member readback for the owner membership created during workspace creation.
- API evidence that Excel import preview and commit work through the HTTP contract, not only the service layer.

What this does not implement:

- Workspace member invitation or role update.
- Full workspace RBAC administration UI.
- Mini App frontend.
- Production-like deployment evidence.

Verification:

- RED run before implementation:
  - `python -m pytest tests/unit/test_stage06_platform_api.py tests/unit/test_stage06_template_import_api.py -q`
  - Result: failed because `GET /workspaces/{workspace_id}/members` returned 404.
- GREEN targeted run:
  - `python -m pytest tests/unit/test_stage06_platform_api.py tests/unit/test_stage06_template_import_api.py -q`
  - Result: `5 passed`.
- Neighbor regression:
  - `python -m pytest tests/unit/test_initial_migration.py tests/unit/test_model_metadata.py tests/unit/test_bitable_views.py tests/unit/test_permissions.py tests/unit/test_stage06_platform_migration.py tests/unit/test_stage06_platform_core.py tests/unit/test_stage06_platform_api.py tests/unit/test_stage06_template_import_migration.py tests/unit/test_stage06_template_import.py tests/unit/test_stage06_template_import_api.py tests/unit/test_stage06_digital_employee_migration.py tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage06_digital_employee_api.py tests/unit/test_stage06_runtime_api_contract.py tests/unit/test_stage06_pilot_acceptance_api.py -q`
  - Result: `57 passed`.
- Full backend regression:
  - `python -m pytest tests -q`
  - Result: `301 passed, 17 skipped`.
  - Skipped tests require `STAGE02_ONLINE_DATABASE_URL` for online PostgreSQL smoke coverage.
- Diff hygiene:
  - `git diff --check`
  - Result: passed with no whitespace errors. Git emitted Windows LF-to-CRLF working-copy warnings only.

### 2026-07-09: Package 5 Backend/API Pilot Evidence

Implemented:

- Added API-level backend pilot acceptance coverage for:
  - workspace creation;
  - CSV import preview and commit;
  - grid view creation;
  - digital employee creation;
  - Telegram binding and `@` mention;
  - permission-filtered summarize;
  - digital employee draft update;
  - user confirmation committing the record update;
  - controlled notification request with dry-run/allowlist blocking;
  - notification request readback;
  - base audit event readback.
- Added `POST /bases/{base_id}/views` to expose the existing Stage06 view creation service for pilot flows.
- Added `GET /bases/{base_id}/audit-events` to read Stage06 audit evidence for a base.
- Added `PATCH /digital-employees/{employee_id}` from the Package 4 API contract.
- Added `POST /notification-requests/{request_id}/confirm` from the Package 4/5 notification contract.

Changed backend files:

- `backend/app/api/routes/stage06_platform.py`
- `backend/app/api/routes/stage06_runtime.py`
- `backend/app/schemas/stage06_platform.py`
- `backend/app/schemas/stage06_runtime.py`
- `backend/app/services/stage06_platform.py`
- `backend/app/services/stage06_digital_employees.py`
- `backend/tests/unit/test_stage06_pilot_acceptance_api.py`
- `backend/tests/unit/test_stage06_runtime_api_contract.py`

What this implements:

- Local backend/API evidence for the Package 5 pilot path.
- Audit readback for Stage06 base-related events.
- Safety close evidence through blocked notification requests when `dry_run` is enabled or allowlist does not include the target.
- API contract closure for digital employee updates and notification confirmation.

What this did not implement at that subphase, superseded by the later 2026-07-10 backend-readiness evidence where noted:

- Mini App frontend smoke evidence.
- Real Telegram entry surface. Superseded for backend smoke by the later real `@ops` Telegram entry evidence; production webhook ingress remains future work.
- Real or production-like deployment evidence.
- Live LLM execution was not yet covered in this historical subphase. Superseded by later real summarize and draft-update OpenRouter smoke evidence.
- Real Telegram sends.
- Online Alembic smoke against a remote PostgreSQL database. Local PostgreSQL Alembic smoke was later completed against a disposable `stage06_smoke` database.

Verification:

- RED run before implementation:
  - `python -m pytest tests/unit/test_stage06_pilot_acceptance_api.py -q`
  - Result: failed because `POST /bases/{base_id}/views` was not implemented.
- RED run for remaining API contract:
  - `python -m pytest tests/unit/test_stage06_runtime_api_contract.py -q`
  - Result: failed because `PATCH /digital-employees/{employee_id}` returned 405.
- GREEN Package 5/API runs:
  - `python -m pytest tests/unit/test_stage06_pilot_acceptance_api.py -q`
  - Result: `1 passed`.
  - `python -m pytest tests/unit/test_stage06_runtime_api_contract.py -q`
  - Result: `1 passed`.
- Stage06 API key path:
  - `python -m pytest tests/unit/test_stage06_pilot_acceptance_api.py tests/unit/test_stage06_runtime_api_contract.py tests/unit/test_stage06_digital_employee_migration.py tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage06_digital_employee_api.py tests/unit/test_stage06_platform_api.py tests/unit/test_stage06_template_import_api.py -q`
  - Result: `13 passed`.
- Neighbor regression:
  - `python -m pytest tests/unit/test_initial_migration.py tests/unit/test_model_metadata.py tests/unit/test_bitable_views.py tests/unit/test_permissions.py tests/unit/test_stage06_platform_migration.py tests/unit/test_stage06_platform_core.py tests/unit/test_stage06_platform_api.py tests/unit/test_stage06_template_import_migration.py tests/unit/test_stage06_template_import.py tests/unit/test_stage06_template_import_api.py tests/unit/test_stage06_digital_employee_migration.py tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage06_digital_employee_api.py tests/unit/test_stage06_runtime_api_contract.py tests/unit/test_stage06_pilot_acceptance_api.py -q`
  - Result: `55 passed`.
- Full backend regression:
  - `python -m pytest tests -q`
  - Result: `299 passed, 17 skipped`.
  - Skipped tests require `STAGE02_ONLINE_DATABASE_URL` for online PostgreSQL smoke coverage.
- Diff hygiene:
  - `git diff --check`
  - Result: passed with no whitespace errors. Git emitted Windows LF-to-CRLF working-copy warnings only.

Current Stage06 status:

- Local backend/API coverage now proves the full non-UI pilot path from workspace/import through digital employee, draft confirmation, audit readback and safety close.
- Full Stage06 exit remains incomplete until Mini App frontend and production-like deployment/pilot evidence are available.

### 2026-07-09: Package 4 Backend Digital Employee Runtime

Implemented:

- Added Stage06 Package 4 backend migration after `20260709_0018`:
  - `digital_employees`
  - `record_change_drafts`
  - `notification_requests`
- Added SQLAlchemy models for digital employees, record-change drafts and controlled notification requests.
- Added digital employee creation from base/table/view context.
- Added deterministic schema-aware tool gateway actions:
  - `schema_inspect`
  - `query`
  - `summarize`
  - `draft_update`
  - `status_advance` as draft-style update path
- Added permission-filtered digital employee view reads through the Package 2 view record service.
- Added AgentRun linkage for digital employee invocations using a local deterministic tool gateway, not a live LLM call.
- Added record-change draft creation for write-like digital employee actions.
- Added draft confirmation and rejection.
- Added confirmation-time record version and field write permission re-check through `update_record`.
- Added Telegram binding and `@` mention resolver for bound workspace/base/default employee context.
- Added effective view scope intersection between employee configured scope and Telegram chat scope.
- Added controlled notification request creation with dry-run/allowlist blocking.
- Added Package 4 backend API routes:
  - `POST /bases/{base_id}/digital-employees`
  - `GET /digital-employees/{employee_id}`
  - `POST /digital-employees/{employee_id}/invoke`
  - `GET /bases/{base_id}/record-change-drafts`
  - `POST /record-change-drafts/{draft_id}/confirm`
  - `POST /record-change-drafts/{draft_id}/reject`
  - `POST /workspaces/{workspace_id}/telegram-bindings`
  - `POST /telegram/mentions`
  - `POST /notification-requests`
  - `GET /bases/{base_id}/notification-requests`

Changed backend files:

- `backend/alembic/versions/20260709_0019_stage06_digital_employee_runtime.py`
- `backend/app/models/stage06_runtime.py`
- `backend/app/models/__init__.py`
- `backend/app/services/stage06_platform.py`
- `backend/app/services/stage06_digital_employees.py`
- `backend/app/schemas/stage06_runtime.py`
- `backend/app/api/routes/stage06_runtime.py`
- `backend/app/main.py`
- `backend/tests/unit/test_stage06_digital_employee_migration.py`
- `backend/tests/unit/test_stage06_digital_employee_runtime.py`
- `backend/tests/unit/test_stage06_digital_employee_api.py`

What this implements:

- The Package 4 backend runtime contract for table-bound digital employees.
- Digital employee reads are permission-filtered and do not leak hidden fields.
- Write-like digital employee actions create drafts rather than directly mutating records.
- User confirmation commits the record update and writes audit evidence.
- Telegram `@` mention resolves a bound workspace/base/default digital employee context.
- Notification requests remain controlled and can be blocked by dry-run/allowlist policy.

What this does not implement:

- Telegram Mini App frontend screens.
- A selected frontend stack or build setup.
- Live LangGraph/OpenRouter LLM execution; current runtime is a deterministic backend tool gateway for pilot safety and testability.
- Real Telegram sends.
- Production deployment/pilot evidence.
- Online Alembic smoke against a real PostgreSQL database, because no disposable `STAGE02_ONLINE_DATABASE_URL` was provided.

Verification:

- RED run before implementation:
  - `python -m pytest tests/unit/test_stage06_digital_employee_migration.py tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage06_digital_employee_api.py -q`
  - Result: failed during collection because `app.services.stage06_digital_employees` and `app.api.routes.stage06_runtime` did not exist.
- GREEN targeted run after implementation:
  - `python -m pytest tests/unit/test_stage06_digital_employee_migration.py tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage06_digital_employee_api.py -q`
  - Result: `8 passed`.
- Neighbor regression:
  - `python -m pytest tests/unit/test_initial_migration.py tests/unit/test_model_metadata.py tests/unit/test_bitable_views.py tests/unit/test_permissions.py tests/unit/test_stage06_platform_migration.py tests/unit/test_stage06_platform_core.py tests/unit/test_stage06_platform_api.py tests/unit/test_stage06_template_import_migration.py tests/unit/test_stage06_template_import.py tests/unit/test_stage06_template_import_api.py tests/unit/test_stage06_digital_employee_migration.py tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage06_digital_employee_api.py -q`
  - Result: `53 passed`.
- Full backend regression:
  - `python -m pytest tests -q`
  - Result: `297 passed, 17 skipped`.
  - Skipped tests require `STAGE02_ONLINE_DATABASE_URL` for online PostgreSQL smoke coverage.
- Diff hygiene:
  - `git diff --check`
  - Result: passed with no whitespace errors. Git emitted Windows LF-to-CRLF working-copy warnings only.

Current Stage06 status:

- Package 1, Package 2, Package 3 and Package 4 backend runtime are implemented and locally full-backend-tested.
- Mini App frontend remains pending because the repository has no existing frontend base and the frontend technology choice has not been confirmed in source documents.
- Historical note: at this point Package 5 still needed pilot acceptance evidence. This is superseded for backend readiness by the later Package 5 backend/API evidence, real OpenRouter smokes, local PostgreSQL smoke, real Telegram smoke and backend exit audit. Mini App/frontend and production-like deployment evidence remain future gates.

### 2026-07-09: Package 3 Template And Import System

Implemented:

- Added Stage06 Package 3 migration after `20260709_0017`:
  - `templates`
  - `template_installations`
  - `import_jobs`
- Added SQLAlchemy models for templates, template installations and import jobs.
- Added official generic templates:
  - CRM / Customer Management
  - Project / Task
  - Customer Service / Ticket
  - Inventory / Asset
  - Advertising Agency Sample as the last optional sample, not the default path.
- Added CSV import preview and commit.
- Added lightweight `.xlsx` first-sheet import preview and commit using the Python standard library, without adding a new dependency.
- Added type inference for text, number, checkbox and date fields.
- Added user-correctable import field mapping before commit.
- Added template installation that creates ordinary bases, tables, fields, views and sample records.
- Added save-as-template support for existing bases.
- Added Package 3 API routes:
  - `GET /templates`
  - `POST /workspaces/{workspace_id}/imports`
  - `GET /imports/{import_job_id}`
  - `POST /imports/{import_job_id}/commit`
  - `POST /workspaces/{workspace_id}/template-installations`
  - `POST /bases/{base_id}/templates`

Changed backend files:

- `backend/alembic/versions/20260709_0018_stage06_template_import.py`
- `backend/app/models/stage06_templates.py`
- `backend/app/models/__init__.py`
- `backend/app/services/stage06_platform.py`
- `backend/app/services/stage06_templates.py`
- `backend/app/schemas/stage06_templates.py`
- `backend/app/api/routes/stage06_templates.py`
- `backend/app/main.py`
- `backend/tests/unit/test_stage06_template_import_migration.py`
- `backend/tests/unit/test_stage06_template_import.py`
- `backend/tests/unit/test_stage06_template_import_api.py`

What this implements:

- Package 3 backend contract for import jobs, template listing, template install and save-as-template.
- Import preview before commit.
- Commit-time creation of ordinary platform resources.
- Official generic templates ordered ahead of the advertising sample.
- Import commit audit and template install audit through `ops_audit_events`.

What this does not implement:

- File upload storage; current API accepts content payloads suitable for the Stage06 pilot/API layer.
- Multi-sheet Excel import.
- Rich spreadsheet formulas, merged cells or attachment fields.
- Template marketplace/version management beyond official seed templates and custom save-as-template.
- Digital employee preset creation from templates; Package 4 will own digital employee runtime.
- Mini App frontend screens for import/template flows.
- Online Alembic smoke against a real PostgreSQL database, because no disposable `STAGE02_ONLINE_DATABASE_URL` was provided.

Verification:

- RED run before implementation:
  - `python -m pytest tests/unit/test_stage06_template_import_migration.py tests/unit/test_stage06_template_import.py tests/unit/test_stage06_template_import_api.py -q`
  - Result: failed during collection because `app.services.stage06_templates` and `app.api.routes.stage06_templates` did not exist.
- GREEN targeted run after implementation:
  - `python -m pytest tests/unit/test_stage06_template_import_migration.py tests/unit/test_stage06_template_import.py tests/unit/test_stage06_template_import_api.py -q`
  - Result: `7 passed`.
- Neighbor regression:
  - `python -m pytest tests/unit/test_initial_migration.py tests/unit/test_model_metadata.py tests/unit/test_bitable_views.py tests/unit/test_permissions.py tests/unit/test_stage06_platform_migration.py tests/unit/test_stage06_platform_core.py tests/unit/test_stage06_platform_api.py tests/unit/test_stage06_template_import_migration.py tests/unit/test_stage06_template_import.py tests/unit/test_stage06_template_import_api.py -q`
  - Result: `45 passed`.
- Full backend regression:
  - `python -m pytest tests -q`
  - Result: `289 passed, 17 skipped`.
  - Skipped tests require `STAGE02_ONLINE_DATABASE_URL` for online PostgreSQL smoke coverage.
- Diff hygiene:
  - `git diff --check`
  - Result: passed with no whitespace errors. Git emitted Windows LF-to-CRLF working-copy warnings only.

Current Stage06 status:

- Package 1, Package 2 and Package 3 are implemented and locally full-backend-tested.
- Historical note: at this point Package 4 and Package 5 were still pending. This is superseded for backend readiness by the later Package 4 runtime, Package 5 backend evidence and backend exit audit. Mini App/frontend evidence remains a separate future gate.

### 2026-07-09: Package 2B Generic Bitable Core Completion

Implemented:

- Added Stage06 service and API support for:
  - `GET /workspaces/{workspace_id}`;
  - `GET /bases/{base_id}`;
  - `PATCH /records/{record_id}`;
  - `GET /views/{view_id}/records` for UUID Stage06 views.
- Added optimistic record version checks for record update.
- Added field-level write permission checks for record update.
- Added view-level read permission denial for Stage06 views.
- Added permission-denial audit without leaking denied record values.
- Added audit writes for Stage06 mutating API paths by reusing the existing `ops_audit_events` audit bridge.
- Added persisted `record_links` synchronization for linked-record fields.
- Added lookup field resolution in view reads using linked-record values.
- Preserved the Stage02-05 fixed view API by constraining the Stage06 view route to UUID paths: `/views/{view_id:uuid}/records`.

Changed backend files:

- `backend/app/services/stage06_platform.py`
- `backend/app/schemas/stage06_platform.py`
- `backend/app/api/routes/stage06_platform.py`
- `backend/tests/unit/test_stage06_platform_core.py`
- `backend/tests/unit/test_stage06_platform_api.py`

What this implements:

- The remaining Package 2 core contract for create/read/update/query of generic bitable records.
- Permission-filtered view reads with field hiding and view denial behavior.
- Write permission enforcement at field level.
- Record update audit and mutation audit for Stage06 API calls.
- Linked record persistence plus lookup read behavior.

What this does not implement:

- CSV/Excel import.
- Template installation.
- Digital employee runtime.
- Draft-confirmation workflow.
- Telegram mention routing.
- Mini App frontend.
- Dedicated Stage06 audit table; Package 2B intentionally reuses existing `ops_audit_events` as the audit bridge.
- Online Alembic smoke against a real PostgreSQL database, because no disposable `STAGE02_ONLINE_DATABASE_URL` was provided.

Verification:

- RED run before implementation:
  - `python -m pytest tests/unit/test_stage06_platform_core.py tests/unit/test_stage06_platform_api.py -q`
  - Result: failed during collection because `update_record` did not exist.
- GREEN targeted run after implementation:
  - `python -m pytest tests/unit/test_stage06_platform_core.py tests/unit/test_stage06_platform_api.py -q`
  - Result: `9 passed`.
- Neighbor regression after resolving route conflict:
  - `python -m pytest tests/unit/test_initial_migration.py tests/unit/test_model_metadata.py tests/unit/test_bitable_views.py tests/unit/test_permissions.py tests/unit/test_stage06_platform_migration.py tests/unit/test_stage06_platform_core.py tests/unit/test_stage06_platform_api.py -q`
  - Result: `38 passed`.
- Full backend regression:
  - `python -m pytest tests -q`
  - Result: `282 passed, 17 skipped`.
  - Skipped tests require `STAGE02_ONLINE_DATABASE_URL` for online PostgreSQL smoke coverage.
- Diff hygiene:
  - `git diff --check`
  - Result: passed with no whitespace errors. Git emitted Windows LF-to-CRLF working-copy warnings only.

Current Package 2 status:

- Package 2A and Package 2B are implemented and locally full-backend-tested.
- Package 2 is not a complete Stage06 exit: imports, templates, digital employees, Telegram mention flow, Mini App and production-like pilot remain Package 3-5 work.

### 2026-07-09: Package 2A Generic Platform Core Skeleton

User confirmation:

- The user confirmed Package 2A code development.
- The user clarified that future development work does not need additional confirmation when it stays within existing source-of-truth and Stage06 document settings. Confirmation remains required for technical selection changes, schema/API/permission model changes beyond current documents, external writes or production-like unsafe actions.

Implemented:

- Added Stage06 generic platform migration after current Alembic head `20260707_0016`:
  - `workspaces`
  - `workspace_members`
  - `stage06_telegram_bindings`
  - `bases`
  - `tables`
  - `fields`
  - `records`
  - `record_links`
  - `views`
  - `forms`
- Added Stage06 SQLAlchemy models using the existing `Base`, UUID primary key and timestamp mixins.
- Added Stage06 service layer with:
  - create workspace;
  - create base;
  - create table;
  - create field;
  - create JSONB-backed record;
  - create view;
  - table schema introspection;
  - view record listing with basic field permission filtering.
- Added Stage06 FastAPI routes for:
  - `POST /workspaces`
  - `POST /workspaces/{workspace_id}/bases`
  - `POST /bases/{base_id}/tables`
  - `POST /tables/{table_id}/fields`
  - `POST /tables/{table_id}/records`
  - `GET /tables/{table_id}/schema`
- Added TDD tests first, verified RED before implementation, then implemented the minimal GREEN path.

Changed backend files:

- `backend/alembic/versions/20260709_0017_stage06_platform_core.py`
- `backend/app/models/stage06_platform.py`
- `backend/app/models/__init__.py`
- `backend/app/services/stage06_platform.py`
- `backend/app/schemas/stage06_platform.py`
- `backend/app/api/routes/stage06_platform.py`
- `backend/app/main.py`
- `backend/tests/unit/test_stage06_platform_migration.py`
- `backend/tests/unit/test_stage06_platform_core.py`
- `backend/tests/unit/test_stage06_platform_api.py`

What this implements:

- Package 2A skeleton for generic platform core.
- JSONB record storage with typed field metadata validation.
- Stage06 field type allowlist enforcement.
- Schema introspection.
- Minimal API path for creating workspace/base/table/field/record.
- Basic view record field filtering using field `permission_policy`.

What this does not implement:

- Record update API (`PATCH /records/{record_id}`).
- `GET /workspaces/{workspace_id}`.
- `GET /views/{view_id}/records` API route, although the service-level view listing exists.
- Full workspace/base/table/view/action permission engine.
- Linked record and lookup service behavior, beyond migration/model storage.
- CSV/Excel import.
- Template installation.
- Digital employee runtime.
- Telegram mention routing.
- Mini App frontend.
- Production-like pilot.

Verification:

- RED run before implementation:
  - `python -m pytest tests/unit/test_stage06_platform_migration.py tests/unit/test_stage06_platform_core.py tests/unit/test_stage06_platform_api.py -q`
  - Result: failed during collection because `app.services.stage06_platform` and `app.api.routes.stage06_platform` did not exist.
- GREEN targeted run after implementation:
  - `python -m pytest tests/unit/test_stage06_platform_migration.py tests/unit/test_stage06_platform_core.py tests/unit/test_stage06_platform_api.py -q`
  - Result: `7 passed`.
- Package 2A surrounding regression:
  - `python -m pytest tests/unit/test_initial_migration.py tests/unit/test_bitable_views.py tests/unit/test_permissions.py tests/unit/test_stage06_platform_migration.py tests/unit/test_stage06_platform_core.py tests/unit/test_stage06_platform_api.py -q`
  - Result: `31 passed`.
- Full backend regression:
  - `python -m pytest tests -q`
  - Result: `278 passed, 17 skipped`.
  - Skipped tests require `STAGE02_ONLINE_DATABASE_URL` for online PostgreSQL smoke coverage.
- Diff hygiene:
  - `git diff --check`
  - Result: passed with no whitespace errors. Git emitted Windows LF-to-CRLF working-copy warnings only.

Current Package 2 status:

- Superseded by Package 2B status above.

### 2026-07-09: Subphase 0 Development Readiness Audit

Completed:

- Re-read Stage06 source documents before code implementation:
  - [Stage 06 Source Of Truth](STAGE_06_SOURCE_OF_TRUTH.md)
  - [Stage 06 Implementation Plan](STAGE_06_IMPLEMENTATION_PLAN.md)
  - [Stage 06 SDD](STAGE_06_SDD.md)
  - [Stage 06 API Data Security Contract](STAGE_06_API_DATA_SECURITY_CONTRACT.md)
  - [Stage 06 BDD And Acceptance](STAGE_06_BDD_AND_ACCEPTANCE.md)
- Re-read current backend structure before relying on prior memory.
- Re-checked current `larksuite/cli` public repository/README. Current benchmark facts still align with the Stage06 benchmark: it is agent-native, MIT licensed, organized around skills, uses a three-layer command system, supports dry-run/schema introspection/structured JSON output, and lists Base capabilities covering tables, fields, records, views, dashboards, workflows, forms, roles and permissions.

Current backend reuse findings:

| Area | Finding | Stage06 decision impact |
| --- | --- | --- |
| SQLAlchemy base | `backend/app/models/base.py` already has shared `Base`, UUID primary key and timestamps | Reuse directly |
| Alembic | Existing migration chain ends at `20260707_0016` and imports `app.models.metadata` | Add a new Stage06 migration after current head |
| API structure | Existing FastAPI routes are simple routers included in `main.py` | Add Stage06 platform router(s), do not replace existing Stage05 routes |
| Tests | Existing tests use pytest, TestClient, fake sessions/data sources and migration source checks | Follow the same TDD style |
| Audit | `record_audit_event` already provides redacted audit writes for old `ops_audit_events` | Reuse initially, then align or bridge with Stage06 `audit_events` only if required |
| Fixed Bitable views | `services/bitable_views.py` is a Stage02-05 fixed business-view registry | Do not mutate it into the generic platform core; keep as historical/compat view layer |
| Permissions | `services/permissions.py` is advertising-role/customer-scope oriented | Add a new generic platform permission layer rather than rewriting old roles in place |
| Agents | Stage05 Agents are vertical draft agents | Keep as historical/template presets; Stage06 digital employee runtime comes later |

Recommended first code subphase, resolved by user confirmation:

```text
Package 2A: Generic Platform Core Skeleton
```

Scope:

- Add Stage06 generic platform models and migration:
  - `workspaces`
  - `workspace_members`
  - `telegram_bindings` or a Stage06-compatible extension table if name conflict requires it
  - `bases`
  - `tables`
  - `fields`
  - `records`
  - `record_links`
  - `views`
  - `forms`
- Add schemas, services and routes for the required Package 2 core path:
  - create workspace
  - create base
  - create table
  - create field
  - create record with JSONB values
  - inspect table schema
  - read records through a view
- Add tests first for:
  - migration file creates required tables;
  - field type validation accepts only Stage06 field types;
  - record values validate against field metadata;
  - schema introspection returns table + fields;
  - view record read applies permission-filtered field output at least at a basic level.

What this subphase will not do:

- No CSV/Excel import yet.
- No template installation yet.
- No digital employee runtime yet.
- No Telegram mention routing yet.
- No Mini App frontend yet.
- No migration of Stage02-05 vertical data into generic records.
- No Feishu/Lark API integration.
- No provider writes, funds movement or uncontrolled Telegram sends.

Technical proposal confirmed before code:

- Add a parallel Stage06 platform module instead of rewriting Stage02-05 modules in place.
- Keep Stage02-05 fixed views and vertical Agents intact as historical compatibility code.
- Use direct REST resources from the Stage06 API contract (`/workspaces`, `/bases`, `/tables`, `/records`, `/views`) rather than Feishu-compatible URLs.
- Reuse the `larksuite/cli` architecture conceptually as:
  - schema/discovery tools;
  - field/view management tools;
  - record read/write tools;
  - structured output envelopes for digital employee tool responses;
  - dry-run/draft-confirmation for write-like Agent actions.
- Do not copy `larksuite/cli` code and do not introduce Go/Node runtime into this Python backend.

### 2026-07-09: Stage06 Platform Documentation Start

Completed:

- Created [Stage 06 LarkSuite Benchmark Audit](STAGE_06_LARKSUITE_BENCHMARK_AUDIT.md).
- Rewrote active top-level project direction to generic platform-first wording.
- Defined advertising-agency workflows as historical evidence and optional template/sample input.
- Drafted Stage06 compact document package:
  - [Stage 06 Source Of Truth](STAGE_06_SOURCE_OF_TRUTH.md)
  - [Stage 06 Implementation Plan](STAGE_06_IMPLEMENTATION_PLAN.md)
  - [Stage 06 SDD](STAGE_06_SDD.md)
  - [Stage 06 API Data Security Contract](STAGE_06_API_DATA_SECURITY_CONTRACT.md)
  - [Stage 06 BDD And Acceptance](STAGE_06_BDD_AND_ACCEPTANCE.md)
  - [Stage 06 Progress](STAGE_06_PROGRESS.md)

Current stage:

```text
docs-first platform rewrite
-> Package 2A generic platform core skeleton
-> Package 2B generic bitable core completion
-> Package 3 template and import system
-> Package 4 Telegram Mini App and digital employee runtime
-> Package 5 production-like pilot acceptance
-> Mini App frontend stack confirmation and UI smoke
```

Open:

- Stage06 Package 2A, Package 2B, Package 3, Package 4 backend and Package 5 backend/API evidence has passed local backend regression.
- Existing backend is still Stage05-oriented and must be refactored/extended in the next phase.
- Frontend/Mini App implementation still needs code-level planning after document confirmation.
- Migration from vertical Stage02-05 data to generic records is not part of the initial Stage06 doc rewrite.

## Risks

| Risk | Status | Mitigation |
| --- | --- | --- |
| Old advertising docs mislead implementation | Active | Active top-level docs rewritten; historical docs marked as historical/template input |
| Stage06 scope becomes too broad | Active | Keep five large packages and defer formula/attachment/full workflow/dashboard/persona |
| Generic record model conflicts with old normalized tables | Active | Add generic platform tables first; do not destructively migrate old tables in Stage06 docs |
| Telegram scope leaks data | Active | Effective scope intersection required |
| Digital employees become generic chatbots | Active | Require base/table/view context, draft writes and audit |

## Next Step

Continue with Mini App frontend stack decision and production-like environment evidence. A frontend implementation requires confirming the frontend stack because the current repository has no existing frontend base.
