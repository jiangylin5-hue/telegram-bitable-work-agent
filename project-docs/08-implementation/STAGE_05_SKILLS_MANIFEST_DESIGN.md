# Stage 05 Skills Manifest Design

## Status

- Document status: active design
- Scope: Static skill manifest shape, layers, matching evidence and AgentRun storage for Stage05 Skills Extension.
- Current Progress: 2026-07-09 Drafted before implementation.

## 1. Manifest Shape

Each skill manifest must be static and JSON-serializable:

```text
skill_id:
priority:
layer:
source_skill:
owning_agent:
primary_agent_node:
primary_endpoint:
description:
positive_triggers:
negative_triggers:
required_entities:
optional_entities:
allowed_tools:
forbidden_actions:
fallback:
stage_allowed:
execution_mode:
```

`description` must describe when to use the skill. It must not summarize the whole workflow.

## 2. Layers

| Layer | Name | Responsibility | Boundary |
| --- | --- | --- | --- |
| L0 | Governance | Skill rules, policy, permission, confirmation and authoring discipline | Does not produce business drafts |
| L1 | Channel/Event | Telegram input, event consumption, customer/contact binding | Does not execute business intent |
| L2 | Bitable/Data | Table/view/record/status endpoint discipline and tabular analysis | Does not invent facts or call provider |
| L3 | Business Atomic | One business intent, one typed output, one primary endpoint | Does not confirm or execute itself |
| L4 | Workflow | Compose skills into review/future/manual workflows | Does not bypass lower-level gates |
| L5 | Controlled Execution | Future provider execution/readback after ticket | Not active in this extension |

## 3. Registered Skills

### Platform and adapter skills

```text
project-base
project-shared
project-im
project-event
project-skill-maker
project-task
project-contact
project-approval
project-tabular-analysis
project-tool-discovery
project-daily-operations-workflow
project-period-summary-workflow
```

### Business intent skills

```text
recharge-draft
customer-reply-draft
bm-invite-draft
card-binding-draft
account-exception-marking
manual-review-handoff
spend-query
spend-table
```

### Not registered

```text
report-draft
```

Reporting remains future business expansion. Reporting workflows may be detected and routed to future/manual review evidence, but no report draft skill may execute or be registered as an active business skill in this round.

## 4. Matching Evidence Shape

Store evidence under:

```text
agent_runs.output_summary.skill_evidence
```

Shape:

```text
manifest_version:
mode:
source:
candidate_skills:
selected_skills:
rejected_skills:
future_scope_skills:
missing_entities:
fallback:
baseline_metrics:
```

Each skill match item:

```text
skill_id:
priority:
layer:
owning_agent:
primary_endpoint:
confidence:
selection:
reason:
fallback:
```

## 5. Matching Rules

- Always include core platform candidates for eligible Stage05 Telegram messages:
  - `project-im`
  - `project-shared`
  - `project-base`
  - `project-event`
- Select business skills from Router intents where possible.
- Use lexical fallback for spend/balance/report phrases so unsupported-but-business-relevant messages are visible.
- Unsupported future reporting must select workflow adapters only with `future_scope` or `manual_review` fallback.
- `report-draft` must appear only as an explicitly rejected or absent skill; it must not be registered.
- Missing required entities should be copied from Router `missing_context` and skill `required_entities`.

## 6. Baseline Metrics

This round records baseline, not hard hit-rate gates:

- candidate count,
- selected count,
- future scope count,
- rejected count,
- selected business skill ids,
- selected platform skill ids.

Hard gates remain safety gates:

- no provider calls,
- no Telegram send,
- no new API,
- no report draft,
- no raw secret/raw prompt/raw response persistence.
