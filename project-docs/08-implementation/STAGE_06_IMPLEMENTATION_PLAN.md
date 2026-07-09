# Stage 06 Implementation Plan

## Status

- Document status: active Stage06 implementation plan
- Scope: Large-package backend-readiness implementation plan for the Stage06 platform pivot
- Current Progress: 2026-07-10 Packages 1-5 retain their backend feature evidence, but backend exit is reopened for approved Package 6 security hardening. Package 6 covers replaceable request identity, active workspace-member authorization, tenant/resource invariants, lookup permission, audit redaction, server-controlled notification fail-closed policy, import limits, cursor pagination, idempotency, database constraints and PostgreSQL negative/concurrency evidence. Mini App remains deferred.

## Goal

Deliver backend readiness for a generic Telegram-first multidimensional table, no-code workspace and table-bound digital employee platform.

## Architecture

Stage06 adds a generic platform layer over the existing backend foundation rather than deleting Stage02-05 vertical code. The new layer introduces workspace/base/table/field/record/view/import/template/digital employee resources, while old advertising workflows remain available as historical code and future template input.

The current pass is backend-only. UI contracts should remain stable for the later Mini App phase, but no frontend project should be created until the user confirms.

## Global Constraints

- Keep Feishu/Lark as product benchmark only; do not integrate Feishu APIs.
- Use PostgreSQL JSONB for generic record values and typed metadata for fields.
- Use FastAPI, SQLAlchemy 2.x, Alembic, Redis, LangGraph and OpenRouter-compatible API.
- Telegram identity is context, not final permission.
- Digital employee effective scope is `agent_configured_scope -> caller_user_scope -> telegram_chat_scope`.
- Write-like digital employee actions default to draft-confirmation.
- Current pass is backend readiness, not production launch.
- Do not implement Mini App UI before separate user confirmation.
- Stage06 pilot evidence uses Telegram ecosystem productivity, not advertising-agency operations.

## Package 1: Platform Source Of Truth Rewrite

**Implementation status:** implemented locally; refreshed for backend-first UI deferral.

**Files:**

- Modify: `AGENTS.md`
- Modify: `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`
- Modify: `project-docs/00-governance/TECHNICAL_DECISIONS.md`
- Modify: `project-docs/01-product/TELEGRAM_MULTIDIMENSIONAL_AGENT_NEW_PROJECT_BRIEF.md`
- Modify: `project-docs/01-product/BUSINESS_SCENARIOS_INDEX.md`
- Modify: `project-docs/03-modules/BITABLE_SCHEMA_BLUEPRINT.md`
- Modify: `project-docs/04-agents/AGENTS_INDEX.md`
- Modify: `project-docs/05-data/PERMISSION_AND_SECURITY_MODEL.md`

**Deliverable:**

Active documents define the project as a generic Telegram-first platform. Advertising-agency language is historical/template-only. UI implementation is explicitly deferred until backend readiness is complete and the user confirms a separate UI phase.

**Acceptance:**

- Active source docs do not present advertising operations as the product center.
- Stage06 source docs link to the benchmark audit and platform blueprint.
- Stage06 docs distinguish current backend-readiness exit from later UI work.

## Package 2: Generic Bitable Core

**Implementation status:** Package 2A and Package 2B are implemented locally.

**Backend areas:**

- migrations for `workspaces`, `workspace_members`, `telegram_bindings`, `bases`, `tables`, `fields`, `records`, `record_links`, `views`, `forms`;
- audit alignment through the existing `ops_audit_events` bridge;
- SQLAlchemy models and repositories;
- Pydantic schemas;
- FastAPI routes;
- permission-filtered read/write services;
- schema introspection service.

**Core routes:**

- `POST /workspaces`
- `GET /workspaces/{workspace_id}`
- `GET /workspaces/{workspace_id}/members`
- `POST /workspaces/{workspace_id}/bases`
- `GET /bases/{base_id}`
- `POST /bases/{base_id}/tables`
- `POST /bases/{base_id}/views`
- `POST /tables/{table_id}/fields`
- `POST /tables/{table_id}/records`
- `PATCH /records/{record_id}`
- `GET /views/{view_id}/records`
- `GET /tables/{table_id}/schema`

**Acceptance:**

- Create a workspace/base/table from scratch.
- Add fields of required Stage06 types.
- Create and update JSONB-backed records.
- Query records through a view with permission filtering.
- Linked record metadata and lookup metadata are persisted.

## Package 3: Template And Import System

**Implementation status:** backend model, migration, service, API and tests are implemented locally.

**Backend areas:**

- `templates`, `template_installations`, `import_jobs`;
- CSV parser and Excel parser;
- type inference;
- import preview;
- import commit;
- template install;
- save-as-template.

**Official templates:**

- CRM/customer management;
- project/task;
- customer service/ticket;
- inventory/asset;
- advertising-agency sample as the last optional sample.

