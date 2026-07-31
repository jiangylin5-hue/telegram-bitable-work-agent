# Stage12 最终质量总验收实施计划

## Status

- Status: in progress
- Scope: strictly the approved Stage12 final acceptance gate after Stage12-A–F local technical acceptance
- Source of truth: `project-docs/02-architecture/stage12-quality-v2/07_SECURITY_OBSERVABILITY_AND_SLO.md` and `project-docs/02-architecture/stage12-quality-v2/08_DELIVERY_TEST_AND_ACCEPTANCE.md`
- Runtime boundary: isolated synthetic workspace only; no production dispatch activation, deployment, production migration, real business write, proposal confirmation, notification delivery or Telegram send
- Rule: TDD; each behavior starts with a test that fails for the intended missing capability. Any change to architecture, schema, API, permission semantics, model/embedding profile or production feature flags requires a new decision and user confirmation.
- Correction dependency: TDR-020 and `2026-07-30-stage12-architecture-correction.md` are approved; Tasks 2–9 below execute only after their corresponding correction-plan prerequisites are green.

## Acceptance interpretation

0. Final answer quality is the primary product acceptance criterion. Planner, Query, Retrieval and Specialist scores are diagnostic dimensions only; they cannot substitute for a correct, complete, grounded and instruction-satisfying user answer. Permission, write and send safety remain non-compensable hard gates.
1. Structured table facts are scored from the authorized Query Engine trace. They are not forced through embedding retrieval.
2. Retrieval V2 is scored on the approved retrieval benchmark corpus and on any final-case objective that actually requires unstructured evidence; structured-only final cases use `not_applicable`, never fabricated candidate IDs.
3. Gold remains scorer-only. The execution request contains only query, round identity and an isolated runtime context; it never contains expected objectives, records, relation paths, aggregates, action targets, fields or values.
4. Action evaluation starts from Planner ActionSlot plus authorized Query results and candidate resolution. The campaign may persist only pending/denied disposable proposals; it never confirms them and never sends externally.
5. The final report must preserve every case/round trace and additionally report mean, worst round, population variance, failure rate, Provider/model/profile, segmented latency and all hard safety deltas.
6. Human Gold approval is independent from agent audit. No script may rewrite `agent_audited_pending_human_signoff` to `human_approved` without explicit user review evidence.
7. Every final answer is evaluated for factual correctness, result completeness, relation/aggregate correctness, grounding, instruction/action satisfaction, Chinese clarity and appropriate refusal/degradation. A failed final answer remains failed even when its component traces meet their individual thresholds.

## Tasks

- [x] 1. Extend the leak-free report contract with per-round and aggregate summaries. Cover mean, minimum, population variance, failure rate, P95 total latency and the literal release thresholds from the approved SLO. Missing observations and any safety failure must fail closed. RED: `4 failed, 3 passed` because `summarize_final_campaign` was absent. GREEN/refactor: `8 passed`; Black formatting API reports both changed files `formatted` (the Black CLI file-discovery path timed out and is not counted as a CLI pass).
- [x] 2. Add an isolated Stage12 execution context and A–C trace adapter. The raw-query runner and leak guards are implemented with deterministic `48/48` evidence.
- [x] 3. Add Retrieval applicability and evidence projection. Structured-only Cases use `not_applicable`; the Retrieval V2 corpus remains a separate hard gate.
- [x] 4. Compose actual Query artifacts through distinct typed handlers and ClaimGraph/Composer. Tabular/Risk/Daily execute in the integrated runner, Specialist-derived facts retain distinct ownership, and F is the integrated Action authority.
- [x] 5. Add blind ActionSlot expansion and disposable persistence projection. F durable expansion, semantic validation, pending/denied persistence and zero effects are implemented; direct integration evidence covers update/create/task and pre-dispatch reminder denial.
- [x] 6. Add an atomic sanitized CLI/report boundary. Deterministic mode is implemented; final mode remains prohibited until Human Gold and must execute exactly three rounds.
- [x] 7. Run focused deterministic and infrastructure verification. Post-ISO-01 evidence is `48/48`, focused `113`, Stage12/Planner `307`, backend `2377/40`, PostgreSQL/pgvector `7`, Mini App `413`, and build PASS.
- [x] 8. Present the 48-case Gold review manifest for explicit human sign-off. The user explicitly confirmed the frozen manifest on 2026-07-31; regenerated status is `human_approved`, count `48/48`, manifest hash `5b959d049c4f46f9dbd92e65c1dfe17a81a357f394f2f9a33b34da4e6ee28114`.
- [x] 9. After Gold sign-off, execute the approved `48 Case × 3` real-LLM campaign, compare every hard gate, report mean/worst/variance, and stop on any safety failure. The auditable campaign completed and correctly returned release `FAIL`; evidence is `project-docs/08-implementation/evidence/stage12-final-provider-campaign-2026-07-31/`.
- [ ] 10. Write final Stage12 acceptance/evidence and update `Current Progress`, handoff and indexes. Stage12 remains incomplete until every required gate has direct evidence.

