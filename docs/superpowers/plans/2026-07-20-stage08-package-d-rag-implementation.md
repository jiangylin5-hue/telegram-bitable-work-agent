# Stage08 Package D RAG and pgvector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不扩大读取权限、不接入外部 embedding Provider 的前提下，实现可重建、可撤销、PostgreSQL 真源的 pgvector 混合检索基础。

**Architecture:** `KnowledgeSource` 保存服务端产生的安全文本投影及版本，`KnowledgeChunk` 保存可删除的切片、关键词和 profile-bound vector。索引请求复用 reference-only outbox；`PostgresRetrievalProvider` 先用结构化过滤/关键词/vector 选候选，再按当前 source、scope、Memory/字段关系重读，最后只返回私有 evidence 与安全 citation。

**Tech Stack:** Python 3.12、FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、PostgreSQL 17+ with pgvector、`pgvector` Python package、既有 `OutboxEvent`、pytest、disposable Docker pgvector database。

## Global Constraints

- 必须完整遵守 `project-docs/08-implementation/decisions/STAGE_08_D_RETRIEVAL_DATA_CONTRACT.md`；C1/C2 D1–D6、Memory 与 Runtime 公共合同不得改变。
- 检索首发为 `PostgresRetrievalProvider`；Milvus、真实 embedding Provider、LLM、Telegram、文件上传/下载、对象存储、Mini App、Coordinator 和外部写入不在范围。
- 任何 source/chunk/embedding/query/citation 必须同时通过 workspace、employee、caller、chat（如有）、relation、field/source validity 的交集；向量命中不是授权。
- 不读取/存储 `Message.raw_text`、`raw_caption`、`normalized_text`、完整群上下文、prompt/response、隐藏字段或 C2 private objects。
- source/chunk 的生命周期变更先同步拒绝读取，再异步 cleanup；outbox payload 仅 reference/hash/version，不含正文。
- 所有 PostgreSQL 用例必须指向专用 disposable pgvector container；native `STAGE06_LOCAL_DATABASE_URL` 缺 `vector` extension，不能作为 D 的通过证据。
- 当前 worktree 是 dirty-safe：不得 stage、commit、reset、checkout、clean 或修改无关变更。每个任务完成后更新自己的 report 与本计划 checkbox，不宣布 Package D 完成。

---

## File Map

| Operation | File | Responsibility |
| --- | --- | --- |
| Create | `backend/docker-compose.stage08-rag.yml` | 专用 `pgvector/pgvector:pg17` disposable integration database，固定本机 55432，不连接现有业务库。 |
| Create | `backend/tests/integration/test_stage08_retrieval_pgvector.py` | Task 0 extension preflight，后续任务在同一模块追加 migration/HNSW/GIN/lifecycle evidence。 |
| Modify | `backend/pyproject.toml` | 加入 `pgvector` SQLAlchemy type dependency，不加入外部模型 SDK。 |
| Create | `backend/app/models/stage08_knowledge.py` | `Stage08KnowledgeSource`、`Stage08KnowledgeChunk` ORM、约束、GIN/HNSW 前置索引 metadata。 |
| Modify | `backend/app/models/__init__.py` | 载入新模型，让 Alembic metadata 可见。 |
| Create | `backend/alembic/versions/20260720_0032_stage08_knowledge_indexing.py` | `vector` extension、source/chunk tables、constraints/indices 和安全 downgrade。 |
| Modify | `backend/app/services/stage06_platform.py` | Protocol、InMemory 与 SQLAlchemy UoW 的 source/chunk/outbox lookup/lock/list 方法。 |
| Create | `backend/app/runtime/stage08_retrieval_contracts.py` | 严格 source projection、scope、chunk/index status、safe view/citation 与 private authority contracts。 |
| Create | `backend/app/services/stage08_retrieval_chunking.py` | canonicalization、hash、CJK/Latin term tokenizer、stable overlap chunking。 |
| Create | `backend/app/services/stage08_retrieval_embeddings.py` | `EmbeddingProvider` protocol、`UnavailableEmbeddingProvider`、test-only deterministic fixed-profile adapter。 |
| Create | `backend/app/services/stage08_retrieval.py` | source registration/versioning, Memory adapter, reference-only outbox, indexing/revoke worker, safe lifecycle services。 |
| Create | `backend/app/services/stage08_retrieval_provider.py` | private authority factory、Postgres hybrid search、post-filter re-read、private evidence renderer。 |
| Create | `backend/app/schemas/stage08_retrieval.py` | 管理 reindex 的极小输入/安全 DTO；不含正文/query/scope/embedding。 |
| Create | `backend/app/api/routes/stage08_retrieval.py` | owner/admin/manager-only reference reindex route，复用 ticket/audit/idempotency。 |
| Modify | `backend/app/main.py` | 只注册管理 reindex route。 |
| Create | `backend/tests/unit/test_stage08_retrieval_contracts.py` | strict DTO/safe view/model-construct/privacy contract corpus。 |
| Create | `backend/tests/unit/test_stage08_retrieval_chunking.py` | deterministic chunk/hash/token/cap corpus。 |
| Create | `backend/tests/unit/test_stage08_retrieval_service.py` | source lifecycle/outbox/index/revoke/Memory adapter corpus。 |
| Create | `backend/tests/unit/test_stage08_retrieval_provider.py` | hybrid candidate/order/authority/post-reread/citation/redaction corpus。 |
| Create | `backend/tests/api/test_stage08_retrieval_api.py` | server-derived actor/input rejection/reindex idempotency/redaction corpus。 |
| Create | `backend/tests/integration/test_stage08_retrieval_pgvector.py` | extension/migration/HNSW/GIN/rebuild/delete/revoke/drift/concurrency evidence。 |
| Create | `project-docs/08-implementation/evidence/stage08-package-d-rag.md` | actual RED/GREEN/PG/static environment evidence。 |
| Create | `.superpowers/sdd/stage08-package-d-task-*.md` | task briefs, reports and independent review records。 |

