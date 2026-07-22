# Stage08 Package E — Task E3 report

## Status

- Status: `DONE_WITH_CONCERNS`
- Scope: E3 analysis, Policy Gate and controlled `pending_confirmation` draft routing only.
- External calls: none. No Telegram, OpenRouter, HTTP provider or deployment write was invoked.

## Changed files

- `backend/app/services/stage08_collaboration.py`
  - Added `Stage08CollaborationDependencies` and `run_stage08_collaboration`.
  - Calls E2 `execute_collaboration_reads`; keeps analysis material process-local via the existing sealed carrier.
  - Validates provider outcome shape, action/draft-intent compatibility and safe citation ordinals; unknown ordinals fail closed.
  - Revalidates active member, employee/action, target record/table scope and current context plan immediately before ticket creation.
  - Uses existing `begin_execution_plan` then `Stage08ToolGateway.execute_plan` for the sole `record_change_draft.create` invocation. It creates an empty-value confirmation proposal, never writes or confirms a business record.
  - Adds terminal AgentRun/audit whitelist summaries that omit query, answer, private material and provider response.
- `backend/tests/unit/test_stage08_collaboration_service.py`
  - RED/GREEN coverage for unknown citation denial and the controlled draft path, including terminal-summary redaction assertions.
- `backend/tests/integration/test_stage08_collaboration_postgres.py`
  - Adds the scoped disposable-pgvector connectivity evidence entry point; it skips safely without the configured local URL.

## TDD evidence

### RED

1. `python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_service.py -k unknown_analysis_citation`
   - Result: `1 failed, 14 deselected`.
   - Expected failure: `E3 coordinator is not implemented`.
2. `python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_service.py -k valid_draft_intent`
   - Result: `1 failed, 15 deselected`.
   - Expected behavioral failure before the policy carrier fix: returned `denied` instead of `draft_pending`.

### GREEN

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
```

- Result: `47 passed in 2.05s`.

```powershell
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_collaboration_postgres.py
```

- Result: `1 skipped in 0.32s` because `STAGE08_RAG_DATABASE_URL` was not configured. No connection URL or credential was printed.

## Safety evidence

- The injected unit providers are deterministic in-process objects; they do not perform network I/O.
- No Telegram/OpenRouter/client/deploy command was run.
- The valid-draft test asserts that the persisted terminal AgentRun/audit summaries exclude the command query, answer and draft-intent text.
- Unknown citation denial creates no draft. The valid route uses the existing ticket and gateway; the source record remains unchanged and the resulting draft is `pending_confirmation`.

## Remaining risks / limitations

- Local disposable PostgreSQL evidence was unavailable in this environment because `STAGE08_RAG_DATABASE_URL` was unset; this is not a PostgreSQL acceptance result.
- The existing runtime/ticket service writes its own established ticket audit structure; E3 avoids copying private collaboration material into its new terminal summaries, but a fresh security review should inspect the complete persisted ticket/audit chain and all exception/replay paths.
- The current restricted intent has only a sealed summary, so E3 intentionally creates an empty-value confirmation draft rather than inventing business-field mutations.

## Temporary cleanup

- No temporary files, credentials, network artifacts or deployment artifacts were created.