**Acceptance:**

- Import CSV and Excel into a new table after preview confirmation.
- User can correct inferred field types before commit.
- Installed templates create ordinary bases/tables/fields/views.
- Advertising sample is not the default first template.

## Package 4: Digital Employee Runtime

**Implementation status:** deterministic backend runtime, API contract and live LangGraph/OpenRouter runtime are implemented locally. Real OpenRouter summarize and draft-update smokes have passed.

**Backend areas:**

- `digital_employees`;
- `record_change_drafts`;
- `notification_requests`;
- AgentRun/audit linkage;
- Telegram mention resolver;
- effective scope calculator;
- schema-aware tool gateway;
- live LangGraph/OpenRouter runtime with permission-filtered context and structured output validation.

**Agent actions:**

- schema inspect;
- record query;
- deterministic record summarize;
- live LLM summarize;
- live LLM draft proposal;
- record-change draft create/update;
- status-advance draft;
- controlled notification request.

**Acceptance:**

- A digital employee can be created from a base/table/view.
- Telegram `@` mention resolves the correct workspace/base/employee context.
- Digital employee reads are permission-filtered.
- Deterministic mode remains available for tests and fallback.
- Live mode uses LangGraph and OpenRouter-compatible API when configured.
- Proposed writes create drafts, not direct writes.
- User confirmation commits the record update and writes audit.
- AgentRun evidence distinguishes `local/deterministic_tool_gateway` from `openrouter/<model>`.

## Package 5: Backend Readiness Acceptance

**Implementation status:** backend/API pilot evidence, real LLM summarize/draft smoke, local PostgreSQL migration smoke and Telegram backend entry smoke are implemented and evidenced for the current non-UI backend pass.

**Pilot path:**

```text
Telegram backend entry
-> generic base/table
-> template or import
-> digital employee
-> permission check
-> real LLM summarize/draft when configured
-> draft confirmation
-> audit event
-> safety close
```

**Environment requirements:**

- local backend test environment;
- local PostgreSQL for migration smoke;
- real OpenRouter credentials for live LLM smoke when configured;
- Telegram test bot/chat/user allowlist for entry smoke when configured;
- Telegram send dry-run or allowlist;
- provider writes disabled;
- visible safety readback.

**Acceptance:**

- Evidence document includes test commands and API/script responses.
- Local PostgreSQL Alembic smoke passes or records a concrete local environment blocker.
- Real OpenRouter smoke passes when credentials are configured.
- Telegram backend entry smoke passes when credentials are configured.
- Safety close proves sends and external writes can be disabled.
- Remaining production risks are listed before the later UI phase.

## Package 6: Stage06 Security Hardening

**Implementation status:** approved design; implementation pending written-spec review and TDD plan.

**Delivery 6A: Identity And Authorization**

- replace fixed privileged Stage06 route identity with a request-identity adapter;
- allow the explicit development identity header only in `local`/`test`;
- fail closed in `staging`/`production` without a verified adapter;
- derive roles from active workspace membership;
- bind Telegram callers to workspace members;
- enforce workspace/base/table/view/record/field/action intersections.

**Delivery 6B: Tenant, Audit And Notification Safety**

- reject cross-workspace and cross-base resource combinations;
- validate digital employee configured scope and make empty scope deny access;
- re-check linked-record/lookup target permissions;
- redact stored and returned audit state;
- restrict audit readback to owner/admin;
- compute notification status from server policy and fail closed by default.

**Delivery 6C: Operational Hardening**

- enforce bounded CSV/Excel import sizes and shapes;
- add cursor pagination with default 50 and maximum 200;
- add `Idempotency-Key` handling for multi-resource mutations;
- add non-destructive Stage06 constraints and indexes;
- add PostgreSQL negative/concurrency tests and sanitized JSON evidence;
- reconcile source, SDD, contract, BDD, progress, risk and exit documents.

**Acceptance:**

- S6-11 and S6-22 through S6-27 pass;
- Stage06 routes no longer use the fixed system actor;
- tenant, lookup, audit and notification security tests pass;
- import/pagination/idempotency tests pass;
- real PostgreSQL migration and concurrency evidence passes or records a concrete environment blocker;
- the full backend regression remains green.

## Deferred UI Phase

Mini App UI remains required for a launch-like product, but it is not implemented in the current backend-readiness pass.

Future UI phase should start only after user confirmation and should use:

- React + Vite + TypeScript;
- Tailwind;
- shadcn/ui;
- lucide-react;
- Telegram Mini App first;
- desktop-browser-compatible route.

## Implementation Notes

- Do not delete Stage02-05 code during Stage06 unless a specific migration plan requires it.
- Prefer adding generic platform modules with clear boundaries.
- Reuse existing audit, outbox, config and worker patterns where they fit.
- Do not introduce Feishu/Lark API integration.
- Keep UI-focused documents as future contracts only until the user confirms UI implementation.