## Task 0: Disposable pgvector Environment Preflight

**Status:** complete — dedicated `pgvector/pgvector:pg17` container passed independent review with `vector=0.8.5`; unset environment skips explicitly and cannot fall back to default/native database. Container remains deliberately running for D1.

**Files:**
- Create: `backend/docker-compose.stage08-rag.yml`
- Create: `backend/tests/integration/test_stage08_retrieval_pgvector.py`
- Create: `.superpowers/sdd/stage08-package-d-task-d0-brief.md`
- Create: `.superpowers/sdd/stage08-package-d-task-d0-report.md`

**Consumes:** Docker Desktop only; no application database URL.

**Produces:** a local `STAGE08_RAG_DATABASE_URL` with `vector` extension and an evidence-only container profile.

- [ ] **Step 1: Write the environment assertion before composing the container**

```python
def test_stage08_rag_database_has_vector_extension() -> None:
    assert extension_version("vector") is not None
```

The test must use `STAGE08_RAG_DATABASE_URL` only and skip with an explicit environment reason when absent; it must never silently fall back to `DATABASE_URL` or `STAGE06_LOCAL_DATABASE_URL`.

- [ ] **Step 2: Verify RED against the existing native database**

Run: `python -m pytest backend/tests/integration/test_stage08_retrieval_pgvector.py -q`

Expected: skip/fail explaining that `STAGE08_RAG_DATABASE_URL` is absent or `vector` is unavailable. Record the native `pgvector_available=false` preflight result without exposing credentials.

- [ ] **Step 3: Add the isolated compose service**

```yaml
services:
  stage08-rag-postgres:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_DB: stage08_rag_test
      POSTGRES_USER: stage08_rag
      POSTGRES_PASSWORD: stage08_rag
    ports: ["127.0.0.1:55432:5432"]
    tmpfs: ["/var/lib/postgresql/data"]
```

The service must have no bind mount, no default project database name and no published port other than loopback 55432.

- [ ] **Step 4: Start, probe and stop/recreate the disposable service**

Run: `docker compose -f backend/docker-compose.stage08-rag.yml up -d --wait`

Expected: container healthy; `SELECT extversion FROM pg_extension WHERE extname='vector'` returns one version. Store only boolean/version and container lifecycle commands in the report.

- [ ] **Step 5: Record cleanup contract**

Run: `docker compose -f backend/docker-compose.stage08-rag.yml down --volumes`

Expected: test data removed. Do not run this final cleanup while later D PostgreSQL tasks are actively using the service; record when it is executed at package closure.

## Task 1: Strict Retrieval Contracts and pgvector Schema

