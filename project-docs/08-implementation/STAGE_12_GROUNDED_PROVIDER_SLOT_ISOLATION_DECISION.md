# Stage12 Grounded Provider Slot Isolation Decision

## Status

- Status: `implemented-local-p2-passed`
- Date: 2026-08-01
- Scope: private Grounded Composer invocation topology and deadline/cost budget only
- User confirmation: confirmed inline on 2026-08-01
- Implementation status: TDD implementation and bounded P1/P2 acceptance completed
- Production status: not deployed or activated

## Trigger And Evidence

The user-approved sealed RenderSlot V3 contract removed model-owned section and
reference arrays. Local deterministic verification passed, including 48 × 3 at
`144/144` real-origin-shaped results. Real P1 also passed `12/12`.

Two immutable exact real P2 campaigns still failed:

```text
RenderSlot V3 initial:
real/final 26/36, fallback 10, grounding-invalid attempts 20, p95 4553 ms
hash e16ab508806f0d6e52bdb4337ea697930514e70f885571abafcbd8fda6598b99

RenderSlot V3 with sealed Action prerequisite context:
real/final 24/36, fallback 12, grounding-invalid attempts 25, p95 4109 ms
hash cda25a7ef5f8475e587e4604bdb84260b87624f090784d9a50da9ce71f415f75
```

Sanitized diagnostics show valid output slot counts and no schema/transport
failure. Remaining failures are `invented_ascii/number` and
`unreferenced_subject` atoms. The same Case may pass another invocation. The
model sees all slots and all authorized atoms in one request, then
intermittently borrows an atom from another slot or adds a new token.

## Proposed Decision

Execute each required RenderSlot through an isolated Provider input:

```text
backend RenderSlotPlan
-> for each required slot (maximum three produced by the current builder)
   -> slot_handle
   -> section/statement instruction
   -> only that slot's sealed claims/findings/actions/context
   -> one text-only strict response
-> validate each text against its own closure
-> atomically compose only when every required slot is valid
-> otherwise deterministic fallback, recorded as acceptance failure
```

Rules:

1. Raw Query, unrelated objectives and other slots are not sent to a slot call.
2. The current builder remains capped at three required slots: synthesis,
   Action status and limitation. Any future fourth slot needs a new decision.
3. Calls may run with bounded concurrency `2`; the existing global 50-second
   deadline remains shared by the whole answer, not reset per slot.
4. Each slot has at most one initial attempt and one bounded repair within the
   shared deadline. No model fallback or selective Case acceptance is added.
5. A result is `real_provider` only when every required slot is returned by the
   fixed GLM 5.2 profile and passes schema, language, atom, Action and runtime
   binding validation. Partial Provider prose is never mixed with fallback.
6. Observability records per-slot attempt counts, latency and sanitized error
   classes, but no raw prompt/output or business atom.
7. Final receipt, headings, citations and coverage remain backend-owned.

## Impact

- Expected benefit: unrelated atoms are absent from each Provider call, making
  cross-slot subject/value leakage structurally unavailable.
- Cost: typical one-slot queries remain one call; mixed/action queries use two
  or three calls and may consume more tokens.
- Latency: bounded parallelism avoids simple serial addition, but total latency
  and rate-limit pressure may increase and must be remeasured.
- Contract: private Provider invocation only. No public API, database schema,
  permission model, Action authority, Telegram behavior or deployment change.

## Rejected Alternatives

- More Case-specific prompt clauses: both P2 campaigns show high variance after
  valid schema output; prompts do not remove unrelated atoms from model input.
- Allow globally authorized atoms in every slot: can attach the wrong target or
  status to an Action/limitation sentence and weakens grounding.
- Remove canonical atom validation: converts measured unsupported prose into
  false passes.
- Force exact deterministic source text: stable, but no longer meaningfully
  relies on real model-authored final prose.

## Required Acceptance

1. RED/GREEN tests prove each call payload contains only its slot closure.
2. Cross-slot subject/value/action leakage is impossible at the Provider input.
3. Missing/failed slot makes the whole Provider result fail visibly.
4. Shared deadline, concurrency `2`, per-slot repair cap and attempt accounting
   are deterministic and tested.
5. Existing permission/version/receipt/zero-effect gates remain green.
6. Full unit regression passes.
7. Run one new P1 and one exact 12 × 3 P2 in new immutable evidence directories;
   stop before P3 on any fallback or final-answer failure.

## Confirmation Gate

```text
确认 Stage12 Grounded Slot Isolation contract
```

## Implementation And Acceptance Result

The approved topology is implemented under private profile
`composer.zh.grounded.glm-5.2.v4` with the fixed `z-ai/glm-5.2` model:

- one strict Provider request per required slot;
- only the selected slot and its exact sealed closure are serialized;
- raw Query, unrelated slots and unrelated candidates are absent;
- maximum three slots, concurrency `2`, one shared 50-second deadline and at
  most two attempts per slot;
- deterministic output ordering and all-or-nothing assembly;
- per-slot sanitized status, attempt count, latency and failure class;
- no partial Provider prose is mixed with fallback.

Fresh final-code verification is `140 passed` on the focused Grounded surface,
`2176 passed` for all backend unit tests, plus `compileall` and
`git diff --check`. Real evidence:

```text
P1:
12/12 HTTP, schema, grounding and real Provider; fallback 0
hash af9b1c69a817611bdae1103b89e4ac89b98bdd86d9304c7d91fb1f190e6fa989

P2 final accepted run:
36/36 real Provider and final-answer gate; fallback 0
mean/p95 3086/4385 ms; effects/writes/sends 0/0/0
hash 54de9da4eb0e7ae7eb65d62bbb85807d5382af05a2b795a29628dc10eecc86cc
```

Two immutable intermediate P2 results remain retained at `31/36` and `35/36`.
They identified a limitation-slot machine-field echo and an unsupported
business-action execution statement. The fixes specialized slot writing
constraints while preserving strict language, atom and Action non-execution
validation; no safety gate was relaxed.

P3, native deployment, runtime activation and Telegram remain outside this
decision's completed acceptance and are not yet accepted.
