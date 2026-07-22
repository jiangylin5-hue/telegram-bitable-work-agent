# Stage08 Runtime API Task 5 Evidence

## Scope

Implemented the confirmed Package A Task 5 Runtime API contract and sequential multi-invocation ticket execution. No migration, schema persistence change, network call, Provider call, Telegram send, notification send, or deployment action was performed.

## RED evidence

Before production implementation:

```powershell
$env:PYTHONPATH='backend'; python -m pytest backend/tests/unit/test_stage08_runtime_api.py backend/tests/unit/test_stage08_tool_gateway.py -q
```

Result: `10 failed, 15 passed`.

- API tests returned `404 Not Found` because `/api/stage08/runtime/execute-plan` was not registered.
- Gateway plan tests raised `AttributeError` because `Stage08ToolGateway.execute_plan` did not exist.
- Existing Task 4 single-invocation tests were already green (`15 passed`).

## GREEN and regression evidence

```powershell
$env:PYTHONPATH='backend'; python -m pytest backend/tests/unit/test_stage08_runtime_api.py backend/tests/unit/test_stage08_tool_gateway.py backend/tests/unit/test_stage08_runtime_service.py backend/tests/unit/test_stage08_runtime_contracts.py -q
```

Result: `77 passed in 3.98s`.

The focused API cases cover unknown/raw prompt-like input rejection, server-derived actor/ticket/state, pre-dispatch workspace authorization, ordered two-invocation redacted output, denial stop behavior and terminal idempotent replay. Gateway cases cover a single ticket transition into sequential success and stopping after a fixed failed summary without invoking the subsequent adapter.

## Send-path scan

```powershell
rg -n -i "telegram|send_request|notification|provider|openrouter|requests\\.|httpx|urllib" backend/app/api/routes/stage08_runtime.py backend/app/runtime/stage08_tool_gateway.py backend/app/schemas/stage08_runtime.py
```

Result: no matches. The `main.py` registration was intentionally excluded because it contains pre-existing Telegram router registrations unrelated to this route.

## Remaining risk

This is synthetic in-memory/unit evidence only. PostgreSQL contention/transaction behavior and broader Stage08 acceptance remain out of this Task 5 scope.