**Status:** complete — initial review correctly found copied chunk scope/version fields were not source-bound; a composite FK remediation added source-side `UNIQUE (id, workspace_id, content_version)` and exact chunk triple FK. Fresh review PASS with 0 open findings; dedicated pgvector final `62 passed -W error`, downgrade/re-upgrade retains `vector=0.8.5` and final head `20260720_0032`.

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/models/stage08_knowledge.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260720_0032_stage08_knowledge_indexing.py`
- Create: `backend/app/runtime/stage08_retrieval_contracts.py`
- Create: `backend/tests/unit/test_stage08_retrieval_contracts.py`
- Modify: `backend/tests/integration/test_stage08_retrieval_pgvector.py`

**Consumes:** Task 0 pgvector database, C1/C2 safe boundary and D data contract.

**Produces:** ORM/migration and Pydantic contracts with no public text/ID carriers.

- [ ] **Step 1: Write failing strict-contract and migration tests**

```python
def test_retrieval_safe_view_rejects_text_ids_scope_and_embedding() -> None:
    with pytest.raises(ValidationError):
        RetrievalSafeView.model_validate({"status": "indexed", "content": "secret"})

def test_pgvector_migration_creates_extension_and_hnsw_profile_index(stage08_rag_postgres):
    assert stage08_rag_postgres.scalar("SELECT extname='vector' FROM pg_extension WHERE extname='vector'")
    assert "hnsw" in stage08_rag_postgres.index_definition("ix_stage08_knowledge_chunk_hnsw_test_profile")
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest backend/tests/unit/test_stage08_retrieval_contracts.py -q -W error`

Expected: import/contract failures because Package D files do not exist.

- [ ] **Step 3: Add strict models and migration**

Implement exact source statuses `pending|active|replaced|revoked|expired|deleted` and chunk statuses `pending|indexed|stale|deleted|failed`; JSON values must be objects; hash/version/status/uniqueness checks belong in both model/migration. The migration must use `op.execute("CREATE EXTENSION IF NOT EXISTS vector")`, `Vector()` for untyped profile-bound storage, GIN `keyword_terms`, and HNSW expression index limited to `stage08.test-hash-v1` cast to `vector(8)`. Downgrade must drop D tables/indexes but never `DROP EXTENSION vector`.

- [ ] **Step 4: Run GREEN in disposable pgvector PostgreSQL**

Run: `$env:DATABASE_URL=$env:STAGE08_RAG_DATABASE_URL; Push-Location backend; python -m alembic upgrade head; python -m pytest -q tests/unit/test_stage08_retrieval_contracts.py tests/integration/test_stage08_retrieval_pgvector.py; Pop-Location`

Expected: source/chunk constraints, extension and profile HNSW proof pass.

- [ ] **Step 5: Independent review gate**

Review rejects any raw/body/actor/UUID carrier in safe contracts, extension downgrade mistake, missing profile dimension validation or change to C1/C2 schema/API.

## Task 2: Source Projection, Chunking and Reference-only Index Requests

**Status:** completed on 2026-07-20 after two corrective rounds and third independent review (`0 Critical / 0 Important / 0 Minor`; D2 40, D1+D2 96, Memory+D2 124). The remediation reports preserve the lineage/trace audit trail.

**Files:**
- Modify: `backend/app/services/stage06_platform.py`
- Create: `backend/app/services/stage08_retrieval_chunking.py`
- Create: `backend/app/services/stage08_retrieval.py`
- Create: `backend/tests/unit/test_stage08_retrieval_chunking.py`
- Create: `backend/tests/unit/test_stage08_retrieval_service.py`

**Consumes:** Task 1 ORM/strict contracts and existing `Stage08MemoryItem` projection service.

**Produces:** `register_knowledge_source`, `request_knowledge_reindex`, `revoke_knowledge_source` and deterministic source/chunk candidates, all internal only.

- [ ] **Step 1: Write failing source/chunk corpus**

```python
def test_chunker_is_stable_and_never_splits_outside_fixed_overlap() -> None:
    assert chunk_projection("甲" * 1201, profile=TEST_PROFILE)[0].text == "甲" * 1200

def test_memory_adapter_rejects_group_scoped_memory_and_writes_reference_only_outbox() -> None:
    result = register_memory_knowledge_source(...)
    assert "payload" not in result.outbox_payload
    assert "raw_text" not in repr(result)
