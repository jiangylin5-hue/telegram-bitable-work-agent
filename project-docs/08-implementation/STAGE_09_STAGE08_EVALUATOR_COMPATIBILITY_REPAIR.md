# Stage09 Stage08 Evaluator Compatibility Repair

## Status

- Status: implemented and locally verified on 2026-07-27; PostgreSQL integration remains a separate environment gate.
- Scope: restore the offline deterministic Stage08 evaluator after the provider prompt builder gained appended skill-policy metadata.
- Non-goals: change user-facing prompt wording, LLM provider transport, Stage08 actions/citations/permissions, score thresholds, test fixtures, database schema, Telegram behavior, or real-provider configuration.

## Root Cause

The Stage08 shared prompt-builder contract changed from three returned values to four:

```text
before: prompt, evidence_count, command_intent
after:  prompt, evidence_count, command_intent, allowed_provider_actions
```

The real OpenRouter adapter was updated for the appended skill-policy output. The offline `_DeterministicAnalysisProvider` in `backend/scripts/stage08_real_provider_evaluation.py` still used a three-target unpack:

```python
prompt, _, _ = _build_prompt(material, command)
```

That raises `ValueError` inside the provider's intentionally broad safety boundary. The boundary correctly redacts the exception and emits an unavailable outcome, but the evaluator then observes no citations, an unexpected `degraded` terminal state and no action telemetry. Consequently 16 unit cases fail with downstream labels such as `citation_invalid`, `terminal_unexpected`, and `provider_invocation_invalid`; those labels are symptoms, not independent citation failures.

## Compatibility Contract

The deterministic evaluator needs only the first `prompt` output to run the outbound prompt guard. It must ignore appended, non-prompt metadata so future additions to the private builder's trailing result do not convert a safe evaluator run into a degraded synthetic result.

```text
shared prompt builder
-> prompt plus optional trailing provider metadata
-> deterministic evaluator consumes prompt only
-> guard decision
-> deterministic action/citation fixture
-> normal Stage08 policy/result evaluation
```

The repair therefore uses star-unpacking after the first value. It neither hides exceptions from the prompt build nor relaxes the guard. A malformed result without a first prompt value still raises inside the existing redacted safety boundary.

## Development Steps

1. Preserve the existing failing evaluator regression as RED evidence: `visible_fact` with `deterministic_fake` currently returns `degraded` instead of a safe read-only result.
2. Change only the deterministic provider's prompt extraction to consume the first prompt value and intentionally discard trailing metadata.
3. Re-run the focused deterministic regression, then the complete Stage08 evaluator file and the full non-PostgreSQL unit suite.
4. Record the outcome in the Stage09 audit. Do not reinterpret the previous failing downstream labels as a quality result.

## Acceptance Criteria

- `visible_fact` deterministic-fake output is passed/read-only with current citation evidence.
- The focused outbound prompt-guard fixture still reports `outbound_prompt_unsafe` first when the prompt contains a hidden marker.
- All Stage08 evaluator unit cases pass without changing expected case strategies or score thresholds.
- The complete unit suite has no Stage08 failures; PostgreSQL integration remains a separately documented environment gate.

## Verification Evidence

- RED: `tests/unit/test_stage08_real_provider_evaluation.py::test_deterministic_fake_provider_uses_the_stage08_dependency_seam` failed before the repair with `degraded`, zero citations and `citation_invalid` / `terminal_unexpected` / `provider_invocation_invalid` labels.
- Focused GREEN: five deterministic-provider and prompt-guard regressions passed.
- Stage08 evaluator: `47 passed`.
- Full non-PostgreSQL unit suite: `1370 passed, 1 skipped`; the skip is the documented POSIX-only persisted-private-target shell check.
- No evaluation fixture, provider configuration, runtime environment, data row, Telegram action or external provider call was changed by this repair.
