# Stage12 Grounded Provider Slot Isolation Decision

## Status

- Status: `proposed-awaiting-user-confirmation`
- Date: 2026-08-01
- Scope: private Grounded Composer invocation topology and deadline/cost budget only
- Implementation status: not started
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