```

Cover NFC/newline canonicalization, 1,200/200 bounds, CJK/Latin terms, 1,000 chunk and 1,000,000 source caps, hash/version idempotency, `memory_item` current safe projection, group-scoped Memory rejection (never group raw/transport/C2 object or opaque group binding enters RAG), scope mismatch, client-like model construction and source replacement.

- [ ] **Step 2: Run RED**

Run: `python -m pytest backend/tests/unit/test_stage08_retrieval_chunking.py backend/tests/unit/test_stage08_retrieval_service.py -q -W error`

Expected: missing source services and chunker.

- [ ] **Step 3: Implement minimum source lifecycle**

Add UoW methods for add/get/lock/list source/chunk and list chunks by source version in all Protocol/InMemory/SQLAlchemy implementations. `register_knowledge_source` accepts only an internal `KnowledgeSourceProjection` issuer, computes canonical hash and creates a new version rather than overwriting. `request_knowledge_reindex` emits an existing `OutboxEvent` with only source UUID/version/hash/trace reference. `revoke_knowledge_source` locks the source, changes status, clears projection text and makes chunks stale synchronously.

### Task 2 remediation: Memory lineage and trace redaction

真实的 Memory supersession 会创建新 UUID 的 `MemoryItem`，因此 `memory_item` 的 `logical_source_fingerprint` 必须从同 workspace `supersedes_id` 链的根 item 推导，而不是从当前 item ID 推导。新版本注册必须将旧 active/pending source 置为 `replaced`、同步使旧 chunks 不可读并建立幂等 cleanup request。所有 caller trace 先派生 `trace_ref = SHA-256("stage08-knowledge-trace-v1:" + caller_trace_id)`；payload 与 `OutboxEvent.trace_id` 只能保存该摘要，任何原始 trace（包括 body/secret/newline carrier）不得持久化、返回或进入错误文本。回归必须使用真实的新行 Memory supersession path，而非原地递增 version 的测试替身。

每一条 predecessor 还必须与当前 item 具有完全相同的 `memory_type` 和经 `MemoryScopeProjection` 验证、序列化后的完整 scope（包括内部 `identity_token`）。仅同 workspace/递增版本不足以证明同一逻辑身份；任一不一致必须在 source/outbox 创建前 fail closed，防止篡改的 `supersedes_id` 将无关 Memory 链合并并误清理另一 Knowledge source。

- [ ] **Step 4: Run GREEN and no-side-effect audit**

Run: `python -m pytest backend/tests/unit/test_stage08_retrieval_chunking.py backend/tests/unit/test_stage08_retrieval_service.py -q -W error`

Expected: deterministic output; no API, provider, Telegram, raw Message or audit text dependency.

- [ ] **Step 5: Independent review gate**

Review source logical identity/versioning, Memory read-only projection usage, outbox redaction and stale-read-before-cleanup semantics.

## Task 3: Index Worker, Test Embedding and Cleanup State Machine

**Status:** completed on 2026-07-21 after one integrity remediation and fresh independent review (`0 Critical / 0 Important / 0 Minor`; D3 77, D1+D3 133, Memory+D3 161, dedicated pgvector 7). The remediation reports preserve the replay/error-convergence audit trail.

**Files:**
- Create: `backend/app/services/stage08_retrieval_embeddings.py`
- Modify: `backend/app/services/stage08_retrieval.py`
- Modify: `backend/tests/unit/test_stage08_retrieval_service.py`
- Modify: `backend/tests/integration/test_stage08_retrieval_pgvector.py`

**Consumes:** Task 2 source/outbox lifecycle.

**Produces:** `process_knowledge_index_event` and `process_knowledge_cleanup_event`, backed by `EmbeddingProvider` protocol.

- [ ] **Step 1: Write failing index state tests**

```python
def test_index_event_rechecks_locked_source_version_and_is_idempotent() -> None:
    first = process_knowledge_index_event(uow, event, provider=TestHashEmbeddingProvider())
    second = process_knowledge_index_event(uow, event, provider=TestHashEmbeddingProvider())
    assert first.indexed_chunk_count == second.indexed_chunk_count

def test_revoke_before_worker_runs_creates_no_readable_chunk() -> None:
    revoke_knowledge_source(...)
    assert process_knowledge_index_event(...).status == "discarded"