## 2026-07-31 real-campaign result

- Human Gold: `48/48`.
- Retrieval: three completed real BGE-M3 rounds; Recall@20 `1.0` in every round, MRR@20 `0.958333` in every round, zero action/write/send effects.
- Composer availability: unavailable `34/48`, `35/48`, `34/48`; aggregate unavailable rate mean `0.715278`, worst `0.729167`. Failure attempts were dominated by `provider_schema_invalid` (`57/59/54`) and `provider_semantic_invalid` (`13/13/15`), plus one HTTP failure.
- End-to-end: `mixed_02` and `mixed_08` failed closed in every round, so core quality metrics were `46/48 = 0.958333`; all safety side-effect counts remained zero. P95 total latency mean was `14475.083333 ms`, worst `15101.8 ms`.
- Result: release `FAIL`, bundle hash `1642b7ff5124f710477033b6d29c76a2328f0b57d976971723f2d9f515cb13e6`.
- A prior real invocation completed calls but produced no acceptable bundle because the new runner compared the Retrieval profile's stable ID against its CLI alias. That evaluation-tool defect was fixed and front-loaded before Composer; the discarded invocation is not included in the reported three-round statistics.
- Immediate non-architectural corrections: reject duplicate Provider section kinds before receipt rendering, retain isolated execution failure codes in future round failure counts, and keep the current failed bundle immutable.
- Architecture decision still required: replace Provider re-emission of all objective/claim/action IDs with a bounded selection/order contract over deterministic prebuilt sections. Do not implement or rerun a final real campaign until the user approves this internal Provider contract change.

## Pre-signoff final-runner completion

2026-07-31 preflight found that `run_v2_report()`, `summarize_final_campaign()`, the real Composer adapter and the real Retrieval V2 benchmark exist independently, but no final command binds them into the approved three-round campaign. The deterministic isolated CLI cannot inject a real Provider and therefore cannot execute Task 9 after Human Gold.

This is an implementation gap inside the already-approved evaluation boundary, not a new product architecture decision. Before real invocation:

1. Add an evaluation-only final campaign runner that refuses any truth set whose 48 audit entries are not all `human_approved`.
2. Hard-code exactly three rounds and `materialize_actions=True`; do not expose a looser CLI override.
3. Bind the frozen `google/gemini-2.5-flash` Composer profile and run three independent real BGE-M3 retrieval rounds.
4. Derive Provider availability, attempts/tokens/latency, confirmation/write/send counts and retrieval recall from runtime observations; never accept them as CLI score inputs.
5. Atomically emit the full scored report, aggregate summary and sanitized observability artifacts. Stop the release gate on any safety delta or missing observation.
6. Cover the runner with fake Provider/retrieval TDD before Human Gold. Real network invocation remains prohibited until explicit 48/48 sign-off.

## Required hard gates

```text
human_gold_signoff = 48/48
objective_exact >= 0.90
predicate_exact >= 0.90
retrieval_candidate_recall_at_20 >= 0.95
final_record_precision >= 0.90
final_record_recall >= 0.90
join_path_accuracy >= 0.95
aggregate_exact >= 0.95
unsupported_claim_rate <= 0.02
action_slot_exact >= 0.90
action_target_accuracy >= 0.95
action_field_accuracy >= 0.95
action_value_accuracy >= 0.95
draft_persistence >= 0.95
permission_safety = 1.00
external_send_safety = 1.00
provider_unavailable <= 0.02
p95_total_latency <= 8000 ms
telegram_send_count = 0
confirmed_action_count = 0
production_write_count = 0
```

## First TDD slice

The first implementation slice is Task 1 only:

- a passing report is summarized across three literal rounds;
- a single safety failure makes the aggregate release gate fail even if means pass;
- a missing observed metric fails closed rather than disappearing from the denominator;
- population variance and worst-round values are hand-derived literals;
- no execution callback or external Provider is invoked by summary tests.
