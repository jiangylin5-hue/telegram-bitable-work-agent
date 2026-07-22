# Stage08 Package A Task 4 Report

## Scope

Implemented only the fixed seven-tool Stage08 Tool Gateway and the minimal Stage06 helpers needed for controlled contact resolution, catalog inspection, create-record drafts, and create-record draft confirmation. No Task schema, migration, API, notification, Telegram, provider, or unrelated Stage07 work was added.

## Exact Files

- `backend/app/runtime/stage08_tool_gateway.py` (new)
- `backend/app/services/stage06_digital_employees.py` (modified)
- `backend/tests/unit/test_stage08_tool_gateway.py` (new)
- `.superpowers/sdd/stage08-task-4-report.md` (new)

## RED Evidence

Command:

```powershell
python -m pytest -q tests/unit/test_stage08_tool_gateway.py
```

Expected and observed failure before implementation:

```text
ModuleNotFoundError: No module named 'app.runtime.stage08_tool_gateway'
```

## GREEN Evidence

Command:

```powershell
python -m pytest -q tests/unit/test_stage08_tool_gateway.py
```

Output:

```text
9 passed in 0.96s
```

The test file covers all seven adapters, UUID/input shape rejection, unknown-tool fail-closed behavior without service execution, runtime policy revocation, terminal-ticket replay rejection, output/ticket/audit redaction, create-record draft confirmation, and rejected create-record draft behavior.

## Regression

Required command:

```powershell
python -m pytest -q tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage06_live_digital_employee_runtime.py tests/unit/test_stage06_skill_matching.py
```

Output:

```text
20 passed in 1.15s
```

Additional affected-service regression:

```powershell
python -m pytest -q tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage08_runtime_service.py
```

Output:

```text
20 passed in 1.61s
```

## No-Send and Safety Scan

Command:

```powershell
rg -n "sendMessage|notification_request\.confirm|Telegram.*send" app/runtime/stage08_tool_gateway.py app/services/stage08_runtime.py
```

Output: no matches.

Additional implementation scan:

```powershell
rg -n "\b(select|insert|update|delete)\b|\.session\b|__import__|importlib|\bgetattr\b|\bsetattr\b" app/runtime/stage08_tool_gateway.py
```

Output: no matches.

`git diff --check` passed for the modified tracked file and the named Task4 paths. The shell emits a pre-existing PowerShell profile execution-policy warning; it did not affect pytest or scan exit status.

## Not Done

- No independent Task/TaskDraft model, migration, or API was created.
- No Runtime API, LangGraph coordinator, Memory/RAG, Telegram/notification send, provider call, or raw record-value response was added.
- No git staging, commit, reset, checkout, or clean operation was performed.

## Risks

- Verification uses the existing in-memory unit-of-work coverage. PostgreSQL integration coverage for this new gateway remains a later package-level concern.
- The pre-existing `create_record` audit remains its established Stage06 behavior; Task4-specific draft creation/confirmation audit payloads omit `proposed_values`, and the gateway ticket summaries only retain `RedactedToolResult` fields.

## Temporary Cleanup

No temporary data, scripts, or artifacts were created.

## Fix Round 1 — Independent Review Security Remediation

### Scope

Addressed the review's C1, C2, I1 and I2 findings only. The gateway now locks and re-fetches a canonical execution ticket from the caller-supplied `ticket.id`, then uses that canonical object exclusively. The Stage06 UoW has a narrow execution-ticket transition lock boundary. Create-record draft confirmation and rejection now use the existing draft transition lock, and confirmation revalidates current membership, `get_create_form(...).can_create`, and `can_actor_write_record_fields` before `create_record`.

### Additional Files

- `backend/app/services/stage06_platform.py` (modified)
- `backend/tests/integration/test_stage08_runtime_postgres.py` (new)

### RED Evidence

Unit regression command:

```powershell
python -m pytest -q tests/unit/test_stage08_tool_gateway.py -k "detached or confirmation_revalidates"
```

Observed before the Fix Round 1 implementation:

```text
4 failed
```

The failures demonstrated that a forged detached ticket invoked the forged employee, a forged workspace resolved a foreign member, and create-record draft confirmation succeeded after field-write revocation or with a different non-writing confirmer.