```

Cover source/hash/profile mismatch, partial chunk failure, failure status with no partial read, replacement/revoke/expiry/delete cleanup, event replay, lock contention, no external provider and chunk/projection scrubbing.

- [ ] **Step 2: Run RED**

Run: `python -m pytest backend/tests/unit/test_stage08_retrieval_service.py -q -W error`

Expected: missing worker/provider symbols.

- [ ] **Step 3: Implement fixed-profile providers and worker**

`UnavailableEmbeddingProvider` must raise a fixed internal availability code before any row write. `TestHashEmbeddingProvider` must be clearly test-only, emit exactly eight finite floats and never be selected by default runtime configuration. Worker locks source, rereads source status/version/hash, chunks, creates profile-bound rows atomically, and only marks indexed after all chunks succeed. Cleanup clears `chunk_text`, `keyword_terms`, embedding and marks `stale/deleted` before/with event completion.

- [ ] **Step 4: Prove real pgvector lifecycle**

Run: `$env:DATABASE_URL=$env:STAGE08_RAG_DATABASE_URL; Push-Location backend; python -m pytest -q tests/integration/test_stage08_retrieval_pgvector.py; Pop-Location`

Expected: actual vector values, HNSW profile index, GIN term index, replay/idempotency and cleanup/read-deny evidence pass on pgvector.

- [ ] **Step 5: Independent review gate**

Review tests cannot select hash provider in runtime defaults, all cleanup is fail-closed, source locks protect version/revoke races, and no body enters outbox/audit/error strings.

## Task 4: Private Authority, Hybrid Search and Safe Citations

**Files:**
- Create: `backend/app/services/stage08_retrieval_provider.py`
- Modify: `backend/app/runtime/stage08_retrieval_contracts.py`
- Create: `backend/tests/unit/test_stage08_retrieval_provider.py`
- Modify: `backend/tests/integration/test_stage08_retrieval_pgvector.py`

**Consumes:** indexed sources/chunks, existing Actor/employee/scope/Mem​ory read-only services.

**Produces:** opaque `Stage08RetrievalAuthorityFactory`, `PostgresRetrievalProvider.search`, private evidence and safe citation view.

- [ ] **Step 1: Write failing retrieval security corpus**

```python
def test_search_prefilters_then_rereads_and_drops_revoked_source() -> None:
    hits = provider.search(uow, authority, query="报价", limit=12, now=NOW)
    revoke_knowledge_source(...)
    assert provider.render_private_evidence(uow, hits, now=NOW) is None

def test_citation_never_exposes_source_chunk_record_field_or_score_ids() -> None:
    rendered = provider.safe_citations(...)
    assert "00000000-" not in repr(rendered)
```

Cover workspace/employee/caller/customer/project/chat mismatch, field/relation drift, Memory `read_only` drift, deleted/replaced source, profile mismatch, keyword-only explicit degradation, vector/keyword deterministic tie order, 12-chunk cap, forged authority and no raw `Message` import.

- [ ] **Step 2: Run RED**

Run: `python -m pytest backend/tests/unit/test_stage08_retrieval_provider.py -q -W error`

Expected: missing provider/authority.

- [ ] **Step 3: Implement current-state search**

Make `Stage08RetrievalAuthorityFactory` the sole constructor for a slots-only opaque authority. Search applies structured PostgreSQL filters first, combines normalized keyword/vector scores only for the fixed profile, then rereads each source with current actor/employee/scope and source-specific verifier. `memory_item` must call the existing read-only Memory projection; unavailable real embeddings return an explicit internal `keyword_only` degradation, not invented vector result. Evidence/chunk text remains private; citations contain only display ordinal/label/source-type/scope category.

- [ ] **Step 4: Run GREEN and drift regression**

Run: `python -m pytest backend/tests/unit/test_stage08_retrieval_provider.py backend/tests/unit/test_stage08_retrieval_service.py -q -W error`

Expected: all stale/revoked/forged cases return no evidence; direct eligible cases retain only current content.

- [ ] **Step 5: Independent review gate**

Review prefilter is never mistaken for authorization, hybrid scoring cannot leak unavailable candidates, citations/errors/repr are safe, and Package E/LLM/RAG handoff has not been prematurely implemented.

## Task 5: Controlled Reindex API and PostgreSQL Package Evidence

**Files:**
- Modify: `backend/app/services/stage08_retrieval.py`
- Create: `backend/app/schemas/stage08_retrieval.py`
- Create: `backend/app/api/routes/stage08_retrieval.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/api/test_stage08_retrieval_api.py`
- Modify: `backend/tests/unit/test_stage08_retrieval_service.py`
- Modify: `backend/tests/integration/test_stage08_retrieval_pgvector.py`
- Create: `project-docs/08-implementation/evidence/stage08-package-d-rag.md`
- Create: `.superpowers/sdd/stage08-package-d-task-d5-report.md`

**Consumes:** service-only reindex event and existing verified API identity, workspace membership, ticket/idempotency/audit boundaries.

**Produces:** management-only reference reindex endpoint and Package D PostgreSQL evidence.

- [ ] **Step 1: Write failing API and final PostgreSQL tests**

```python
def test_reindex_rejects_client_projection_scope_embedding_and_query(client) -> None:
    response = client.post("/api/stage08/knowledge/reindex", json={"projection_text": "secret"})
    assert response.status_code == 422

