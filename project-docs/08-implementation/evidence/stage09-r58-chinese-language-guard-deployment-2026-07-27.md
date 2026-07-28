# Stage09 r58 Chinese Response Language Guard Deployment — 2026-07-27

## Scope

- Candidate: `stage09-p1-20260727-r58-chinese-language-guard`
- Change: enforce the Stage08 Chinese response-language contract before a Provider answer becomes an `AnalysisDecision`.
- Explicit non-goals: no database migration, schema/API/permission/skill-selection change, Base/record/import/draft write, Telegram send, or ingress change.

## Trigger

An authenticated r57 workbench observation submitted the Chinese greeting `你好` to the real analysis flow and rendered the English language refusal: `I cannot answer questions in Chinese. Please use English.` The old strict JSON parser accepted this as a structurally valid non-empty answer.

## Candidate Gates

The native candidate passed before activation:

```text
release-layout: pass
release-manifest: pass
release-assets: pass
static-parity: pass
readiness-gate: pass
```

The first r58 source package was fail-closed by `verify-release-layout.sh` because it carried a historical `deploy/stage07-acceptance/runtime/.env.stage07-acceptance.example` file. The file is not part of the Stage09 native runtime and was excluded from the sealed candidate. The gate was then rerun and passed; no `current` link changed before that pass.

## Activation

The activation switched the three matching links atomically and restarted only:

- `stage09-p1-api`
- `stage09-p1-worker`
- `stage09-p1-outbox-bridge`

The activation script retained previous source, venv and static targets and restores all three if service restart or the bounded readiness check fails.

```text
readiness-gate: pass
stage09-activation: pass
artifact-id: stage09-p1-20260727-r58-chinese-language-guard
```

Post-activation read-only checks resolved all three targets to r58. API, worker, outbox, Redis and Nginx were `active`; public root and `/health` returned `200`.

## Verification Boundary

- Local focused Provider/evaluator regression: `82 passed`.
- Related runtime/configuration regression: `106 passed`.
- The pre-existing r57 full backend and Mini App suites remain separate evidence; a new all-backend command exceeded the local 120-second command window and is not counted as a fresh pass.
- Browser automation found the user's authorized Workbench tab, but two DOM-claim attempts reached the extension deadline before any UI action. It did not type or send `你好`; therefore this evidence does not claim the final rendered language result.

## Remaining Acceptance

Repeat the existing authenticated Workbench flow against r58: enter `你好`, send once, and verify the completed answer is Chinese guidance rather than the observed English refusal. For an evidence-bound Chinese query, verify either a cited Chinese answer or the existing unavailable/degraded path; never accept a fabricated translated fact or draft.
