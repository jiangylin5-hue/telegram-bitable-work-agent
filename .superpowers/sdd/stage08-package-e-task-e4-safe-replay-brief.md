# Stage08 Package E — E4 safe idempotency replay remediation

## Confirmed defect

The E4 reviewer reproduced an Important defect: a completed first response
contains a valid safe answer/citations, but the same-key replay reconstructs
only `status/draft_id` and returns an incomplete response. This violates the
approved E4 behavior that replay returns the prior safe result without
re-running the graph.

The documentation-first correction is
`decisions/STAGE_08_E4_SAFE_REPLAY_PROJECTION_DECISION.md`.

## Required minimal repair

1. Persist a versioned, allowlisted safe replay projection from an already
   `validate_assistant_query_safe_view`-validated result. It may contain only
   status, bounded answer, citation ordinal/label, degradation codes and
   optional existing draft ID.
2. Reconstruct replay strictly into `AssistantQuerySafeView`; reject unknown,
   missing, forged, wrong-version or wrong-type projection data with the
   existing 409 safe replay error. Do not attempt a partial empty response and
   do not run the graph again.
3. Keep query/private context/RAG/group material/provider raw data/authority
   and all internal IDs out of the projection. AgentRun/audit/outbox/logging
   remain content-free.
4. Preserve pre-replay current-scope revalidation, different-semantic 409 and
   rollback behavior.
5. Add focused RED/GREEN regression proving first and replay JSON are equal,
   graph is called once, projections are strictly allowlisted, forged replay
   is 409, revoked replay is 403 and conflicting key is 409.

## Boundaries and verification

No schema/migration/public request-response field/permission/Provider/
Telegram/deployment change. Run E4 API tests, collaboration focused tests,
loopback disposable pgvector integration, compileall and diff check. Update
the existing E4 implementation report with remediation evidence. No external
calls or Git write operations.
