# Stage12 Grounded Provider Compact Reference / Hard Deadline Decision

## Status

- Status: `proposed`
- Date: 2026-07-31
- Scope: private Grounded Answer Provider request/response references and real HTTP wall-clock deadline only
- Public API / database / permission impact: none
- Deployment / production activation: not authorized by this decision
- Implementation gate: explicit user confirmation required

## 1. Trigger

Five immutable P1 attempts prove that model replacement alone is insufficient:

| Attempt | Fixed model/profile | Real grounded | Primary failure |
| --- | --- | ---: | --- |
| 01 | Gemini 2.5 Flash | `0/12` | upstream Schema serving-state limit |
| 02 | Qwen3 235B | `7/12` | language/Schema instability and long tail |
| 03 | Qwen3 Next 80B | `2/12` | five token-cap truncations and five visible-text violations |
| 04 | DeepSeek V3.2 | `11/12` | one `1600`-token invalid JSON truncation |
| 05 | DeepSeek V3.2 fixed-seed experiment | `9/12` | deterministic token-cap truncation regression |

The best candidate is DeepSeek V3.2, but the current Provider contract repeats 64-hex handles throughout input and output. A 7-claim answer repeats long `claim:sha256:*` and `evidence:sha256:*` values even though those values are meaningful only to the backend. The same campaigns also produced observations up to `77.478s` despite a `25s` request timeout, proving that the current `httpx` phase timeout is not a total wall-clock deadline.

## 2. Proposed Decision

### 2.1 Request-local compact references

Change only Provider-visible private references to deterministic request-local aliases:

```text
objective -> o001 ... o016
claim     -> c001 ... c128
evidence  -> e001 ... e256
action    -> a001 ... a032
finding   -> f001 ... f064
version   -> v001 ... bounded request maximum
```

The aliases are assigned from the already deterministic canonical ordering used by the request builder. The Provider sees aliases plus authorized safe labels/values only. The backend reconstructs the alias-to-canonical binding from the sealed request and current `ClaimGraphV1`; canonical claim/evidence/action IDs remain the only IDs written to `FinalAnswerRenderReceiptV1`.

Security does not depend on alias entropy. Safety continues to depend on:

1. exact alias membership and reference closure;
2. request `content_hash`;
3. current `scope_hash` / field-policy / schema / record-version binding;
4. deterministic atom, citation, Action-status and objective-coverage validation;
5. final runtime rebind to the sealed canonical graph.

An invented alias, duplicate alias, alias reorder/tamper or stale canonical binding fails closed. No public identifier, permission proof or execution authority is shortened.

### 2.2 Output budget

Keep the concise/non-repetition prompt and DeepSeek V3.2 profile. Raise Grounded Composer `max_output_tokens` from `1600` to `2400` only after compact references are implemented. The higher ceiling is not a quality pass: P1/P2/P3 still require valid complete JSON, grounding and zero fallback, and latency remains a non-compensable gate.

### 2.3 True wall-clock deadline

For real network calls, replace the current synchronous phase-timeout assumption with an async HTTP request wrapped by a cancellable total timeout equal to the remaining UTC deadline. Injected test clients remain synchronous. A total timeout must:

- cancel and close the in-flight request;
- produce exactly one `provider_timeout` observation/fingerprint;
- never leave a background request or retry running;
- preserve the existing per-role semaphore and at-most-two-attempt policy;
- never persist prompt/output/secret content.

## 3. Rejected Alternatives

- Continue switching models: three model families already proved that the repeated contract overhead remains; this adds variance without fixing the boundary.
- Keep rerunning the `11/12` profile: selective luck is not stability evidence.
- Only raise `max_output_tokens`: may hide truncation while increasing cost and latency; does not remove unnecessary handle overhead.
- Accept deterministic fallback: directly violates the confirmed real-model acceptance goal.
- Truncate canonical IDs globally: would weaken non-Provider identity and audit semantics. Only request-local aliases are proposed.

## 4. Required RED/GREEN Evidence

1. Provider request/output Schema accepts only the bounded alias formats and contains no canonical `*:sha256:*` handle.
2. Builder assigns stable unique aliases and no hidden/private field or canonical ID leaks into Provider JSON.
3. Runtime binding maps every alias back to the exact canonical objective/claim/evidence/action/version; tamper, reorder, unknown and stale bindings fail.
4. Existing invented-fact, citation, permission, Action and language exploit tests remain green.
5. A 7-claim synthetic request demonstrates a material serialized-byte/token reduction versus the retained attempt evidence.
6. A delayed real/injected HTTP response is cancelled at the wall-clock deadline with one sanitized timeout observation and no background completion.
7. Focused unit/adjacent suites pass before any real rerun.
8. One new complete DeepSeek P1 executes exactly `(1, 2, 4, 7) × 3`, with `12/12` real grounded output and zero fallback. Failed baselines remain immutable.

## 5. Boundary

This decision does not change structured table facts, Planner, Query Engine, Retrieval/Embedding, Specialist responsibilities, permission rules, Action authority, public HTTP/SSE contracts, database schema, Telegram behavior or deployment topology. P2, P3, native server and Telegram remain blocked until the corrected P1 passes.
