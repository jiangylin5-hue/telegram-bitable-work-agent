# Stage08 Package A / Task 1 Report

## Status

Completed. This task adds only strict, redacted Pydantic runtime contracts and their unit tests. It does not call providers, Telegram, databases, migrations, APIs, or external services.

## Implementation

- Added `backend/app/runtime/stage08_contracts.py`.
  - Exports `JSONScalar`, bounded `ExecutionBudget`, allowlisted `ToolInvocation`, importable `ExecutionTicketState` and `ExecutionPlan`, and redacted-only `RedactedToolResult`.
  - Rejects prohibited input keys recursively and case-insensitively: `prompt`, `response`, `api_key`, `token`, and `raw_text`.
  - Uses strict validation for invocation input so non-JSON collection values are rejected.
  - Forbids undeclared fields on every DTO; result DTO has only tool metadata, entity references, visible field keys, counts, and fixed error codes.
- Added `backend/tests/unit/test_stage08_runtime_contracts.py`.
  - Covers invalid budgets, unknown tools, nested `prompt`, non-JSON nested values, valid safe input, absence of free-text result fields, and importability of plan/ticket contracts.

## Files Changed

- `backend/app/runtime/stage08_contracts.py`
- `backend/tests/unit/test_stage08_runtime_contracts.py`
- `.superpowers/sdd/stage08-task-1-report.md`

## TDD Evidence

### RED 1

Command (from `backend`):

```powershell
python -m pytest -q tests/unit/test_stage08_runtime_contracts.py
```

Result: failed during collection with `ModuleNotFoundError: No module named 'app.runtime'`, as expected before the contract module existed.

### RED 2

Command (from `backend`):

```powershell
python -m pytest -q tests/unit/test_stage08_runtime_contracts.py
```

Result: after the first minimal implementation, failed with `RecursionError` while Pydantic resolved the implicit recursive JSON alias. Replaced it with Pydantic-compatible `TypeAliasType` recursion.

### RED 3

Command (from `backend`):

```powershell
python -m pytest -q tests/unit/test_stage08_runtime_contracts.py
```

Result: new strict-JSON test failed as expected (`DID NOT RAISE`) because Pydantic accepted a nested tuple. Set `ToolInvocation` to strict validation.

### GREEN

Command (from `backend`):

```powershell
python -m pytest -q tests/unit/test_stage08_runtime_contracts.py
```

Result: `15 passed in 0.11s`.

Validation command (from repository root):

```powershell
git diff --check -- backend/app/runtime/stage08_contracts.py backend/tests/unit/test_stage08_runtime_contracts.py
```

Result: exit code 0; no whitespace errors.

## Self-review

- All required seven tool names are closed `Literal` values.
- Budget limits match the task brief exactly, including `max_retrieval_chunks == 0`.
- Input accepts JSON scalars and JSON object/list structures only; it recursively denies all five prohibited keys before any later consumer can use them.
- `RedactedToolResult` is extra-forbidden and contains no `answer` or `content` field; result failure details are constrained to a fixed code set.
- No production runtime behavior, persistence, credentials, prompts, provider outputs, or external calls were added.

## Concerns

- This is a contract-only foundation. Later Stage08 tasks must choose from these fixed ticket states and error codes (or revise the contract through the required documented/approved contract-change process).
- The targeted unit suite and diff check passed. The full backend suite was intentionally not run because this bounded task requested the targeted verification only.

## Temporary Cleanup

No temporary files, data, external artifacts, or generated outputs were created.

---

## Review Follow-up (2026-07-17)

### Implementation

- `ExecutionPlan` now requires strict-string `workspace_id`, `employee_id`, `actor`, `action`, `trace_id`, and `idempotency_key` fields in addition to `ticket_id`.
- Added a model-level `ExecutionPlan` validator that rejects plans whose invocation count exceeds `budget.max_tool_calls`.
- Expanded recursive sensitive-input coverage to all five forbidden keys and a list-nested path.

### RED

Command (from `backend`):

