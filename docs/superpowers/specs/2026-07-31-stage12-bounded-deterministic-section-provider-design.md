# Stage12 Bounded Deterministic-Section Provider Design

## Status

- Status: `approved-for-implementation-planning`
- Scope: Stage12 internal Composer Provider contract correction only
- Trigger evidence: real Human-Gold `48 × 3` campaign bundle `1642b7ff5124f710477033b6d29c76a2328f0b57d976971723f2d9f515cb13e6`
- Production status: unchanged; Stage11/r76 remains authoritative
- User decision: option 1, bounded deterministic-section handles, approved in-thread on 2026-07-31

## 1. Problem Statement

The current `ComposerProviderRequestV2 -> ComposerAnswerPlanV2` boundary asks the model to reconstruct complete sections and repeat every authorized `objective_id`, `claim_id`, and `action_slot_id`. The real campaign measured Composer unavailable counts of `34/48`, `35/48`, and `34/48`. Provider attempts were dominated by `provider_schema_invalid` (`57`, `59`, `54`) and `provider_semantic_invalid` (`13`, `13`, `15`).

The same campaign exposed a second contract mismatch: a schema-valid Provider plan could repeat `section_kind`. `FinalAnswerRenderReceiptV1` requires unique section kinds, so the error could escape the Provider fallback boundary and collapse `mixed_02` and `mixed_08` into empty fail-closed traces. Duplicate section kinds are now rejected, but the Provider boundary remains unnecessarily generative.

The correction must make Provider participation reliable without moving facts, citations, permissions, actions, or execution authority into the model.

## 2. Goals

1. Build every answer section deterministically from the sealed `ClaimGraphV1`, presentation projection, and action statuses before any Provider call.
2. Let the Provider choose only the order of existing section handles and a bounded connector code for each handle.
3. Prevent the Provider from creating, removing, regrouping, or editing Objective, Claim, Citation, Action, permission, denial, or degradation content.
4. Keep Provider failure inside the Composer degradation boundary and return the complete deterministic answer instead of an empty runtime trace.
5. Reduce Provider output size and validation complexity enough to meet the existing availability and latency gates without weakening them.
6. Preserve the failed real campaign as immutable evidence and produce a separate post-correction campaign.

## 3. Non-Goals

- No public API change.
- No database model or Alembic migration.
- No permission, field-policy, ActionSlot, confirmation, Tool Gateway, write, notification, or Telegram change.
- No change to Planner, Query Engine, Retrieval V2, Specialist fact calculation, ClaimGraph fact authority, or Human Gold.
- No business-context design; that remains outside Stage12.
- No Stage12 production activation, deployment, production migration, or Stage11 dispatch change.
- No model/profile substitution. The frozen Composer profile remains `google/gemini-2.5-flash` / `composer.zh.baseline.v1` unless a separate measured decision is approved.

## 4. Chosen Architecture

```text
ClaimGraphV1 + authorized presentation + action statuses
  -> deterministic ComposerAnswerPlanV2
  -> DeterministicSectionSetV1
       private immutable section contents
       public bounded section candidates
  -> ComposerSectionOrderingRequestV1
  -> real Provider
  -> ComposerSectionOrderingPlanV1
       ordered_section_handles[]
       connector_by_handle{}
  -> exact handle/connector validation
  -> expand handles to original immutable sections
  -> render answer + receipt
```

`ComposerAnswerPlanV2` remains the internal complete plan and rendering input. The Provider no longer produces it. A new, smaller ordering contract is added at the Provider boundary.

## 5. Contracts

### 5.1 Private deterministic section

`DeterministicComposerSectionV1` is strict, frozen, and never serialized into the Provider response contract.

```python
class DeterministicComposerSectionV1(StrictFrozenModel):
    version: Literal["deterministic-composer-section.v1"]
    section_handle: str  # section:sha256:<64 lowercase hex>
    section: ComposerAnswerSectionPlanV2
    default_rank: int  # 0..6
    allowed_connector_codes: tuple[
        Literal["direct", "next", "however", "safety_boundary"], ...
    ]
    content_hash: Sha256Hex
```

`section_handle` is derived from the canonical payload of `section`, `default_rank`, and `allowed_connector_codes`. It does not contain a Case ID, record code, field value, prompt fragment, or Gold value.

The deterministic plan has at most one section for each existing kind:

```text
summary, facts, risks, daily, actions, denial, degradation
```

Maximum section count is therefore seven. Section-kind uniqueness is a deterministic invariant, not a Provider preference.

`DeterministicSectionSetV1` owns the private immutable collection:

```python
class DeterministicSectionSetV1(StrictFrozenModel):
    version: Literal["deterministic-section-set.v1"]
    sections: tuple[DeterministicComposerSectionV1, ...]  # 1..7
    content_hash: Sha256Hex
```

It validates unique section handles, section kinds, and contiguous `default_rank` values `0..len(sections)-1`; every child hash and the set `content_hash` must match canonical payloads. Tuple order must equal `default_rank` order.

### 5.2 Public Provider candidate

`ComposerSectionCandidateV1` contains only the bounded information needed for ordering:

```python
class ComposerSectionCandidateV1(StrictFrozenModel):
    section_handle: str
    section_kind: Literal[
        "summary", "facts", "risks", "daily",
        "actions", "denial", "degradation"
    ]
    objective_statuses: tuple[
        Literal["completed", "proposed", "degraded", "denied", "failed"], ...
    ]
    default_rank: int
    allowed_connector_codes: tuple[ConnectorCode, ...]
```

The candidate excludes Objective IDs, Claim IDs, Action IDs, evidence IDs, record identities, field identities, values, rendered facts, raw query text, and private source artifacts. `objective_statuses` is deduplicated and sorted in stable enum order.

### 5.3 Provider request

```python
class ComposerSectionOrderingRequestV1(StrictFrozenModel):
    version: Literal["composer-section-ordering-request.v1"]
    candidates: tuple[ComposerSectionCandidateV1, ...]  # 1..7
    default_order: tuple[str, ...]
    scope_hash: Sha256Hex
    schema_hash: Sha256Hex
    field_policy_version: Literal["stage12-field-policy.v2"]
    field_policy_hash: Sha256Hex
    content_hash: Sha256Hex
```

The request validates that:

- candidate handles are unique;
- `default_order` is an exact permutation of candidate handles;
- section kinds are unique;
- all candidates have at least one allowed connector;
- scope/schema/field-policy proofs are present and hash-valid.

### 5.4 Provider response

```python
class ComposerSectionOrderingPlanV1(StrictFrozenModel):
    version: Literal["composer-section-ordering-plan.v1"]
    ordered_section_handles: tuple[str, ...]  # 1..7
    connector_by_handle: dict[str, ConnectorCode]
```

Validation requires:

1. `ordered_section_handles` is an exact permutation of the request handles.
2. `connector_by_handle` has exactly the same key set.
3. Every connector is allowed by that candidate.
4. The first ordered handle uses `direct`.
5. No subsequent handle uses `direct`.
6. No unknown, missing, duplicate, blank, or malformed handle is accepted.

The Provider cannot omit a denied/degraded/action section to make an answer look successful.

## 6. Connector Policy

The deterministic builder assigns these allowed connectors:

| Section kind | Allowed connector codes |
| --- | --- |
| summary | `direct`, `next` |
| facts | `direct`, `next` |
| risks | `direct`, `next`, `however` |
| daily | `direct`, `next` |
| actions | `direct`, `next`, `safety_boundary` |
| denial | `direct`, `however`, `safety_boundary` |
| degradation | `direct`, `however`, `safety_boundary` |

When a Provider result is invalid or unavailable, the default deterministic plan and its existing connectors are used unchanged.

## 7. Expansion and Rendering

Expansion is a pure function:

```python
expand_ordering_plan(
    section_set: DeterministicSectionSetV1,
    ordering: ComposerSectionOrderingPlanV1,
) -> ComposerAnswerPlanV2
```

It performs handle lookup only. It copies the original `objective_ids`, `claim_ids`, `action_slot_ids`, and `section_kind` from the private deterministic section. Only section order and validated connector codes come from the Provider response.

After expansion, `_render_plan` applies only fixed Chinese connector text; the Provider never returns prose:

```text
direct          -> no prefix
next            -> 接下来，
however         -> 不过，
safety_boundary -> 安全边界：
```

The current renderer does not consume `connector_code`; implementing this fixed mapping is part of the correction and must be covered by exact rendering tests. `_render_receipt` then hashes the final answer. Receipt coverage must equal the deterministic plan coverage exactly.

## 8. Failure Semantics

Provider failures retain the existing taxonomy:

- `provider_schema_invalid`
- `provider_semantic_invalid`
- `provider_timeout`
- `provider_rate_limited`
- `provider_quota_exhausted`
- `provider_http_error`
- `deadline_exhausted`

Missing/duplicate/unknown handles, invalid connector maps, non-permutation order, or a connector outside the candidate allowlist are `provider_semantic_invalid`.

The Gateway may perform the existing single bounded repair attempt. If no valid ordering is produced, `compose_claim_graph` returns the complete deterministic plan with the Provider failure recorded as a degradation code. Provider failure cannot produce an empty trace, remove safe facts, change permission outcomes, or change Action status.

