# Stage12 Task 9 Final Answer Quality Correction Implementation Plan

## Status

- Status: `implemented-local-correction`; next core correction wave requires separate confirmation
- Approved proposal: `project-docs/08-implementation/STAGE_12_TASK9_FINAL_ANSWER_QUALITY_CORRECTION_PROPOSAL.md`
- Workspace: existing linked worktree `codex/stage09-ai-conversation-sse`
- Method: strict RED/GREEN/refactor, one observable behavior at a time
- Boundary: synthetic isolated Stage12 only; no deployment, activation, confirmed Action, business write, notification or Telegram send

## Dependency Order

```text
bounded AnswerPlan + render receipt
-> final-answer hard-gate scorer
-> A–F Action/permission/degradation/required-fact wiring
-> real Composer Provider adapter
-> focused acceptance
-> regenerate Gold manifest
-> separate 48/48 human Gold sign-off
-> exactly three real Provider rounds
```

## Task 1 — Bounded AnswerPlan and deterministic receipt

Files:

- `backend/app/schemas/agent_specialist_results.py`
- `backend/app/services/agent_claim_graph.py`
- `backend/app/services/agent_composer_v2.py`
- `backend/tests/unit/test_agent_composer_v2.py`

TDD sequence:

1. RED: a valid Provider plan may group/reorder only known required objective, Claim and Action IDs and produces a Chinese answer plus hashed renderer-owned receipt.
2. RED: unknown/duplicate IDs, omitted required objectives/Claims/Action statuses and raw free-form factual prose fail closed to `provider_semantic_invalid`.
3. RED: denied, conflicted, deferred and optional degraded statuses produce explicit Chinese disclosures; no success/write/send claim is possible.
4. GREEN: add strict `ComposerAnswerPlanV2`, section plan, citation edge and `FinalAnswerRenderReceiptV1` contracts; bind receipt to answer, ClaimGraph, scope and statuses.
5. GREEN: render factual values/citations and controlled connectors deterministically; Provider owns section grouping/order only.

Acceptance: deterministic fallback and bounded Provider plan both produce receipt-verifiable answers; existing unsupported-prose safety remains green.

## Task 2 — Final-answer hard-gate score

Files:

- `backend/scripts/stage12_quality_evaluation.py`
- `backend/scripts/stage12_real_quality_report.py`
- `backend/tests/unit/test_stage12_quality_answer_action_safety_scores.py`
- `backend/tests/unit/test_stage12_real_quality_report.py`

TDD sequence:

1. RED: `permission_01` false success prose fails refusal appropriateness.
2. RED: fluent Chinese with missing required Claim/Objective/Action coverage fails instruction satisfaction/completeness.
3. RED: hidden degradation, missing relation/aggregate coverage, wrong citation edge, raw JSON-only, mojibake and duplicate sections each fail their own dimension.
4. RED: a fully receipt-bound Chinese response passes all seven dimensions.
5. GREEN: add `FinalAnswerQualityScoreV2` with seven non-compensable dimensions and reason codes.
6. GREEN: make `CaseScoreV2.release_gate_pass` and final three-round summary require the final-answer gate; expose every dimension's mean, worst and population variance.

Acceptance: changing only `rendered_answer` can change the final-answer gate; no component score can rescue it.

## Task 3 — Correct A–F final-answer wiring

Files:

- `backend/scripts/stage12_isolated_af_runner.py`
- `backend/app/services/agent_claim_graph.py`
- related focused tests

TDD sequence:

1. RED: Action admission occurs before fan-in/Composer and every slot status appears in the final receipt/answer.
2. RED: permission denied/partial outcomes are derived from runtime Planner/Query/Action observations rather than a constant `allowed` value.
3. RED: required result identities, relation output and aggregate facts reach ClaimGraph without inventing values or leaking Gold.
4. RED: optional failure produces explicit degradation while retaining verified facts; required failure produces a safe refusal.
5. GREEN: minimally reorder and enrich the isolated pipeline while preserving raw request blindness and zero external effects.

Acceptance: representative join, aggregate, draft, reminder, partial-permission, denial and fault Cases produce independently checkable final receipts.

## Task 4 — Real Composer Provider adapter

Files:

- `backend/app/services/agent_composer_provider.py` (new if needed)
- `backend/scripts/stage12_isolated_af_runner.py`
- focused unit tests with a transport-boundary fake only

TDD sequence:

1. RED: the existing frozen `google/gemini-2.5-flash` Composer profile receives only permission-filtered ClaimGraph/Objective/Action IDs and strict AnswerPlan JSON schema.
2. RED: schema, semantic, language, citation, timeout, 429 and quota failures retain the approved error taxonomy and safe deterministic fallback/degradation.
3. RED: Provider metadata/model/profile/attempts/latency are emitted into sanitized observations.
4. GREEN: wire the existing `ModelGatewayV1` and baseline profile; do not add or change a model/profile decision.

Acceptance: focused fake-boundary tests prove request shape and failure handling; no real call is counted until the human Gold gate opens.

## Task 5 — Focused acceptance and next gate

1. Run Composer, ClaimGraph, Evaluation, report, isolated A–F and no-Gold-leak focused tests.
2. Run all 48 deterministic Cases and require complete trace or explicit fail-closed error; list every final-answer failure rather than averaging it away.
3. Run compile, format/diff, secret scan and temporary cleanup checks.
4. Update proposal, correction SOT, implementation index, handoff and retained evidence with actual results.
5. Regenerate the reviewer manifest and verify fixture/Gold hashes.
6. Stop for separate explicit 48/48 human Gold sign-off. Do not start exactly three real Provider rounds in the same approval step.

Acceptance: no oral completion; every proposal criterion has direct test/evidence and remaining failures are listed.

## Implementation Result

- Tasks 1–4 and the approved Task 5 verification boundary are implemented locally.
- All 48 deterministic executions produce complete receipts; safety and refusal/degradation gates are `48/48`.
- The final-answer hard gate is `30/48`; the complete Case release gate is `10/48`.
- The 18 remaining failing Cases are retained in `project-docs/08-implementation/evidence/stage12-task9-final-answer-correction-2026-07-30.md`.
- Planner decomposition, Query relation/aggregate semantics and ActionSlot normalization are outside this approved correction boundary and require separate confirmation.
- Human Gold remains `0/48`; exactly three real Provider rounds have not started.
