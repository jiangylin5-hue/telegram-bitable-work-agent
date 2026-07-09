# Stage 06 Source Of Truth

## Status

- Document status: active Stage06 source of truth
- Scope: Stage06 backend-readiness boundary for a generic Telegram-first multidimensional table, no-code workspace and table-bound digital employee platform
- Current Progress: 2026-07-10 Package 6 security hardening is implemented and verified. Stage06 routes now use replaceable request identity plus active workspace membership, enforce tenant/resource and Telegram-member scope, redact audit values, apply server-controlled notification fail-closed policy, bound imports and list pages, and protect multi-resource writes with idempotency and PostgreSQL constraints. Real local PostgreSQL negative/concurrency evidence passed at Alembic head `20260710_0020`. Backend-readiness is passed; Mini App UI and production deployment evidence remain deferred.

## 1. Stage Goal

Stage06 moves the project from a vertical advertising-operation backend into a generic Telegram-first platform foundation:

```text
workspace
-> base
-> table
-> field
-> record
-> view / form-lite
-> import / template
-> digital employee
-> real LLM reasoning
-> draft confirmation
-> audit
-> backend-readiness evidence
```

The stage should feel close to launch from a backend and contract perspective, but it is not production cutover and it does not implement UI in the current pass.

## 2. Confirmed Product Direction

- The product is a generic Feishu-like multidimensional table and no-code workspace.
- Telegram is the primary ecosystem and productivity entry.
- Telegram Mini App remains the main UI target, but UI implementation is deferred until backend readiness is complete and the user explicitly confirms a separate UI phase.
- A desktop-browser-compatible route is still required for future heavy building/import.
- Users can create bases and tables, import data, configure views and permissions, and create digital employees.
- Digital employees are bound to bases/tables/views and can be invoked with `@` in Telegram.
- Stage06 pilot evidence should use Telegram productivity scenarios: chats, tasks, mentions, notifications, table records, draft confirmations and audit.
- Advertising-agency workflows are a weak official sample/template only.
- The project does not integrate Feishu/Lark and does not target Feishu API compatibility.

## 3. Primary Reference Documents

Read in this order:

1. [AGENTS.md](../../AGENTS.md)
2. [Implementation Source Of Truth](../00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md)
3. [Technical Decisions](../00-governance/TECHNICAL_DECISIONS.md)
4. [Bitable Schema Blueprint](../03-modules/BITABLE_SCHEMA_BLUEPRINT.md)
5. [Stage 06 LarkSuite Benchmark Audit](STAGE_06_LARKSUITE_BENCHMARK_AUDIT.md)
6. [Stage 06 SDD](STAGE_06_SDD.md)
7. [Stage 06 API Data Security Contract](STAGE_06_API_DATA_SECURITY_CONTRACT.md)
8. [Stage 06 Implementation Plan](STAGE_06_IMPLEMENTATION_PLAN.md)
9. [Stage 06 BDD And Acceptance](STAGE_06_BDD_AND_ACCEPTANCE.md)
10. [Stage 06 Progress](STAGE_06_PROGRESS.md)
11. [Stage 06 Backend Exit Audit](STAGE_06_BACKEND_EXIT_AUDIT.md)
12. [Stage 06 Remaining Risks And Next Cases](STAGE_06_REMAINING_RISKS_AND_NEXT_CASES.md)
13. [Stage 06 LarkSuite Skills Integration Design](STAGE_06_LARKSUITE_SKILLS_INTEGRATION_DESIGN.md)
14. [Stage 06 LarkSuite Skills Runtime Implementation Plan](STAGE_06_LARKSUITE_SKILLS_RUNTIME_IMPLEMENTATION_PLAN.md)

Stage02 to Stage05 documents are historical implementation evidence and capability references. They do not override this document.

## 4. Stage06 Delivery Packages

Stage06 has five large backend-first packages:

| Package | Outcome |
| --- | --- |
| 1. Platform Source Of Truth Rewrite | Active docs no longer present advertising operations as the product center |
| 2. Generic Bitable Core | User-created workspace/base/table/field/record/view model works |
| 3. Template And Import System | CSV/Excel import and official generic templates work |
| 4. Digital Employee Runtime | Table-bound digital employees can be created, invoked and audited |
| 5. Backend Readiness Evidence | Local PostgreSQL, real LLM, Telegram backend entry, audit and safety evidence pass |

Mini App UI is not part of the current backend-readiness pass. It remains the next user-confirmed phase after backend completion.

## 5. Required Scope

### 5.1 Generic Bitable Core

Required:

