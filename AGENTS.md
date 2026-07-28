# AGENTS.md

## Status

- Document status: active project collaboration rule
- Scope: Generic Telegram-first multidimensional table, no-code workspace and table-bound digital employee platform
- Current Progress: 2026-07-28 Stage10 read-only Agent event runtime is implemented, deployed and accepted on public artifact `stage09-p1-20260728-r66-conversation-routing`. PostgreSQL owns run/checkpoint/command/artifact/event/outbox state and short-lived AES-GCM private inputs; independent publisher/specialist services use Redis Streams with lease, fencing, idempotency and XAUTOCLAIM recovery; SSE reauthorizes and projects safe events only. The React workbench now keeps automatic queries as `mixed`, exposes mutually exclusive `aria-pressed` skill state and never replaces the user's query with skill copy; the backend alone recognizes bounded pure greetings while greeting-plus-business text still performs table retrieval. Fresh evidence: 1537 backend Unit+API tests, 71 server API tests, 79 Mini App files/411 tests, production build and exact static parity, production Alembic head `20260728_0034`, real Redis/PostgreSQL/OpenRouter 20-case Chinese evaluation with 100% skill hit/precision/recall/readiness/answer accuracy, and public browser verification with zero application console errors. Telegram send, automatic draft confirmation, business-record writes and unrestricted Agent capabilities remain excluded.

## Current Handoff

- New sessions must read root `HANDOFF.md`, `project-docs/08-implementation/STAGE_10_AGENT_EVENT_RUNTIME_ACCEPTANCE.md` and its linked r66 evidence before extending the Agent runtime.
- The current confirmed implementation is the deployed Stage10 read-only distributed runtime; Stage08 remains the compatibility and draft-confirmation path. New capabilities require a new documented stage and must not broaden write authority implicitly.
- Branch/worktree ownership, document tiers, retention and generated-artifact cleanup follow `project-docs/00-governance/PROJECT_STRUCTURE_AND_DOCUMENT_LIFECYCLE.md`. `.superpowers/` is execution scratch and must remain Git-ignored.

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

Current Stage09 AI conversation rule:

- The Codex-style workbench design, SSE API boundary and implementation plans are approved; implementation is in progress and must keep its reviewed scope.
- Implementation must begin with failing tests and must reuse the existing Stage08 identity, scope, permission, idempotency, audit and collaboration services.
- The current approval does not authorize schema changes, permission-model changes, persistent chat history, raw model-token/reasoning exposure, deployment or real external/business writes.
- Deployment and any real draft, import, table or Telegram write remain separate action-level gates.

Current Stage10 Agent event-runtime rule:

- The approved architecture and detailed implementation boundary are defined by `project-docs/02-architecture/AGENT_EVENT_RUNTIME_PROPOSAL.md` and `project-docs/08-implementation/STAGE_10_AGENT_EVENT_RUNTIME_ACCEPTANCE.md`.
- PostgreSQL is the durable truth; Redis Streams is at-least-once transport only. Exactly-once effects rely on database uniqueness, leases and idempotent state transitions.
- LangGraph private state remains in memory with `checkpointer=None` in v1. Durable checkpoints contain redacted control fields only.
- The first capability is read-only `platform.tabular.analyse`. Draft, write, external-send and generic delegation capabilities are not enabled.
- Stage10 traffic remains feature-flagged until full local recovery, security and browser acceptance pass; deployment remains a separate confirmation gate.

Stage02 to Stage08 documents remain historical or accepted implementation evidence according to the active indexes. They must not override the current top-level source of truth and handoff.

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
| Mini App frontend | React + Vite + TypeScript + Tailwind + shadcn/ui + lucide-react; Stage07 workspace foundation is delivered and the current approved work is the Stage09 conversation surface |

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
- The Stage09 SSE route and synchronous assistant route must share authorization, scope, idempotency, audit and execution services.
- The frontend may render only the approved event allowlist and the final validated `SafeView`; hidden reasoning, raw tool output and raw group content remain forbidden.
- Stage10 checkpoints, commands, artifacts, events, outbox messages and SSE must not persist or expose raw queries, prompts, provider responses, retrieved record values, credentials or private LangGraph state.
- Deployment and real draft/import/table/Telegram writes require their own current evidence and confirmation gates.
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
4. `project-docs/00-governance/PROJECT_STRUCTURE_AND_DOCUMENT_LIFECYCLE.md` for branch/worktree/document ownership.
5. Root `HANDOFF.md` and the authoritative handoff it names.
6. `project-docs/03-modules/BITABLE_SCHEMA_BLUEPRINT.md`, `project-docs/05-data/PERMISSION_AND_SECURITY_MODEL.md` and `project-docs/00-governance/TECHNICAL_DECISIONS.md`.
7. The current Stage design, implementation plan, detailed TDD plan and current evidence named by the handoff.
8. Historical Stage source/design/contract/acceptance/evidence documents when the current task touches their owned resources.
9. Migrations and original advertising-agency documents as history or template background only.

## 11. Completion Rule

Any stage delivery summary must include:

- Changed files.
- What changed.
- Verification.
- Skipped tests.
- Remaining risks.
- Temporary cleanup.
