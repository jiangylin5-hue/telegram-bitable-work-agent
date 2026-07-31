# Stage12 Integrated Specialist / Observability Correction Plan

## Status

- Status: `implemented-local-awaiting-human-gold-signoff`
- Source: `project-docs/08-implementation/STAGE_12_INTEGRATED_SPECIALIST_OBSERVABILITY_COMPLETION_AUDIT.md`
- Scope: close already-approved correction-package runtime-wiring and observability requirements only
- Method: TDD; no public contract, permission, profile or activation change
- Approval: user explicitly approved closing the current ISO-01 gap on 2026-07-31

## Task 1 — Freeze runtime mapping and RED tests

1. Add raw-Query runner tests that spy on all four existing typed handler classes.
2. Prove risk/daily cases currently miss their handlers and action cases miss typed preflight.
3. Add a strict expected observability-ledger test covering every approved field and latency segment.

Status: completed; initial RED was `6 failed`.

## Task 2 — Typed Risk/Daily fan-in

1. Reuse sealed structured fact artifacts produced by Tabular.
2. Resolve dependencies by TaskSpec objective/dependency IDs, never by Case ID or Gold.
3. Build an authorized synthetic risk policy from visible schema fields only.
4. Execute Risk and Daily handlers with their declared ports and persist their results in the in-memory artifact map.
5. Feed validated risk claims and objective outcomes to ClaimGraph; Daily remains a typed presentation artifact over already-sealed facts/risks.

Status: completed locally. ISO-01 records distinct Specialist artifact/fact ownership; validated risk facts ground Answer/final-answer scoring while Query scoring remains Query-only.

## Task 3 — Integrated Action authority

1. Prove the existing F durable Action Specialist is the integrated A–F authority.
2. Cover update/create/task candidate identities and pre-dispatch reminder denial.
3. Do not add a parallel E preflight or fake existing target record for creates.
4. Preserve zero confirmation/write/send.

Status: completed locally. The initial E preflight approach was removed after source audit proved F already owns the complete semantics.

## Task 4 — Complete observability ledger

1. Add a strict internal observation model for the approved trace dimensions.
2. Record runtime-derived hashes/counts/statuses/revalidation totals and Provider token/attempt totals.
3. Emit the exact approved latency segment names, including per-capability Specialist and per-role Provider maps.
4. Keep artifacts sanitized and hash-bound.

Status: completed locally with focused and full-regression coverage.

## Task 5 — Regression and documentation

1. Rerun focused RED/GREEN and deterministic 48-Case release.
2. Rerun expanded Stage12/Planner, full backend, PostgreSQL/pgvector, Mini App and build when affected.
3. Update the stale Task 9 and final-campaign plan states using fresh evidence.
4. Do not mutate Human Gold or start real Provider rounds without explicit 48/48 sign-off.

Status: completed locally. Human Gold and Provider status remain unchanged.
