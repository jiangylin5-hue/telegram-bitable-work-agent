# Stage 06 LarkSuite Benchmark Audit

## Status

- Document status: active Stage06 benchmark audit
- Scope: Stage06 planning reference for a generic Feishu-like no-code multidimensional table workspace and table-agent platform.
- Current Progress: 2026-07-09 Created after user confirmed the product pivot from an advertising-agency-specific tool to a generic platform. This audit uses the official `larksuite/cli` repository and Feishu/Lark public product/API/AI documentation as benchmark sources, while explicitly excluding the Stage05 LarkSuite documents because they were written under the advertising-agency scenario.

## 1. Confirmed Direction

Stage06 should move the project toward:

```text
Generic multidimensional table platform
-> no-code workspace
-> templates and import
-> Telegram Mini App entry
-> @ digital employees based on tables/views/permissions
-> draft confirmation and audit
-> production-like pilot
```

This means Stage06 is not a continuation of an advertising-agency-only product. The advertising-agency workflow becomes one official template or sample workspace, not the product constitution.

Confirmed user decisions:

- The final product form is closer to Feishu Base: a universal multidimensional table and no-code workspace for many business scenarios.
- Telegram remains the main entry. Telegram Mini App is the main UI, and Bot/group `@` mentions are digital-employee entry points.
- The project is isolated from Feishu/Lark. We should imitate and reuse product patterns, modules, templates and capability structure, but we do not integrate Feishu APIs or aim for Feishu API compatibility.
- Stage06 should be close to formal launch, but still treated as a production-like pilot rather than production cutover.
- Stage06 tasks should be large, coherent delivery packages. Do not split them into overly fine tasklets that slow execution.

## 2. Source Boundary

### 2.1 Sources Used

