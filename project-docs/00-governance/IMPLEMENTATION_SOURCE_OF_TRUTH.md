# Implementation Source Of Truth

## Status

- Document status: active source of truth
- Scope: 顶层产品目标、边界、阶段、技术基线、安全约束和 Stage06 平台化方向
- Current Progress: 2026-07-10 Updated after Stage06 backend-readiness evidence. The active project truth is now a generic Telegram-first multidimensional table, no-code workspace and table-bound digital employee platform. The current non-UI backend-readiness pass has evidence for local PostgreSQL migration smoke, real LangGraph/OpenRouter summarize and draft-update invocation, and Telegram-ecosystem productivity backend entry. Mini App UI remains a product target but must wait for separate user confirmation. Advertising-agency workflows are retained only as historical Stage02-05 evidence and optional template/sample material.

## 1. Product Goal

The project will build a generic Telegram-first multidimensional table and no-code workspace platform.

The product should let users:

- create workspaces and bases;
- create or import multidimensional tables;
- configure fields, linked records, views, forms, permissions and templates;
- use Telegram Mini App as the main workspace entry;
- use a desktop browser route for heavier building and import workflows;
- create table-bound digital employees from bases, tables or views;
- `@` those digital employees in Telegram contexts;
- let digital employees query, summarize, draft updates, process queues and create controlled notifications;
- confirm write-like actions before commit;
- audit every material action.

The platform should imitate Feishu Base / Lark Base product grammar and learn from the official `larksuite/cli` skill and command structure, but it must remain independent from Feishu/Lark integration.

## 2. Product Shape

```text
Telegram Bot / Group / Mini App
-> workspace
-> base
-> table
-> field schema
-> record values
-> view / form / dashboard-lite
-> permission
-> template / import
-> digital employee
-> real LLM reasoning when enabled
-> draft confirmation
-> backend service write
-> audit event
```

Telegram is the primary ecosystem and productivity surface, not only an alert channel. Complex table building, import review and permission configuration must also work in a desktop browser.

## 3. What Changed From Stage05

Stage02 to Stage05 proved useful backend capabilities around Telegram ingestion, binding, OpenRouter, LangGraph, draft generation, confirmation, controlled sends, audit and staging safety. Those artifacts remain valuable.

The product definition has changed:

| Old active framing | New active framing |
| --- | --- |
| Advertising-agency operations platform | Generic Telegram-first no-code multidimensional table workspace |
| Fixed vertical business tables | User-created bases, tables and fields |
| Role-specific business Agents | Configurable table-bound digital employees |
| Recharge/account/card workflows as core product | Advertising workflow as optional official template |
| Bitable-like views over fixed backend schema | Generic table/view/form/template/import platform |

Any active document that still presents advertising operations as the product center should be treated as historical or rewritten before implementation depends on it.

## 4. Platform Constitution

Every feature must resolve into platform resources:

```text
workspace
base
table
field
record
linked_record
view
form
dashboard-lite
template
import_job
permission
digital_employee
record_change_draft
automation_event
audit_event
```

No workflow is complete if it only produces a chat answer or temporary Agent state.

Before implementing a feature, answer:

- Which workspace/base owns it?
- Which table and fields store it?
- Which view or form exposes it?
- Which permission layer controls it?
- Does a digital employee need access?
- What action is draft-only, confirmable or direct?
- What audit event proves it happened?

## 5. Confirmed Technical Baseline

| Area | Decision |
| --- | --- |
| Backend language | Python 3.12+ |
| Backend framework | FastAPI |
| API style | REST first, async jobs for long work |
| ORM | SQLAlchemy 2.x |
| Migration | Alembic |
| Primary database | PostgreSQL |
| Generic record storage | JSONB values with typed field metadata |
| Vector extension | pgvector |
| Queue/cache | Redis |
| Queue pattern | Redis Streams / reliable job queue first, Temporal as future candidate |
| Agent orchestration | LangGraph-first |
| LLM provider | OpenRouter-compatible API |
| LLM model binding | Runtime config, not hard-coded in business logic |
| Stage06 LLM acceptance | At least one real LangGraph/OpenRouter call when credentials are configured |
| Telegram integration | Bot API + Webhook + Mini App |
| Frontend stack | React + Vite + TypeScript + Tailwind + shadcn/ui + lucide-react |
| Frontend target | Telegram Mini App first, desktop-browser-compatible route required; implementation deferred until backend readiness is complete and the user confirms a separate UI phase |
| Observability | Audit events, draft logs, job logs, agent trace ids, controlled notification logs |

## 6. Digital Employee Authority Model

