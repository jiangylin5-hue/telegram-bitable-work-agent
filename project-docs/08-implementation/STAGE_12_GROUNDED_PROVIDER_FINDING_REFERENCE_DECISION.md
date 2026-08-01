# Stage12 Grounded Provider Finding Reference Decision

## Status

- Status: `accepted-local-implementation`
- Date: 2026-08-01
- Scope: private Grounded Answer Provider finding references, objective coverage and final campaign release propagation
- Public API / database / permission / Telegram impact: none
- Production activation: not authorized by this decision
- Implementation gate: user explicitly confirmed `finding refs + final gate` on 2026-08-01

## 1. Trigger

The compact-reference and hard-deadline focused suite passes, but the required adjacent 48-case campaign exposed a pre-existing contract gap:

- `StructuredFactSetV1`, `RiskAssessmentSetV1` and `DailyBriefV1` are projected into `GroundedAnswerProviderRequestV2`;
- `GroundedAnswerStatementV2` can reference only claim, evidence and action handles;
- completed `risk_analysis` and `daily_summary` objectives can therefore have a sealed typed finding but no legal output reference that covers the objective;
- a valid test Provider reaches all `144/144` calls, yet `90/144` answers are rejected as `grounded_answer_required_objective_missing` and fall back;
- the current final campaign summary can still report `release_gate_pass=True`, because per-case `FinalAnswerQualityScoreV2.gate_pass` failures are not propagated into the campaign release gate.

This is not a model-quality failure and cannot be fixed safely by prompt changes or by weakening objective coverage.

## 2. Proposed Decision

### 2.1 Typed finding references

Extend only the private Provider contract:

- every `GroundedSpecialistFindingV2` carries its exact request-local `objective_handle`;
- every `GroundedAnswerStatementV2` carries `finding_handles[]` in addition to claim/evidence/action handles;
- analysis/recommendation/daily/risk statements may be grounded by an exact typed finding reference;
- the backend, not the Provider, expands each finding reference into its sealed claim/evidence closure before atom validation and receipt rendering;
- the Provider may not invent, duplicate or reorder a finding alias, and may not use a finding outside its request-local closure;
- canonical finding artifacts, claims, evidence and versions remain backend-only.

`FinalAnswerRenderReceiptV1` continues to contain canonical objective/claim/evidence/action identities. No public receipt schema changes.

### 2.2 Zero-claim action prerequisites

When an Action objective has a sealed pending/denied/deferred Action status and the planner also emitted an internal `fact_query` prerequisite with no ClaimGraph claim, the action-status statement may cover that zero-claim prerequisite. This does not authorize execution and does not convert an unverified fact into a user-visible fact.

### 2.3 Final campaign gate

Add a non-compensable final-answer-quality campaign metric:

- observed count must equal `144`;
- every result must have `FinalAnswerQualityScoreV2.gate_pass=True`;
- every result must have `real_provider_origin=True`;
- any fallback, grounding failure, schema failure or language failure makes the campaign release gate fail even if all other means pass.

## 3. Rejected Alternatives

- Treat completed Risk/Daily objectives as limitations: misrepresents a completed specialist result as degradation.
- Mark missing objectives optional at render time: weakens the sealed `TaskSpecV2` contract and hides Planner defects.
- Let Action status cover all objectives unconditionally: would allow unrelated factual objectives to pass without evidence.
- Keep the summary gate unchanged: reproduces the false-positive acceptance that the user explicitly rejected.

## 4. Required RED/GREEN Evidence

1. A typed Daily/Risk finding can cover its exact objective through `finding_handles[]` and renders canonical receipt closure.
2. Unknown, duplicate, reordered, cross-objective and stale finding bindings fail closed.
3. Invented atoms, citation closure, permission, Action-status and language tests remain green.
4. Zero-claim Action prerequisite coverage is limited to the defined Action case and cannot cover an unrelated fact objective.
5. A valid deterministic test Provider produces `144/144` real-origin, grounding-valid answers with zero fallback.
6. Three injected Provider failures produce exactly three final-answer failures and force the campaign release gate to fail.
7. The compact-reference, hard-deadline, ClaimGraph, isolated-runner and full backend regressions remain green before real P1.

## 5. Confirmation Gate

User confirmation was received on 2026-08-01. Local RED/GREEN implementation is authorized; deployment and production activation remain outside this decision.