def test_reindex_owner_creates_reference_only_idempotent_event(client) -> None:
    response = client.post(...)
    assert set(response.json()) == {"ticket_id", "status"}
```

Cover non-owner/non-admin manager behavior exactly as approved policy, stale source selector, same/different idempotency fingerprints, audit/DTO redaction, extension upgrade/downgrade, HNSW filter recall baseline, worker cleanup race and no external network call.

- [ ] **Step 2: Run RED**

Run: `python -m pytest backend/tests/api/test_stage08_retrieval_api.py -q -W error`

Expected: missing route/schema.

- [ ] **Step 3: Implement the narrow route**

Accept only typed `workspace_id`, server-validated `knowledge_source_id`, `idempotency_key`, and `trace_id`; derive actor and permission server-side using existing owner/admin/manager rules, call service, create the existing ticket/audit reference and return no source/chunk/body/query/scope/embedding content. Register the router only after tests prove anonymous/client-derived input denial.

- [ ] **Step 4: Run complete Package D evidence**

Run:

```powershell
$originalDatabaseUrl = $env:DATABASE_URL
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL
Push-Location backend
python -m alembic upgrade head
python -m alembic heads
python -m pytest -q tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py tests/unit/test_stage08_retrieval_provider.py tests/api/test_stage08_retrieval_api.py tests/integration/test_stage08_retrieval_pgvector.py
$exitCode = $LASTEXITCODE
Pop-Location
$env:DATABASE_URL = $originalDatabaseUrl
exit $exitCode
```

Expected: one head, real pgvector D suite passes, no skips counted as pass. Also run `python -m compileall -q backend/app/models/stage08_knowledge.py backend/app/runtime/stage08_retrieval_contracts.py backend/app/services/stage08_retrieval_chunking.py backend/app/services/stage08_retrieval_embeddings.py backend/app/services/stage08_retrieval.py backend/app/services/stage08_retrieval_provider.py`, production privacy/external scans and `git diff --check`.

- [ ] **Step 5: Independent package review**

Review D-01–D-04, migration downgrade, source/chunk lifecycle, pre/post authorization, citations, outbox redaction, HNSW/GIN proof, keyword-only degradation, Docker cleanup and the explicit absence of Milvus/real provider/Telegram. Only then update Stage08 source/plan/acceptance docs to close Package D and hand off to Package E.

## Plan Self-Review

- **Spec coverage:** Tasks 1–2 implement source/chunk/version/projection; Task 3 implements index/reindex/delete/revoke worker and profile handling; Task 4 implements hybrid retrieval, pre/post authorization and citations; Task 5 implements controlled API and D-01–D-04 package evidence.
- **No-placeholder scan:** every task names concrete files, symbols, tests, RED/GREEN commands and expected outcomes. No task is allowed to select a real provider or Milvus.
- **Type consistency:** source/chunk statuses, `KnowledgeSourceProjection`, `EmbeddingProvider`, `PostgresRetrievalProvider`, `Stage08RetrievalAuthorityFactory` and reindex lifecycle names are identical to the data contract and are produced before their consumers.

## Execution Handoff

This plan is ready for task-by-task subagent-driven execution after the Docker pgvector preflight succeeds. Each task needs a fresh independent review. Do not start Task 1 if Task 0 cannot prove `vector` in the dedicated disposable database.
