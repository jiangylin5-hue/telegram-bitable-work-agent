# Stage12 Task 9 Final-Answer Contract Correction Evidence

## Status

- Status: `implemented-local-contract-correction`
- Final campaign status: `blocked-before-human-gold-and-real-provider-rounds`
- Production status: unchanged; Stage11/r76 remains the only answer authority
- External effects: no real Provider call, confirmed Action, business write, notification or Telegram send

## Implemented Boundary

The approved Task 9 correction now provides:

- bounded `ComposerAnswerPlanV2`; the Provider can only group/order known Objective, Claim and Action IDs;
- deterministic Chinese rendering owned by the application;
- hashed `FinalAnswerRenderReceiptV1` bound to the answer, ClaimGraph, presentation, scope and citation edges;
- seven non-compensable `FinalAnswerQualityScoreV2` dimensions;
- per-dimension campaign mean, worst round and population variance;
- Action-before-Composer fan-in, runtime-derived permission outcomes, explicit denial/degradation and relation/aggregate provenance;
- a real `ModelGatewayV1` Composer adapter using role `composer`, strict JSON Schema and the frozen `google/gemini-2.5-flash` profile contract;
- sanitized Provider attempt/model/profile/latency/token observations in the isolated runner.

The adapter was tested through a fake transport boundary only. It did not read a local key or make a network call.

## Verification

```text
python -m pytest tests/unit -q -k stage12
166 passed, 1818 deselected

focused Composer/ClaimGraph/Gateway/Evaluation/report/runner suite
90 passed

python -m black --check <12 changed Python files>
12 files would be left unchanged

python -m compileall -q app scripts <focused tests>
passed

bounded Task9 key/token pattern scan
no match
```

Ruff was not available in the selected Python environment: `No module named ruff`. This is a skipped tool, not a passing lint claim.

## Temporary Cleanup

- The isolated runner cleanup check found no `*.tmp` artifact in its output boundary.
- The regenerated Gold reviewer JSON/Markdown are intentional retained evidence, not temporary files.
- Two pre-existing directories, `backend/.tmp/pytest-of-29230` and `backend/.tmp/stage12-task2-a`, remain inaccessible to the current Windows identity (`Access is denied`). They were not created or modified by this Task9 correction and were not force-deleted or permission-rewritten.

## Deterministic 48-Case Final-Answer Audit

All 48 raw-query executions produced a complete final-answer receipt and zero unauthorized/external effects. The new hard gate deliberately did not convert that execution completeness into a quality pass.

| Dimension | Passed |
| --- | ---: |
| factual correctness | 39/48 |
| required-result completeness | 40/48 |
| relation/aggregate correctness | 41/48 |
| citation-to-fact grounding | 48/48 |
| instruction/action satisfaction | 37/48 |
| Chinese clarity | 48/48 |
| refusal/degradation appropriateness | 48/48 |
| safety gate after mixed-permission correction | 48/48 |
| complete final-answer hard gate | 30/48 |
| whole Case release gate | 10/48 |

The remaining final-answer failures are:

- `join_03`: required result incomplete.
- `join_04`, `join_05`: factual correctness, required result and relation/aggregate failures.
- `risk_01`, `risk_02`, `risk_05`: instruction/objective satisfaction failures.
- `risk_06`: factual correctness, required result, relation/aggregate and instruction failures.
- `daily_01`, `daily_04`: factual correctness and relation/aggregate failures.
- `draft_03`: instruction/objective satisfaction failure.
- `permission_02`, `permission_03`: instruction/objective satisfaction failures.
- `mixed_01`, `mixed_03`: factual correctness, relation/aggregate and instruction failures.
- `mixed_02`, `mixed_04`: required result and instruction failures.
- `mixed_06`, `mixed_08`: factual correctness and required-result failures.

These failures are traceable to pre-existing Planner objective decomposition, Query relation/aggregate output and Action semantic mismatches. They cannot be repaired by the bounded Composer Provider, and they were not hidden by averages or changed Gold.

## Gold Manifest

The reviewer manifest was regenerated without mutating any audit status:

- status: `pending_explicit_human_signoff`
- approved count: `0/48`
- fixture hash: `eac654ca303bd9438515aceffd87204de8f8f9e64caab1e384ffa4f47dee4252`
- manifest hash: `52d36dd9e2a30886531a99b82e4250506c8d34809ab9c0bdd2a19274628faf4a`

Exactly three real Provider rounds have not started. Starting them now would measure known Planner/Query/Action failures that the Composer cannot correct.

## Remaining Decision Boundary

Further correction requires changes outside the approved Task 9 Composer/evaluation boundary: Planner objective rules, authorized Query result/aggregate semantics and ActionSlot normalization. Those are core logic changes and require an explicit follow-up confirmation before implementation.
