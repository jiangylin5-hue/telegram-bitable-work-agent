# Stage08 Package B Task B4 实施报告

## Status

- Status: DONE
- Scope: 受控 Telegram 群聊 Memory candidate、promotion/conflict/lifecycle、安全 list/revoke API、本地 PostgreSQL 证据。
- Boundary: 仅支持 `telegram_message + group_candidate_projection + stage06-binding:<uuid>`；固定门槛精确为 `Decimal("0.85")`。

## Changed Files

- `backend/app/services/stage08_group_memory_source.py`
  - 新增 strict、无文本的短命 `TrustedGroupMessageInput` / `GroupMemorySourceProjection`。
  - 仅在当前进程内比较 chat ID，输出只保留内部 message UUID 和 `stage06-binding:<uuid>` opaque ref。
  - 重验 active workspace/binding/chat_user/member；不读 Message 表、不调 Telegram API。
- `backend/app/runtime/stage08_memory_contracts.py`
  - 新增 strict `GroupMemoryCandidateProjection`。
  - 固定 `0.85` 最低置信度；仅允许精确 group source/ref 形状。
  - 强制 payload 非空、最多 16 个顶层 key、lower snake case、字符串最多 500 code points、深度最多 4、列表最多 20，并递归拒绝 raw/message/content 载体 key。
- `backend/app/services/stage08_memory.py`
  - 新增 candidate create/resolve、safe list、exact-fingerprint accepted revoke 和安全生命周期回执。
  - candidate 与 Memory 复用同一 canonical fingerprint；同 fingerprint 幂等，冲突不覆盖 active fact。
  - 读取时 source missing/corrupt -> `deleted`，binding/member invalid -> `revoked`，TTL -> `expired`，并立即 fail closed。
  - SQLAlchemy `autoflush=False` 下对新 candidate 做事务内显式 flush，保证 replay/resolve 可见。
- `backend/app/schemas/stage08_memory.py`
  - 新增 strict list/revoke request/response DTO，不含 ID、scope、source ref、binding/chat/Telegram identity。
- `backend/app/api/routes/stage08_memory.py`
  - 新增 `GET /api/stage08/memory` 与 `POST /api/stage08/memory/extractions/{candidate_id}/revoke`。
  - 仅复用已有 `workspace.read` / `member.manage`、verified identity、commit/rollback 与固定错误码。
  - 任何 path/query/body Pydantic validation 失败只返回 `stage08_memory_request_invalid`，不回显输入。
  - source-invalid revoke 是唯一受控 409 生命周期例外：先持久 candidate `expired` 再返回 409；其他错误 rollback。
- `backend/app/main.py`
  - 仅注册 Stage08 Memory router，保留共享工作树既有改动。
- `backend/tests/unit/test_stage08_memory_contracts.py`
  - 新增 threshold、raw carrier、payload bounds、exact source/ref 和 adapter fail-closed 测试。
- `backend/tests/unit/test_stage08_memory_service.py`
  - 新增 candidate 持久化/幂等/promotion/conflict、二次 threshold gate、binding/TTL/corrupt lifecycle、exact revoke 和 safe list 测试。
- `backend/tests/unit/test_stage08_memory_api.py`
  - 新增 API identity/authorization/403/404/409/422 redaction 与安全输出测试。
- `backend/tests/integration/test_stage08_memory_postgres.py`
  - 新增真实本地 PostgreSQL candidate 幂等、binding revoke/read fail-closed、audit 脱敏与 exact-fingerprint accepted revoke 证据。
  - 既有双 session `FOR UPDATE` 测试继续覆盖 candidate/item lifecycle lock 阻塞。
- `.superpowers/sdd/stage08-package-b-task-b4-report.md`
  - 本报告。

## TDD Evidence

### RED-1: contract and adapter

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py -k "group_candidate or adapter"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- Result: exit 1, collection error.
- Expected cause: `ImportError: cannot import name 'GroupMemoryCandidateProjection'`.

