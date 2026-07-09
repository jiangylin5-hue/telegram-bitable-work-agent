# Stage 06 LarkSuite Skills Integration Design

## Status

- Document status: active Stage06 skills design and implementation boundary
- Scope: Project-native adaptation of the 27 official `larksuite/cli` skills, Stage06 skill layering, deterministic routing/matching and executable-tool boundary
- Current Progress: 2026-07-10 The approved core implementation is connected. All 27 source skills have project-native manifest coverage, 11 generic core skills are active, deterministic `skill_evidence` is stored in runtime evidence, the 5-case real OpenRouter smoke passed, and the 118-case deterministic hit-rate benchmark passes its gates. This does not mean all 27 skills have executable backend tools or that LLM reranking is implemented.

## 1. Purpose

Stage06 already moved the product from an advertising-agency-specific tool to a generic Feishu-like multidimensional table, no-code workspace and table-bound digital employee platform.

The next recommended step is to introduce a project-native skills layer before expanding real LLM smoke tests. The goal is:

```text
user input
-> context/resource detection
-> skill candidate selection
-> permission and scope filtering
-> LLM/tool execution with selected skill context
-> draft/answer/audit evidence
```

This should preserve the official `larksuite/cli` skill discipline as much as possible:

- each skill has a clear "when to use" boundary;
- each skill has explicit non-goals;
- identity, permission and high-risk action rules stay visible;
- write-like actions prefer preview/draft/confirmation;
- output is structured and auditable;
- large schema/reference details live behind the skill rather than inside prompts.

The adaptation must remain project-native:

- no Feishu/Lark API integration;
- no Feishu API compatibility target;
- no runtime dependency on `larksuite/cli`;
- no direct copy of official skill source into production code;
- no reintroduction of advertising-agency-specific skills as the platform default.

## 2. Sources

- Official skills directory: <https://github.com/larksuite/cli/tree/main/skills>
- Retrieval date: 2026-07-10
- Observed skills: 27
- Retrieval method: GitHub contents API plus raw `SKILL.md` reads for each skill.

The 27 observed skills are:

```text
lark-approval
lark-apps
lark-attendance
lark-base
lark-calendar
lark-contact
lark-doc
lark-drive
lark-event
lark-im
lark-mail
lark-markdown
lark-minutes
lark-note
lark-okr
lark-openapi-explorer
lark-shared
lark-sheets
lark-skill-maker
lark-slides
lark-task
lark-vc
lark-vc-agent
lark-whiteboard
lark-wiki
lark-workflow-meeting-summary
lark-workflow-standup-report
```

Stage05 skills documents are historical local references only. They are useful for learning what not to carry forward:

- do not keep advertising operations as the center;
- do not keep `recharge-draft`, `bm-invite-draft`, `card-binding-draft` and similar vertical skills as platform defaults;
- keep the manifest discipline, evidence shape and matching-test habit.

## 3. Integration Principle

Stage06 should use adapter-style preservation:

```text
official larksuite skill
-> project-native semantic equivalent
-> minimal boundary rewrite
-> backend Tool Gateway/service call
-> draft/confirmation/audit envelope
```

Preserve:

- skill identity and responsibility area;
- trigger and non-trigger boundaries;
- shortcut-first / high-level-action-first thinking;
- explicit permissions and identity rules;
- resource-type routing;
- fallback and clarification behavior;
- workflow composition style.

Change only:

- Feishu resources become project resources:

```text
tenant/user/open_id      -> workspace member / project user / Telegram identity
Base app/table/view      -> workspace/base/table/view
record/file/doc/task     -> project record/file/document/work item
lark-cli command         -> backend service/tool action
Feishu approval          -> project draft/approval/confirmation object
Feishu IM                -> Telegram bot/group/private chat adapter
OpenAPI explorer         -> project Tool Gateway/service discovery
```

Do not change:

- the safety model that separates read, draft and commit;
- the requirement that destructive or external actions need confirmation;
- the principle that skills describe capabilities, not hidden prompt branches.