The first PostgreSQL run additionally exposed test-fixture `autoflush=False` setup errors, which were corrected before interpreting behavior. The corrected PostgreSQL run then exposed two real implementation defects: the JSONB `tool_summary` in-place mutation was not persisted (`len(ticket.tool_summary) == 0`), and `expected_version=0` violated the existing positive-version database constraint for create-record drafts.

### GREEN Evidence

Focused unit command:

```powershell
python -m pytest -q tests/unit/test_stage08_tool_gateway.py -k "detached or confirmation_revalidates"
```

Output:

```text
4 passed, 9 deselected in 1.39s
```

Affected unit regression:

```powershell
python -m pytest -q tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage06_live_digital_employee_runtime.py tests/unit/test_stage06_skill_matching.py tests/unit/test_stage08_runtime_service.py
```

Output:

```text
45 passed in 1.63s
```

Full Stage08 PostgreSQL module:

```powershell
python -m pytest -q tests/integration/test_stage08_runtime_postgres.py
```

Output:

```text
8 passed in 12.06s
```

### PostgreSQL Lock Evidence

The four new PostgreSQL cases use two independent SQLAlchemy sessions and call `pg_blocking_pids(blocked_pid)` directly through the existing `_wait_until_backend_is_blocked` helper before the first transaction is released:

- execution-ticket claim: the second gateway call blocks on `lock_execution_ticket_for_transition`; exactly one AgentRun and one persisted redacted tool summary remain; the second call returns `ticket_not_planned`;
- double create-record confirmation: the second confirmer blocks on `lock_record_change_draft_for_transition`; exactly one record remains and the second call returns `record_change_draft_invalid_state`;
- reject-first confirm/reject race: zero records and terminal `rejected`;
- confirm-first confirm/reject race: exactly one record and terminal `confirmed`.

All worker sessions rollback in exception paths and all lock-holder sessions use `finally` rollback guards.

### Safety Scan

```powershell
rg -n "sendMessage|notification_request\.confirm|Telegram.*send" app/runtime/stage08_tool_gateway.py app/services/stage08_runtime.py
rg -n "__import__|importlib|\bgetattr\b|\bsetattr\b|\.session\b|\btext\(" app/runtime/stage08_tool_gateway.py
```

Both scans had no matches. `git diff --check` passed for all modified Task4 paths. The shell continues to emit a local PowerShell profile execution-policy warning; it did not affect any command's result.

### Remaining Risks / Not Done

- No schema, migration, API, Task/TaskDraft model, Telegram/notification/provider action, external write, Runtime API, Memory/RAG, or LangGraph coordinator was added.
- The evidence is against the allowed local disposable PostgreSQL database, not remote staging or production.
- No staging, commit, reset, checkout, or clean operation was performed.

## Fix Round 2 — FR1-I1 Canonical Membership Actor

### Scope

Fixed only FR1-I1. After obtaining the existing draft transition lock, the active-member helper now returns the current `WorkspaceMember`. Create-record draft creation and confirmation derive a canonical `Actor(actor_type="user", actor_id=member.user_id, role=member.role)` from that member. The canonical actor is used for create-form and field-write authorization, `create_record`, and create/confirmation audit events. The incoming actor is no longer trusted for a stale role on this path.

### RED Evidence

```powershell
python -m pytest -q tests/unit/test_stage08_tool_gateway.py -k "stale_actor_after_member_role_downgrade"
```

Observed before the Fix Round 2 implementation:

```text
1 failed, 14 deselected
```

The test created a draft as an operator, changed the active workspace member role to `viewer`, then supplied the stale `Actor(role="operator")`. Confirmation incorrectly succeeded before this fix.

### GREEN Evidence

Focused regression:

```powershell
python -m pytest -q tests/unit/test_stage08_tool_gateway.py -k "stale_actor_after_member_role_downgrade"
```

Output:

```text
1 passed, 14 deselected in 1.10s
```

Affected regression:

```powershell
python -m pytest -q tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage06_live_digital_employee_runtime.py tests/unit/test_stage06_skill_matching.py
```

Output:

```text
31 passed in 1.36s
```

### Not Done

- The PostgreSQL suite was intentionally not rerun because Fix Round 2 does not change the UoW or row-lock implementation; Fix Round 1 PostgreSQL lock evidence remains retained.
- No schema, migration, API, notification, Telegram, provider, Task/TaskDraft model, or unrelated Stage07 change was added.
- No staging, commit, reset, checkout, or clean operation was performed.
