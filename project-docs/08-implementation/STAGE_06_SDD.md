# Stage 06 SDD

## Status

- Document status: active Stage06 software design document
- Scope: Backend architecture for generic Bitable core, templates/import, digital employees, real LLM runtime, Telegram backend entry and pilot safety
- Current Progress: 2026-07-10 The approved security-hardening design is implemented. Identity resolution, workspace-member authorization, tenant invariants, lookup/audit redaction, server-controlled notification safety, bounded imports, cursor pagination, idempotency and additive PostgreSQL guards passed unit, API and real local PostgreSQL verification.

## 1. Architecture Overview

```text
Telegram Bot/Webhook or Backend Smoke
        |
        v
Telegram Context Resolver
        |
        v
Workspace/Base Permission Layer
        |
        +--> Generic Bitable API
        |       -> workspace/base/table/field/record/view services
        |
        +--> Import/Template Services
        |       -> import preview/commit, template install/save
        |
        +--> Digital Employee Runtime
                -> schema introspection
                -> permission-filtered record tools
                -> deterministic fallback
                -> LangGraph/OpenRouter live runtime
                -> record_change_draft / notification_request
                -> audit
```

The Stage06 architecture adds a generic platform module while preserving existing Stage02-05 capabilities as historical code and template input.

Mini App/Desktop UI is a future consumer of these APIs. It must not be implemented during the current backend-readiness pass.

## 2. Module Boundaries

| Module | Responsibility |
| --- | --- |
| Platform Identity | Workspace members, Telegram bindings, user/chat/base context |
| Generic Bitable Core | Bases, tables, fields, records, links, views and forms |
| Permission Service | Workspace/base/table/view/field/action filtering |
| Import Service | CSV/Excel parse, type inference, preview, commit |
| Template Service | Template manifests, install, save-as-template |
| Digital Employee Runtime | Configured employees, tool gateway, LangGraph orchestration and live LLM calls |
| Draft Confirmation | Record-change drafts and confirmation commit |
| Notification Service | Controlled Telegram/in-app notifications |
| Audit Service | Durable evidence for all material actions |
| Local PostgreSQL Smoke | Alembic upgrade validation against real local PostgreSQL |
| Future Mini App/Desktop UI | Deferred workspace, table, import, template, employee and confirmation screens |

## 3. Data Flow: Create Table From Scratch

```text
API caller or future UI opens workspace context
-> create workspace/base
-> create table
-> add fields
-> create default grid view
-> create records
-> audit created resources
```

## 4. Data Flow: Import

```text
Submit CSV/Excel content
-> create import_job
-> parse header and sample rows
-> infer field types
-> return preview
-> caller confirms or corrects mapping
-> create base/table/fields/records
-> audit import commit
```

## 5. Data Flow: Template Install

```text
Caller selects template
-> validate template manifest
-> create base
-> create tables/fields/views/sample records
-> create optional digital employees only if included later
-> write template_installation resource map
-> audit
```

## 6. Data Flow: Digital Employee Invocation

```text
Telegram @ mention or backend API invoke
-> resolve Telegram user/chat if present
-> resolve workspace/base/default employee
-> compute effective scope
-> inspect schema
-> read permission-filtered records
-> choose deterministic fallback or live LangGraph/OpenRouter
-> answer or create draft
-> AgentRun evidence
-> audit
```

For write-like actions:

```text
digital employee output
-> record_change_draft
-> user confirms
-> permission re-check
-> record write
-> audit event
```

## 7. Live LLM Runtime Design

Live mode must be built as a thin LangGraph wrapper around permission-filtered backend tools:

```text
prepare_context node
-> call_openrouter node
-> validate_structured_output node
-> produce_answer_or_draft node
```

Rules:

- LLM context contains only permitted schema fields and view records.
- LLM never receives raw database credentials or raw SQL access.
- LLM output must be a JSON object.
- Summaries return answer text and citations to table/view/record identifiers.
- Draft proposals must pass backend field validation and become `record_change_draft`.
- Invalid output creates a failed AgentRun/audit event and no draft commit.
- Deterministic gateway remains the default test/fallback path.

