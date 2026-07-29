# Implementation Source Of Truth

## Status

- Document status: active source of truth
- Scope: 顶层产品目标、边界、阶段、技术基线、安全约束，以及当前 Stage11 多 Agent 协调运行时与工作台方向
- Current Progress: 2026-07-29 Stage11 coordination middleware is deployed on public r76 over the accepted Stage10 control plane. PostgreSQL remains the durable truth; Redis Streams carries registered read Specialists; SSE reauthorizes and projects safe events. Task Gateway decomposes multi-semantic Chinese requests into a DAG, Agent Registry fixes capability-to-skill/tool/risk bindings, Supervisor owns fan-out/fan-in terminal state, and Tool Gateway only creates pending drafts or blocked notification requests. A real isolated r75 48-case run completed 48/48 using production identity, PostgreSQL, Redis, SSE and `google/gemini-2.5-flash`, with permission/external-send safety at 1.00 and zero Telegram sends; r76 adds only atomic terminalization of unfinished sibling commands after required failure. Fresh backend verification covers 1561/1561 tests. This is not a quality acceptance: retrieval precision/recall and action accuracy remain below protocol gates, and public durable action orchestration is not yet enabled.

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
| Frontend target | Telegram Mini App first with a desktop-browser-compatible route; the Stage07 workspace foundation is delivered and the current approved extension is the Stage09 Codex-style conversation workbench |
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

## 7. Current Stage08/Stage09 Goal

Stage08/Stage09 turn the accepted platform backend into a usable, permission-safe collaboration workspace without changing the product constitution.

The current delivery chain is:

1. Stage08 permission-filtered context, memory, retrieval and collaboration runtime.
2. Stage09 native deployment and workspace interaction remediation.
3. Codex-style AI conversation workbench with a controlled SSE compatibility path.
4. Product-level browser evidence for a real read-only case.
5. Separately confirmed evidence for any real draft, import or table write.

The approved SSE work changes presentation and transport only. It retains the existing synchronous query route, identity resolution, workspace/employee/record intersection, idempotency, audit, `run_stage08_collaboration`, `validate_assistant_query_safe_view` and draft-confirmation boundary. It does not add a conversation-history database, raw model token streaming, hidden reasoning, new schema, new permission semantics or new external send authority.

On 2026-07-26 the user additionally required UI skill tabs to invoke corresponding backend LLM skills instead of acting as prompt-only shortcuts, and then explicitly approved `STAGE_09_LLM_SKILL_LAUNCHER_DESIGN.md`. The active implementation reuses the Stage06 manifest registry and adds a read-only skill catalog plus a versioned execution profile intersected with employee, caller, resource, record and chat permissions. The approval does not add database schema, deployment authority, external send authority or real-write authority.

Task5 has locally verified rendered Nginx transport contracts for the exact SSE route in the internal and public HTTPS templates. This evidence proves only the repository assets: it is not a deployed-host check, a browser acceptance result or authorization for an external write.

### Stage10 durable Agent control plane

On 2026-07-28 the user approved the architecture and implementation of a durable supervisor/sub-agent runtime. PostgreSQL is authoritative for runs and redacted control checkpoints; Redis Streams is at-least-once transport; database uniqueness, leases and idempotent transitions provide exactly-once effects. LangGraph continues with `checkpointer=None` in v1 so private prompts, retrieved records and model output are not serialized into checkpoints.

The first activation slice contains only `platform.tabular.analyse`, a read-only Specialist that reuses the existing Stage08 permission, skill selection, LangGraph/OpenRouter, idempotency and safe-view contracts. Browser SSE is a permission-rechecked projection and not the internal event bus. Stage10 does not authorize arbitrary delegation, direct table writes, self-confirmed drafts, Telegram sends or production traffic.

### Stage11 coordination middleware