### GREEN-1

- Same command result: `9 passed, 16 deselected in 0.67s`.

### RED-2: service lifecycle

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_service.py -k "group_candidate or group_memory or accepted_candidate"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- Result: exit 1, collection error.
- Expected cause: `ImportError: cannot import name 'CandidateRevocationResult'`.

### GREEN-2

- Same command result: `6 passed, 28 deselected in 0.76s`.
- Full service file: `34 passed in 0.76s`.

### RED-3: API

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_api.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- Result: exit 1, `4 failed`; every request returned expected pre-router `404`.

### GREEN-3

- Same command result: `4 passed in 3.03s`.
- The invalid body/query/path sentinel and `raw_text` field are absent from every 422 response.

### PostgreSQL RED/GREEN

- Initial B4 PostgreSQL run exposed two fixture flush gaps, then a real service defect under SQLAlchemy `autoflush=False`: replay created a second in-session candidate and immediate resolve could not see the first candidate.
- Minimal correction: flush the newly added candidate inside the transaction before audit/replay/resolve.
- Focused PostgreSQL rerun: `2 passed, 7 deselected in 4.72s`.

## Fresh Verification

### Required B4 aggregate, including real local PostgreSQL

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_memory_api.py tests/integration/test_stage08_memory_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- Fresh final result: `72 passed in 13.86s`.
- PostgreSQL URL resolved to the configured disposable local `stage06_smoke` database on `127.0.0.1`.
- Evidence is local PostgreSQL only; it is not staging/production evidence.
- The aggregate includes the existing two-session candidate/item lifecycle `FOR UPDATE` blocking evidence, JSONB/unique constraints and workspace materialization serialization.

### B3/B2/runtime regression

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_confirmed_record.py tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage08_runtime_api.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- Fresh final result: `110 passed in 4.98s`.

### Migration head

