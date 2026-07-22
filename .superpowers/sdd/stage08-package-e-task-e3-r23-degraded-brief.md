# Stage08 Package E — E3 R2/R3 terminal mapping follow-up

## Scope

User has confirmed the previously documented E1 contract extension: a valid
`AnalysisProviderOutcome(status="unavailable")` must finish the collaboration
in terminal `degraded`, instead of `failed`.

This is a minimal close-out of the already implemented E3 R2/R3 package. It
does not introduce a schema, public API, permission, provider, Telegram, or
deployment change.

## Required implementation

1. Add `degraded` consistently to the Stage08 collaboration terminal type,
   state-machine terminal handling, transition validation and graph terminal
   ordering/precedence where required.
2. Map only a *validated* `AnalysisProviderOutcome(status="unavailable")` to
   `degraded`. Malformed/forged provider values, validation failures and
   runtime exceptions remain `failed`.
3. Enforce the terminal safe-view invariant for `degraded`:
   `answer is None`, no citations, no draft reference, no Gateway dispatch,
   and a fixed `analysis_unavailable` degradation code.
4. Preserve all existing safe-execution semantics from E3 R1/R2/R3:
   atomic Gateway rollback, scope re-check, idempotency replay and minimal
   trace/audit projection.
5. Update the existing R23 implementation report with the final evidence and
   remove its contract concern once it is resolved.

## Verification

Run the existing focused degraded/graph/service tests, the R23 selected unit
set, the Stage08 PostgreSQL collaboration integration test against the
disposable local Stage08 pgvector database, and `compileall`. Do not call
OpenRouter, Telegram, or deployment services.

## Out of scope

Do not edit unrelated product code or tests, change defaults outside the
Stage08 safe path, or relax redaction/authorization invariants merely to
accommodate this terminal status.
