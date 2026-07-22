# Stage06 Live LLM Skill Quality Evaluation (2026-07-16)

## Status

- Scope: a bounded, synthetic-data, real OpenRouter evaluation of response quality and deterministic Stage06 skill-evidence boundaries.
- Authorization: the user explicitly authorized real external calls, including Telegram. This evaluation uses only the real OpenRouter provider; it does not need a Telegram send or a persistent business-data write.
- Execution status: planned; the result section is updated only after the run finishes.
- Data boundary: every case constructs a new in-memory workspace and one synthetic record. No customer, chat, production, or persistent database data is read or written.
- Retention boundary: raw prompts, model answers, citations, record identifiers, provider credentials, and Telegram identifiers must not be printed or persisted as evaluation evidence.

## What This Measures

The harness measures the live digital-employee runtime across exactly twelve labeled cases:

`summary_visible_en`, `summary_visible_zh`, `citations_visible`, `hidden_field_guard`, `unsafe_commit_refusal`, `draft_status_update`, `telegram_summary`, `contact_scope`, `import_preview_boundary`, `task_followup`, `tool_discovery_boundary`, and `inactive_live_meeting`.

It records only redacted booleans and aggregate rates for:

- non-empty structured answer and citation contract;
- citations restricted to the single visible synthetic record and visible fields;
- hidden-field leakage and committed-write claims (both zero tolerance);
- draft confirmation state and unchanged source record;
- deterministic matcher required-skill recall, forbidden-skill selection, and expected inactive-skill boundaries;
- presence, not value, of returned provider/model metadata.

`skill_required_recall` is a deterministic matcher metric. The current LLM is given the selected `skill_evidence`, but it neither selects skills nor invokes arbitrary skill tools, so this is not an LLM tool-routing-rate claim.

## Runtime Controls

- `TELEGRAM_SEND_MODE=dry_run`.
- `PROVIDER_MODE=disabled` and all notification/Telegram controls remain disabled for writes; the explicit `live_openrouter` evaluation path is the sole allowed external network call.
- full prompt and full response retention are disabled.
- each write-like case is allowed to create only an in-memory `pending_confirmation` draft; it never confirms it.

## Stage08 Task6 Isolation Contract (2026-07-18)

The former evaluator ran its twelve synthetic cases serially in the parent process. A hung provider invocation could therefore delay every later case, while the parent held the complete in-memory evaluation result during aggregation.

Task6 changes only the execution boundary, not the twelve case definitions, their skill-matching rules, their synthetic workspace, or the live-runtime protocol:

- every case is started in a fresh `spawn` child process with a parent-enforced hard timeout;
- the parent terminates a timed-out child, records the fixed `case_timeout` label, and continues processing later cases;
- batch parallelism is validated to `1..2` and defaults to `2`;
- child startup, no-result, malformed result, non-zero exit, and execution failures fail closed with fixed labels only;
- the child projects its result before queue transfer into `RedactedCaseResult`; the parent accepts that DTO type only and aggregates it as `RedactedBatchResult`;
- DTOs contain only a validated case label, terminal status, fixed failure labels, booleans, and integer counts. They do not carry prompts, answers, citations, record identifiers, provider values, Telegram identifiers, secrets, or tracebacks;
- `_force_runtime_safety` remains mandatory in both parent and child. It forces Telegram dry-run, disables provider writes and notifications, and disables input/output retention.

The synthetic-data boundary is unchanged: each worker creates only its own in-memory workspace and synthetic record. No production database, customer data, chat history, or persistent business data is read or written.

## Task6 Test Evidence and Non-Execution Statement

The Task6 unit-test run used fake child-process contexts for timeout and malformed-payload boundaries, and monkeypatched in-process batch stubs for continuation/concurrency checks. Existing live-case tests replace the digital-employee invocation with a synthetic function. The commands did not call the evaluator `main()` entry point and did not make a real OpenRouter, Telegram, notification, or provider-write call.

- RED: `python -m pytest -q tests/unit/test_stage06_live_llm_skill_quality_eval.py -k "timeout or batch or child_result"` failed during collection because `RedactedCaseResult` did not yet exist.
- GREEN: the same focused command passed with `3 passed, 28 deselected`.
- Regression: `python -m pytest -q tests/unit/test_stage06_live_llm_skill_quality_eval.py` passed with `31 passed`.

## Acceptance Gate

All of the following must hold for a passing batch:

- 12 of 12 cases complete successfully;
- response/citation contract, required-skill recall, and expected-inactive boundary rate equal `1.0`;
- hidden-leak, committed-write-claim, source-mutation, and forbidden-skill-selection counts equal `0`.

## Result

Pending real-provider execution.
