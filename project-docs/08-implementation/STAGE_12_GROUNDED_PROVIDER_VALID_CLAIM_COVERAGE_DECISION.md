# Stage12 Grounded Provider Valid-Claim Coverage Decision

## Status

- Status: `accepted-local-implementation`
- Date: 2026-08-01
- Scope: private Grounded Answer request projection and deterministic coverage validation only
- Implementation status: complete with focused and adjacent local evidence
- Production status: not deployed or activated
- Confirmation: user explicitly approved `valid-only claim projection + exact
  claim coverage` on 2026-08-01

## Trigger

The confirmed Seed 2.0 Lite versus GLM 5.2 representative real-Case A/B used
the same 12 Human-Gold Cases, strict Schema, Grounded V2 adapter, one bounded
repair and 50-second total deadline. After the clarified construction prompt:

| Candidate | Real Provider | Final-answer gate | Fallback | Provider p95 |
| --- | ---: | ---: | ---: | ---: |
| `bytedance-seed/seed-2.0-lite` | 9/12 | 9/12 | 3 | 6,482 ms |
| `z-ai/glm-5.2` | 11/12 | 10/12 | 1 | 14,984 ms |

Neither candidate passed the zero-fallback and `12/12` final-answer gate, so no
model winner was selected. No failed Case was selectively accepted.

## Confirmed Contract Gaps

### 1. Non-valid claims remain Provider-visible but are not answerable

`risk_02` contains valid fact claims plus two `conflicted` risk claims. The
request projects all claims, while deterministic validation correctly prohibits
direct use of non-valid claims. The atom validator nevertheless sees their
subject/predicate/value tokens. Both models repeatedly used the natural
`风险等级` wording exposed by those conflicted claims and failed
`grounded_answer_unreferenced_atom`, including after repair.

This creates a contradictory private contract:

```text
Provider can see conflicted claim text
-> Provider cannot cite that claim
-> repeating its visible wording can still fail atom validation
```

### 2. Objective coverage does not imply result-set coverage

The validator currently passes an Objective after any referenced valid claim or
finding covers it. The final-answer scorer correctly requires the render receipt
to cover exactly every runtime valid claim and citation edge.

In the measured `join_01` run, the Provider plan passed Grounded validation and
produced a real answer, but the final gate failed `citation_grounding_failed`
because the receipt covered only a subset of the valid result claims. Therefore
the Provider validator and the final acceptance contract disagree.

## Proposed Decision

After explicit user confirmation:

1. Project only `status=valid` claims into `GroundedAnswerProviderRequestV2.claims`.
   `stale` and `conflicted` claims remain sealed in `ClaimGraphV1`, runtime audit
   and deterministic status calculation; they are not offered as answerable
   Provider facts.
2. Preserve denied/degraded/failed Objective status and safe reason codes through
   the existing Objective/limitation path. Preserve typed Specialist conclusions
   through sealed `finding_handles` linked only to valid claims.
3. Require the accepted Provider plan to cover every Provider-visible valid claim
   and its exact evidence closure, not merely one claim per Objective.
4. Reject duplicate claim coverage across statements so the same fact cannot be
   repeated to satisfy the set check.
5. Keep current permission, scope, schema, field-policy, runtime-binding, atom,
   Action, language and citation validators unchanged or stricter. Do not treat
   stale/conflicted values as valid and do not weaken the final scorer.
6. Add RED/GREEN regressions for `risk_02`-shaped conflicted claims and
   `join_01`-shaped multi-claim completeness before another real A/B.
7. Re-run the complete same 12-Case A/B once. No selective Case retry or merged
   model output may count as acceptance.

## Boundary And Impact

This changes only the private Provider input and validator agreement. It changes
no public HTTP/SSE API, database schema, permission model, Action authority,
embedding/retrieval model, Telegram behavior, deployment topology or production
activation. `ClaimGraphV1` still retains non-valid claims for audit and conflict
handling; only their exposure as answer candidates is removed.

## Acceptance Criteria

1. A request built from mixed valid/conflicted claims exposes only valid claim
   handles while preserving the graph binding and safe Objective state.
2. A plan omitting any visible valid claim fails
   `grounded_answer_required_claim_missing`.
3. A plan covering one claim twice fails
   `grounded_answer_claim_repeated`.
4. Existing unknown-reference, citation-closure, invented-atom, Action,
   limitation, permission and runtime-binding tests remain green.
5. The same representative real-Case A/B produces a new immutable report; old
   inconclusive reports remain retained and are not overwritten.

## Acceptance Evidence

- Focused and adjacent Grounded/ClaimGraph/final-campaign suite:
  `84 passed in 29.84s`.
- The request exposes only valid claims and derives conflicted-only Objective
  status as `degraded/conflicted_claim`; runtime binding revalidates that
  projection.
- Fact, Risk and Daily findings now use exact artifact-derived Claim identities;
  redundant closures are removed and internal aggregate IDs/UUID/JSON remain
  suppressed.
- Same 12-Case immutable A/B result:
  `b968f3e0e8d8cacb3a661a46b1005e573fbf13f5eaa61daf88b74a45d5998a58`.
- GLM 5.2: `12/12` real Provider, `12/12` final-answer gate, zero fallback.
- Seed 2.0 Lite: `11/12`; the failed Case remains failed and was not merged or
  selectively accepted.
- No production write, Telegram send, deployment or model-binding change was
  performed by this acceptance.

## Confirmation Gate

```text
确认 valid-only claim projection + exact claim coverage
```

## References

- `backend/app/services/agent_grounded_answer_request.py`
- `backend/app/services/agent_grounded_answer_validation.py`
- `backend/scripts/stage12_quality_evaluation.py::_answer_citations_match_receipt`
- `project-docs/08-implementation/STAGE_12_GROUNDED_PROVIDER_FINDING_REFERENCE_DECISION.md`
- `project-docs/08-implementation/STAGE_12_GROUNDED_COMPOSER_DOMESTIC_CANDIDATE_DECISION.md`
