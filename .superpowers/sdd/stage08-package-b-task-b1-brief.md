# Stage08 Package B Task B1：Memory 持久化基础

## Scope

实现 Package B 的持久化边界，完全遵循：

- `docs/superpowers/plans/2026-07-18-stage08-package-b-business-memory.md` 的 Task B1；
- `project-docs/08-implementation/STAGE_08_PACKAGE_B_MEMORY_BDD_AND_ACCEPTANCE.md` 的 B-01；
- `project-docs/08-implementation/STAGE_08_DATA_API_SECURITY_CONTRACT.md` 的 `MemoryItem` 和 `MemoryExtractionCandidate` 合同。

本任务只新增模型、迁移、UoW 访问方法和局部测试。不得实现 Memory materializer、outbox、群聊读取、API、向量、Provider、Telegram、外部写入或任何 source payload 投影。

## Required persistent model

Create `backend/app/models/stage08_memory.py` with:

```python
Stage08MemoryItem(
  id, created_at, updated_at,
  workspace_id, memory_type, status,
  scope, payload, source_refs, source_fingerprint,
  version, supersedes_id, valid_until, revoked_at, deleted_at,
)
Stage08MemoryExtractionCandidate(
  id, created_at, updated_at,
  workspace_id, candidate_type, status, confidence,
  scope, normalized_payload, source_refs, source_fingerprint,
  version, valid_until, reviewed_at, reviewed_by_user_id,
)
```

Both use UUID PK/timestamps, workspace FK and PostgreSQL JSONB.

Exact status checks:

```text
MemoryItem: active|conflicted|superseded|revoked|expired|deleted
Candidate: candidate|accepted|rejected|expired
```

Exact constraints:

- `scope`, `payload`/`normalized_payload` are JSON objects; `source_refs` is a JSON array.
- `version > 0`; `confidence >= 0 AND confidence <= 1`.
- unique `MemoryItem(workspace_id, memory_type, source_fingerprint)` and `Candidate(workspace_id, candidate_type, source_fingerprint)`.
- lifecycle index `(workspace_id, status, valid_until)` on both models.
- `supersedes_id` only references a MemoryItem; it may be null.

Update model registry and create Alembic revision `20260718_0029_stage08_business_memory.py` with `down_revision="20260717_0028"`.

## Unit-of-work contract

Add exact parity methods to `Stage06PlatformUnitOfWork`, `InMemoryStage06PlatformUnitOfWork` and `SqlAlchemyStage06PlatformUnitOfWork`:

```python
def add_memory_item(self, item: Stage08MemoryItem) -> None: ...
def get_memory_item(self, item_id: UUID) -> Stage08MemoryItem | None: ...
def lock_memory_item_for_lifecycle(self, item_id: UUID) -> Stage08MemoryItem | None: ...
def list_memory_items(self, workspace_id: UUID) -> list[Stage08MemoryItem]: ...
def add_memory_extraction_candidate(self, candidate: Stage08MemoryExtractionCandidate) -> None: ...
def get_memory_extraction_candidate(self, candidate_id: UUID) -> Stage08MemoryExtractionCandidate | None: ...
def lock_memory_extraction_candidate_for_lifecycle(self, candidate_id: UUID) -> Stage08MemoryExtractionCandidate | None: ...
def list_memory_extraction_candidates(self, workspace_id: UUID) -> list[Stage08MemoryExtractionCandidate]: ...
```

Ordering is `created_at DESC, id DESC` in both implementations. SQL lifecycle reads must use `with_for_update()`.

## TDD and verification

1. First add focused `backend/tests/unit/test_stage08_memory_contracts.py` and `backend/tests/integration/test_stage08_memory_postgres.py` tests for model import/contract, JSONB shape, canonical statuses, positive version/confidence, unique source fingerprints, round-trip and lock query.
2. Run those tests before production code. Record the expected import/table/migration failure in `.superpowers/sdd/stage08-package-b-task-b1-report.md`.
3. Implement only enough model/migration/UoW code to pass.
4. Run focused tests and an Alembic-head check. Do not run broad acceptance.
5. Report exact changed files, RED/GREEN commands/results, skipped scope, PostgreSQL availability/evidence and no-external-call statement in the report.

## Non-negotiable safety

- Schema must not introduce raw-text, prompt, response, provider key, Telegram user ID or chain-of-thought columns.
- JSONB constraints validate shape only; do not attempt broad content scanning inside database triggers.
- Do not stage, commit, reset, checkout or clean the dirty worktree.
