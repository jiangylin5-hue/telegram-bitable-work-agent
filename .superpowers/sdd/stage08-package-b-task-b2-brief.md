# Stage08 Package B — Task B2: 类型化投影与安全 Memory 生命周期服务

## Scope

实施 `docs/superpowers/plans/2026-07-18-stage08-package-b-business-memory.md` 的 Task B2，以及 `STAGE_08_PACKAGE_B_MEMORY_BDD_AND_ACCEPTANCE.md` 的 B-04/B-05 服务层部分。B2 消费已完成的 B1 模型和 UoW；仅建立类型化、安全、无 API 的 Memory 生命周期服务。

本任务必须保持 `Memory` 是已确认业务事实的投影，而不是原始对话或自由 prompt 的容器。不可实现 B3 的 confirmed-record hook/outbox、B4 API/Telegram candidate adapter、RAG、向量、LangGraph、provider、Redis、前端或外部调用。

## Files and public surface

Create only:

- `backend/app/runtime/stage08_memory_contracts.py`
- `backend/app/services/stage08_memory.py`
- `backend/tests/unit/test_stage08_memory_contracts.py`（extend B1 file）
- `backend/tests/unit/test_stage08_memory_service.py`

The public typed surface is:

```python
MemoryType = Literal["decision", "preference", "risk", "customer_fact", "project_fact"]

class MemorySourceRef(BaseModel):
    source_kind: Literal["platform_record", "record_change_draft", "telegram_message"]
    source_id: UUID
    source_version: int | None
    field_keys: tuple[str, ...]

class MemoryScopeProjection(BaseModel):
    workspace_id: UUID
    base_id: UUID | None = None
    table_id: UUID | None = None
    customer_record_id: UUID | None = None
    project_record_id: UUID | None = None
    group_chat_ref: str | None = None

class MemoryMaterializationProjection(BaseModel):
    memory_type: MemoryType
    scope: MemoryScopeProjection
    payload: dict[str, JsonSafeValue]
    source_refs: tuple[MemorySourceRef, ...]
    valid_until: datetime | None = None

def materialize_memory_from_projection(uow, projection, *, actor, now) -> Stage08MemoryItem: ...
def read_memory_projection(uow, item_id, *, actor, now) -> dict[str, object] | None: ...
def revoke_memory_candidate(uow, candidate_id, *, actor, expected_version, now) -> Stage08MemoryExtractionCandidate: ...
```

`JsonSafeValue` may be expressed with supported Pydantic JSON-safe primitives/containers. It must reject non-JSON values and recursively reject the forbidden keys below. Do not add a new database column or migration in B2.

## Exact semantic decisions

These decisions realize the approved B2 plan without changing its schema/API/permission boundary:

1. **Forbidden content keys.** Every recursive object key in `scope`, `payload`, `source_refs`, or any nested contract payload rejects (case-insensitively) `prompt`, `response`, `raw_text`, `normalized_text`, `api_key`, `token`, `telegram_user_id`. Field keys must be unique, non-empty lower snake-case identifiers, at most 120 characters. `source_refs` must be non-empty.
2. **Source boundary.** The contract may parse the three declared source kinds, but B2 materialization and read validation support only `platform_record`. Any draft or Telegram source is fail-closed with a fixed `memory_source_not_supported` validation code and must not dereference its payload. B3/B4 are the only later tasks allowed to add their respective adapters.
3. **Scope boundary.** `workspace_id` is mandatory. If `base_id`/`table_id` are present, they must resolve and chain to the same workspace. If `customer_record_id` or `project_record_id` is present, it must resolve to a record whose table/base belongs to that workspace. A non-empty `group_chat_ref` is allowed by contract but no B2 item using it is readable/materializable until B4 adds a controlled group source adapter; fail closed rather than look up Telegram state.
4. **Identity and fingerprint.** Compute a canonical JSON SHA-256 `identity_fingerprint` from `{memory_type, scope}` and a separate SHA-256 `source_fingerprint` from `{memory_type, scope, payload, source_refs}`. Canonical JSON has sorted keys and compact separators; it never uses raw external content. Do not persist an additional identity column: derive it from stored `memory_type` and `scope` when comparing B1 items.
5. **Version/conflict rules.** First acquire the existing server-owned workspace row lock through `uow.lock_workspace_for_stage08_execution(workspace_id)` (the method name is historical; B2 reuses its physical workspace-row serialization and does not create a new lock contract), then validate the full typed projection, active caller membership and readable current source fields. Re-read items only inside that lock. Then:
   - an existing item with the same `source_fingerprint` is returned unchanged (idempotent);
   - for the same identity, a different fingerprint but canonically equal payload creates a new `active` item with `version = prior.version + 1`, `supersedes_id = prior.id`, and marks the previous active item `superseded`;
   - for the same identity with a different canonical payload, create a new `conflicted` item with `version = prior.version + 1`, never overwrite/supersede the existing active item;
   - otherwise create a new `active` version 1 item.
   Only active items participate in the identity comparison. B2 does not silently resolve conflicts.
