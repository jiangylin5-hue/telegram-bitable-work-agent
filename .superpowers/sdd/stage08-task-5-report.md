# Stage08 Task 5 Runtime API Report

## Status

Completed locally in the requested Task 5 scope. No files were staged, committed, reset, checked out, or cleaned.

## Scope

- Added the strict `POST /api/stage08/runtime/execute-plan` request/response DTOs and route.
- Registered the route from `backend/app/main.py`.
- Added `Stage08ToolGateway.execute_plan()` for one locked ticket and sequential invocation execution.
- Kept existing `Stage08ToolGateway.execute()` single-invocation behavior unchanged.
- Added focused API and plan-sequence tests, BDD/acceptance documentation and machine-readable task evidence.

Out of scope and not performed: Memory/RAG, LangGraph, Provider/OpenRouter calls, Telegram or notification sends, direct record writes, new permissions, migrations, deployment, external network calls, and a broad Stage07/Stage08 sweep.

## RED

Command run before production implementation:

```powershell
$env:PYTHONPATH='backend'; python -m pytest backend/tests/unit/test_stage08_runtime_api.py backend/tests/unit/test_stage08_tool_gateway.py -q
```

Observed expected failure: `10 failed, 15 passed`.

- All new API cases returned `404 Not Found`: the Runtime API route was not registered yet.
- The two new gateway cases failed with `AttributeError`: `execute_plan` was not implemented yet.
- The original Task 4 gateway cases accounted for the 15 passing tests.

## GREEN

Minimal implementation added only after RED:

- Client body accepts only `workspace_id`, `employee_id`, `action`, `trace_id`, `idempotency_key`, `budget` and bounded invocations. Actor, ticket ID and state are server-derived.
- Existing workspace authorization for `digital_employee.invoke` happens before PolicyGate/ticket creation.
- The plan path locks one planned ticket, transitions once into `executing`, appends only redacted results in order, then reaches `succeeded`; the first denial/failure appends one fixed redacted error and stops.
- Terminal replay returns the persisted ticket without calling the gateway again.

Focused GREEN command:

```powershell
$env:PYTHONPATH='backend'; python -m pytest backend/tests/unit/test_stage08_runtime_api.py backend/tests/unit/test_stage08_tool_gateway.py -q
```

Result: `25 passed in 3.88s`.

## Verification

```powershell
$env:PYTHONPATH='backend'; python -m pytest backend/tests/unit/test_stage08_runtime_api.py backend/tests/unit/test_stage08_tool_gateway.py backend/tests/unit/test_stage08_runtime_service.py backend/tests/unit/test_stage08_runtime_contracts.py -q
```

Result: `77 passed in 3.98s`.

Targeted new-code send-path scan:

```powershell
rg -n -i "telegram|send_request|notification|provider|openrouter|requests\\.|httpx|urllib" backend/app/api/routes/stage08_runtime.py backend/app/runtime/stage08_tool_gateway.py backend/app/schemas/stage08_runtime.py
```

Result: no matches.

## Skipped work and risks

- PostgreSQL-specific transaction and concurrent lock evidence was not run; Task 5 requested synthetic in-memory or existing local test infrastructure and no broad acceptance sweep.
- No Provider, Telegram, notification, deployment, or external network test was run, by scope.
- The API returns only terminal `succeeded`/`denied`/`failed` states. Unexpected persistent transaction failures remain represented by the existing API error contract rather than exposed raw.

## Temporary cleanup

No temporary runtime data, scripts, or artifacts were created. No cleanup was required.

## Fix Round 1 — strict nested input and validation redaction

### RED

Focused tests were added before the fix for nested-budget coercion and raw validation-body leakage:

```powershell
$env:PYTHONPATH='backend'; python -m pytest backend/tests/unit/test_stage08_runtime_api.py -q
```

Observed expected failure: `3 failed, 11 passed`.

- `budget.max_retrieval_chunks=False` and `0.0` were coerced to `0`, received HTTP `201`, and created/executed a ticket.
- A rejected nested `{"prompt": "RUNTIME_VALIDATION_SECRET"}` appeared in FastAPI's default `422` response under `detail[*].input` (and the error context), proving the raw request leak.

### GREEN

- The shared `ExecutionBudget` Pydantic contract now uses a bounded `StrictInt` for `max_retrieval_chunks`, so only integer `0` is valid; `False`, `0.0`, strings and other non-strict values are rejected before dispatch.
- Only the Stage08 Runtime router now uses a custom route handler that catches `RequestValidationError` and returns the fixed `stage08_runtime_request_invalid` envelope. It includes no body, input, error context, prompt-like key, or original value. Other API routes keep their existing validation behavior.

Focused GREEN command:

```powershell
$env:PYTHONPATH='backend'; python -m pytest backend/tests/unit/test_stage08_runtime_api.py backend/tests/unit/test_stage08_runtime_contracts.py -q
```

Result: `54 passed in 5.37s`.

### Fix Round 1 verification

```powershell
$env:PYTHONPATH='backend'; python -m pytest backend/tests/unit/test_stage08_runtime_api.py backend/tests/unit/test_stage08_tool_gateway.py backend/tests/unit/test_stage08_runtime_service.py backend/tests/unit/test_stage08_runtime_contracts.py -q
```

Result: `86 passed in 5.44s`.

The repeated scoped send-path scan returned no matches. No Provider, Telegram, notification, network, staging, commit, or deployment action was performed.
