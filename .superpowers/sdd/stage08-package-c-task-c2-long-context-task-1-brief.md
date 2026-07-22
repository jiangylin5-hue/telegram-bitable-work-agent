# Stage08 Package C2 Long Context — Task 1 Brief

## Task

Implement Task 1, **D3 Decision Record and Contract Reconciliation**, from `docs/superpowers/plans/2026-07-19-stage08-package-c2-long-context-implementation.md`.

## Context

This is the documentation gate before C2 schema or code. The user has approved long context as **context**, not Memory: new/edited authorized group messages create a controlled projection; a 30-day / 120-fragment / 60,000-code-point working window emits a 24,000-code-point compression signal for C3/E; C2 itself never calls a Provider or persists a digest. D3 is `best_effort_group_deletion`: known edit, server-authorized purge and retention expiry are reliable; ordinary Telegram group deletion is not.

## Exact Scope

Create:

- `project-docs/08-implementation/decisions/STAGE_08_C2_D3_GROUP_CONTEXT_DATA_CONTRACT.md`

Modify only:

- `project-docs/08-implementation/STAGE_08_PACKAGE_C2_GROUP_HISTORY_BDD_AND_ACCEPTANCE.md`
- `project-docs/08-implementation/STAGE_08_SOURCE_OF_TRUTH.md`
- `project-docs/08-implementation/STAGE_08_IMPLEMENTATION_PLAN.md`
- `project-docs/08-implementation/STAGE_08_DATA_API_SECURITY_CONTRACT.md`
- `docs/superpowers/plans/2026-07-19-stage08-package-c2-group-history.md`

Do not modify production Python, migrations, tests, API routes, secrets, Telegram configuration, external systems, git index or commits.

## Binding Values

- D1: only new authorized group/supergroup inbound messages and known edits create a controlled projection. Historical `Message.raw_text`, `raw_caption`, `normalized_text` never become C2 input, are not backfilled and are not deleted by this task.
- D2: retention 30 days; at most 120 fragments; 500 Unicode code points per fragment; raw work window 60,000 code points; final group context 24,000 code points; newest 24 raw fragments at most 12,000 code points; ephemeral digest at most 12,000 code points; 7-day history half-life.
- C2 only exposes a private long window plus `compression_required = raw_selected_chars > 24000`. C3 owns C1/C2 merge/global budget. Package E owns the only future `ContextCompressor` Provider call. Digest is process-local to a current invocation and may not be stored in MemoryItem/candidate/database/Redis/RAG/pgvector/AgentRun/audit/log/LangGraph checkpoint.
- D3: `best_effort_group_deletion`; source `event_at` is Telegram `message.date` converted to UTC; late delivery never changes event order. Known edit creates a new version; server-authorized purge and expiry erase controlled fragment text. A normal group remote deletion/revoke has no trusted general Bot API event and cannot be claimed to be instantly known.
- D4: one active Stage06 chat-user binding maps to one current same-workspace customer `PlatformRecord` and one project `PlatformRecord`; null/ambiguous/drift fails closed.
- D5: only an internal `Stage08GroupContextAuthorityFactory`, built from verified actor/employee/current workspace, can create non-Pydantic/non-JSON authority. No HTTP/Mini App/Telegram update/outbox/audit/client field may construct it.
- D6: label `group_context`, source_type `group_message_fragment`, display id `group_context:NN`; scope exposes dimensions only, not values; C2 is non-consumable before C3.
- The existing no-ingestion wording must be refined: no new Telegram network, webhook endpoint, polling, outgoing request or historical raw read. The existing verified local ingress transaction may write the new controlled projection.

## Required Document Content

1. The decision record must include scope/non-goals, exact data-contract fields, status/omission matrix, lifecycle/edit/purge/retention facts, mapping/authority boundaries, C3/E handoff and acceptance evidence.
2. Reconcile obsolete active C2 values `recent 20/history 12/group 6000` and the absolute no-ingestion phrase. Historical reports may retain dated history only when explicitly labelled historical.
3. Keep documents Chinese-first. Do not claim implementation, migration, tests, external calls or production readiness.
4. Every active status must say Task 1 docs are in progress/review, C2 code/migration/tests remain unimplemented.

## Verification

Run:

```powershell
rg -n "recent 20|history 12|group 6000|即时删除|D3.*未确认|TODO|TBD" project-docs/08-implementation/STAGE_08_PACKAGE_C2_GROUP_HISTORY_BDD_AND_ACCEPTANCE.md project-docs/08-implementation/STAGE_08_SOURCE_OF_TRUTH.md project-docs/08-implementation/STAGE_08_IMPLEMENTATION_PLAN.md project-docs/08-implementation/STAGE_08_DATA_API_SECURITY_CONTRACT.md docs/superpowers/plans/2026-07-19-stage08-package-c2-group-history.md
git diff --check -- project-docs/08-implementation docs/superpowers/specs docs/superpowers/plans .superpowers/sdd
```

Expected: no stale active values or whitespace errors. If a historical value remains, document why it is historical.

## Report

Write the complete report to `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-1-report.md`, including changed files, command outputs, no-code/no-external scope statement, self-review and concerns. Return only status, one-line verification, concerns, and report path.
