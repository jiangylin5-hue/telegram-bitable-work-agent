# Current Project Handoff

This root file is the stable current entry point. Stage10 supersedes the older
Stage08/Stage09 execution handoff while retaining those documents as design and
compatibility history.

Read it together with:

1. `AGENTS.md`
2. `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`
3. `project-docs/00-governance/PROJECT_STRUCTURE_AND_DOCUMENT_LIFECYCLE.md`
4. `project-docs/02-architecture/AGENT_EVENT_RUNTIME_PROPOSAL.md`
5. `project-docs/08-implementation/STAGE_10_AGENT_EVENT_RUNTIME_ACCEPTANCE.md`
6. `docs/superpowers/plans/2026-07-28-agent-event-runtime.md`
7. `project-docs/08-implementation/evidence/stage10-r66-public-deployment-and-ui-acceptance-2026-07-28.md`
8. `project-docs/08-implementation/evidence/stage10-r7-real-20-case-distributed-report-2026-07-28.md`

The historical Stage07 R0-R3 handoff remains available through Git history and
the Stage07 implementation/evidence documents. It is not the current execution
entry.

## Current Progress

2026-07-28 final update: public artifact
`stage09-p1-20260728-r66-conversation-routing` is active with database head
`20260728_0034`. The durable Stage10 read-only path uses PostgreSQL control-plane
state, an outbox, Redis Streams, independent publisher/specialist services,
LangGraph/OpenRouter execution and reauthorized safe SSE. Stage08 remains the
synchronous/legacy-stream compatibility path and the only draft-confirmation
write path.

The production browser was exercised with explicit skill selection, automatic
multi-table retrieval, a pure greeting and a greeting-plus-business boundary
case. The final local regressions are 1537 backend Unit+API tests and 411 Mini
App tests; the production JS/CSS hashes exactly match the local build. The real
20-case Chinese report used 3 tables, 32 records, real PostgreSQL/Redis and real
OpenRouter, with all reported hit/retrieval/readiness/accuracy rates at 100%.
Temporary acceptance services, databases, roles, failed r62/r63 candidates and
upload archives were removed. r64/r65, r66 and the pre-r64 database backup are
retained for rollback. Do not add a write-capable Specialist or broaden external
send authority without a new architecture/contract stage and explicit approval.
