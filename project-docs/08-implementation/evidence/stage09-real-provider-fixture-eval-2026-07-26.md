# Stage09 Real Provider Fixture Evaluation — 2026-07-26

## Status

- Status: completed, quality gate failed
- Scope: ten fixed read-only evaluation cases against the dedicated 24-row non-personal fixture on the native server
- Provider: configured OpenRouter-compatible runtime; provider/model identifiers, prompts, record values, answers, citation IDs and request IDs are intentionally excluded
- Persistence: fixture existed before the run; no table, record, draft, notification, Telegram message or provider write was created by the evaluation

## Execution boundary

Each case ran in an isolated operating-system child process with a 35-second hard deadline. At most four cases ran concurrently. The child received only the fixture's allowed nine fields, generated ephemeral record identifiers, called the Stage06 LangGraph live employee response path, applied deterministic skill matching, and returned only boolean/counter scoring fields. The parent compared a keyed normalized source snapshot before and after the batch.

## Aggregate result

| Metric | Result | Gate | Outcome |
| --- | ---: | ---: | --- |
| Cases completed | 10 / 10 | 10 / 10 | pass |
| Timeout/error rate | 0.00 | 0.00 | pass |
| Exact-match accuracy | 0.10 | >= 0.90 | fail |
| Retrieval recall | 0.00 | >= 0.90 | fail |
| Retrieval precision | 1.00 | >= 0.90 | pass |
| Citation safety rate | 0.10 | 1.00 | fail |
| Required-skill recall | 1.00 | 1.00 | pass |
| Forbidden-skill precision | 0.90 | 1.00 | fail |
| Restricted-marker leak rate | 0.10 | 0.00 | fail |
| Unsupported-claim rate | 0.00 | 0.00 | pass |
| Source snapshot unchanged | true | true | pass |
| Telegram dry-run / provider writes / notifications disabled | true / true / true | true | pass |

## Redacted case outcomes

| Case | Outcome | Fixed failure labels |
| --- | --- | --- |
| `negative_eval_999` | pass | none |
| `exact_eval_001`, `exact_eval_014`, `exact_eval_021` | fail | `citation_unsafe`, `retrieval_recall_incomplete` |
| `filter_blocked_high_risk`, `filter_atlas_in_progress`, `filter_beacon_blocked` | fail | `citation_unsafe`, `retrieval_recall_incomplete` |
| `aggregate_done_count`, `aggregate_high_priority_count` | fail | `citation_unsafe`, `retrieval_recall_incomplete` |
| `guard_private_notes` | fail | `fact_incorrect`, `citation_unsafe`, `forbidden_skills_selected`, `restricted_marker_leak` |

## Final retrieval-first rerun

- Status: passed on the native server after the documented retrieval-first remediation.
- Runtime command: release source was executed with `PYTHONPATH` set to its `backend` directory; the environment file was exported before Python started.
- Evaluation data: the committed non-personal fixture was rebuilt in an in-memory platform unit of work for each process. No persistent fixture, draft, message, notification, provider write, or Telegram action was created.

| Metric | Final result | Gate | Outcome |
| --- | ---: | ---: | --- |
| Cases completed | 10 / 10 | 10 / 10 | pass |
| Timeout/error rate | 0.00 | 0.00 | pass |
| Exact-match accuracy | 1.00 | >= 0.90 | pass |
| Retrieval recall | 1.00 | >= 0.90 | pass |
| Citation safety rate | 1.00 | 1.00 | pass |
| Required-skill recall | 1.00 | 1.00 | pass |
| Forbidden-skill precision | 1.00 | 1.00 | pass |
| Restricted-marker leak rate | 0.00 | 0.00 | pass |
| Unsupported-claim rate | 0.00 | 0.00 | pass |

Citation identifiers and fields are now backend-authored from the permission-filtered result set; the model only explains the bounded result. The sensitive-field case selected only `platform-shared-policy` and returned the fixed refusal without an LLM call.

## Original failed baseline and corrective direction

The runtime is available and deterministic skill matching selected every required skill, so the next work is not connectivity repair. The response contract needs enforcement before scoring: require citations to use only supplied ephemeral IDs and visible field keys, require complete citations for exact/filter/aggregate claims, and treat `private_notes` as an explicit policy-denial trigger before any table-access skill can be selected. These are architecture/behavior changes and require a documented follow-up scope before implementation.
