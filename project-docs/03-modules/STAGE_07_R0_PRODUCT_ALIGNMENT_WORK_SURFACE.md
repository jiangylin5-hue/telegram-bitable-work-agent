# Stage07 R0 Product Alignment Work Surface

## Status

- Status: `completed` documentation surface.
- User-facing UI/API surface: none.
- Runtime mutation: none.

## Purpose

R0 gives every Stage07 capability a visible product role before further code work begins. It prevents the current generic platform from receiving more isolated features that cannot be connected to a Telegram customer-project workflow.

## Confirmed Future User Journey

| Actor | Real need | Durable system outcome | Channel |
| --- | --- | --- | --- |
| Sales / customer operations | preserve customer context and promises | Customer/Opportunity plus related Project is current | Mini App / imported data |
| Project manager | assign accountable delivery work | Project-linked Task with owner, due date and fixed state | Mini App; later internal Bot action |
| Delivery member | know next action and escalate blockers | permitted task/project view and internal risk reminder | Mini App / Telegram |
| Manager | intervene before customer impact | project-health view showing risk signals | Mini App |
| Customer | communicate a need or confirm a result | message remains controlled; later proposal may create an internal candidate | Telegram customer project group |

## R0 Documentation Surfaces

| Surface | Owner document | Purpose |
| --- | --- | --- |
| Product truth | R0 Design | defines target team, objects, channels and safe future boundary |
| Acceptance behavior | R0 BDD | defines what truthful reconciliation means |
| State architecture | R0 SDD | defines classification, ownership and conflict rules |
| Complex constraints | R0 Complex Feature Index | records risks that cannot be hidden by a generic backlog |
| Delivery ownership | updated Roadmap/Source/Traceability | assigns R1/R2/R3 and later decision gates |

## Explicitly Absent Interfaces

R0 creates no HTTP method, database table, browser route, queue job, webhook, Bot command, Mini App page, import format, external notification or permission action. Any proposal that needs one of those interfaces must leave R0 and enter a user-approved technical decision.
