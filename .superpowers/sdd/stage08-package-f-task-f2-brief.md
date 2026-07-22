# Stage08 Package F — F2 synthetic 12-case isolated evaluation runner

## Scope

Implement F2 only, using the approved Package F BDD and F plan. F1 is review
clean. F2 creates the strict synthetic case manifest and isolated runner but
does **not** call real OpenRouter; that is F3 after F2 review.

## Files

- create `backend/scripts/stage08_real_provider_evaluation.py`
- create `backend/tests/unit/test_stage08_real_provider_evaluation.py`
- create/update only Stage08 F task report under `.superpowers/sdd/`

## Required behavior

1. Define exactly twelve static case IDs covering the F BDD matrix: visible
   fact, hidden field, revoked scope, general advice, group freshness, RAG
   lifecycle, provider unavailable, policy deny, draft pressure,
   budget/cancel, replay and multilingual.
2. Each case runs in a new subprocess with a fresh synthetic-only in-memory
   workspace/employee/data fixture. The parent permits no raw prompt/answer,
   IDs, tokens, provider request IDs or exception text to cross the process
   boundary.
3. Child/parent DTOs must be strict and contain only static case ID, terminal
   status, boolean gates, fixed failure labels, count/bucket fields and
   provider/usage metadata *presence* booleans. Parent revalidates child DTO.
4. Runner allows at most two child cases concurrently; hard timeout terminates
   only that child and later cases continue. No output artifact is written.
5. Force safety environment in child: Telegram dry-run, notifications and
   provider-write mode disabled, full prompt/response retention disabled. An
   absent explicit `STAGE08_F_ENV_FILE` produces a clean non-network result.
6. Add deterministic fake-provider mode solely for runner tests; it must use
   F1's injected adapter seam, never an external HTTP call. Include direct
   tests for isolation, timeout cleanup, redaction, exact manifest, concurrency
   cap, parent forged DTO rejection and safety-env forcing.

## Verification

Run F2 focused tests, F1 tests, relevant existing isolation evaluator tests,
compileall and diff check. Do not call OpenRouter, Telegram or deployment;
do not modify API/schema/permissions/migrations. Write a Chinese F2 report.