Stage11 extends the Stage10 run/command/event/checkpoint model rather than creating another Agent framework. A deterministic Task Gateway identifies multiple objectives in one request and creates a registered capability DAG. The Agent Registry owns capability, command, schema version, failure policy, allowed tools, write boundary and fixed execution-skill binding. Supervisor alone owns run terminal state and waits for every required child command; optional failures produce an explicit degraded result.

`platform.tabular.analyse`, `platform.risk.analyse` and `platform.daily.summarise` are durable Redis-stream commands. `platform.action.propose` is currently evaluated through a post-read backend adapter with an already permission-filtered target/field allowlist; it is not yet a fourth public durable command. Tool Gateway can persist only `pending_confirmation` drafts or `blocked` notification requests and cannot confirm, update a business record, or send Telegram messages.

The r75 real 48-case report is the current evidence source. Its successful runtime and safety results must be preserved together with its failed quality metrics. The next stage must improve retrieval/grounding before changing the scorer, then define and approve an explicit action-slot and authorized-candidate API before adding a durable action worker or UI contract.

## 8. Historical Stage Documents

Stage02 to Stage05 remain useful implementation history:

- Stage02: backend kernel, early bitable-like views, draft/confirmation, mock Telegram/provider.
- Stage03: real Telegram webhook, binding and Redis worker path.
- Stage04: binding management and restricted test send.
- Stage05: real OpenRouter, LangGraph supervisor, draft Agents, controlled private test send, staging safety close.

They are not the current product definition.

## 9. Current Non-Goals

The current Stage09 AI conversation slice does not include:

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

The current implementation entry is:

- [Current root handoff](../../../HANDOFF.md)
- [Project structure and document lifecycle](PROJECT_STRUCTURE_AND_DOCUMENT_LIFECYCLE.md)
- [Stage09 Codex-style AI conversation design](../08-implementation/STAGE_09_CODEX_STYLE_AI_CONVERSATION_DESIGN.md)
- [Stage09 Codex-style AI conversation implementation plan](../08-implementation/STAGE_09_CODEX_STYLE_AI_CONVERSATION_IMPLEMENTATION_PLAN.md)
- [Approved Stage09 LLM skill launcher design](../08-implementation/STAGE_09_LLM_SKILL_LAUNCHER_DESIGN.md)
- [Stage09 SSE transport task evidence](../08-implementation/evidence/stage09-codex-ai-conversation-sse-2026-07-26.md)
- [Stage09 UI functional remediation plan](../08-implementation/STAGE_09_UI_FUNCTIONAL_REMEDIATION_PLAN.md)
- [Stage09 r40 regression and live-readiness evidence](../08-implementation/evidence/stage09-r40-regression-and-live-readiness-2026-07-26.md)
- [Stage10 Agent event-runtime architecture](../02-architecture/AGENT_EVENT_RUNTIME_PROPOSAL.md)
- [Stage10 implementation and acceptance](../08-implementation/STAGE_10_AGENT_EVENT_RUNTIME_ACCEPTANCE.md)
- [Stage11 coordination middleware architecture](../02-architecture/STAGE_11_MULTI_AGENT_COORDINATION_MIDDLEWARE.md)
- [Stage11 complex Chinese evaluation protocol](../08-implementation/STAGE_11_COMPLEX_CHINESE_EVALUATION_PROTOCOL.md)
- [Stage11 implementation and acceptance](../08-implementation/STAGE_11_ACCEPTANCE.md)
- [Stage11 r75 real 48-case report](../08-implementation/evidence/stage11-r75-real-48case-report-2026-07-28.md)

## 11. Confirmation Rule

User confirmation is required before:

- changing the technical baseline;
- changing the platform resource model;
- changing permission semantics;
- changing schema or API contracts;
- enabling real external provider writes;
- enabling broad or customer-facing Telegram sends;
- bypassing the approved Stage09 design or implementation plan;
- treating a local/API/provider smoke as product-level browser acceptance;
- treating the Stage09 native deployment as authorization for new production writes.