```powershell
python -m pytest -q tests/unit/test_stage08_runtime_contracts.py
```

Result: failed as expected. `ExecutionPlan` rejected the six newly required interface fields as `extra_forbidden` before the contract was extended.

### GREEN

Command (from `backend`):

```powershell
python -m pytest -q tests/unit/test_stage08_runtime_contracts.py
```

Result: `21 passed in 0.18s`.

Validation command (from repository root):

```powershell
git diff --check -- backend/app/runtime/stage08_contracts.py backend/tests/unit/test_stage08_runtime_contracts.py
```

Result: exit code 0; no whitespace errors.

### Follow-up Self-review

- The budget check is on the `ExecutionPlan` model rather than relying on callers, so every plan construction path is covered.
- The valid-plan test supplies and asserts all six required interface fields.
- Parameterized tests cover `prompt`, `response`, `api_key`, `token`, and `raw_text`; a separate test covers a sensitive key inside nested lists.
- No external calls, database activity, migrations, staging, commits, or unrelated file changes were made.

---

## State Machine Contract Follow-up (2026-07-17)

### Approved State List

`ExecutionTicketState` now permits exactly:

- `planned`
- `executing`
- `succeeded`
- `failed`
- `denied`
- `cancelled`
- `timed_out`
- `expired`

Retired and rejected at contract level: `pending_confirmation`, `confirmed`, and `rejected`.

`ToolResultStatus` is aligned to `succeeded`, `failed`, and `denied`; it no longer exposes `rejected`.

### RED

Command (from `backend`):

```powershell
python -m pytest -q tests/unit/test_stage08_runtime_contracts.py
```

Result: 6 expected failures. `denied` and `timed_out` were absent, retired states were still accepted, and `RedactedToolResult` still accepted `rejected` rather than `denied`.

### GREEN

Command (from `backend`):

```powershell
python -m pytest -q tests/unit/test_stage08_runtime_contracts.py
```

Result: `33 passed in 0.14s`.

Validation command (from repository root):

```powershell
git diff --check -- backend/app/runtime/stage08_contracts.py backend/tests/unit/test_stage08_runtime_contracts.py
```

Result: exit code 0; no whitespace errors.

### Follow-up Self-review

- Tests parameterize all eight approved states and assert all three retired states raise `ValueError`.
- `RedactedToolResult` has a direct acceptance test for `denied` and rejection test for `rejected`.
- This change is contract-only: no Provider, Telegram, database, migration, staging, commit, or unrelated file operation was performed.

---

## Independent Review Minor Follow-up (2026-07-17)

### Test-first Coverage Added

- Added an exact-set assertion for `ExecutionTicketState`, requiring the value set to be exactly `planned`, `executing`, `succeeded`, `failed`, `denied`, `cancelled`, `timed_out`, and `expired`. This prevents unreviewed future state additions.
- Parameterized `RedactedToolResult` rejection coverage for all retired values: `pending_confirmation`, `confirmed`, and `rejected`.

### RED / GREEN Evidence

The new tests were written before any implementation change. No code RED was possible or appropriate: the immediately preceding state-machine implementation already correctly exposed exactly the approved eight states and rejected all three retired result statuses. Deliberately mutating the production contract or using monkeypatch to manufacture a failure would not validate a production defect and would weaken the test-first evidence.

Command (from `backend`, immediately after test addition):

```powershell
python -m pytest -q tests/unit/test_stage08_runtime_contracts.py
```

Result: direct GREEN, `37 passed in 0.13s`. No production file changes were required.

Validation command (from repository root):

```powershell
git diff --check -- backend/app/runtime/stage08_contracts.py backend/tests/unit/test_stage08_runtime_contracts.py
```

Result: exit code 0; no whitespace errors.

### Follow-up Self-review

- The exact set assertion checks both absence of retired states and absence of any unapproved additions.
- Result-status rejection now covers the full retired terminology set, not only `rejected`.
- Only the permitted test and report files changed in this follow-up; no external calls, database/migration actions, staging, or commits occurred.
