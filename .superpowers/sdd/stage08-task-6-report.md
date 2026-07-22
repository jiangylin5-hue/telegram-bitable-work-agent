# Stage08 Package A Task6 Report — Evaluation Isolation

## Scope

Implemented only Task6: child-process isolation and redacted batch aggregation for the existing synthetic Stage06 live-LLM evaluator. The twelve business cases, their matching rules, database schema, APIs, and other Stage08 tasks were not changed.

## Exact Files

- `backend/scripts/stage06_live_llm_skill_quality_eval.py`
- `backend/tests/unit/test_stage06_live_llm_skill_quality_eval.py`
- `project-docs/08-implementation/evidence/stage06-live-llm-skill-quality-2026-07-16.md`
- `.superpowers/sdd/stage08-task-6-report.md` (this delivery report required by the Task6 brief)

## RED

Command:

```powershell
python -m pytest -q tests/unit/test_stage06_live_llm_skill_quality_eval.py -k "timeout or batch or child_result"
```

Result: expected collection failure. `RedactedCaseResult` could not be imported because the Task6 DTO and isolation API did not exist yet.

## GREEN

Focused command:

```powershell
python -m pytest -q tests/unit/test_stage06_live_llm_skill_quality_eval.py -k "timeout or batch or child_result"
```

Result: `3 passed, 28 deselected`.

Regression command:

```powershell
python -m pytest -q tests/unit/test_stage06_live_llm_skill_quality_eval.py
```

Result: `31 passed`.

## Isolation and Retention Evidence

- Each case uses a fresh `spawn` process and a parent hard timeout.
- Parent output accepts only `RedactedCaseResult`, then aggregates `RedactedBatchResult`; malformed queue payloads fail closed.
- Batch execution preserves case order, keeps running after a timeout/failure, and validates `max_parallelism` to `1..2`.
- DTO tests prove timeout labels and malformed child payloads do not expose the supplied secret value or prompt text.
- Runtime safety is forced in both parent and child: Telegram dry-run; provider writes and notifications disabled; input/output retention disabled.

## No Network / External-Write Proof

No evaluator `main()` run occurred. Timeout tests use a fake multiprocessing context; batch tests monkeypatch `run_case_isolated`; existing direct live-case tests monkeypatch `invoke_digital_employee` with synthetic results. Therefore this Task6 run made no real Provider, OpenRouter, Telegram, notification, or external write call.

## Not Done / Remaining Risks

- No real-provider evaluation was run; that remains a separately authorized future activity.
- Unit tests validate isolation protocol with fakes. A real child process is intentionally not allowed to reach the live provider in this task.
- No temporary files or generated artifacts were retained.

## Fix Round 1 — Review Remediation

### Scope

Fixed only the two Important review findings: bounded stubborn-child cleanup and strict parent-side child-payload revalidation. No case semantics, API, schema, or external integration changed.

### RED

```powershell
python -m pytest -q tests/unit/test_stage06_live_llm_skill_quality_eval.py -k "stubborn or revalidates_exact"
```

Result: `2 failed, 31 deselected`. The prior implementation recorded a `join(None)` against a stubborn child and accepted forged/subclass DTO payloads.

### GREEN

```powershell
python -m pytest -q tests/unit/test_stage06_live_llm_skill_quality_eval.py -k "stubborn or revalidates_exact"
```

Result: `2 passed, 31 deselected`.

```powershell
python -m pytest -q tests/unit/test_stage06_live_llm_skill_quality_eval.py
```

Result: `33 passed`.

### Evidence

- Timeout cleanup now uses only the requested timeout plus bounded `0.05s` terminate/optional-kill grace joins. A child that remains alive is not closed and cannot block the batch worker indefinitely.
- The parent accepts only `type(payload) is RedactedCaseResult`; it rejects subclasses, `model_construct` values, unknown object fields, non-exact dumps, failed revalidation, non-fixed case labels, and labels that do not match the launched case.
- The focused tests use fake process/queue objects and no evaluator `main()` run occurred. No Provider, OpenRouter, Telegram, notification, or external write was called.

## Fix Round 2 — DTO Fixed-Label Validator

- RED: `python -m pytest -q tests/unit/test_stage06_live_llm_skill_quality_eval.py -k "non_static_case_id"` failed because `other_static_label` matched the generic pattern and was accepted.
- GREEN: the same command passed with `1 passed, 32 deselected` after `RedactedCaseResult.case_id` itself was constrained to the existing twelve labels.
- Regression: `python -m pytest -q tests/unit/test_stage06_live_llm_skill_quality_eval.py` passed with `33 passed`.
- No evaluator entry point or external Provider/Telegram/notification call was run.
