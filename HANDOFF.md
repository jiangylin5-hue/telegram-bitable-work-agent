# Current Project Handoff

This root file is the stable current entry point. Stage11 extends the accepted
Stage10 read-only event runtime with a bounded coordination middleware while
retaining Stage08/Stage09/Stage10 documents as compatibility and evidence history.

Read it together with:

1. `AGENTS.md`
2. `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`
3. `project-docs/00-governance/PROJECT_STRUCTURE_AND_DOCUMENT_LIFECYCLE.md`
4. `project-docs/02-architecture/STAGE_11_MULTI_AGENT_COORDINATION_MIDDLEWARE.md`
5. `project-docs/08-implementation/STAGE_11_COMPLEX_CHINESE_EVALUATION_PROTOCOL.md`
6. `project-docs/08-implementation/STAGE_11_ACCEPTANCE.md`
7. `docs/superpowers/plans/2026-07-28-stage11-multi-agent-coordination.md`
8. `project-docs/08-implementation/evidence/stage11-r75-real-48case-report-2026-07-28.md`

The historical Stage07 R0-R3 handoff remains available through Git history and
the Stage07 implementation/evidence documents. It is not the current execution
entry.

## Current Progress

2026-07-29 final update: public artifact
`stage09-p1-20260729-r76-stage11-terminal-fan-in` is active with database head
`20260728_0034`. Stage11 adds deterministic multi-objective planning, a versioned
capability registry with fixed execution-skill bindings, durable tabular/risk/daily
commands, multi-command fan-out/fan-in, terminal failure semantics, a specialist
worker pool, strict OpenRouter action proposals and a Tool Gateway that can only
create pending drafts or blocked notification requests.

The final real evaluation used an isolated 7-table/39-record PostgreSQL fixture,
production identity dependency, Redis Streams, SSE and `google/gemini-2.5-flash`.
All 48 Chinese complex cases reached a parseable HTTP/SSE terminal result. Safety
passed (`permission_safety=1`, `external_send_safety=1`, 9 pending drafts,
7 blocked reminders, zero Telegram sends), but quality did not fully pass:
record precision/recall are `0.566/0.6521`, retrieval readiness is `0.7917`,
action/field/persistence are `0.8229`, objective exact match is `0.375`, and the
overall score is `83.8144` against an 85 target. Preserve these failures.

The public run endpoint durably executes the three read capabilities. Action
proposal/materialization is proven through a post-read backend adapter in the
acceptance runner, not yet as a fourth durable Redis command or a public UI action
contract. Do not claim unified durable action orchestration, automatic confirmation,
or production send authority. The next architecture stage should address retrieval
quality first, then define the explicit action-slot/authorized-candidate API before
adding an action worker.

The r75 artifact remains the exact real 48-case quality evidence source. r76 changes
only required-child terminalization so unfinished sibling commands cannot retry after
the Supervisor has failed a run; it does not alter the truth set, scorer, retrieval,
action proposal or LLM prompt used by the report.

Final verification covers all 1561 backend Unit/API tests through two complementary
fresh commands (one real child-process matrix plus the other 1560 tests). Production
health, six native services, Alembic head/current, warning journal, isolated action
statuses, revoked browser sessions and zero Telegram sends were rechecked after
cleanup. The loopback evaluation API, `/run` evaluation env, uploaded scripts and
r67-r72 Stage11 candidates were removed; r73-r76 and the test-only fixture remain as
explicit evidence/rollback artifacts.
