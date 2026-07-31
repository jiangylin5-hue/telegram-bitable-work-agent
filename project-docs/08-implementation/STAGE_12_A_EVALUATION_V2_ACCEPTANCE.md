# Stage12-A Evaluation V2 Acceptance

## Status

- Status: acceptance reopened by the 2026-07-30 comprehensive audit; not accepted
- Date: 2026-07-29
- Scope: evaluation-only code and fictional fixtures; production runtime contracts and behavior unchanged
- Decision: Stage12-B may start; large real-model evaluation remains a Stage12 final acceptance gate
- Superseding audit: `STAGE_12_COMPREHENSIVE_ARCHITECTURE_AUDIT.md` proves wrong fact values can pass the Answer gate and normal non-recovery runs fail Durability; the historical acceptance table below is retained as implementation evidence, not the current decision

## Acceptance criteria

| Criterion | Result | Evidence |
| --- | --- | --- |
| Strict V2 contracts | PASS | Frozen Pydantic contracts reject extra fields and invalid graph/predicate/action structures |
| 48-case Gold truth | PASS with explicit review state | 48 unique cases and 48 audit entries; every entry is `agent_audited_pending_human_signoff` |
| Known Gold defect | PASS | `risk_02` requires `MT-017` and forbids legacy `MT-008` |
| Planner/Query/Retrieval separation | PASS | Independent typed traces and scores; Retrieval is not inferred from answers |
| Answer quality | PASS | Typed claims/evidence are scored; non-empty answer is not a quality metric |
| Action evaluation | PASS | Slot, target, field, value, confirmation, schema, persistence, denial reason and effects are separate |
| Safety hard gates | PASS at component level | Permission and external-send violations cannot be offset by Overall score |
| Gold leak prevention | PASS | Execution payload guard rejects expected/gold/action target/field/value keys |
| Executable fixture | PASS | Seven tables materialized through Stage06 services; records, versions, relations and ACLs are reconstructed and checked |
| Stage11 compatibility | PASS | Legacy tests remain green; missing V2 trace fields are `not_observed` |
| Focused tests | PASS | `58 passed in 2.66s` |
| Backend regression | PASS with infrastructure skips | `1714 passed, 132 skipped in 142.57s` after excluding four unavailable PostgreSQL-only historical files |
| Real LLM multi-round run | DEFERRED | User explicitly prioritized Stage12 technical architecture; execute after B–F |
| Human Gold sign-off | PENDING | No human approval is claimed |
| Deterministic engine recomputation | DEFERRED | Recompute after Stage12-C Authorized Query Engine exists |

## Changed files

Evaluation implementation:

- `backend/scripts/stage12_quality_evaluation.py`
- `backend/scripts/stage12_evaluation_fixture.py`
- `backend/scripts/stage12_stage11_trace_adapter.py`
- `backend/scripts/stage12_real_quality_report.py`

Truth and tests:

- `backend/tests/fixtures/stage12_complex_cases_v2.json`
- `backend/tests/fixtures/stage12_complex_cases_v2.audit.json`
- seven `backend/tests/unit/test_stage12_*.py` files

Governance, architecture, plan and handoff documents:

- `AGENTS.md`
- `HANDOFF.md`
- `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`
- `project-docs/08-implementation/README.md`
- `project-docs/02-architecture/stage12-quality-v2/*`
- `docs/superpowers/plans/2026-07-29-stage12-a-evaluation-v2.md`
- this acceptance file and its JSON/Markdown evidence pair

## What changed

The evaluator now consumes typed layer artifacts rather than extracting record identifiers from rendered answers. Query and Retrieval are separate because a complete structured aggregate query must not be truncated by Retrieval Top-K. The Stage11 adapter records unavailable layers as `not_observed`. The Action runner keeps Gold exclusively in the scorer process after execution. A standalone fictional fixture expresses schema, records and relation edges using existing service boundaries and is validated against the same hashed source used by the Gold cases.

## Verification

Commands and exact results are recorded in [stage12-a-evaluation-v2-baseline-2026-07-29.md](evidence/stage12-a-evaluation-v2-baseline-2026-07-29.md) and its machine-readable JSON companion.

## Skipped tests

132 tests were skipped by their existing environment gates, primarily local/online PostgreSQL, Redis and pgvector integration evidence. Four additional historical PostgreSQL-only files had to be explicitly excluded because they import a fixture that reads `STAGE06_LOCAL_DATABASE_URL` without carrying a local `skipif` marker.

## Remaining risks

1. Gold entries are agent-audited but not human-approved.
2. Aggregate/result Gold is source-audited and hash-frozen, but must be recomputed through the Stage12-C deterministic engine once that engine exists.
3. PostgreSQL fixture replay is not proven on this machine because the configured role cannot create the `vector` extension.
4. r75 lacks V2 trace identities, so it cannot be converted into a truthful V2 product-quality score.
5. Three-round real-LLM variance and Provider failure rate remain deliberately deferred to final Stage12 acceptance.

## Temporary cleanup

No temporary scripts, databases, test output files, provider sessions, Telegram resources or external artifacts were created. Python bytecode produced by `compileall` is ignored build output and is not part of the change set.

## Next gate

Stage12-B must begin with its own code-level plan and failing tests for `TaskSpec V2`, `ActionSlot`, lexical parsing, schema binding, conflict detection and shadow comparison. It must not implement Stage12-C query execution or later-stage Retrieval/Specialist/Action behavior early.