```powershell
Push-Location backend; python -m alembic heads; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- Result: `20260718_0029 (head)`.
- B4 did not create or modify a migration.

### Compile, whitespace and no-external-call checks

- `python -m compileall -q` on all B4 production modules and `main.py`: exit 0.
- scoped `git diff --check`: exit 0; only the pre-existing `main.py` LF/CRLF warning was printed.
- static search of B4 production surfaces for HTTP/Telegram client/OpenRouter/Redis/LangGraph/vector/send markers: `NO_EXTERNAL_CALL_MARKERS`.

## Security Evidence

- Exact constant and DTO/service double gate use `Decimal("0.85")`; a test-bypassed `0.8499` projection creates no candidate, Memory or outbox.
- Candidate/Memory share the same SHA-256 canonical fingerprint over type, safe scope, normalized payload and source refs; confidence and chat/user IDs are excluded.
- Candidate, Memory, audit and HTTP tests assert raw/chat/user sentinel values are absent.
- Private chat DTOs, missing/inactive/wrong-type bindings, inactive members, foreign workspace, non-manager, version conflict, stale/corrupt source and TTL all fail closed.
- Conflict creates a `conflicted` item and preserves the prior active payload.
- Accepted candidate revoke locks and revokes only the exact same-fingerprint item; an unrelated active item remains active.
- No candidate-create HTTP route exists.

## Skipped Tests and Out-of-Scope Work

- Full backend suite was not run; the task-required focused suites, B3/B2/runtime regressions and full Stage08 Memory PostgreSQL module were run.
- No staging/production deployment or remote PostgreSQL evidence.
- No Telegram Bot API/send/read, webhook/parser/ingestion change, historical Message read, provider/LLM, Redis, RAG/vector, LangGraph, frontend, migration, new role/action or external call.
- Per the brief's document-conflict rule, Stage08 source/BDD/contract/plan and project-doc evidence files were not modified; this `.superpowers/sdd` report is the task evidence document.

## Remaining Risks

- Historical `Message` persistence may already retain raw Telegram text/caption; B4 never reads or extends it, but removal requires a separately approved ingestion-retention/schema task.
- `Stage06TelegramBinding` has no persisted chat-type/version column. Group/supergroup is proven only in the trusted short-lived adapter; later reads revalidate active binding/workspace/member.
- Structural allowlists and size/depth bounds prevent known raw carrier fields, but cannot mathematically prove an arbitrary allowed string is not verbatim text; the trusted extraction producer remains a future control boundary.
- No candidate list/review UI or public candidate-create endpoint was added.

## Temporary Cleanup

- No temporary scripts, data files or generated artifacts were created.
- No git stage/commit/reset/checkout/clean operation was executed.

## Fix Round 1 — Independent Review C1/C2/I1/I2/I3/I4

### Status and Scope

- Status: DONE
- Authority: `.superpowers/sdd/stage08-package-b-task-b4-review.md`.
- Scope remained inside the approved B4 contracts, service, route and tests. No migration, action/role, Telegram/webhook/ingestion, frontend or external-call expansion occurred.

### Corrections

- C1: public `materialize_memory_from_projection()` now rejects every group/`telegram_message` projection. Only `resolve_group_candidate()` can enter the private group materializer after reconstructing and validating the strict stored candidate contract. Safe reads independently revalidate the same group contract before returning payload.
- C2: recursive group payload rejection now also includes `chat_id`, `binding_id`, `group_chat_ref`, `source_refs` and `field_keys`. Candidate creation reconstructs the strict DTO, so `model_copy`/unsafe internal construction cannot bypass the service boundary. Corrupt stored group payloads transition to `deleted` and never enter list/API output.
- I1: accepted-candidate revoke reconstructs the stored strict candidate, recomputes its canonical fingerprint, compares it to the stored fingerprint, and validates the matched Memory's canonical projection before revocation. Fingerprint corruption expires/fails closed without touching unrelated items.
- I2: revoke checks candidate TTL before version, source and state transitions. Candidate or accepted candidate TTL expiry transitions to `expired`, increments version, writes `memory_candidate_ttl_expired` audit metadata and returns the fixed 409 path; an associated item is not revoked.
- I3: group reads validate binding/workspace/member authorization state before generic scope validation. Authorization loss becomes `revoked`; malformed/missing source remains `deleted`; TTL remains `expired`.
- I4: every newly created/superseding/conflicted Memory is flushed after `add_memory_item()`. Real PostgreSQL coverage proves same-transaction list and exact accepted-candidate revoke work without an intervening commit.

### RED Evidence

#### C2 contract

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py -k "transport_and_source_identity"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- RED: `5 failed, 25 deselected in 0.81s`; all five carrier keys were accepted.
- GREEN: `5 passed, 25 deselected in 0.59s`.

#### C1/I1/I2/I3 service

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_service.py -k "generic_group or source_identity or recomputes or expired_group or expired_accepted or inactive_workspace_revokes"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- RED: `6 failed, 34 deselected in 1.03s`.
- Failures reproduced generic raw-caption persistence, stored carrier list exposure, unrelated fingerprint revoke, candidate/accepted TTL mis-transition and inactive-workspace `deleted` misclassification.
- GREEN: `6 passed, 34 deselected in 0.62s`.

#### API carrier exposure

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_api.py -k "identity_carrier"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- RED: `1 failed, 4 deselected in 2.41s`; corrupt `group_chat_ref` payload was returned.
- GREEN: `1 passed, 4 deselected in 2.22s`; response is `{"items":[]}` and the item becomes `deleted`.

#### I4 real local PostgreSQL no-commit visibility

```powershell
Push-Location backend; python -m pytest -q tests/integration/test_stage08_memory_postgres.py -k "visible_to_list_and_exact_revoke_without_commit"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- RED: `1 failed, 9 deselected in 3.78s`; same-transaction list returned no item.
- GREEN: `1 passed, 9 deselected in 3.41s`; list and exact revoke both succeed before commit.
- This is disposable local PostgreSQL evidence, not staging/production evidence.