## 4. Suitability Levels

| Level | Meaning | Stage06 handling |
| --- | --- | --- |
| Core | Needed for the generic table/workspace/digital employee platform | Design now; implement after user approval |
| Near-term | Common work scenarios that strengthen the platform but can be partial | Keep in manifest as inactive/planned or read-only first |
| Future | Useful generic extension, but not required for current launch-like backend phase | Preserve summary and boundary, defer runtime tools |
| Reference only | Not directly suitable or too Feishu-specific/high-risk | Keep as benchmark; do not expose as active skill |

## 5. 27 Official Skills Analysis

| Official skill | Official responsibility | Suitability | Proposed project-native skill | Boundary adaptation |
| --- | --- | --- | --- | --- |
| [`lark-approval`](https://github.com/larksuite/cli/tree/main/skills/lark-approval) | Handles approval tasks, approval instances, searchable approval definitions and native approval submission. It separates approval todos from ordinary tasks. | Core | `platform-approval` | Map to record-change draft review, human confirmation, approval queues and escalation. Do not create a complex approval-definition builder in Stage06. |
| [`lark-apps`](https://github.com/larksuite/cli/tree/main/skills/lark-apps) | Covers Miaoda/Spark app creation, hosting, deployment, logs, metrics, env vars and app runtime operations. | Reference only | `platform-app-ops-reference` | Use as release/ops guardrail inspiration only. This project is not integrating Miaoda/Spark and Stage06 UI hosting is separately deferred. |
| [`lark-attendance`](https://github.com/larksuite/cli/tree/main/skills/lark-attendance) | Queries a user's attendance/check-in records. | Future | `template-attendance` | Generic HR/timekeeping template candidate. Not part of Stage06 core because it is a narrow vertical module. |
| [`lark-base`](https://github.com/larksuite/cli/tree/main/skills/lark-base) | Core Base operations: tables, fields, records, views, statistics, formulas/lookups, forms, dashboards, workflows, roles and permissions. | Core | `platform-base` | Main product reference. Map to workspace/base/table/field/record/view/form-lite/dashboard-lite/workflow-reserved/RBAC services. Formula/dashboard/workflow stay partial or reserved. |
| [`lark-calendar`](https://github.com/larksuite/cli/tree/main/skills/lark-calendar) | Manages calendars, events, meetings, participants, busy/free lookup and meeting rooms. | Near-term | `platform-calendar` | Generic scheduling skill for teams and digital employees. Stage06 can keep as planned/inactive unless a local calendar table template exists. |
| [`lark-contact`](https://github.com/larksuite/cli/tree/main/skills/lark-contact) | Resolves people by name/email/open id and reverse-looks up contact information. | Core | `platform-contact` | Map to Telegram users, workspace members, customer contacts and assignee resolution. It must not become unrestricted user enumeration. |
| [`lark-doc`](https://github.com/larksuite/cli/tree/main/skills/lark-doc) | Reads and edits cloud documents; routes embedded sheets/base/whiteboards to the right skill. | Near-term | `platform-doc` | Useful for SOPs, notes and generated reports. Stage06 should preserve boundary but avoid implementing full document editing before table-first flows are stable. |
| [`lark-drive`](https://github.com/larksuite/cli/tree/main/skills/lark-drive) | Manages cloud files/folders, metadata, upload/download, import/export, permissions, comments and versions. | Core partial | `platform-file-import` | Map to import files, attachments, evidence files and future file resources. Stage06 should focus on import/attachment metadata, not full cloud drive parity. |
| [`lark-event`](https://github.com/larksuite/cli/tree/main/skills/lark-event) | Consumes real-time events as bounded streams, including IM, task, VC, minutes and whiteboard events. | Core | `platform-event` | Map to Telegram webhook/polling events, internal queue events and bounded smoke subscribers. Preserve ready-marker, timeout and max-event discipline. |
| [`lark-im`](https://github.com/larksuite/cli/tree/main/skills/lark-im) | Sends/replies/searches IM messages, manages chats, files, reactions, interactive cards and card callbacks. | Core | `platform-telegram-im` | Map to Telegram message intake, replies, files, inline buttons and future Mini App callbacks. Sends remain draft/confirmation or dry-run until explicitly enabled. |
| [`lark-mail`](https://github.com/larksuite/cli/tree/main/skills/lark-mail) | Handles email drafting, sending, replying, forwarding, reading, searching, folders, labels, contacts and mail events. | Near-term | `platform-mail` | Common business channel. Keep as future channel adapter. Mail content must be treated as untrusted external input, following the official safety stance. |
| [`lark-markdown`](https://github.com/larksuite/cli/tree/main/skills/lark-markdown) | Reads, creates, edits, patches and diffs Markdown files. | Near-term | `platform-markdown-doc` | Useful for generated docs, templates and knowledge snippets. Not a core end-user skill unless the platform exposes document/file editing. |
| [`lark-minutes`](https://github.com/larksuite/cli/tree/main/skills/lark-minutes) | Searches/reads/updates Minutes artifacts, uploads/downloads audio/video and edits transcript-derived products. | Future | `platform-minutes` | Generic meeting-knowledge extension. Defer until meeting/document module exists. |
| [`lark-note`](https://github.com/larksuite/cli/tree/main/skills/lark-note) | Looks up known meeting notes by `note_id`, display type, related doc token and raw transcript. | Future | `platform-note` | Narrow meeting-artifact lookup. Defer; do not confuse with generic table notes. |
| [`lark-okr`](https://github.com/larksuite/cli/tree/main/skills/lark-okr) | Manages OKR cycles, objectives, key results, alignments, metrics and progress. | Future | `template-okr` | Useful as a generic template built on tables/tasks. Not required for Stage06 runtime. |
| [`lark-openapi-explorer`](https://github.com/larksuite/cli/tree/main/skills/lark-openapi-explorer) | Discovers native Feishu OpenAPI not wrapped by existing skills/commands. | Core governance, project-only | `platform-tool-discovery` | Do not discover Feishu APIs. Adapt the pattern to internal Tool Gateway discovery, service schema introspection and missing-tool reporting. |
| [`lark-shared`](https://github.com/larksuite/cli/tree/main/skills/lark-shared) | Shared auth, identity, scopes, JSON output contract, update checks, notices and high-risk approval protocol. | Core | `platform-shared-policy` | Centralize identity, permission intersection, structured envelopes, error contract and high-risk confirmation policy. |
| [`lark-sheets`](https://github.com/larksuite/cli/tree/main/skills/lark-sheets) | Creates and operates spreadsheets, worksheets, ranges, formulas, styles, comments, charts, pivots, filters and batch updates. | Core partial | `platform-tabular-analysis` | Map to imported spreadsheets, table analysis, formula-like summaries and chart/dashboard-lite planning. Do not implement full spreadsheet parity in Stage06. |
| [`lark-skill-maker`](https://github.com/larksuite/cli/tree/main/skills/lark-skill-maker) | Creates reusable custom skills that wrap APIs or multi-step workflows. | Core | `platform-skill-maker` | Use for project-native skill authoring rules, manifest validation, examples and regression prompt generation. Do not expose user-installed arbitrary skills yet. |
| [`lark-slides`](https://github.com/larksuite/cli/tree/main/skills/lark-slides) | Creates/reads/edits slides and slide pages. | Future | `platform-slides-export` | Useful for report export later. Defer runtime implementation. |
| [`lark-task`](https://github.com/larksuite/cli/tree/main/skills/lark-task) | Manages tasks, lists, subtasks, assignees, attachments and task-agent records. | Core | `platform-task` | Map to generic work items, follow-ups, assignments, queues and digital employee task logs. |
| [`lark-vc`](https://github.com/larksuite/cli/tree/main/skills/lark-vc) | Searches historical video meetings, meeting artifacts, summaries, todos, chapters, transcripts and participant snapshots. | Future | `platform-meeting-history` | Useful once calendar/meeting artifacts exist. Not Stage06 core. |
| [`lark-vc-agent`](https://github.com/larksuite/cli/tree/main/skills/lark-vc-agent) | Lets an app bot join/leave active meetings, read in-meeting events and send in-meeting messages/reactions. | Reference only | `platform-live-meeting-agent-reference` | High-risk and unrelated to Telegram-first table workflows. Do not implement in Stage06. |
| [`lark-whiteboard`](https://github.com/larksuite/cli/tree/main/skills/lark-whiteboard) | Queries/exports/updates whiteboards as images, SVG/code or raw node structures. | Future | `platform-diagram-board` | Useful for visual workflow/architecture boards later. Defer; preserve only as diagram capability reference. |
| [`lark-wiki`](https://github.com/larksuite/cli/tree/main/skills/lark-wiki) | Manages wiki spaces, nodes, members and document hierarchy. | Near-term | `platform-knowledge-space` | Useful for SOP/knowledge organization. Stage06 should keep as planned/inactive unless a docs/wiki module is introduced. |
| [`lark-workflow-meeting-summary`](https://github.com/larksuite/cli/tree/main/skills/lark-workflow-meeting-summary) | Composes meeting/minutes retrieval into structured period meeting summaries. | Near-term workflow | `workflow-period-summary` | Adapt as a generic period-summary workflow over tables/tasks/messages, not only meetings. Can be tested with LLM after core skills route correctly. |
| [`lark-workflow-standup-report`](https://github.com/larksuite/cli/tree/main/skills/lark-workflow-standup-report) | Composes calendar agenda and tasks into a daily/weekly arrangement summary. | Near-term workflow | `workflow-daily-briefing` | Adapt as a generic daily briefing over tasks, table records and Telegram mentions. Calendar integration can remain optional. |

## 6. Recommended Stage06 Skill Set

### 6.1 Active Core Manifests

These should be present in the first project-native manifest registry after user approval:

```text
platform-shared-policy
platform-base
platform-telegram-im
platform-event
platform-contact
platform-file-import
platform-task
platform-approval
platform-tabular-analysis
platform-skill-maker
platform-tool-discovery
```

Why these first:

- they cover the current product core: Telegram input, table resources, imports, tasks/drafts, approval, analysis and governance;
- they are generic enough for common work scenarios;
- they can be connected to the existing Stage06 backend without adding a new product vertical;
- they give LLM tests a stable capability catalog before multi-case prompts are expanded.

### 6.2 Planned Generic Manifests

These should be documented in the registry as `planned` or `inactive` until their backend surfaces exist:

```text
platform-calendar
platform-mail
platform-doc
platform-markdown-doc
platform-knowledge-space
workflow-daily-briefing
workflow-period-summary
```

They fit common work scenarios but should not pretend to execute before tool support exists.

### 6.3 Future Template Or Export Manifests

These should be preserved as future product directions:

```text
template-attendance
template-okr
platform-minutes
platform-note
platform-meeting-history
platform-slides-export
platform-diagram-board
```

### 6.4 Reference-Only Manifests

These should not become active Stage06 runtime skills:

```text
platform-app-ops-reference
platform-live-meeting-agent-reference
```

## 7. Layering Design

The recommended project-native skill hierarchy is:

| Layer | Name | Responsibility | Skill examples | Boundary |
| --- | --- | --- | --- | --- |
| L0 | Governance and Policy | Manifest rules, identity, permissions, high-risk protocol, output envelope, audit requirements | `platform-shared-policy`, `platform-skill-maker`, `platform-tool-discovery` | Does not answer business questions or mutate records |
| L1 | Channel and Event | Input/output channels, Telegram events, webhook/polling, user/contact resolution | `platform-telegram-im`, `platform-event`, `platform-contact`, future `platform-mail` | Does not decide table writes by itself |
| L2 | Workspace Resource | Workspace/base/table/field/record/view/file/document/knowledge resources | `platform-base`, `platform-file-import`, `platform-tabular-analysis`, future `platform-doc`, `platform-knowledge-space` | Does not bypass permissions or create workflow conclusions alone |
| L3 | Work Object | Common business work objects such as task, approval, calendar item, message draft, follow-up | `platform-task`, `platform-approval`, future `platform-calendar` | Does not commit high-risk actions without L0 confirmation policy |
| L4 | Workflow Composition | Multi-step workflows that compose L1-L3 skills into user-facing outcomes | `workflow-daily-briefing`, `workflow-period-summary` | Does not own raw resource operations; must call lower-layer skills |
| L5 | Live Agent Runtime | LangGraph/OpenRouter execution, selected skill context, tool calls, draft creation, audit evidence | digital employee runtime | Does not invent capabilities; must use manifest-selected skills and Tool Gateway |

Why this layering:

1. **Routing accuracy**: broad skills such as `platform-base`, `platform-task` and `platform-telegram-im` can overlap. Layers let the router first detect the resource type, then the work object, then the workflow.
2. **Safety**: L0 centralizes permission, confirmation and audit so individual skills do not each invent safety rules.
3. **Extensibility**: adding a future skill such as `platform-calendar` does not require rewriting the agent runtime.
4. **No-code product fit**: the hierarchy mirrors the product object model: channel -> workspace resource -> work object -> workflow -> agent execution.
5. **Testing**: each layer can have separate routing fixtures, negative prompts and permission cases.

## 8. Manifest Shape

Each project-native skill should be a static, JSON-serializable manifest first. Runtime code can load these manifests after user approval.

Recommended fields:

```text
skill_id:
source_skill:
status: active | planned | future | reference_only
layer:
name:
description:
when_to_use:
not_for:
resource_patterns:
positive_triggers:
negative_triggers:
required_context:
optional_context:
input_artifacts:
allowed_actions:
forbidden_actions:
output_contract:
confirmation_policy:
permission_policy:
fallback:
test_prompts:
```

Rules:

- `description` explains when to use the skill, not the whole workflow.
- `not_for` is mandatory because many common work skills overlap.
- `required_context` must identify resource requirements, such as `workspace_id`, `base_id`, `table_id`, `view_id`, `record_id`, `telegram_chat_id` or `actor_user_id`.
- `allowed_actions` must use project service/tool action names, not Feishu CLI commands.
- `confirmation_policy` must state whether the skill is read-only, draft-only or commit-capable after confirmation.
- `test_prompts` must include positive and negative examples.

## 9. Matching And Hit-Rate Design

### 9.1 Matching Pipeline

User input should pass through a deterministic-first, LLM-assisted router:

```text
raw input
-> normalize source context
-> extract explicit signals
-> generate rule-based candidates
-> apply permission/context filter
-> LLM rerank small candidate set
-> threshold decision
-> skill evidence stored with AgentRun
```

### 9.2 Step Details

1. **Normalize source context**
   - input channel: Telegram private chat, Telegram group mention, Mini App, API;
   - actor identity: Telegram user -> workspace member mapping;
   - current scope: workspace/base/table/view/record if available;
   - attachments and file types;
   - mentioned digital employee alias.

2. **Extract explicit signals**
   - URL or resource patterns;
   - table/base/record identifiers;
   - `@digital_employee` mention;
   - slash/command-like phrases;
   - attached CSV/XLSX/Markdown/PDF/image;
   - action verbs such as summarize, import, create task, update record, approve, send, search.

3. **Generate rule-based candidates**
   - match `positive_triggers`;
   - remove `negative_triggers`;
   - use `resource_patterns` before free-text similarity;
   - always add L0 governance candidates;
   - add channel skill from source context.

4. **Apply permission/context filter**
   - candidate must fit:

```text
digital_employee_scope
∩ actor_user_scope
∩ telegram_chat_scope
∩ skill_permission_policy
```

5. **LLM rerank**
   - give the LLM only the top candidate manifests, not all tools;
   - require structured output:

```json
{
  "selected_skill_ids": ["platform-base"],
  "rejected_skill_ids": [
    {"skill_id": "platform-task", "reason": "No task object requested"}
  ],
  "missing_context": ["table_id"],
  "confidence": 0.82,
  "requires_clarification": true
}
```

6. **Threshold decision**
   - high confidence + complete context: answer or create draft;
   - medium confidence or missing context: ask clarification;
   - low confidence: route to generic triage or `platform-skill-maker` suggestion;
   - high-risk action: force draft/approval even with high confidence.

7. **Evidence logging**
   - store candidate, selected, rejected and fallback decisions under `agent_runs.output_summary.skill_evidence`;
   - include confidence, reasons and missing context;
   - never persist raw prompt/response unless explicitly enabled for a controlled diagnostic run.

### 9.3 Hit-Rate Controls

Stage06 skill matching is validated with a deterministic prompt corpus independently from the real LLM smoke. This separation keeps routing quality, LLM behavior and backend-tool coverage measurable as different concerns.

Implemented corpus:

- 5 positive prompts per active core skill;
- 3 negative prompts per active core skill;
- 10 ambiguous prompts that intentionally overlap skills;
- 5 high-risk prompts that try to bypass confirmation;
- 5 permission prompts that request hidden or inaccessible data.
- 5 missing-context prompts;
- 5 inactive-skill prompts.

Recommended acceptance gates:

| Metric | Gate |
| --- | --- |
| Active core top-1 routing accuracy | >= 85% on fixture corpus |
| Active core top-3 recall | >= 95% on fixture corpus |
| High-risk false commit route | 0 |
| Hidden-field/unauthorized-data false positive | 0 |
| Required clarification when context is missing | >= 90% |
| Skill evidence present in AgentRun | 100% of routed live/deterministic cases |

Implemented evidence on 2026-07-10:

| Evidence | Result |
| --- | --- |
| Corpus size | 118 cases: 55 positive, 33 negative, 10 ambiguous, 5 high-risk, 5 permission, 5 missing-context, 5 inactive |
| Active core top-1 routing accuracy | 89.23% |
| Active core top-3 recall | 100% |
| High-risk false commit routes | 0 |
| Hidden-field/unauthorized-data false positives | 0 |
| Missing-context clarification rate | 100% |
| Skill evidence shape presence | 100% |

Command: `python scripts/stage06_skill_hit_rate_eval.py` from `backend/`.

The remaining top-1 misses are retained as evaluator `diagnostics`; they do not hide or override the gate result. Safety violations and unmet gates remain hard `failures`.

## 10. Relationship To LLM Multi-Case Smoke

The real OpenRouter smoke ran after the skills manifest was connected, so the model received the same selected-skill context used by the runtime.

Verified cases: `summarize_basic`, `draft_update_status`, `hidden_field_guard`, `unsafe_commit_refusal`, and `citations_required`. Result: 5/5 passed, two pending drafts created, no direct record mutation, and no raw prompt/response persistence.

Recommended post-skill LLM cases:

| Case | Expected selected skills | Acceptance |
| --- | --- | --- |
| Summarize table records | `platform-base`, `platform-tabular-analysis` | Uses only visible fields, cites table/record context |
| Draft record update | `platform-base`, `platform-approval` | Creates pending draft, does not mutate record |
| Import attached spreadsheet | `platform-file-import`, `platform-base` | Produces import preview or missing-file clarification |
| Create follow-up task | `platform-contact`, `platform-task` | Resolves assignee or asks clarification |
| Telegram reply draft | `platform-telegram-im`, `platform-approval` | Produces draft/send request only |
| Daily briefing | `workflow-daily-briefing`, `platform-task`, optional `platform-base` | Summarizes tasks/records without inventing facts |
| Hidden-field guard | `platform-shared-policy`, selected domain skill | Does not reveal hidden fields |
| Unsafe commit refusal | `platform-shared-policy`, `platform-approval` | Refuses bypassing confirmation |

## 11. Implemented Stage06 Scope

The approved implementation stayed within the following boundary:

1. Add a Stage06 static skill manifest registry.
2. Convert the 27 official skills into project-native manifest entries with status flags.
3. Add deterministic skill matching using manifest triggers, resource patterns and negative triggers.
4. Keep optional LLM rerank deferred until deterministic candidates are narrowed and benchmarked.
5. Store `skill_evidence` in the existing AgentRun output shape if possible; avoid DB migrations unless the existing JSON field is insufficient.
6. Update live digital employee prompt to include selected skill descriptions and boundaries.
7. Add fixture tests for core skill matching.
8. Run real OpenRouter multi-case smoke only after deterministic tests pass.

## 12. Explicit Non-Goals

This design does not approve:

- connecting to Feishu/Lark APIs;
- making the platform Feishu API-compatible;
- copying official `SKILL.md` files into runtime;
- exposing arbitrary user-installed skills;
- enabling external sends or writes without confirmation;
- implementing all 27 skills as full backend tools in Stage06;
- reintroducing advertising-agent skills as platform defaults.

## 13. Resolved Review Questions

The user-approved answers are:

1. Include all 27 adapted manifests with status flags, while activating only the generic core subset.
2. Use deterministic matching first; keep LLM rerank deferred.
3. Keep `platform-calendar`, `platform-mail`, `platform-doc` and `platform-knowledge-space` planned/inactive in Stage06.

## 14. Review And Approval Checklist

The following review points were accepted before implementation:

| Review item | Proposed answer | Rationale |
| --- | --- | --- |
| Official source count | Use all 27 observed `larksuite/cli` skills as source coverage | Keeps the benchmark complete and prevents cherry-picking only the easy skills |
| Runtime activation scope | Activate only the core subset first; keep near-term/future/reference skills in manifest with status flags | Avoids a large runtime rebuild while preserving official skill taxonomy |
| Business orientation | Generic work scenarios only; no advertising-operation default skills | Matches the Stage06 platform pivot and avoids Stage05 pollution |
| Feishu relationship | Imitate skill organization and safety discipline; do not integrate Feishu APIs | Matches project source of truth |
| Matching strategy | Deterministic candidate generation first, optional LLM rerank after filtering | Improves hit rate and keeps costs/safety controlled |
| Evidence strategy | Store skill candidates, selected skills, rejected skills, missing context and confidence in AgentRun output | Makes LLM routing auditable and testable |
| LLM smoke timing | Run multi-case OpenRouter smoke only after skill evidence exists | Tests the real prompt/runtime shape rather than a pre-skill prompt |
| Confirmation policy | Read actions may answer directly; write/send/destructive actions create drafts or require confirmation | Preserves current Stage06 safety model |
| Implementation boundary | No DB migration unless existing JSON output fields cannot hold skill evidence | Keeps the next implementation small and reversible |

Implemented flow:

```text
approved design
-> write implementation plan
-> add static Stage06 skill manifest registry
-> add deterministic matcher and tests
-> connect selected skill context to digital employee runtime
-> run deterministic fixtures
-> run the user-confirmed real multi-case OpenRouter smoke
```

Approval does not mean:

- all 27 skills become fully executable backend tools;
- Feishu/Lark APIs are connected;
- external sends or writes are enabled;
- UI work starts;
- real LLM multi-case smoke runs without a separate explicit confirmation.

## 15. Current Recommendation

Use this approach:

```text
all 27 skills documented and represented in manifests
-> 11-skill active core connected
-> deterministic matching benchmarked
-> skill evidence stored in AgentRun
-> real OpenRouter multi-case smoke passed
-> keep LLM rerank and additional backend tools as explicit later hardening work
```

This keeps the official skills complete and recognizable, but avoids a large runtime rebuild. It also fits the user's current direction: common work scenarios first, Telegram-first platform entry, no advertising-business default, no Feishu integration.
