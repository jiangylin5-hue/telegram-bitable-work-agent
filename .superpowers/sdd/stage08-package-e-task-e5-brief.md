# Stage08 Package E — E5 production coordinator remediation

## Why this task exists

Package E final review I-01 proved that production `run_stage08_collaboration`
only *looked* like a three-way LangGraph fan-out: the real C3/D4 work was
sequential inside `fan_in`, while graph read nodes were no-ops; cancellation
and time budgets were not enforced in the service. Package E is HOLD until
this is fixed.

Read and implement exactly:

- `project-docs/08-implementation/decisions/STAGE_08_E5_PRODUCTION_COORDINATOR_EXECUTION_DECISION.md`
- `docs/superpowers/plans/2026-07-22-stage08-e5-production-coordinator-remediation.md`
- existing E contract/BDD and E1–E4 reports.

## Required outcome

1. Production graph `read_composite_context`, `read_retrieval`, and
   `mark_general_advice` must perform the actual bounded branch work. `fan_in`
   may merge sealed branch results only; it must not execute C3/D4 business
   reads.
2. SQLAlchemy branch execution must use isolated read-only sessions/UoWs;
   never share the request session across concurrently scheduled nodes. The
   original request UoW remains owner of E3 writes. InMemory fallback may be
   serial for compatibility, but must be unmistakably non-production and
   never count as parallel proof.
3. Add a sealed, process-local runtime control with monotonic deadline and
   cancellation probe. Check it before/after read, compression, analysis,
   policy and draft boundaries. Once expired/cancelled, terminal result is
   `timed_out`/`cancelled`, and later Policy/Gateway/draft paths do not run.
4. A valid branch failure only yields existing safe degradation. No private
   branch state/session/clock/cancel data may surface in safe views, replay
   projection, AgentRun, audit, outbox, logs or errors.
5. Preserve C3/D4 consumption-time scope proofs and E3 current-state locks,
   rollback and safe audit. Do not weaken E4 strict API/replay behavior.

## RED/GREEN evidence

Add focused production-service tests (not fake-node-only tests) that prove:

- the real three read nodes invoke their branch implementations and `fan_in`
  is I/O-free;
- SQLAlchemy local pgvector C3/D4 branches overlap and have distinct session
  identities; use a barrier/explicit probe, not timing guesses;
- an injected cancellation before and during the coordinator prevents analysis,
  Policy Gate and Gateway/draft;
- deadline/slow compressor or analysis port produces a fixed terminal state
  and no subsequent side effect;
- source/plan proof drift still fails closed and trace/audit/private-output
  scans remain clean.

Run a compact E suite, dedicated disposable loopback pgvector integration,
compileall and diff check. Do not execute the full repository suite or any
external Provider/Telegram/deployment action.

## Boundaries

No public API/request/response change, schema/migration/global role change,
real Provider, Telegram, Milvus, deployment or Git write operation. Keep the
implementation scoped to Stage08 collaboration/runtime/tests and write
`.superpowers/sdd/stage08-package-e-task-e5-report.md` in Chinese. Do not
claim Package E closed; independent review follows.
