# Stage 05 LarkSuite Skills Official Summary

## Status

- Document status: reference summary
- Scope: Concise local summary of the 27 official `larksuite/cli` skills for Stage05 Skills Extension. This is not a copy of the official source.
- Current Progress: 2026-07-09 Added after user chose to save a compact reference summary rather than full official `SKILL.md` snapshots.

## Source

- Official source: https://github.com/larksuite/cli/tree/main/skills
- Retrieval date: 2026-07-09
- Observed count: 27 skills

## Summary Table

| Official Skill | Responsibility Summary | Project Use |
| --- | --- | --- |
| `lark-approval` | Approval task/instance handling and approval submission boundaries | Adapt confirmation and escalation patterns |
| `lark-apps` | Miaoda/Spark app development, hosting, logs, env and release guardrails | Reference only for ops guardrails |
| `lark-attendance` | Attendance record query | Excluded |
| `lark-base` | Base table, field, record, view, workflow and permission operations | Core Bitable-like structure reference |
| `lark-calendar` | Calendar, meetings, rooms, busy/free lookup | Future scheduling reference only |
| `lark-contact` | Resolve people/open ids/contact info | Adapt customer/operator/contact binding |
| `lark-doc` | Read/edit Docx/Wiki docs and embedded resource routing | SOP/report document reference only |
| `lark-drive` | Drive files/folders/import/export/permissions | Future attachment/evidence reference |
| `lark-event` | Bounded event consume/listen workflows | Adapt webhook/worker event contract |
| `lark-im` | IM messages, chats, files, cards, callbacks | Adapt Telegram channel semantics |
| `lark-mail` | Mail draft/send/read/search/listen | Future channel reference only |
| `lark-markdown` | Markdown read/create/edit/diff | Internal docs reference only |
| `lark-minutes` | Minutes search/read/upload/download/edit outputs | Excluded for this product stage |
| `lark-note` | Known note id lookup and transcript access | Excluded |
| `lark-okr` | OKR cycle/objective/key result management | Excluded |
| `lark-openapi-explorer` | Discover native OpenAPI not wrapped by CLI | Adapt only as Tool Gateway discovery governance |
| `lark-shared` | Auth, identity, scopes, JSON/error contract and high-risk protocol | Core shared policy reference |
| `lark-sheets` | Spreadsheet structure, values, formulas, charts and analysis | Adapt tabular analysis and value discipline |
| `lark-skill-maker` | Create reusable Lark CLI skills | Adapt skill authoring discipline |
| `lark-slides` | Create/edit/read slides | Future report export reference |
| `lark-task` | Tasks, lists, task agent and task records | Adapt handoff/review/pending work |
| `lark-vc-agent` | Bot joins active meetings and reads/sends in-meeting events | Excluded high-risk unrelated scope |
| `lark-vc` | Historical video meeting records and artifacts | Excluded |
| `lark-whiteboard` | Query/export/update whiteboards | Diagram reference only |
| `lark-wiki` | Wiki spaces, nodes, members and hierarchy | Future knowledge/SOP reference only |
| `lark-workflow-meeting-summary` | Summarize meeting artifacts over a period | Adapt only as period summary workflow pattern |
| `lark-workflow-standup-report` | Compose calendar/tasks into day summary | Adapt only as future daily operations workflow pattern |

## Preservation Rules

Preserve:

- concise trigger descriptions,
- explicit non-goals,
- permission/identity rules,
- write-operation gates,
- recovery tables,
- reference links for large schemas,
- workflow composition style.

Change:

- Lark tokens and ids become project ids such as `message_id`, `customer_id`, `service_draft_id`, `agent_run_id`.
- Lark CLI commands become backend Tool Gateway/service calls.
- Lark IM becomes Telegram channel semantics.
- Lark Base becomes project Bitable-like views and records.

Do not copy:

- raw official `SKILL.md` bodies,
- Lark auth flows into product runtime,
- Lark OpenAPI execution authority,
- Lark-specific business domains unrelated to advertising operations.
