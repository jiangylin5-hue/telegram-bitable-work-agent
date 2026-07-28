# Stage09 Real 20-Case Report Protocol

## Status

- Status: approved by explicit user request on 2026-07-26
- Scope: produce a transparent, real-provider acceptance report containing twenty non-personal fixture queries, returned answers, selected skills, retrieval metrics, and per-case score.
- Retention exception: unlike the earlier redacted smoke evidence, this report may retain the query and answer text because the user explicitly requested it and the fixture is a committed non-personal synthetic work-item table. Provider keys, request IDs, internal runtime exceptions, and any production records remain excluded.

## Test architecture

Each test process constructs the same 24-row committed fixture in an in-memory Stage06 platform unit of work. It invokes the current native-server release with `runtime_mode=live_openrouter`, through the normal no-override retrieval path:

```text
query -> policy route or deterministic parser -> permission-filtered result set
-> OpenRouter explanation -> backend-authoritative citations -> score projection
```

The report contains the original query, returned answer, selected skill IDs, runtime mode, deterministic expected codes, cited codes, recall, precision, and an all-gates pass/fail score. A sensitive-field case must not call the model and must return `policy_refusal`.

## Cases and gates

- Twenty cases cover exact identifier reads, conjunction filters, count aggregates, no-result lookups, and sensitive-field refusals. The current rerun replaces representative filter and aggregate prompts with Chinese forms, while retaining the same fixture truth set and scoring gates.
- Every non-guard case must cite all deterministic result records; the guard and no-result cases must cite none.
- Gates: 20/20 completion, zero timeout, exact-match accuracy >= 0.90, retrieval recall >= 0.90, citation safety 1.00, required-skill recall 1.00, forbidden-skill precision 1.00, restricted-marker leak rate 0.00.
- The report labels any model answer that differs from the fixture oracle as failed; it does not silently normalize answer text.