#### Service-boundary revalidation and TTL audit reason

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_service.py -k "revalidates_bypassed or expired_group_candidate_revoke"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- RED: `2 failed, 39 deselected in 1.06s`; unsafe `model_copy` payload persisted and TTL audit used the source-invalid reason.
- GREEN: `2 passed, 39 deselected in 0.72s`.

### Fresh Final Verification

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_memory_api.py tests/integration/test_stage08_memory_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- Result: `87 passed in 16.02s`.

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_confirmed_record.py tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage08_runtime_api.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- Result: `122 passed in 4.97s`.

```powershell
Push-Location backend; python -m alembic heads; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- Result: one unchanged head, `20260718_0029 (head)`.

- `compileall`: exit 0.
- Scoped `git diff --check`: exit 0, with only the pre-existing `main.py` LF/CRLF warning.
- Static external-call marker search: `NO_EXTERNAL_CALL_MARKERS`.
- No Telegram API, Provider/LLM, Redis, HTTP client, vector/RAG, migration, new permission, external write or git operation ran.

## Fix Round 2 - Recursive Telegram Identity Carriers and Version Precedence

### Status and Scope

- Status: DONE
- C2 is closed at both strict DTO and service persistence boundaries. Recursive group payload validation rejects `telegram_chat_id`, `telegram_message_id`, `telegram_update_id` and the reported transport/source synonyms `message_id`, `update_id`, `source_id`, `source_ref`.
- I2 is corrected: after authorization, `expected_version` is checked before TTL or any lifecycle mutation. A stale request cannot change candidate status/version/review metadata, Memory status or audit rows. A subsequent current-version request retains the approved TTL-expiry behavior.
- Valid normalized business payload remains unchanged and is still proven through candidate acceptance, list and API tests.

### RED Evidence

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py -k "telegram_transport"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- RED: `7 failed, 30 deselected in 0.83s`; all required Telegram-prefixed and reported transport/source synonym keys were accepted recursively.

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_service.py -k "telegram_transport or stale_version"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- RED: `5 failed, 41 deselected in 1.12s`; three bypassed Telegram identifiers reached candidate persistence, while candidate and accepted-candidate stale revokes performed TTL expiry before rejecting the version.

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_api.py -k "telegram_transport or stale_version"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- RED: `2 failed, 6 deselected in 2.82s`; a corrupt `telegram_update_id` payload was returned and stale+expired revoke returned `memory_candidate_expired` after mutation.

### Focused GREEN Evidence

- Contract: `7 passed, 30 deselected in 1.97s`.
- Service: `5 passed, 41 deselected in 0.76s`.
- API: `2 passed, 6 deselected in 3.61s`.
- Service assertions prove candidate and accepted states, versions, review metadata, Memory status and audit count remain unchanged after stale+expired revoke; correct versions then produce the existing fixed `memory_candidate_expired` transition.
- Candidate creation assertions prove forbidden Telegram identifiers create no candidate, Memory or audit output. Corrupt persisted payload defense-in-depth deletes the item before list/API serialization.

### Fresh Final Verification

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_memory_api.py tests/integration/test_stage08_memory_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- B4 aggregate: `101 passed in 14.91s`.

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_confirmed_record.py tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage08_runtime_api.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

- B3/B2/runtime regression: `134 passed in 5.68s`.
- Alembic remains one unchanged head: `20260718_0029 (head)`.
- `python -m compileall -q app tests`: exit 0.
- Scoped `git diff --check`: exit 0.
- Static production-surface search: `NO_EXTERNAL_CALL_MARKERS`.

### Skipped Tests, Risks and Cleanup

- Full backend suite was not run; B4 aggregate, real local PostgreSQL B4 coverage and the B3/B2/runtime regression set passed.
- No migration, role/action, Telegram/webhook/ingestion, frontend, provider/LLM, Redis, RAG/vector, LangGraph or external call was added or executed.
- No temporary files/artifacts were created and no git stage/commit/reset/checkout/clean operation was executed.