6. **Current source revalidation.** A supported `platform_record` source must exist, have exactly the referenced version, resolve to the projection workspace/table chain, and expose every `field_key` through `read_record_for_actor`. Require every payload key to occur in the union of source field keys and to equal the current readable record value for that key. Any missing/deleted/stale/hidden field or mismatch is failure; materialization raises a fixed validation error and reading marks the memory `deleted`, writes a redacted audit event, and returns `None`.
7. **Read is fail closed.** Require an active user workspace membership matching `actor.actor_id` before processing. Return `None` if item is missing, not `active`, out of workspace scope, uses group scope before B4, has expired TTL, has invalid source or lacks current field visibility. On TTL expiry transition `active → expired`; source invalidity transitions `active → deleted`. Return only `{id, memory_type, version, scope, payload, valid_until}` for a valid item. Never include `source_refs`, field keys, source IDs, fingerprints, raw source values not already in the permitted payload, audit details, prompt/response, or provider/Telegram identifiers.
8. **Candidate revocation.** Require active same-workspace `user` actor with role `owner` or `admin`, exact positive `expected_version`, and a lifecycle lock. Candidate must currently be `candidate`; change it to `rejected`, set `reviewed_at=now`, `reviewed_by_user_id` only when `actor.actor_id` is a UUID (otherwise leave it null), then increment version. Invalid state/expected version/foreign workspace/non-manager all fail closed with stable `PlatformValidationError` codes. B2 does not revoke a linked item because B1 has no candidate-to-item relation; B4 may extend the controlled workflow.
9. **Audit.** Every create/reuse/supersede/conflict/expiry/source-delete/candidate-revoke transition uses the existing audit service through the UoW session target. Audit state may contain only IDs, type, status, versions and fixed reason code — never `payload`, `scope`, `source_refs`, fingerprint, field key or source content. Do not add a new audit schema.

## Test-driven execution

1. Extend/create tests first, then run:

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Record the expected missing-contract/service RED result in `.superpowers/sdd/stage08-package-b-task-b2-report.md` before production code.

2. Add focused tests for all of:

- recursive raw-key rejection, malformed field keys/source refs, unknown memory type and non-JSON values;
- same source fingerprint idempotency; same identity/equal-payload supersession; same identity/different-payload conflict without overwriting the active item;
- active membership and workspace/base/table/relation scope mismatch denials;
- TTL transition/read refusal, stale source version and field-visibility loss transition/read refusal;
- safe response excludes source provenance and audit entries exclude a sentinel payload string;
- candidate lock/version/role/workspace state checks and safe revocation receipt.

3. Implement only enough contracts/service code to make the focused tests pass. Add no migration, route, outbox, source adapter, external client, worker or send path.

4. Run the focused command again. If the existing local PostgreSQL fixture is useful for B1 regressions, it may be run separately, but do not broaden into package acceptance. Report exact commands/results, audit evidence, no-external-call statement, skipped scope and risks in `.superpowers/sdd/stage08-package-b-task-b2-report.md`.

## Non-negotiable safety

- Do not read a Telegram message, draft payload or provider content in B2.
- Do not persist raw message/prompt/response, provider key/token, Telegram user ID or chain of thought.
- Do not accept client-claimed permissions, field visibility, source version or scope validity.
- Do not stage, commit, reset, checkout or clean the dirty shared worktree.

## Fix Round 1 — mandatory review corrections

The initial implementation review found real fail-open paths. Apply every correction below before reporting B2 complete. Extend the focused unit tests and, only for the concurrency evidence below, `backend/tests/integration/test_stage08_memory_postgres.py`. Do not change B2's API, schema, migration, source adapter, external-system or Git scope.

1. **Full valid-state chain.** A workspace, base, table, field, source record or relation-scope record is valid only with its status equal to `active`. Materialization must reject every inactive/deleted link with fixed `memory_scope_invalid` or `memory_source_invalid`; safe read must lock the active item, set it `deleted`, set `deleted_at=now`, write a redacted audit record and return `None`. Candidate revocation must reject an inactive workspace. Add regressions for each inactive workspace/base/table/field, deleted source record and inactive customer/project relation record.
2. **Strict contract input.** Reject case-insensitive forbidden names when they appear as `MemorySourceRef.field_keys` values, reject all non-finite floats recursively (`NaN`, `+Inf`, `-Inf`), and make `_canonical_json(..., allow_nan=False)` a defense-in-depth assertion. `valid_until` must be timezone-aware; reject a naive value at the contract boundary. Add parameterized tests.
3. **Lifecycle serialization.** `materialize_memory_from_projection` must obtain the existing workspace row lock before reading item state and retain it through idempotency/supersede/conflict writes. Add a real disposable PostgreSQL dual-session test using `pg_blocking_pids`: a blocked same-fingerprint call must resolve to the existing item after the first commits, and a blocked different-fingerprint/same-identity call must form the correct post-lock version chain rather than create competing `active` version 1 rows.
4. **Expected version and audit projection.** `expected_version` is accepted only when `isinstance(value, int)` and not `bool`, and it is positive; `None`, string, float, bool, zero and negative values must return fixed `memory_candidate_expected_version_invalid` without a native `TypeError`. B2 audit `permission_snapshot` may contain only fixed action/reason code; remove actor role and keep all other state limited to ID/type/status/version/reason.
5. **Evidence hygiene.** The report must append a Fix Round 1 section with exact RED/GREEN commands/results and correct any initial claim that these cases were already covered. The independent reviewer must re-review before B2 is marked complete.
