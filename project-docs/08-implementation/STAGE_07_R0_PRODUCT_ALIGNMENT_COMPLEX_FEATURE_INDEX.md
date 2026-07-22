# Stage07 R0 Product Alignment Complex Feature Index

## Status

- Status: `completed`; later implementation gates remain active.
- Scope: complexity that must be resolved in documents before R1 code planning.

| ID | Complexity | Why it matters | R0 control | Later implementation gate |
| --- | --- | --- | --- | --- |
| R0-C01 | Many local features, no single business journey | A passing Builder or Bot test can mask an unusable product workflow. | Map every item to Customer/Project/Task, controlled collaboration or explicit later scope. | R1/R2 scenario BDD approval. |
| R0-C02 | `partial-local` overload | The label currently combines missing code, missing evidence and deliberately deferred scope. | Require one primary backlog class and one owner per row. | R0 matrix review. |
| R0-C03 | Stale S6 external statements | Old pending text can misrepresent already observed Telegram evidence or cleanup. | Preserve historical sequence but add dated top-level corrections. | Documentation reconciliation only. |
| R0-C04 | Telegram customer-group context | A group-to-project mapping changes identity, persistence, external side effects and permissions. | Mark as contract-gated; no implied implementation. | Future technical decision and user approval. |
| R0-C05 | Direct task creation versus draft safety | Internal structured creation and customer-originated requests have different authority and abuse risks. | Distinguish them in the business truth; retain backend authority and confirmation boundaries. | Future action/permission decision. |
| R0-C06 | Risk visibility versus customer communication | Internal risk interpretation must not leak automatically to a customer group. | Record internal-first reminder and confirmation-before-customer-send rule. | Future notification decision. |
| R0-C07 | Acceptance workload versus product delivery | Re-running all old tests can consume effort without improving the customer outcome. | Group evidence work by R1/R2/R3 and run only evidence required to close a row. | Per-substage implementation plan. |
| R0-C08 | Scope expansion pressure | Memory, RAG, files, public sharing and production deployment can derail the first product loop. | Mark them deferred/contract-gated with no silent re-entry. | Dedicated later decision. |

## Index Acceptance

The index is complete when every listed complexity has a named R0 control and a later approval/acceptance gate. It is not a substitute for a database-index design; no physical index is proposed in R0.
