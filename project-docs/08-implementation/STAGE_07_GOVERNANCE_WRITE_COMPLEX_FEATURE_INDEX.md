# Stage07 Governance Write Complex Feature Index

## Status

- Status: implementation reconciled against local evidence; GW-I08 retains delayed field-policy and GW-I10 retains Browser negative-lifecycle evidence gaps.

| ID | Concern | Required rule | Required proof |
| --- | --- | --- | --- |
| GW-I01 | privilege escalation | fixed roles/actions; owner/admin target matrix rechecked under lock | role service/API negative matrix |
| GW-I02 | owner safety | no S4 owner mutation, self-role mutation or owner transfer | unit/PostgreSQL no-write tests |
| GW-I03 | lost update | independent member and field revisions compare under row lock | concurrent disposable PostgreSQL tests |
| GW-I04 | idempotency | same command replays one receipt/audit; changed replay conflicts | route/service replay tests |
| GW-I05 | field-policy grammar | exactly five roles and three modes; owner always write | schema/property/API tests |
| GW-I06 | enforcement intersection | policy mode cannot add a missing fixed role action; hidden applies through schema/presentation/detail/lookup | cross-layer regression tests |
| GW-I07 | view-policy duplication | use existing V1 grant route only; no global/general policy route | route inventory and UI integration test |
| GW-I08 | stale UI | no optimistic result; exact cache clear and canonical reread after every terminal outcome | QueryClient/App delayed-response tests |
| GW-I09 | disclosure | no action map, policy snapshot, raw error/detail or hidden data in transport/state/DOM/URL | parser/component negative tests |
| GW-I10 | mobile confirmation | every state is labelled/reachable at 1440/1280/430/390 with focus return | Browser synthetic evidence |
| GW-I11 | audit integrity | audit contains stable delta/revision only and no raw sensitive state | audit redaction/PostgreSQL assertions |
| GW-I12 | cleanup | temporary fixture/proxy/processes removed; no production/Telegram claim | evidence document and port/process check |

Current reconciliation: GW-I01--GW-I07, GW-I09 and GW-I11 have bounded local implementation evidence. GW-I08 has typed protected-state and canonical-reread coverage; its delayed old-workspace role `401/403/404/409` App-flow matrix is complete, while delayed field-policy permutations remain. GW-I10 has built-client observations at all four target widths, but its stale/denied/retry/focus-return Browser permutations remain pending. GW-I12 is closed only for the synthetic local material recorded in `evidence/stage07-governance-write.md`.

## Scope Guards

No index item authorizes an invitation workflow, deactivation, owner transfer, custom RBAC, group policy, field formula/configuration change, view public sharing, Bot/employee action, Telegram behavior, deployment or a general authorization library.
