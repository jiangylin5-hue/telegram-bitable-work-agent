# Stage12 Grounded Composer Domestic Candidate Decision

## Status

- Status: `binding-implemented-p1-pass-p2-failed`
- Date: 2026-08-01
- Scope: Stage12 Grounded Composer model binding only
- Implementation status: fixed GLM binding implemented locally; P1 passed; P2 failed
- Production status: not deployed or activated
- Confirmation: user explicitly approved the Seed 2.0 Lite versus GLM 5.2
  representative real-Case A/B on 2026-08-01
- Binding confirmation: user explicitly confirmed the fixed
  `z-ai/glm-5.2` Composer binding on 2026-08-01

## Post-Correction Selection Result

After the separately approved valid-only Claim projection, exact Claim coverage,
exact Specialist finding closure and safe Daily projection corrections, the same
12 Human-Gold Cases were run once for each candidate with the unchanged strict
Schema, one bounded repair and 50-second total deadline:

| Candidate | Real Provider | Final-answer gate | Fallback | Provider mean / p95 |
| --- | ---: | ---: | ---: | ---: |
| `bytedance-seed/seed-2.0-lite` | 11/12 | 11/12 | 1 | 4,114 / 6,045 ms |
| `z-ai/glm-5.2` | 12/12 | 12/12 | 0 | 4,523 / 7,400 ms |

Selection result: `z-ai/glm-5.2` is the unique winner. Seed failed
`permission_04` with `provider_grounding_invalid` and is not accepted. The
immutable comparison content hash is
`b968f3e0e8d8cacb3a661a46b1005e573fbf13f5eaa61daf88b74a45d5998a58`.

The fixed model-binding confirmation gate below has been satisfied. The local
binding and post-change P1 evidence remain required before P2.

## Post-Binding Gate Result

- Production-bound P1: `12/12` HTTP, Schema, grounding and real Provider;
  fallback `0`; hash
  `08d1573aeec0f89632332ccff9716f313b11622e11619bf02a769fd43f3c3130`.
- Representative P2: `33/36` real Provider and final-answer gate; fallback `3`;
  hash `0702da842befaae8e3271e196515d1a3cb6231aaba9551fbb16c2c2707a820e7`.
- P2 failures remain failures. Full `48 × 3`, native deployment and Telegram
  acceptance are blocked before the proposed RenderSlot decision is reviewed.

## Representative Real-Case Result

The confirmed A/B was executed with the same 12 Human-Gold Cases. The first
run exposed a runner error that disabled the production bounded repair policy;
that report remains an invalid-for-selection, inconclusive diagnostic. After
restoring the existing two-attempt maximum and clarifying construction rules,
the latest complete comparison remained inconclusive:

| Candidate | Real Provider | Final-answer gate | Fallback | Provider p95 |
| --- | ---: | ---: | ---: | ---: |
| `bytedance-seed/seed-2.0-lite` | 9/12 | 9/12 | 3 | 6,482 ms |
| `z-ai/glm-5.2` | 11/12 | 10/12 | 1 | 14,984 ms |

No candidate is selected. The repeated failures exposed the separately
documented private valid-claim projection and exact-coverage contract gaps in
`STAGE_12_GROUNDED_PROVIDER_VALID_CLAIM_COVERAGE_DECISION.md`. Another A/B is
blocked until that decision is confirmed and implemented with RED/GREEN.

## Trigger

The confirmed compact-reference, typed-finding and cancellable hard-deadline
corrections removed the previously identified request-contract failures. Two new
complete DeepSeek V3.2 P1 campaigns nevertheless failed the unchanged zero-
fallback gate:

| Campaign | HTTP | Schema | Grounding | Real Provider | Failure |
| --- | ---: | ---: | ---: | ---: | --- |
| post-correction attempt 01 | 11/12 | 11/12 | 11/12 | 11/12 | `provider_timeout=1` at 50,013 ms |
| post-correction attempt 02 | 11/12 | 10/12 | 10/12 | 10/12 | `provider_timeout=1`, `provider_schema_invalid=1` |

The failures were retained as failures. No fallback, selected-Case retry, relaxed
Schema, increased timeout or altered scoring was used to make them pass.

## Bounded Domestic Candidate Evidence

Every probe used the complete `GroundedAnswerPlanV2` JSON Schema, the production
Gateway and Grounded Provider adapter, `reasoning.effort=none`, one attempt, the
same 50-second hard deadline and no raw response persistence.

