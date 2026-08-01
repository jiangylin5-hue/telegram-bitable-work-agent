# Stage12 Grounded Provider Render Slot Decision

## Status

- Status: `approved-for-implementation`
- Date: 2026-08-01
- Scope: private Grounded Answer Provider response structure only
- User confirmation: confirmed inline on 2026-08-01
- Implementation status: `implemented-local-p1-pass-p2-failed`; superseding slot-isolation decision pending
- Production status: not deployed or activated

## Trigger

The user-confirmed fixed `z-ai/glm-5.2` binding passed the post-binding P1 gate:

```text
HTTP completed: 12/12
Schema valid: 12/12
Grounding valid: 12/12
Real Provider: 12/12
Fallback: 0
content_hash: 08d1573aeec0f89632332ccff9716f313b11622e11619bf02a769fd43f3c3130
```

The exact representative P2 campaign then failed and was retained as failed:

```text
Cases × rounds: 12 × 3
Real Provider: 33/36
Final-answer gate: 33/36
Fallback: 3
Provider p95: 13667 ms
Failures: provider_grounding_invalid=6 attempts
content_hash: 0702da842befaae8e3271e196515d1a3cb6231aaba9551fbb16c2c2707a820e7
```

Failed results were `permission_04` in rounds 02 and 03 and `mixed_02` in
round 02. No unauthorized effect, production write or Telegram send occurred.

## Root Cause Evidence

Sanitized structural diagnostics retained no answer text and showed two distinct
failure shapes:

1. `permission_04` has `actions=[]`, but the model intermittently creates an
   `actions` section containing an `action_status` statement with no
   `action_handles`. Strict Schema correctly rejects the empty statement.
2. `mixed_02` has disjoint Fact and Risk findings. The model intermittently
   writes the Risk predicate in the statement that references only the Fact
   finding, or combines direct Claim handles with the same sealed finding.
   Exact atom/reference validation correctly rejects the result.

The same model can return a valid shape on another round. Therefore this is not
missing evidence, unavailable Provider, wrong model binding or a deterministic
validator bug. The unstable boundary is asking the model to author prose while
also reconstructing section type, statement type and four independent reference
arrays that the backend already knows deterministically.

## Proposed Decision

Replace the private free-form statement-reference assembly with sealed render
slots:

```text
TaskSpec + ClaimGraph + exact findings + Action status
-> backend RenderSlotPlan
   - slot_handle
   - section_kind
   - statement_kind
   - sealed claim/finding/evidence/action closure
   - required/optional state
-> Provider writes Chinese text for each required slot
-> backend validates text atoms against that slot's sealed closure
-> backend renders the model-authored text and canonical receipt
```

Rules:

1. The backend, not the model, decides which slots exist. `actions=[]` produces
   no Action slot, so an empty Action statement is structurally impossible.
2. The backend groups compatible disjoint Fact/Risk/Daily findings into a
   synthesis slot when their language may legitimately cross-reference the same
   result. The model cannot attach a sentence to the wrong closure.
3. The Provider response remains a fixed-property/fixed-array JSON Schema and
   must return every required `slot_handle` exactly once. Unknown, duplicate,
   omitted or reordered slots fail closed.
4. Every visible sentence remains model-authored. This is not deterministic
   fallback and still requires a real Provider call for acceptance.
5. Existing Chinese, invented atom, permission, scope, field-policy, runtime
   binding, Action non-execution, deadline, zero-fallback and final-answer gates
   remain unchanged or stricter.
6. Canonical Claim/evidence/action IDs remain backend-only. The model receives
   only request-local compact handles and safe authorized labels.
7. No automatic multi-model routing, silent fallback or extra retry is added.

## Rejected Alternatives

- Keep adding Case-specific Prompt clauses: measured fixes move failures between
  shapes and do not make the structural contract deterministic.
- Increase attempts or deadline: hides instability, increases p95 and violates
  the bounded acceptance intent.
- Auto-rewrite invalid model references after generation: can silently change
  meaning and make an invalid answer appear grounded.
- Render all factual prose deterministically: reliable but would no longer meet
  the user's requirement that the final answer text come from a real model.
- Weaken duplicate/atom/final-answer validation: converts real grounding defects
  into false passes.

## Required RED/GREEN Evidence

1. A request with `actions=[]` exposes no Action slot and the response Schema
   cannot express `action_status` for that request.
2. Mixed Fact/Risk findings produce the documented sealed synthesis slot; the
   model returns text only and cannot alter its closure.
3. Missing, duplicate, unknown and reordered slot handles fail closed.
4. Invented entity/number/status, Action execution wording, permission/version
   drift and non-Chinese text remain rejected.
5. Render receipt expands slots to the exact canonical Claim/evidence/action set.
6. Deterministic 48 × 3 test Provider campaign remains `144/144` real origin.
7. Re-run one exact 12 × 3 P2 campaign. The failed P2 evidence remains retained
   and cannot be overwritten or merged with the new result.

## Boundary And Impact

This changes only the private Composer request/response contract and validator.
It changes no public HTTP/SSE API, database schema, permission model, Action
authority, embedding/retrieval model, Planner/Specialist execution, Telegram
behavior, deployment topology or production activation state.

## Confirmation Gate

```text
确认 Stage12 Grounded RenderSlot contract
```

## Current Progress

- Private request contract advanced to `grounded-answer-provider-request.v3` with backend-owned ordered `render_slots`.
- Active Provider response advanced to `grounded-answer-plan.v3`; it exposes only `slot_outputs[{slot_handle,text}]`.
- Request projection creates no Action slot when `actions=[]`, groups disjoint Fact/Risk closures into one synthesis slot, and seals exact objective/Claim/evidence/finding/Action closure.
- Validation rejects missing, duplicate, unknown, reordered and atom-tampered slot output; Action text must preserve its sealed status and may not claim execution.
- Rendering derives deterministic headings, citations and canonical receipt only from backend-owned slot metadata while retaining model-authored visible prose.
- Focused schema/request/validation/provider/preflight/campaign/isolated tests: `143 passed` on 2026-08-01. The included deterministic 48 × 3 campaign is `144/144` real-origin-shaped with zero fallback. Full unit regression after Action context correction: `2167 passed`.
- Real V3 P1 passed `12/12` with hash `a9b9de907774c69830344e56e7553a5a13b60c2a081c80d7eae20df8facfb4c5`.
- Two new exact real P2 campaigns failed and remain immutable: `26/36` real/final with hash `e16ab508806f0d6e52bdb4337ea697930514e70f885571abafcbd8fda6598b99`, then `24/36` after sealed Action prerequisite context with hash `cda25a7ef5f8475e587e4604bdb84260b87624f090784d9a50da9ce71f415f75`.
- Sanitized failures are cross-slot or invented textual atoms, not response slot count, schema, transport or latency failures. `STAGE_12_GROUNDED_PROVIDER_SLOT_ISOLATION_DECISION.md` is proposed; P3 remains blocked.