- workspace/base/table/field/record/view model;
- JSONB-backed generic record values;
- typed field metadata;
- linked record and lookup metadata;
- grid/table, kanban, calendar and form-lite views;
- schema introspection for future UI and digital employees.

Field types:

- text;
- number;
- date;
- status;
- single_select;
- multi_select;
- user;
- checkbox;
- url;
- email;
- phone;
- json;
- linked_record;
- lookup.

### 5.2 Templates And Import

Required:

- CSV import;
- Excel import;
- type inference;
- preview confirmation;
- commit imported table/base;
- save imported base/table as template;
- official templates:
  - CRM/customer management;
  - project/task;
  - customer service/ticket;
  - inventory/asset;
  - advertising-agency sample as weak sample.

### 5.3 Digital Employees

Required:

- create digital employee from base/table/view;
- configure name, description, Telegram alias, accessible tables/views, actions, response style and confirmation policy;
- invoke by Telegram `@` mention or backend API;
- query/summarize records;
- call a real LangGraph/OpenRouter runtime when live mode and credentials are configured;
- create/update record-change drafts;
- advance statuses through drafts;
- create controlled notifications;
- write AgentRun/audit evidence.

Effective scope:

```text
agent_configured_scope
-> caller_user_scope
-> telegram_chat_scope
```

### 5.4 Telegram Backend Entry

Required in the current pass:

- Telegram binding API;
- Telegram mention resolver;
- allowlisted test chat/user smoke path when Telegram credentials are configured;
- no broad sends;
- notification dry-run/allowlist enforcement;
- audit readback.

Full Mini App UI is deferred.

### 5.5 Backend Readiness Safety

Required:

- safety switches for digital employee execution;
- dry-run or allowlist controls for notifications;
- provider/external writes disabled unless separately approved;
- local PostgreSQL Alembic migration smoke against real PostgreSQL;
- real OpenRouter-compatible LLM smoke when credentials are configured;
- audit readback;
- acceptance evidence.

## 6. Explicit Non-Goals

Stage06 current pass does not include:

- Mini App frontend implementation;
- Feishu/Lark integration;
- Feishu API compatibility;
- direct copy from `larksuite/cli`;
- full formula engine;
- full attachment storage/preview;
- full workflow builder;
- full dashboard builder;
- digital clone/persona runtime;
- production launch;
- broad uncontrolled Telegram sends;
- real external provider writes;
- funds movement or irreversible account operations;
- advertising-agency-first pilot positioning.

## 7. Success Criteria

Stage06 backend-readiness passes only if:

- active top-level documents are platform-first and Telegram-ecosystem-first;
- UI is explicitly deferred and no frontend implementation is created in this pass;
- a generic base can be created without an advertising template;
- CSV/Excel import can create a table after preview confirmation;
- official generic templates can install ordinary platform resources;
- a digital employee can be created from a base/table/view;
- Telegram `@` invocation resolves user/chat/base/employee context;
- digital employee reads are permission-filtered;
- real LangGraph/OpenRouter invocation is implemented and smoke-tested when credentials are configured;
- write-like digital employee actions create drafts;
- user confirmation commits the record update;
- audit evidence exists;
- local PostgreSQL migration smoke passes or is explicitly blocked by local PostgreSQL availability;
- safety close can disable sends and high-risk execution.

## 8. Stage Exit

The backend-only exit decision is restored after Package 6 passed the permission, tenant-isolation, audit, notification, import, pagination, idempotency, database and real local PostgreSQL gates. This is backend-readiness only and does not claim Mini App, remote staging or production launch readiness.

Security-hardening exit additionally requires:

- no Stage06 route depends on a fixed privileged system actor;
- every workspace-owned request resolves an active workspace member;
- Telegram identity resolves through an explicit workspace-member binding;
- cross-workspace and cross-base resource combinations are rejected;
- lookup and audit readback cannot bypass field permissions;
- notification policy is server-controlled and fail-closed;
- import limits, pagination, idempotency and database constraints are verified;
- real PostgreSQL negative/concurrency evidence is retained as sanitized JSON.

Current backend-readiness exit has produced:

- updated top-level platform docs;
- implemented generic platform core;
- implemented import/template flow;
- implemented deterministic and live LLM digital employee runtime modes;
- Telegram backend entry smoke evidence;
- local PostgreSQL migration smoke evidence;
- BDD/acceptance evidence;
- safety close evidence;
- recommendation and explicit confirmation gate for the separate UI phase.

The backend-only exit evidence is recorded in [Stage 06 Backend Exit Audit](STAGE_06_BACKEND_EXIT_AUDIT.md). This does not replace the later Mini App/frontend and production-style deployment gates.
