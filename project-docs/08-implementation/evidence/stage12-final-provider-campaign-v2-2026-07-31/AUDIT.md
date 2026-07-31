# Stage12 Bounded Composer Real Provider Campaign Audit

## Status

- Status: `FAIL`
- Scope: frozen Human-Gold 48 Cases, exactly three independent real Retrieval/Composer rounds after the bounded deterministic-section correction
- Human Gold: `48/48`
- Manifest hash: `5b959d049c4f46f9dbd92e65c1dfe17a81a357f394f2f9a33b34da4e6ee28114`
- Runtime approval hash: `b5448bcd7315b3a9449f6cfd9d355394c85a0d4c983b408b8fa3c8228689dff1`
- Bundle hash: `6b15446524a5a084d744dfc82564a73354d1477260c8e2e705375e9c392f1aa8`
- Production activation: unchanged; Stage11/r76 remains authoritative

## Result

The correction is a positive improvement to returned-answer integrity, but it does not pass the Stage12 release gate.

- All `144/144` Case results passed Planner, Query, Retrieval, Answer, final-answer, Action, Safety and Durability release dimensions.
- Every final-answer metric has mean/worst `1.0`: factual correctness, required-result completeness, relation/aggregate correctness, citation grounding, instruction/action satisfaction, Chinese clarity and refusal/degradation appropriateness.
- `mixed_02` and `mixed_08` no longer collapse into empty fail-closed traces.
- Unsupported claim rate remained `0`; confirmed actions, production writes and Telegram sends remained `0/0/0`.
- Retrieval completed all three rounds with Recall@20 `1.0`, MRR@20 `0.958333`, forbidden candidates `0` and effects `0/0/0`.
- Release remains `FAIL` because Composer availability and total latency miss their unchanged hard gates.

## Provider observations

| Round | Required | Unavailable | Attempts | Schema invalid | Semantic invalid | Provider latency mean | Provider latency P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 01 | 48 | 36 | 85 | 72 | 1 | 4111 ms | 8983 ms |
| 02 | 48 | 47 | 96 | 94 | 1 | 3603 ms | 5003 ms |
| 03 | 48 | 37 | 86 | 74 | 1 | 3819 ms | 7608 ms |

The aggregate Provider unavailable rate was mean `0.833333`, worst `0.979167`, population variance `0.010706`, observed `3/3`; the gate is `<= 0.02`.

Every unavailable Case exhausted two schema-invalid attempts. One additional semantic-invalid attempt occurred in each round and recovered. The bundle deliberately retains only sanitized failure taxonomy and aggregate telemetry, not raw Provider output, so the exact malformed response shape cannot be proven from this evidence.

## Latency

Total-latency P95 was observed for all `144/144` results. The summary was:

- mean of round P95: `11636.716667 ms`;
- worst round P95: `13775.800000 ms`;
- population variance: `2897161.287222`;
- gate: `<= 8000 ms`, therefore `FAIL`.

## Comparison with the immutable pre-correction baseline

| Dimension | Pre-correction bundle | Bounded correction bundle | Direction |
| --- | ---: | ---: | --- |
| Complete Case/final-answer quality | `46/48` each round | `48/48` each round | improved |
| Final-answer metric worst | `0.958333` | `1.0` | improved |
| Collapsed Cases | `mixed_02`, `mixed_08` every round | none | improved |
| Total-latency P95 mean | `14475.083333 ms` | `11636.716667 ms` | improved but still fails |
| Total-latency P95 worst | `15101.8 ms` | `13775.8 ms` | improved but still fails |
| Provider unavailable mean | `0.715278` | `0.833333` | regressed |
| Provider schema-invalid attempts | `170` | `240` | regressed |
| Provider semantic-invalid attempts | `41` | `3` | improved |

The deterministic ownership/fallback architecture therefore fixes the user-visible answer collapse and semantic-reference problem. It does not fix real model conformance to the strict response schema. Most passing answers in this campaign came through deterministic fallback, so this evidence must not be described as reliable real-Provider composition.

## Verification and hygiene

- `FinalProviderCampaignBundleV1.model_validate_json` accepted the bundle and recomputed its content hash.
- Shape: `case_count=48`, `rounds=3`, `results=144`; round identities are exactly `round-01` through `round-03`.
- Human Gold is `48/48`; output directory was absent before execution.
- No selective retry, extra round or merge was performed. The real command ran once and returned exit code `1` only because `release_gate_pass=false` after writing the complete bundle.
- The evidence directory contains only the JSON bundle, generated Markdown summary and this audit; `.tmp` count is zero.
- Secret-value, raw query/prompt/response, Gold payload and nonzero-effect scans are empty.
- Final same-revision backend verification: `2411 passed, 40 skipped in 399.67s`; skips are 3 Stage10 Redis, 17 Stage02 online PostgreSQL, 3 Stage08 collaboration PostgreSQL and 17 Stage08 pgvector tests, and are not counted as passes.
- Final disposable PostgreSQL/pgvector verification: `7 passed in 7.24s`; Black, compileall, bundle model/hash and global diff checks passed.
- No deployment, production migration, Stage12 activation, confirmed Action, business write, notification or Telegram send occurred.

## Remaining decision

Stage12 is not complete and must remain inactive. The next correction is not authorized by this audit. The evidence supports three bounded options that require a separate user decision because they alter an internal contract, acceptance definition or technical profile:

1. replace the dynamic connector map with a strict list of `{section_handle, connector_code}` items and prove real OpenRouter/Gemini schema compatibility before another full campaign;
2. make Composer presentation planning optional and remove Provider availability from the release gate, accepting deterministic answer rendering as the product contract;
3. select a different frozen Composer model/profile after a focused real compatibility benchmark.

No further `48 × 3` run should be started until one option is documented, approved, implemented and passes focused real preflight.