```text
Telegram or UI request
-> resolve user identity
-> resolve workspace/base/chat context
-> compute effective agent scope
-> inspect allowed schema/views
-> read permitted records
-> LangGraph/OpenRouter reasoning when live mode is enabled
-> propose answer or record_change_draft
-> human confirmation for write-like actions
-> backend service commit
-> audit event
```

Effective scope:

```text
agent_configured_scope
-> caller_user_scope
-> telegram_chat_scope
```

Digital employees can:

- query permitted tables and views;
- summarize records;
- answer questions with citations to table resources;
- create or update record-change drafts;
- advance statuses in controlled queues when permitted;
- create controlled notifications;
- call controlled execution tools only when the relevant stage explicitly enables them and a confirmation artifact exists.

Digital employees cannot:

- access raw PostgreSQL or raw SQL;
- bypass Tool Gateway/backend service methods;
- self-confirm high-risk writes;
- modify permissions unless explicitly granted and confirmed;
- treat Telegram group membership as sufficient system permission;
- create broad external sends without a safety gate;
- claim success without persisted evidence.

## 7. Stage06 Active Goal

Stage06 is a production-like pilot stage for the generic platform direction, with Telegram ecosystem productivity as the pilot cut.

The stage should deliver five large packages:

1. Platform Source Of Truth Rewrite.
2. Generic Bitable Core.
3. Template And Import System.
4. Telegram Mini App And Digital Employee Runtime.
5. Pilot Acceptance Evidence.

Stage06 must be close to launch in feel, but it is not production cutover. Real external provider writes, broad group sends, funds movement and irreversible external operations remain out of scope unless a later explicit approval changes that.

Stage06 pilot evidence must include:

- local PostgreSQL Alembic migration smoke against a real local PostgreSQL database;
- real Telegram entry smoke with a test bot and allowlisted chat/user when credentials are configured;
- at least one real LangGraph/OpenRouter LLM invocation when credentials are configured;
- audit and safety readback.

Mini App/desktop frontend smoke is still required before a final launch-like Stage06 exit, but it is explicitly out of scope for the current backend-readiness pass and must not begin without separate user confirmation.

Local PostgreSQL smoke is acceptable for Stage06, but it is not remote staging or production evidence.

## 8. Historical Stage Documents

Stage02 to Stage05 remain useful implementation history:

- Stage02: backend kernel, early bitable-like views, draft/confirmation, mock Telegram/provider.
- Stage03: real Telegram webhook, binding and Redis worker path.
- Stage04: binding management and restricted test send.
- Stage05: real OpenRouter, LangGraph supervisor, draft Agents, controlled private test send, staging safety close.

They are not the product definition for Stage06.

## 9. Current Non-Goals

Stage06 does not include:

- Feishu/Lark API integration;
- Feishu API compatibility;
- full formula engine;
- full attachment storage and preview;
- full workflow builder;
- full dashboard builder;
- digital clone/persona runtime;
- real production launch;
- uncontrolled Telegram group sending;
- real external provider writes without separately approved production execution docs;
- advertising-agency-first pilot positioning.

## 10. Documentation System

- `00-governance`: active truth and technical decisions.
- `00-research`: historical and current external research.
- `01-product`: product brief and template/scenario index.
- `02-architecture`: architecture references.
- `03-modules`: platform resource blueprints.
- `04-agents`: digital employee platform index and historical Agent docs.
- `05-data`: data, permission and security references.
- `06-queue`: queue and worker references.
- `07-acceptance`: historical acceptance.
- `08-implementation`: Stage documents and acceptance evidence.

During Stage06, the main implementation entry is:

- [Stage 06 Source Of Truth](../08-implementation/STAGE_06_SOURCE_OF_TRUTH.md)
- [Stage 06 Implementation Plan](../08-implementation/STAGE_06_IMPLEMENTATION_PLAN.md)
- [Stage 06 SDD](../08-implementation/STAGE_06_SDD.md)
- [Stage 06 API Data Security Contract](../08-implementation/STAGE_06_API_DATA_SECURITY_CONTRACT.md)
- [Stage 06 BDD And Acceptance](../08-implementation/STAGE_06_BDD_AND_ACCEPTANCE.md)
- [Stage 06 Progress](../08-implementation/STAGE_06_PROGRESS.md)

## 11. Confirmation Rule

User confirmation is required before:

- changing the technical baseline;
- changing the platform resource model;
- changing permission semantics;
- changing schema or API contracts;
- enabling real external provider writes;
- enabling broad or customer-facing Telegram sends;
- moving from Stage06 documentation to code implementation;
- treating Stage06 pilot as production launch.
