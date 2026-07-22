# Stage08 Package F — F1 OpenRouter analysis-provider task

Implement only F1 from `docs/superpowers/plans/2026-07-22-stage08-package-f-real-provider-evaluation.md` and the Package F BDD.

Create the opt-in `OpenRouterStage08AnalysisProvider` plus focused unit tests.
It must never be enabled by default API dependencies and must not make a real
network call in this task. It should use `httpx` with an explicit transport
timeout bounded by `min(E5 remaining deadline, CollaborationBudget provider
budget)`, preserve sealed/private input internally, return strictly validated
`AnalysisProviderOutcome`, and never let an external model form a draft value.

Test no-key, timeout, HTTP error, malformed JSON/shape, bounded timeout,
safe output validation, and no raw/private persistence. Do not add env fields,
public API/schema/migration/permission/Telegram/deployment changes. Write the
Chinese task report in `.superpowers/sdd/` and run focused tests/compile/diff.