- [`larksuite/cli`](https://github.com/larksuite/cli): official Lark/Feishu CLI repository maintained by the LarkSuite team.
- [`larksuite/cli` `lark-base` skill](https://raw.githubusercontent.com/larksuite/cli/main/skills/lark-base/SKILL.md): Base operation skill covering table, field, record, view, statistics, formula, lookup, form, dashboard, workflow and permissions.
- [Lark/Feishu CLI official documentation](https://open.larksuite.com/document/mcp_open_tools/feishu-cli-let-ai-actually-do-your-work-in-feishu): official description of using CLI as an AI-operable gateway for Feishu/Lark work.
- [Feishu Base product page](https://www.feishu.cn/product/base): official positioning of Base as an AI-driven table and business-system building platform.
- [Feishu Open Platform Bitable overview](https://open.feishu.cn/document/server-docs/docs/bitable-v1/bitable-overview?lang=zh-CN): official API overview for Base/Bitable.
- [Feishu Base AI Agent workflow node](https://www.feishu.cn/hc/zh-CN/articles/643175485940-%E4%BD%BF%E7%94%A8%E5%B7%A5%E4%BD%9C%E6%B5%81%E7%9A%84-ai-agent-%E8%8A%82%E7%82%B9): official AI Agent node reference for Base workflows.
- [Feishu Base AI field shortcuts](https://www.feishu.cn/hc/zh-CN/articles/464880997049-%E4%BD%BF%E7%94%A8%E5%A4%9A%E7%BB%B4%E8%A1%A8%E6%A0%BC-ai-%E5%AD%97%E6%AE%B5%E6%8D%B7%E5%BE%84): official AI field shortcut reference.

### 2.2 Sources Not Used

- Stage05 LarkSuite documents in this project are not used as product benchmark input for Stage06 because they were produced under the old advertising-agency framing.
- Airtable, Notion, Coda and other competitors are excluded from this audit by user decision.
- Feishu internal/private behavior is not assumed unless it is visible in official public material or the public `larksuite/cli` repository.

## 3. Benchmark Summary

The key lesson from Feishu Base and `larksuite/cli` is not a single feature. It is the product grammar:

```text
base/app
-> block/page/resource directory
-> table
-> field schema
-> record values
-> view/form/dashboard/workflow
-> role/permission
-> AI skill/shortcut/agent action
```

For this project, the equivalent Stage06 grammar should be:

```text
workspace
-> base
-> table
-> field schema
-> record JSONB values
-> view/form/dashboard-lite/import/template
-> workspace/base/table/view/field/action permission
-> digital employee skill/action manifest
-> draft confirmation
-> audit event
```

## 4. `larksuite/cli` Findings

### 4.1 Agent-Native Command Surface

The official CLI is built for both humans and AI Agents. Its README positions the CLI as a gateway over multiple business domains, including Messenger, Docs, Base, Sheets, Calendar, Tasks, Mail, Approval and more. For Base specifically, it covers tables, fields, records, views, dashboards, workflows, forms, roles and permissions.

Stage06 implication:

- Our platform should not expose table-agent capability as ad hoc prompt code.
- We should define an explicit capability surface for digital employees, similar to a command/skill manifest:

```text
capability
-> required context
-> allowed tables/views
-> allowed actions
-> output schema
-> confirmation policy
-> audit events
-> recovery rules
```

### 4.2 Three-Layer Operation Model

The CLI uses a layered operation model:

- human/AI-friendly shortcuts;
- platform-synced API commands;
- raw API access for full coverage.

Stage06 should copy the layering idea, not the Feishu API:

| Benchmark layer | Stage06 equivalent |
| --- | --- |
| Shortcuts | product-level user actions, such as create base from template, import table, ask digital employee, confirm draft |
| API commands | internal service methods with stable request/response contracts |
| Raw API | reserved admin/dev API, not exposed to normal agents |

Agents should normally call product-level tools, not raw database operations.

### 4.3 Base Skill Structure

The `lark-base` skill routes work by resource and risk:

- base discovery and URL/title resolution;
- table lifecycle;
- field lifecycle and field JSON;
- record read/write/upsert/batch write;
- record search and data query;
- formula and lookup field guidance;
- form detail and form submit;
- view filters and view configuration;
- dashboard blocks and chart data;
- workflow steps;
- role and advanced permissions;
- confirmation gates for destructive actions.

Stage06 implication:

- The generic platform should have module boundaries around the same resource model.
- A digital employee should always be able to explain which base/table/view/record/action it is operating on.
- Destructive operations and external messages must require confirmation and audit.

### 4.4 JSON Output, Dry Run And Schema Introspection

The CLI emphasizes structured output, dry-run previews and schema introspection. These are agent-friendly controls, not only developer conveniences.

Stage06 implication:

- Agent tools should return stable structured envelopes, for example:

```json
{
  "ok": true,
  "action": "record_change_draft.create",
  "resource": {
    "workspace_id": "wrk_x",
    "base_id": "base_x",
    "table_id": "tbl_x",
    "record_id": "rec_x"
  },
  "draft_id": "draft_x",
  "confirmation_required": true,
  "audit_event_id": "audit_x"
}
```

- Every write-like action should support preview/draft behavior before commit.
- Schema introspection should be a first-class tool for both UI builders and digital employees.

### 4.5 Security Warnings

The official CLI warns that AI Agents operating under user identity can create permission, leakage and unauthorized-operation risks.

Stage06 implication:

- Keep the existing safety stance: agents do not receive raw database credentials, raw SQL access, provider keys or unrestricted send rights.
- Effective agent scope must be the intersection of:

```text
agent_configured_scope
∩ caller_user_scope
∩ telegram_chat_scope
```

- Agent writes should default to draft-confirmation:

```text
Agent proposes change
-> record_change_draft
-> user confirms in Mini App or Telegram
-> backend writes record
-> audit event
```

## 5. Feishu Base Product Findings

### 5.1 Base Is A Business-System Builder

Feishu Base is positioned as more than a spreadsheet. It combines structured data, multiple views, collaboration, dashboards, forms, automation and AI into a business-system building platform.

Stage06 implication:

- The product should be defined as a universal workspace builder.
- Existing advertising operations are no longer the top-level product scenario.
- Top-level docs must be rewritten to prevent misleading future implementation.

### 5.2 App/Page/Block Mental Model

Feishu Base uses an application-like mental model: a Base can contain data tables, forms, dashboards, pages and other resources. `larksuite/cli` also exposes a `base-block` style resource directory.

Stage06 implication:

- The backend model should allow a base to contain multiple resource types, even if Stage06 only implements part of them.
- Minimal Stage06 resource set:

```text
workspace
base
table
field
record
view
form-lite
dashboard-lite
template
digital_employee
automation/reserved workflow
```

### 5.3 Field And View Breadth

Feishu Base relies on field schemas and view configuration as the core no-code layer.

Stage06 should implement a practical generic field set:

- text
- number
- date
- status
- single_select
- multi_select
- user
- checkbox
- url
- email
- phone
- json
- linked_record
- lookup

Stage06 should reserve but not fully implement:

- formula engine
- attachment storage and preview
- full workflow builder

Stage06 view scope:

- grid/table
- kanban
- calendar
- form-lite

Dashboard should be designed as `dashboard-lite` or reserved metadata unless needed for the pilot.

### 5.4 AI Field Shortcuts And Workflow AI Agent Node

Feishu's AI capabilities show two important patterns:

- AI can be embedded into fields or field shortcuts, turning unstructured input into structured values.
- AI Agent nodes can run inside workflows and use Base context to generate structured outputs.

Stage06 implication:

- Digital employees should be table-bound and context-bound, not generic chatbots.
- Stage06 should support digital employees created from a base/table/view with:

```text
name
description
accessible tables/views
allowed actions
response style
confirmation policy
@ alias
```

- Digital clone/persona should be designed as a future extension, not Stage06 core.

## 6. Stage06 Product Capability Map

| Product area | Benchmark reference | Stage06 recommendation |
| --- | --- | --- |
| Workspace/base | Feishu Base app model | Implement generic `workspace -> base -> table` model. |
| Tables/fields | Base table and field schema | Implement generic schema with JSONB record values and typed field metadata. |
| Records | Base record APIs and record upsert/search patterns | Implement create/read/update/delete through backend services, with draft-first agent writes. |
| Views | Base table/kanban/calendar/form views | Implement grid/table, kanban, calendar and form-lite. |
| Forms | Base form submit and question model | Implement form-lite for data collection and import/pilot scenarios. |
| Dashboard | Base dashboard blocks | Reserve `dashboard-lite` model; only implement if pilot needs visible charts. |
| Workflow | Base workflow and AI Agent node | Reserve workflow engine; Stage06 can support controlled status advancement and notifications. |
| Import | Feishu import to bitable pattern | Implement CSV and Excel import with type inference, preview confirmation and save-as-template. |
| Templates | Feishu app-building/product templates | Implement official template system with generic templates plus advertising-agency sample. |
| Permissions | roles/advanced permissions | Implement workspace/base/table/view/field/action permissions and field masking. |
| Digital employees | CLI skills and Base AI Agent node | Implement table-bound digital employees with skill/action manifests, @ mention routing and draft-confirmation writes. |
| Audit | CLI safety and project constitution | Keep audit events for every agent decision, draft, confirmation, write and controlled message. |

## 7. Stage06 Required Imitation Principles

Stage06 should imitate these Feishu/Lark patterns:

1. Base-first information architecture.
2. Generic table/field/record/view model before any vertical scenario.
3. Templates as installable starting points, not hardcoded business logic.
4. Agent capabilities as skills/action manifests, not hidden prompt branches.
5. Schema introspection before record writes or analysis.
6. Draft/dry-run/confirmation for write and send operations.
7. Permission intersection for user, chat and digital employee.
8. Structured outputs and audit-friendly evidence.
9. Import and save-as-template as a core adoption path.
10. Workflow and dashboard as reserved product surfaces, not forced Stage06 blockers.

## 8. Stage06 Recommended Delivery Packages

Stage06 should be organized into five large packages:

### Package 1: Platform Source Of Truth Rewrite

Rewrite active top-level truth documents from advertising-agency-specific to platform-first.

Required outputs:

- Project-level `AGENTS.md` product positioning update.
- `IMPLEMENTATION_SOURCE_OF_TRUTH.md` platform-first rewrite.
- Product brief rewrite.
- Generic Bitable blueprint rewrite.
- Business scenarios index converted into templates/scenarios index.
- Agent index converted into digital-employee platform index.
- Explicit note that Stage02 to Stage05 remain historical implementation evidence.

Acceptance:

- No active top-level document should claim the project is primarily an advertising-agency tool.
- Advertising workflow is described as an official template/sample only.
- Stage06 source of truth can reference this benchmark audit.

### Package 2: Generic Bitable Core

Implement or refactor the core model toward a generic multidimensional table platform.

Required outputs:

- `workspace`, `base`, `table`, `field`, `record`, `view` model.
- JSONB-backed generic record values.
- typed field metadata.
- linked record and lookup design.
- grid/table, kanban, calendar and form-lite views.
- schema introspection API for UI and agents.

Acceptance:

- A user can create a base without choosing an advertising template.
- A user can create a table, add fields, add records and switch views.
- A digital employee can inspect schema before answering or drafting changes.

### Package 3: Template And Import System

Build the adoption path for non-technical users.

Required outputs:

- CSV import.
- Excel import.
- import preview with type inference and manual correction.
- save imported base/table as template.
- official templates: CRM/customer management, project/task, customer service/ticket, inventory/asset.
- advertising-agency template retained as a weak official sample.

Acceptance:

- A user can import a spreadsheet, confirm field types, create a base and save it as a reusable template.
- The template list does not make advertising operations look like the default product.

### Package 4: Telegram Mini App And Digital Employee Runtime

Make Telegram the main entry without making Telegram chat the only product surface.

Required outputs:

- Telegram Mini App workspace/base/table UI for pilot flows.
- Desktop-browser-compatible frontend route for complex building/import.
- Bot/group `@digital_employee` routing.
- digital employee config: name, description, accessible tables/views, allowed actions, response style, confirmation policy and alias.
- effective permission intersection:

```text
agent_configured_scope
∩ caller_user_scope
∩ telegram_chat_scope
```

- agent actions:
  - query and summarize;
  - create/update record drafts;
  - process queues or advance statuses;
  - controlled messages/notifications.

Acceptance:

- A user can create or configure a digital employee based on a base/table.
- Mentioning a digital employee from Telegram uses the correct base/chat/user context.
- Any write-like action creates a draft and requires confirmation before commit.

### Package 5: Production-Like Pilot Acceptance

Stage06 should end with a pilot that feels close to launch, but does not silently become production.

Required outputs:

- pilot workspace with at least one generic template and one imported table.
- Telegram Mini App flow:

```text
Telegram entry
-> Mini App
-> generic base/table
-> template or import
-> digital employee
-> permission check
-> draft confirmation
-> audit event
-> safety close
```

- controlled staging configuration.
- kill switch for sends, external writes and agent execution.
- acceptance report with evidence.

Acceptance:

- The full path works in a real or production-like pilot environment.
- No real external provider write or broad group send is allowed without explicit later approval.
- The project is ready for a Stage07 production-hardening or launch decision.

## 9. Explicit Stage06 Non-Goals

Stage06 should not include:

- Feishu/Lark API integration.
- Feishu API compatibility.
- direct code copy from `larksuite/cli`.
- using Stage05 LarkSuite documents as Stage06 benchmark truth.
- full formula engine.
- full attachment storage/preview.
- full workflow builder.
- full dashboard builder.
- digital clone/persona runtime.
- real external provider writes without a separately confirmed production execution plan.

## 10. Risks And Controls

| Risk | Impact | Control |
| --- | --- | --- |
| Old advertising docs continue to guide implementation | New generic platform gets polluted by vertical logic | Package 1 must happen before code implementation. |
| Over-imitation of Feishu API | Platform becomes constrained by an external product we do not integrate | Copy product grammar and module boundaries only, not API compatibility. |
| Stage06 becomes too broad | Near-launch pilot slips | Keep five large delivery packages and defer full formula/attachment/workflow/dashboard/persona. |
| Agent permissions become confusing | Data leakage or unauthorized writes | Use permission intersection and draft-confirmation as mandatory rules. |
| Import creates messy schemas | Users lose trust during first onboarding | Require type inference preview and manual correction before commit. |
| Digital employees become generic chatbots | Product loses table-first constitution | Require every digital employee action to name base/table/view/record/action and audit event. |

## 11. Recommended Next Step

Before writing Stage06 implementation docs or code, update the active top-level project truth:

```text
AGENTS.md
IMPLEMENTATION_SOURCE_OF_TRUTH.md
product brief
BITABLE_SCHEMA_BLUEPRINT.md
BUSINESS_SCENARIOS_INDEX.md
AGENTS_INDEX.md
```

After that rewrite is confirmed, write the Stage06 source of truth, SDD, BDD, implementation plan, API/database/permission design and acceptance checklist as one platform-first document package.