## 8. Telegram Backend Entry

The current pass validates backend Telegram entry without requiring UI:

```text
test bot/update or direct backend smoke payload
-> Telegram binding lookup
-> alias resolution
-> effective scope intersection
-> digital employee invocation
-> response/audit evidence
```

If real Telegram credentials are not configured, the smoke script must report a clear skipped/blocker state instead of claiming real entry success.

## 9. Permission Design

Every read/write path must call the permission service.

Required checks:

- workspace membership;
- base access;
- table access;
- view access;
- field read/write/mask;
- record scope;
- action permission;
- digital employee configured scope;
- Telegram chat scope.

## 10. Error Handling

| Error | Behavior |
| --- | --- |
| Unknown Telegram binding | safe binding/onboarding response and audit |
| Missing workspace permission | 403 plus audit |
| Field hidden | omit from response and Agent context |
| Import parse failure | keep import_job failed with redacted error |
| Type inference uncertainty | require user correction before commit |
| OpenRouter credentials missing | live smoke reports blocked/skipped, deterministic tests still run |
| Agent output schema invalid | reject output, no draft commit, failed AgentRun/audit |
| Draft confirmation stale version | reject with conflict, require reload |
| Notification blocked by safety switch | mark blocked and audit |
| Local PostgreSQL unavailable | migration smoke reports concrete blocker |

## 11. Observability

Stage06 must preserve:

- `trace_id` on Telegram, API, Agent, draft and audit paths;
- structured AgentRun summaries;
- model provider/model name/usage for real LLM calls;
- import job status;
- template installation resource map;
- audit events for permission and write paths;
- safety switch readback.

## 12. Future Frontend Design Boundary

Future Stage06 UI should be utilitarian and workspace-first:

- no marketing landing page as the main screen;
- show workspace/base/table immediately after login/context resolution;
- stable table dimensions and predictable controls;
- Mini App first, desktop compatible;
- import/template/employee configuration usable in desktop width.

This boundary is retained for the future UI phase only.

## 13. Stage06 Out Of Scope For Current Pass

- Mini App frontend implementation;
- full formula execution engine;
- full attachment preview/storage;
- full dashboard builder;
- full workflow automation builder;
- digital clone/persona;
- production launch;
- uncontrolled external sends or provider writes;
- advertising-agency-first pilot flow.

## 14. Security Hardening Architecture

### 14.1 Identity Boundary

Stage06 routes use a replaceable request-identity adapter. `local` and `test` may use the explicit `X-Stage06-User-Id` development adapter. `staging` and `production` must reject that adapter and fail with `401` unless a verified identity adapter is configured.

The request identity supplies only a stable user id and source. The effective role is always loaded from an active `workspace_members` row. Telegram mentions resolve the caller through a binding that references a concrete workspace member.

### 14.2 Authorization Boundary

```text
verified identity
-> resolve resource workspace
-> active workspace member
-> role/action permission
-> base/table/view/record scope
-> field read/write/mask policy
-> digital employee scope
-> Telegram scope when present
```

An empty digital employee table/view scope grants no resource access. Resource ids in a request must belong to the same workspace/base chain before any data is read or written.

### 14.3 Audit And Notification Boundary

Audit events store identifiers, field keys, counts, versions and safe statuses, not raw record values, import rows, notification bodies, Telegram raw text or LLM raw payloads. Audit readback is owner/admin only, paginated and sanitized.

Notification policy is derived from server settings and may only be narrowed by request policy. Default mode is `disabled`; confirmation never bypasses server mode or allowlist, and Stage06 adds no real sender.

### 14.4 Import, Pagination And Idempotency Boundary

Import parsing is bounded by decoded payload size, row count, column count and cell size. View-record, draft, notification and audit lists use cursor pagination with default 50 and maximum 200 items. Multi-resource mutations use an `Idempotency-Key` record and PostgreSQL row locks to prevent duplicate commits.

The detailed approved design is [Stage06 Security Hardening Design](../../docs/superpowers/specs/2026-07-10-stage06-security-hardening-design.md).