| Candidate | Four-shape result | Measured outcome |
| --- | ---: | --- |
| `qwen/qwen3.6-flash` | 0/4 | four `provider_schema_invalid` |
| `qwen/qwen3.6-plus` | 0/4 | four `provider_schema_invalid` |
| `moonshotai/kimi-k2.6` | 3/4 | 7-claim `provider_schema_invalid` |
| `z-ai/glm-5.1` | 2/4 | two `provider_schema_invalid` |
| `moonshotai/kimi-k3` | 4/4 | 6,552–9,473 ms; exceeds the 8-second target in one shape |
| `z-ai/glm-5.2` | 4/4 | 3,826–5,863 ms |
| `bytedance-seed/seed-1.6` | 0/4 | four `provider_http_error` |
| `bytedance-seed/seed-1.6-flash` | 0/4 | four `provider_http_error` |
| `bytedance-seed/seed-2.0-mini` | 4/4 | 2,018–4,286 ms |
| `bytedance-seed/seed-2.0-lite` | 4/4 | 3,372–5,006 ms |

The complete GLM 5.2 candidate campaign then passed:

```text
model_id=z-ai/glm-5.2
http_completed=12/12
schema_valid=12/12
grounding_valid=12/12
answer_source_real_provider=12/12
fallback_count=0
latency_min_ms=2327
latency_mean_ms=4772.5
latency_max_ms=6800
content_hash=a8042220ee45f5aa6cb7d0005e2fd04e4eaad05c1e1565499dad4952fafd628b
```

The complete ByteDance Seed 2.0 Lite candidate campaign also passed:

```text
model_id=bytedance-seed/seed-2.0-lite
http_completed=12/12
schema_valid=12/12
grounding_valid=12/12
answer_source_real_provider=12/12
fallback_count=0
latency_min_ms=2985
latency_mean_ms=4298.6
latency_max_ms=6485
content_hash=8f904946023c9fdd7c748ba8b8092de416bdf014b3f82cc2c8db06ea214244de
```

OpenRouter's current model metadata reports `reasoning`, `response_format` and
`structured_outputs` support for `z-ai/glm-5.2`. OpenRouter documents that
`require_parameters=true` restricts routing to endpoints that support the
requested structured-output parameters.

## Proposed Selection Gate

P1 proves compatibility and latency, not complex business-answer quality. Do not
select a final Composer solely from these synthetic results. Before requesting
the final model-binding confirmation:

1. Compare `z-ai/glm-5.2` and `bytedance-seed/seed-2.0-lite` on the same bounded
   representative Stage12 real-Case set and final-answer scorer.
2. Require real Provider origin, exact Schema/grounding, final-answer gate pass,
   zero fallback and measured latency for every compared Case.
3. Select one fixed winner from answer quality first, then stability and latency;
   do not use an automatic fallback between them.
4. Rename the private Composer profile ID so telemetry cannot mix model evidence.
5. Keep the complete fixed Schema, compact references, typed finding closure,
   semantic/grounding validation, `temperature=0.1`, 2,400-token ceiling,
   `reasoning.effort=none`, one-attempt P1, production retry policy and 50-second
   hard deadline unchanged.
6. Do not add automatic multi-model routing, silent model fallback or per-Case
   switching. One fixed model must own the complete P1/P2/P3 campaign.
7. Re-run the exact production-bound 12-call P1 after the code binding changes.
   The diagnostic candidate campaign is selection evidence, not a substitute
   for post-change P1 evidence.
8. Proceed to P2 only if the post-change P1 is again 12/12 with zero fallback.

## Boundary And Impact

This proposal changes no public HTTP/SSE contract, database schema, permission
model, Action authority, embedding model, Planner/Specialist model binding,
Telegram behavior, deployment topology or production activation state. Stage11
remains runtime authority until P1, P2, full regression, native server P3 and
Telegram gates pass.

## Confirmation Gate

The final implementation confirmation is not open until the representative
quality comparison identifies one winner. At that point the confirmation must
name the exact fixed model ID.

```text
确认 Stage12 Composer 切换至 z-ai/glm-5.2
```

## References

- `project-docs/00-governance/TECHNICAL_DECISIONS.md` TDR-023 through TDR-025
- `project-docs/08-implementation/STAGE_12_GROUNDED_PROVIDER_COMPACT_REFERENCE_DECISION.md`
- `project-docs/08-implementation/STAGE_12_GROUNDED_PROVIDER_FINDING_REFERENCE_DECISION.md`
- https://openrouter.ai/api/v1/models
- https://openrouter.ai/docs/guides/features/structured-outputs
- https://openrouter.ai/docs/guides/routing/provider-selection
