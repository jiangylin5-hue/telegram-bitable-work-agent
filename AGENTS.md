# AGENTS.md

## Status

- Current Progress Update (2026-07-31, bounded Composer real campaign): Human Gold remains `48/48` with manifest hash `5b959d049c4f46f9dbd92e65c1dfe17a81a357f394f2f9a33b34da4e6ee28114`. The approved bounded deterministic-section contract is implemented locally and one new independent real `48 × 3` campaign completed with release `FAIL`. Returned-answer integrity improved to `48/48` in every round and all seven final-answer dimensions are `1.0`; `mixed_02`/`mixed_08` no longer collapse. Retrieval Recall@20 remains `1.0`. Composer unavailable is `36/48`, `47/48`, `37/48`, dominated by `240` schema-invalid attempts, and total-latency P95 worst is `13775.8 ms`; confirmed/write/send remain `0/0/0`. Current bundle hash: `6b15446524a5a084d744dfc82564a73354d1477260c8e2e705375e9c392f1aa8`; pre-correction bundle `1642b7ff5124f710477033b6d29c76a2328f0b57d976971723f2d9f515cb13e6` remains immutable history. Stage12 is local, undeployed, inactive and not finally accepted. No further full campaign is authorized until a focused Provider-schema compatibility direction is documented and approved.

- Document status: active project collaboration rule
- Scope: Generic Telegram-first multidimensional table, no-code workspace and table-bound digital employee platform
- Previous local-audit snapshot: Tasks 1–9/Task9B, HG-01–HG-10 and ISO-01 were implemented before Human Gold and the real campaign; its earlier counts are superseded by the later Current Progress Update above.

## Current Handoff

- New sessions must read root `HANDOFF.md`, `project-docs/08-implementation/STAGE_12_COMPREHENSIVE_ARCHITECTURE_AUDIT.md`, `project-docs/02-architecture/stage12-quality-v2/README.md` and `project-docs/02-architecture/stage12-quality-v2/08_DELIVERY_TEST_AND_ACCEPTANCE.md` before extending Stage12. Historical A–F acceptance documents no longer override the comprehensive audit.
- The current production implementation is still Stage11/r76. Stage12-A–F and the bounded Composer correction are local-only and not finally accepted. Human Gold and the required post-correction real campaign are complete, but Provider availability and latency still fail. The next gate is a separately approved focused Provider-schema compatibility correction or acceptance-contract decision; do not run another `48 × 3` campaign first.
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

Current Stage11 coordination rule:

- `project-docs/02-architecture/STAGE_11_MULTI_AGENT_COORDINATION_MIDDLEWARE.md` and `project-docs/08-implementation/STAGE_11_COMPLEX_CHINESE_EVALUATION_PROTOCOL.md` define the implemented control-plane and evaluation boundary.
- Task Gateway may decompose one query into multiple objectives, but only registered capabilities can become commands; capability-to-skill binding is fixed server-side.
- PostgreSQL remains authoritative and Redis Streams remains transport. SSE is a safe browser projection, not the Agent-to-Agent protocol.
- Read capabilities are durable commands. Action proposals remain constrained by an authorized target/field allowlist and can only create pending or blocked artifacts through Tool Gateway.
- The r75 48-case report proves runtime and safety behavior but does not pass the retrieval/action quality gates or prove autonomous public action-slot selection.

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
