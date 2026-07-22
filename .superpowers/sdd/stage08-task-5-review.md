## Task 5 scoped review — 2026-07-18

- Spec compliance: **FAIL**
- Task quality: **FAIL**
- Critical: None.

### Important

1. The Runtime API request is not fully strict at the nested budget boundary. `RuntimeExecutionPlanRequest` sets `strict=True`, but strict mode does not propagate into `ExecutionBudget`; its `max_retrieval_chunks: Literal[0]` currently accepts JSON `false` and `0.0`, normalizes either to integer `0`, and the endpoint executes the plan with `201 succeeded`. This violates Task 5's explicit strict request-DTO requirement. The focused tests miss the coercion case. Make this nested field/model strict and add an API regression asserting non-integer zero values are rejected before ticket/service dispatch.

### Verification observed during review

- `python -m pytest backend/tests/unit/test_stage08_runtime_api.py backend/tests/unit/test_stage08_tool_gateway.py backend/tests/unit/test_stage08_runtime_service.py backend/tests/unit/test_stage08_runtime_contracts.py -q` → `77 passed in 4.50s`.
- Targeted Provider/Telegram/notification/network/direct-write scan of the three scoped runtime files → no matches.

## Fix Round 1 review — 2026-07-18

- Verdict: **PASS**
- Spec compliance: **PASS**
- Task quality: **PASS**
- Critical: **0**
- Important: **0**

The original Important is resolved: `max_retrieval_chunks` now uses a bounded `StrictInt`, and independent HTTP reproduction confirmed that JSON `false`, `0.0`, and `"0"` each return `422` without creating a ticket. The newly reported validation leak is also resolved: the forbidden nested prompt sentinel is absent from the fixed Stage08 error envelope and no ticket is created.

Redaction remains route-scoped. Runtime application inspection found exactly one `_RedactedRuntimeValidationRoute`, at `/api/stage08/runtime/execute-plan`; an invalid request to the existing `/workspaces` endpoint retained its ordinary FastAPI validation response, confirming that other APIs were not changed.

Focused verification: `86 passed in 5.17s` for the Task 5 API, gateway, runtime-service, and runtime-contract test set.