Only a deterministic invariant failure—for example, a section set whose own handles do not validate—may fail the Composer pipeline. Such a failure is an implementation defect, not a Provider availability event.

## 9. Observability

An attempt is `completed` only after the ordering response passes exact handle and connector validation. A schema-valid but unexpandable response is not counted as available.

The final campaign continues to derive, rather than accept as input:

- Provider required/unavailable counts;
- attempt and repair counts;
- input/output token counts;
- mean and P95 Provider latency;
- failure taxonomy;
- isolated execution failure taxonomy;
- confirmed action, production write, and Telegram send counts.

No raw Provider response, prompt, query, API key, record value, Gold object, or private section contents are written to evidence.

## 10. Security and Authority Invariants

1. Query Engine remains the authority for identifiers, filters, joins, counts, groups, sums, versions, and provenance.
2. Specialist artifacts and ClaimGraph remain the only source of answer facts and citations.
3. Provider input contains no unrestricted infrastructure handle or credential.
4. Provider output cannot introduce or remove an Objective, Claim, Citation, Action, denial, or degradation.
5. Action confirmation, persistence, Tool Gateway execution, business write, notification delivery, and Telegram send remain outside Composer authority.
6. Stage12 remains inactive in production until all release gates pass and deployment receives separate approval.

## 11. Compatibility and Rollout

- The public API and persisted schemas are unchanged.
- `ComposerAnswerPlanV2` remains the internal rendering plan, so deterministic callers and receipts do not need a V3 migration.
- `ComposerProviderAdapterV1` changes its internal callable boundary to ordering request/response types. Existing test fakes must be migrated; there is no deployed Stage12 consumer requiring dual-write or backward compatibility.
- No feature flag is activated. The corrected path remains limited to Stage12 local evaluation/shadow boundaries.
- The failed bundle `1642b7ff5124f710477033b6d29c76a2328f0b57d976971723f2d9f515cb13e6` is immutable and remains the pre-correction baseline.

## 12. Verification and Acceptance

### Contract and unit gates

- strict/frozen models; unknown fields rejected;
- stable handle and content hashes;
- request excludes raw query, facts, IDs, evidence, values, Gold, and secrets;
- exact permutation and connector-key coverage;
- missing, duplicate, unknown, malformed, reordered, and connector-forgery cases;
- repair success and repair exhaustion;
- deterministic fallback preserves exact receipt coverage;
- duplicate section kind cannot escape the Provider boundary;
- Provider failure never converts a complete deterministic Case into an empty trace.

### Deterministic and fake campaign gates

- all 48 deterministic Cases pass every component and complete release gate;
- fake valid ordering runs `48 × 3 = 144` Provider opportunities;
- fake invalid ordering proves safe fallback and sanitized failure counts;
- confirmed actions, production writes, and Telegram sends remain `0/0/0`;
- no Gold key or Case-ID branch enters production modules.

### Infrastructure gates

- affected Stage12/Planner/Composer suite passes;
- full backend regression passes with every skip classified;
- real local PostgreSQL/pgvector Stage12 suite passes;
- Alembic current equals single head `20260730_0039` and temporary schema count is zero;
- Mini App/build need rerun only if frontend files change; this design does not require a frontend change.

### Post-correction real campaign

Run one new, independent, auditable `48 Case × 3` campaign. Do not merge it with the failed baseline or selectively retry Cases. Existing hard gates remain unchanged, including:

```text
human_gold_signoff = 48/48
provider_unavailable_rate <= 0.02
p95_total_latency_ms <= 8000
permission_safety = 1.00
external_send_safety = 1.00
confirmed_action_count = 0
production_write_count = 0
telegram_send_count = 0
```

All answer-quality gates from the approved final campaign remain mandatory. Stage12 is not accepted if the new campaign fails any hard gate.

## 13. Expected Files

Implementation is expected to remain bounded to:

- `backend/app/services/agent_composer_v2.py`
- `backend/app/services/agent_composer_provider.py`
- `backend/scripts/stage12_isolated_af_runner.py`
- `backend/scripts/stage12_final_provider_campaign.py`
- `backend/tests/unit/test_agent_composer_v2.py`
- `backend/tests/unit/test_agent_composer_provider.py`
- `backend/tests/unit/test_stage12_isolated_af_runner.py`
- `backend/tests/unit/test_stage12_final_provider_campaign.py`
- Stage12 status, plan, handoff, and final evidence documents

`agent_model_gateway.py` changes only if a failing contract test proves the generic strict-schema/repair boundary cannot carry the smaller response. No database, API, frontend, permission, or Action file is in scope.
