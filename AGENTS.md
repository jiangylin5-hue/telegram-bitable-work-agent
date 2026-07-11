# AGENTS.md

## Status

- Document status: active project collaboration rule
- Scope: Generic Telegram-first multidimensional table, no-code workspace and table-bound digital employee platform
- Current Progress: 2026-07-12 Stage06 backend-stage acceptance remains the baseline. Stage07 bounded Package 2 substages P3, F1 and the user-approved F2 relation/lookup slice are `implemented-local`. The user has approved and authorized implementation of V1 Saved View Builder's comprehensive design—Grid/Kanban/Calendar/Form, private/restricted member ACL, system-default Grid invariant, typed server query semantics and required migration/index/test evidence. V1-1 through V1-11 now provide local durability, strict typed contracts, canonical projection, versioned ACL mutations, V1 Grid filtering/grouping/stable sorting before cursor pagination, five approved safe HTTP endpoints, real disposable PostgreSQL default/rollback/hidden-field/index-plan/list-ACL evidence, typed Mini App transport/protected query keys/fixed error mapping, safe callback-driven Builder/Access/Query panels, App/BaseCanvas authoritative rereads and conflict/responsive recovery. The Base-list and direct-presentation paths resolve V1 ACL before emitting a summary or projection; only V1 safe scope/access/default markers supplement the legacy list shape. Presentation/member `409` clears incompatible draft state then rereads canonical safe data; `422`/`5xx` retains only local safe draft; 390px retains V1 entries/touch targets and focus returns on close. The measured access query uses existing indexes, so both optional non-unique V1 indexes remain explicitly deferred and no migration was added. Four-width Browser acceptance, Telegram identity, staging and production remain pending; V1 and Stage07 are not accepted.

## 1. Project Positioning

This project is a generic multidimensional table and no-code workspace platform with Telegram as the primary entry and table-bound digital employees as the AI operating layer.

The target product shape is:

```text
workspace
-> base
-> table
-> field schema
-> record
-> view / form / dashboard-lite
-> permission
-> template / import
-> digital employee
-> draft confirmation
-> audit
```

Telegram is the primary ecosystem and productivity surface. The Telegram Mini App should provide the main workspace UI, while the same frontend should also be usable in a desktop browser for heavier table building, imports and permission configuration.

The project should heavily imitate Feishu Base / Lark Base product grammar and the official `larksuite/cli` capability organization, but it is an isolated platform. It must not depend on Feishu API integration or Feishu API compatibility.

Advertising-agency operations from Stage02 to Stage05 are now:

- historical implementation evidence;
- a useful capability source;
- one optional official template/sample workspace.

They are no longer the top-level product definition.

## 2. Product Constitution

Multidimensional tables are the product constitution. All platform and business design must start from the table system, not from free-form chat.

Design order:

```text
workspace
-> base
-> table
-> field and field type
-> linked records
-> view / form / dashboard-lite
-> permission
-> automation or queue
-> digital employee capability
-> draft / controlled action
-> audit
```

Forbidden design order:

```text
invent an Agent
-> invent what it might do
-> find somewhere to store the result later
```

Every workflow must land back into the table platform. A result counts as complete only when at least one of these is true:

- a record is created or updated;
- a record status changes;
- a record appears in a defined view or queue;
- a template/base/table/import operation is persisted;
- a draft is created and waits for confirmation;
- a digital employee action is recorded;
- an audit event is written;
- a controlled notification or external action is linked to a record.

Telegram messages, temporary Agent memory, unpersisted JSON and oral answers are not durable business results.

## 3. Digital Employee Model

Agents are digital employees running on top of tables, views, permissions and automations.

A digital employee must have:

- `name`
- `description`
- accessible workspaces, bases, tables and views
- allowed field visibility
- allowed actions
- response style
- confirmation policy
- Telegram `@` alias or entry rule
- audit policy

Effective runtime authority is always:

```text
agent_configured_scope
-> caller_user_scope
-> telegram_chat_scope
```

Agent writes default to draft-confirmation:

```text
Agent proposes change
-> record_change_draft
-> user confirms in Mini App or Telegram
-> backend writes record
-> audit event
```

Digital employees may query, summarize, classify, draft record changes, advance controlled statuses and create controlled notifications. They may not bypass permissions, confirmation, audit or backend service boundaries.

## 4. Language

- 默认使用中文沟通。
- 代码、API、数据库表名、字段名、命令、技术名词保持英文。
- 文档中文为主，但稳定状态字段使用英文，例如 `Status`、`Scope`、`Current Progress`、`Acceptance Criteria`。

## 5. Documentation First

Architecture changes, product-boundary changes, schema changes, permission model changes, API contract changes and stage transitions must be written into local Markdown documents before implementation.

Current Stage06 rule:

- First rewrite active top-level truth documents to platform-first wording.
- Then write Stage06 source, design, plan, contract and acceptance docs.
- Only after user confirmation should code implementation begin.

Current Stage07 UI rule:

- First record the approved Mini App visual, responsive, safety and contract boundary in Stage07 design documents.
- Then require user review of the written specification and create a detailed implementation plan.
- Do not start frontend code until the plan is approved; do not implement proposed schema, API-contract or permission changes until they receive separate explicit user confirmation.

Stage02 to Stage05 documents remain historical evidence. They must not override the Stage06 platform-first source of truth.

## 6. Confirmed Technical Baseline

| Layer | Decision |
| --- | --- |
| Backend language | Python 3.12+ |
| Backend framework | FastAPI |
| ORM | SQLAlchemy 2.x |
| Migration | Alembic |
| Primary database | PostgreSQL |
| Generic record storage | PostgreSQL JSONB plus typed field metadata |
| Vector search | pgvector |
| Queue/cache | Redis |
| Agent orchestration | LangGraph-first |
| LLM provider | OpenRouter-compatible API with real Stage06 smoke required |
| Telegram | Bot API + Webhook + Mini App |
| Mini App frontend | React + Vite + TypeScript + Tailwind + shadcn/ui + lucide-react; implementation waits for separate user confirmation after backend readiness |

Changing this baseline requires a technical decision document and user confirmation.

## 7. Safety Boundaries

Digital employees may use backend-authorized tools. They must not receive raw database credentials, raw SQL access, external provider keys or unrestricted send rights.

Allowed:

- inspect table schema through authorized tools;
- read permitted records and views;
- summarize or classify permitted data;
- call real LLMs through LangGraph/OpenRouter only with permission-filtered context;
- create record-change drafts;
- update low-risk internal state through explicit backend services when permitted;
- create controlled notifications;
- after confirmation, call controlled backend tools with an execution ticket when such a capability is in scope;
- write audit events through backend services.

Forbidden:

- raw PostgreSQL access;
- unapproved SQL execution;
- bypassing Tool Gateway/service layer;
- bypassing user permission, chat scope or agent scope;
- self-confirming high-risk writes;
- treating Telegram identity as sufficient system permission;
- reading sensitive fields without field permission;
- claiming success without a persisted record, send log, execution log or audit event;
- broad Telegram group send, provider write, funds movement or account operation without explicit later-stage approval.

## 8. Development Rules

- Do not write business code before the relevant documents are written and confirmed.
- Each stage must have clear `Scope` and `Acceptance Criteria`.
- Do not split stage work into tiny fragments when a coherent delivery package is clearer.
- Keep changes scoped to the current stage.
- Update `Current Progress` when modifying active documents.
- If a workflow has no table endpoint, it cannot enter implementation.
- If a new scenario is proposed, define its workspace/base/table/fields/views/permissions/agent landing point first.
- Tests and acceptance must cite commands, evidence or manual verification notes.
- Do not claim production readiness without production readiness evidence.
- Stage06 pilot evidence should be Telegram-ecosystem productivity first, not advertising-agency first.
- Stage06 database smoke may use local PostgreSQL, but it must be real PostgreSQL and must not be counted as remote staging/production evidence.
- Stage06 digital employee acceptance requires at least one real LangGraph/OpenRouter LLM invocation when credentials are configured; deterministic backend tool gateway remains only a test and fallback mode.
- Do not implement the Mini App UI in the current backend-readiness pass. Backend must be connected first; UI begins only after the user explicitly confirms a separate UI phase.
- Temporary files, scripts, test data and artifacts created during a stage must be cleaned before deployment or documented as retained artifacts.

## 9. Architecture Reuse Rule

Prefer mature patterns and ecosystems:

- imitate Feishu Base product grammar and `larksuite/cli` capability organization;
- reuse LangGraph graph/state/checkpoint/human-in-the-loop/supervisor patterns;
- use OpenRouter through an OpenAI-compatible API style;
- use FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, JSONB, pgvector and Redis;
- do not self-invent a general agent framework, ORM, migration system, queue system or permission engine unless a document explains why.

## 10. Source Of Truth Order

1. User current explicit instruction.
2. This file `AGENTS.md`.
3. `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`.
4. `project-docs/03-modules/BITABLE_SCHEMA_BLUEPRINT.md`.
5. `project-docs/08-implementation/STAGE_06_SOURCE_OF_TRUTH.md` during Stage06.
5a. `project-docs/08-implementation/STAGE_07_SOURCE_OF_TRUTH.md`, `STAGE_07_MINI_APP_UI_DESIGN.md`, the approved F2 documents and the V1 Saved View Builder design/BDD/SDD/work-surface/index package during Stage07 design/planning.
6. `project-docs/00-governance/TECHNICAL_DECISIONS.md`.
7. Stage06 SDD, implementation plan, API/data/security contract and acceptance docs.
8. Historical Stage02 to Stage05 implementation documents.
9. Migration/original advertising-agency documents as background only.

## 11. Completion Rule

Any stage delivery summary must include:

- Changed files.
- What changed.
- Verification.
- Skipped tests.
- Remaining risks.
- Temporary cleanup.
