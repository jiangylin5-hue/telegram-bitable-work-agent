# Stage12-D Retrieval, Embedding and Chunk V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a permission-preserving three-layer retrieval index and objective-specific hybrid retrieval pipeline that improves fuzzy schema/entity/non-structured recall while leaving exact table facts, joins and aggregates under Stage12-C deterministic Query Engine authority.

**Architecture:** Stage12-D adds versioned schema/record/relation projections, one-record canonical chunks, a fixed-dimension pgvector profile, objective/table-bounded hybrid retrieval and a typed `EvidenceBundleV2`. Projection and embedding run after commit through the transactional outbox; revoke/permission contraction wins synchronously over asynchronous rebuild. Stage11 V1 remains the only production dispatch authority and D is observed only through a default-off workspace allowlisted shadow.

**Tech Stack:** Python 3.12+, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL 16 + pgvector 0.8.3, `httpx`, Hugging Face BGE-M3 tokenizer/runtime for the local benchmark candidate, OpenRouter-compatible embeddings API for the remote benchmark candidate, pytest.

## Current Execution Status

- Stage12-A/B/C: accepted locally; D may consume their frozen truth, `TaskSpecV2`, authorized schema snapshots and `StructuredQueryResultV1` but may not change their contracts silently.
- Source audit: Stage08 stores an unbounded `Vector()` column and only creates an HNSW expression index for `stage08.test-hash-v1` at 8 dimensions. Runtime defaults to `UnavailableEmbeddingProvider`; this is test infrastructure, not a production profile.
- Candidate decision proposed, not yet approved: compare local `BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181`, remote OpenRouter `baai/bge-m3` with observed canonical slug `baai/bge-m3-20251117`, and remote OpenRouter `intfloat/multilingual-e5-large` with observed canonical slug `intfloat/multilingual-e5-large-20251117`. All use 1024 dimensions, L2 normalization, cosine distance and the same focused Chinese retrieval corpus. The second remote model is a quality challenger; local/remote BGE-M3 isolates hosting latency, cost and residency.
- Remote benchmark: the key was loaded transiently from the ignored local Stage05 workflow env without logging it. Both OpenRouter candidates received real synthetic-only calls; final fixed-boundary results are recorded in the Stage12-D profile evidence.
- Confirmation gate: do not add the production fixed-dimension vector table, production runtime dependency or provider configuration until the user confirms the candidate/profile boundary. After measured results, record the winning profile in `TECHNICAL_DECISIONS.md` and obtain confirmation before activation.
- Task 1: implemented by RED/GREEN on 2026-07-29; strict contracts and the 12-case focused corpus pass `9` tests.
- Task 2: implemented by RED/GREEN on 2026-07-29; canonical schema/record/long-field/relation projections and Task 1 compatibility pass `13` tests.
- Task 3: implemented by RED/GREEN on 2026-07-29; strict local/remote adapters, BGE-M3 bridge, fixed named-profile CLI, POST response identity enforcement, warm-up/failure handling and sanitized report runner bring the D focused suite to `35 passed`.
- Task 4: remote BGE-M3 passed the real fixed-boundary benchmark; remote E5 failed the 20-second hard gate. Local BGE-M3 remains unmeasured because its pinned weight transfer stalled after runtime preparation. The user explicitly accepted TDR-018 on 2026-07-29; Task 5 fixed `vector(1024)` implementation is authorized, while deployment/activation/real-workspace external embedding remain closed.
- Tasks 5–8: implemented and verified locally. Final D evidence is `91 passed` focused, `2 passed` real C+D PostgreSQL integration, `1906 passed` unit/API and `2005 passed, 134 skipped` full backend under the documented historical four-file boundary. The real synthetic-only OpenRouter diagnostic completed `1/1` with Recall@20 `1.0`, MRR@20 `0.9583333333`, forbidden `0`, P95 `2498.3266 ms` and zero Action expansion, record write or external send. Stage12-D is accepted locally but remains undeployed, default-off and unable to alter V1 dispatch.

## Global Constraints

- Stage12-D only: do not implement typed Specialist handlers, answer Provider V2, durable Action expansion, Mini App changes, public API/SSE changes, deployment, Telegram send or business writes.
- Embedding is limited to fuzzy schema/entity aliases, authorized non-structured text recall and reranking. It must never decide exact identifiers, permissions, typed predicates, joins, counts, groups, sums or action targets.
- Projection input is the intersection `agent scope -> caller scope -> chat/view scope`; hidden/sensitive fields never enter canonical text, hash, chunk, vector, benchmark trace or error detail.
- Embeddings are derived sensitive data. Every source, chunk, vector and relation edge carries workspace/table/field scope and a visibility-profile hash; retrieval revalidates current authority before evidence release.
- Exact identifier candidates occupy a separate priority band and cannot be removed by semantic Top K.
- Default budgets are 20 primary candidates per objective, 10 linked edges per primary record and 24 compact evidence nodes. A truncated retrieval result sets `truncated=true` and cannot support “全部/唯一/精确总数” unless a complete Stage12-C QueryResult supplies that fact.
- The Stage12-A 48-case truth remains `agent_audited_pending_human_signoff`. D uses a focused deterministic retrieval slice and does not run the 48-case × 3 real-LLM campaign.
- Stage11 V1 remains the only dispatch authority. D shadow is `off` by default, workspace allowlisted and unable to alter HTTP/SSE bytes, answer text, action candidates, records or sends.
- Provider calls use synthetic evaluation data during benchmark. Real workspace data may not leave the machine until the winning profile and data policy are explicitly accepted.
- The repository's one-final-commit rule overrides generic per-task commit examples; do not create intermediate commits.

---

## File Map

| File | Responsibility |
| --- | --- |
| `backend/app/schemas/retrieval_v2.py` | Strict embedding profile, projection, candidate, score, relation and `EvidenceBundleV2` contracts |
| `backend/app/services/retrieval_v2_projection.py` | Canonical schema/record/field/relation projection and token-aware chunk construction |
| `backend/app/services/retrieval_v2_embeddings.py` | Validated embedding provider protocol, local benchmark adapter and OpenRouter remote adapter |
| `backend/app/services/retrieval_v2_indexing.py` | Versioned projection/outbox processing, active-version switch, revoke-first cleanup and rollback |
| `backend/app/services/retrieval_v2_hybrid.py` | Exact/keyword/semantic/link expansion, quotas, component scores and stable rerank |
| `backend/app/services/retrieval_v2_evidence.py` | EvidenceBundle assembly, token/node budget, citation identity, completeness and truncation |
| `backend/app/services/retrieval_v2_shadow.py` | Default-off/allowlisted sanitized V1/V2 candidate comparison |
| `backend/app/models/stage12_retrieval.py` | Profile, source, fixed-dimension chunk/vector and relation-edge persistence |
| `backend/app/models/__init__.py` | Register Stage12-D metadata |
| `backend/alembic/versions/20260729_0035_stage12_retrieval_v2.py` | Additive fixed-dimension pgvector and three-layer index migration after profile confirmation |
| `backend/app/core/config.py` | D off/shadow mode, allowlist, profile/provider/timeouts and strict production validation |
| `backend/app/services/stage06_platform.py` | Emit reference-only projection events after authorized schema/record/link commits |
| `backend/app/api/routes/agent_runs.py` | Invoke sanitized D shadow only behind B/C/D gates without response changes |
| `backend/scripts/stage12_retrieval_benchmark.py` | Same-corpus profile benchmark; emits hashes and metrics, never raw vectors or secrets |
| `backend/scripts/stage12_retrieval_v2_evaluation.py` | Focused deterministic D diagnostic and safety counters |
| `backend/tests/fixtures/stage12_retrieval_benchmark_v2.json` | Frozen schema/entity/non-structured retrieval corpus with relevant/forbidden candidate IDs |
| `backend/tests/unit/test_retrieval_v2_contracts.py` | Strict contract, hash and budget tests |
| `backend/tests/unit/test_retrieval_v2_projection.py` | Canonical text/chunk/data-minimization tests |
| `backend/tests/unit/test_retrieval_v2_embeddings.py` | Adapter, dimension, finite-value, normalization, timeout and redaction tests |
| `backend/tests/unit/test_retrieval_v2_indexing.py` | Outbox, version switch, replay, revoke, failure and rollback tests |
| `backend/tests/unit/test_retrieval_v2_hybrid.py` | Exact band, quotas, component scores, link expansion and stable rank tests |
| `backend/tests/unit/test_retrieval_v2_evidence.py` | Evidence/citation/completeness/truncation tests |
| `backend/tests/unit/test_retrieval_v2_shadow.py` | Default-off, allowlist, sanitization and V1 authority tests |
| `backend/tests/integration/test_stage12_retrieval_v2_postgres.py` | Real PostgreSQL/pgvector persistence, HNSW, permission drift and atomic switch tests |
| `backend/tests/unit/test_stage12_retrieval_benchmark.py` | Corpus freeze, Gold-leak, output and metric tests |
| `backend/tests/unit/test_stage12_retrieval_v2_evaluation.py` | Diagnostic exactness and zero-effect tests |
| `project-docs/00-governance/TECHNICAL_DECISIONS.md` | Winning production embedding profile and rejected alternative evidence |
| `project-docs/08-implementation/STAGE_12_D_RETRIEVAL_EMBEDDING_ACCEPTANCE.md` | D gate-by-gate acceptance record |
| `project-docs/08-implementation/evidence/stage12-d-retrieval-embedding-2026-07-29.{md,json}` | Human/machine-readable D evidence |

### Task 1: Freeze strict Retrieval V2 contracts and the focused corpus

**Files:**
- Create: `backend/app/schemas/retrieval_v2.py`
- Create: `backend/tests/fixtures/stage12_retrieval_benchmark_v2.json`
- Create: `backend/tests/unit/test_retrieval_v2_contracts.py`
- Create: `backend/tests/unit/test_stage12_retrieval_benchmark.py`

**Interfaces:**
- Consumes: Stage12-A case IDs/query text, Stage12-B objective IDs/table and field bindings, Stage12-C result/evidence references.
- Produces: `EmbeddingProfileV1`, `RetrievalProjectionV2`, `RetrievalChunkV2`, `RetrievalRequestV2`, `RetrievalCandidateV2`, `RetrievalRelationV2`, `EvidenceNodeV2`, `EvidenceBundleV2` and `canonical_retrieval_sha256()`.

- [x] **Step 1: Write RED contract tests**

  Require strict/frozen models, exact version literals, UUID identity, SHA-256 hashes, unique candidate/evidence IDs, finite component scores in `[0,1]`, one exact priority band, `complete != truncated`, maximum 20 primary candidates, maximum 10 relation expansions per primary and maximum 24 evidence nodes. Reject arbitrary SQL, provider-created record IDs, hidden field carriers and vectors in evidence output.

  ```python
  def test_evidence_bundle_rejects_vector_payload() -> None:
      payload = _valid_evidence_bundle_payload()
      payload["nodes"][0]["embedding"] = [0.1, 0.2]
      with pytest.raises(ValidationError):
          EvidenceBundleV2.model_validate(payload)


  def test_truncated_bundle_cannot_be_complete() -> None:
      with pytest.raises(ValidationError, match="retrieval_completeness_invalid"):
          EvidenceBundleV2.model_validate(
              {**_valid_evidence_bundle_payload(), "complete": True, "truncated": True}
          )
  ```

- [x] **Step 2: Run tests and verify RED**

  Run: `python -m pytest -q tests/unit/test_retrieval_v2_contracts.py tests/unit/test_stage12_retrieval_benchmark.py`

  Expected: FAIL because the V2 contracts and corpus do not exist.

- [x] **Step 3: Implement the contracts and freeze the corpus**

  The corpus is generated once from the audited Stage12 fixture and checked in. Include only queries whose semantic/schema relevance is measurable without Provider interpretation: no exact record code in the query, at least one relevant schema/record candidate, and an explicit forbidden decoy. Store candidate IDs and canonical texts from synthetic fixture data, never production text. Split metrics into `schema`, `entity_alias` and `non_structured` categories.

  ```python
  class EmbeddingProfileV1(_StrictFrozenModel):
      version: Literal["embedding-profile.v1"]
      profile_name: NonEmptyStr
      model_revision: NonEmptyStr
      dimension: StrictInt
      normalization: Literal["l2"]
      distance_metric: Literal["cosine"]
      max_input_tokens: StrictInt
      batch_size: StrictInt
      provider_location: Literal["local", "remote"]
      data_residency: NonEmptyStr


  class EvidenceBundleV2(_StrictFrozenModel):
      version: Literal["evidence-bundle.v2"]
      objective_id: NonEmptyStr
      query_result_ref: NonEmptyStr | None
      nodes: tuple[EvidenceNodeV2, ...] = Field(max_length=24)
      relations: tuple[RetrievalRelationV2, ...]
      scope_hash: Sha256Hex
      complete: StrictBool
      truncated: StrictBool
      bundle_hash: Sha256Hex
  ```

- [x] **Step 4: Run contract/corpus tests and verify GREEN**

  Run: `python -m pytest -q tests/unit/test_retrieval_v2_contracts.py tests/unit/test_stage12_retrieval_benchmark.py`

  Expected: PASS and the corpus hash is stable across two loads.

### Task 2: Implement canonical schema, record, long-field and relation projections

**Files:**
- Create: `backend/app/services/retrieval_v2_projection.py`
- Create: `backend/tests/unit/test_retrieval_v2_projection.py`

**Interfaces:**
- Consumes: `AuthorizedSchemaSnapshot`, `AuthorizedRecord`, visible field IDs, `AuthorizedRelationSpec`, source versions and a `TokenCounter`.
- Produces: `build_schema_projections(snapshot)`, `build_record_projection(snapshot, record)`, `build_relation_projections(snapshot, records, catalog)` and `chunk_projection(projection, token_counter, max_tokens)`.

- [x] **Step 1: Write RED data-minimization and chunk tests**

  Cover stable schema-position ordering, Unicode NFC, table/record headers, enum descriptions, aliases, one canonical record per source, separate long-field chunks, no cross-record overlap, parent record/field identity, exact token offsets, content hash stability and relation direction/version/scope proof. Verify hidden UUID/internal audit fields and an explicit sensitive field never appear in text, hashes derived from text, keyword terms or chunk metadata.

- [x] **Step 2: Run projection tests and verify RED**

  Run: `python -m pytest -q tests/unit/test_retrieval_v2_projection.py`

  Expected: FAIL because projection builders do not exist.

- [x] **Step 3: Implement pure canonical projection functions**

  ```python
  class TokenCounter(Protocol):
      def encode(self, text: str) -> tuple[int, ...]: ...
      def decode(self, token_ids: tuple[int, ...]) -> str: ...


  def build_record_projection(
      snapshot: AuthorizedSchemaSnapshot,
      record: AuthorizedRecord,
      *,
      visible_field_ids: frozenset[UUID],
  ) -> RetrievalProjectionV2: ...


  def chunk_projection(
      projection: RetrievalProjectionV2,
      *,
      token_counter: TokenCounter,
      max_tokens: int,
      overlap_tokens: int = 32,
  ) -> tuple[RetrievalChunkV2, ...]: ...
  ```

  Canonical record text follows `[table]`, `[record]` and visible schema-position field lines. Long-field overlap stays inside that field only. Relation edges remain structured and are not turned into large prose chunks.

- [x] **Step 4: Run projection tests and verify GREEN**

  Run: `python -m pytest -q tests/unit/test_retrieval_v2_projection.py`

  Expected: PASS with zero hidden-field marker matches.

### Task 3: Implement validated local and remote embedding adapters plus benchmark runner

**Files:**
- Create: `backend/app/services/retrieval_v2_embeddings.py`
- Create: `backend/scripts/stage12_retrieval_benchmark.py`
- Create: `backend/tests/unit/test_retrieval_v2_embeddings.py`
- Modify: `backend/pyproject.toml` only after candidate-boundary confirmation

**Interfaces:**
- Consumes: `EmbeddingProfileV1`, batches of canonical synthetic text and an injected `httpx.Client`/local encoder.
- Produces: `EmbeddingProviderV2.embed_documents()`, `EmbeddingProviderV2.embed_queries()`, `LocalBgeM3EmbeddingProvider`, `OpenRouterEmbeddingProvider`, `run_retrieval_profile_benchmark()` and sanitized `RetrievalProfileBenchmarkReport`.

- [x] **Step 1: Write RED adapter tests**

  Test document/query encoding separation, input count/order, batch limits, 1024 dimensions, float32 finite values, L2 normalization, timeout, 401/402/429/5xx mapping, unexpected model/revision refusal, no fallback provider, redacted exceptions and no API key/text/vector in report JSON.

- [x] **Step 2: Run adapter tests and verify RED**

  Run: `python -m pytest -q tests/unit/test_retrieval_v2_embeddings.py`

  Expected: FAIL because adapters do not exist.

- [x] **Step 3: Implement the provider protocol and adapters**

  ```python
  class EmbeddingProviderV2(Protocol):
      profile: EmbeddingProfileV1

      def embed_documents(
          self, texts: tuple[str, ...]
      ) -> tuple[tuple[float, ...], ...]: ...

      def embed_queries(
          self, texts: tuple[str, ...]
      ) -> tuple[tuple[float, ...], ...]: ...
  ```

  Local candidate: `BAAI/bge-m3` at revision `5617a9f61b028005a4858fdac845db406aefb181`, dense vectors only, 1024 dimensions, CPU benchmark mode. Remote candidates use OpenRouter `/embeddings`: request `baai/bge-m3` and validate canonical slug `baai/bge-m3-20251117`; request `intfloat/multilingual-e5-large` and validate canonical slug `intfloat/multilingual-e5-large-20251117`, with `query: ` / `passage: ` prefixes and a 384-token projection cap below its 512-token model limit. Both remote routes set `data_collection="deny"`, `zdr=true`, `allow_fallbacks=false` and a 20-second timeout. Normalize and validate every vector after float32 conversion.

- [x] **Step 4: Implement the sanitized benchmark runner**

  For each profile, warm up once, then run the same frozen corpus three times. Calculate category and overall Recall@20, MRR@20, forbidden-candidate rate, mean/P95 batch latency, estimated request cost, corpus/profile hashes and failure counts. Do not persist raw vectors, keys or input text.

- [x] **Step 5: Run unit tests and verify GREEN**

  Run: `python -m pytest -q tests/unit/test_retrieval_v2_embeddings.py tests/unit/test_stage12_retrieval_benchmark.py`

  Expected: PASS using injected deterministic/fake providers; this does not count as the real profile benchmark.

### Task 4: Execute the real focused profile benchmark and freeze the Technical Decision

**Files:**
- Modify: `project-docs/00-governance/TECHNICAL_DECISIONS.md`
- Create: `project-docs/08-implementation/evidence/stage12-d-embedding-profile-benchmark-2026-07-29.md`
- Create: `project-docs/08-implementation/evidence/stage12-d-embedding-profile-benchmark-2026-07-29.json`

**Interfaces:**
- Consumes: frozen corpus, local candidate runtime and configured `OPENROUTER_API_KEY`.
- Produces: one measured recommendation with exact `profile_name`, `model_revision`, `dimension`, `normalization`, `distance_metric`, `max_input_tokens`, `batch_size`, `provider_location` and `data_residency`.

- [x] **Step 1: Verify prerequisites without exposing credentials**

  Confirm the corpus hash, local disk/RAM budget, pgvector version, key presence and OpenRouter catalog canonical slug. Abort before any request if the key is absent or the remote revision changed.

- [ ] **Step 2: Run the same-corpus local and remote benchmark**

  Run from `backend`:

  ```powershell
  $stage12DTemp = Join-Path ([System.IO.Path]::GetTempPath()) 'stage12-d-embedding-benchmark'
  New-Item -ItemType Directory -Force -Path $stage12DTemp
  python -m scripts.stage12_retrieval_benchmark --profile local-bge-m3 --rounds 3 --output-json (Join-Path $stage12DTemp 'local-bge-m3.json')
  python -m scripts.stage12_retrieval_benchmark --profile openrouter-bge-m3 --rounds 3 --output-json (Join-Path $stage12DTemp 'openrouter-bge-m3.json')
  python -m scripts.stage12_retrieval_benchmark --profile openrouter-multilingual-e5-large --rounds 3 --output-json (Join-Path $stage12DTemp 'openrouter-multilingual-e5-large.json')
  ```

  Expected: all three reports have the same corpus hash, `dimension=1024`, zero forbidden candidates and three completed rounds. Temporary output paths must be inside an explicit task temp directory and removed after evidence is sanitized.

- [x] **Step 3: Apply the approved weighted decision**

  Score Chinese Recall@20 30%, schema matching 15%, P95 15%, data residency/privacy 15%, cost 10%, operations 10% and revision pinning 5%. A profile cannot win if any hard gate fails: Recall@20 regression versus keyword baseline, forbidden candidate, dimension/revision drift, non-finite vector, data policy mismatch or failed round.

- [x] **Step 4: Pause for user confirmation before schema/runtime selection**

  Present the measured table, recommended profile and trade-off. Do not create migration `0035`, add a production runtime dependency or enable provider configuration until confirmed.

### Task 5: Add fixed-dimension, versioned schema/record/relation persistence

**Files:**
- Create: `backend/app/models/stage12_retrieval.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260729_0035_stage12_retrieval_v2.py`
- Create: `backend/tests/integration/test_stage12_retrieval_v2_postgres.py`

**Interfaces:**
- Consumes: user-confirmed production profile and 1024-dimensional normalized embeddings.
- Produces: `Stage12RetrievalProfile`, `Stage12RetrievalSource`, `Stage12RetrievalChunk`, `Stage12RelationEdge` and one partial HNSW cosine index for the approved active profile.

- [x] **Step 1: Write RED PostgreSQL model/migration tests**

  Assert one Alembic head, `vector(1024)` typmod, profile/source/version uniqueness, active-version uniqueness, FK workspace/source/version integrity, relation endpoint/version/scope constraints, partial HNSW cosine index predicate, rollback without Stage08 table mutation and rejection of 8/1536-dimensional vectors.

- [x] **Step 2: Run PostgreSQL tests and verify RED**

  Run: `python -m pytest -q -m postgres tests/integration/test_stage12_retrieval_v2_postgres.py`

  Expected: FAIL because the models/migration do not exist.

- [x] **Step 3: Implement additive models and migration**

  Do not alter or reinterpret Stage08 vectors. Persist source type, source identity/version, table/record/field identities, visibility-profile hash, scope hash, content hash, profile/revision and lifecycle state. `Stage12RetrievalChunk.embedding` is exactly `Vector(1024)`. The HNSW index is partial on indexed, non-revoked rows for the confirmed profile.

- [x] **Step 4: Run migration/model tests and verify GREEN**

  Run: `python -m alembic heads` and `python -m pytest -q -m postgres tests/integration/test_stage12_retrieval_v2_postgres.py`

  Expected: one head `20260729_0035`; all D PostgreSQL tests pass inside rollback transactions.

  Verified 2026-07-29: `python -m alembic heads` reports one head
  `20260729_0035`; the disposable local PostgreSQL integration test passes
  `1/1`, including upgrade, typmod/index/constraint checks, invalid dimension
  rejection, downgrade isolation and re-upgrade.

### Task 6: Implement outbox indexing, atomic activation, revoke-first cleanup and rollback

**Current status (2026-07-30):** completed locally. TDR-019 was explicitly confirmed and implemented as a default-off, workspace-allowlisted two-stage mutation/projection outbox. Lifecycle and security tests pass `22/22`; the complete D focused suite through Task6 passes `60/60`, including the real disposable local PostgreSQL migration/indexing/mutation test. Deployment, activation and real-workspace external embedding remain closed.

**Files:**
- Create: `backend/app/services/retrieval_v2_indexing.py`
- Modify: `backend/app/services/stage06_platform.py`
- Create: `backend/tests/unit/test_retrieval_v2_indexing.py`
- Extend: `backend/tests/integration/test_stage12_retrieval_v2_postgres.py`

**Interfaces:**
- Consumes: reference-only `stage12.retrieval_projection.requested` and `stage12.retrieval_projection.revoked` outbox events.
- Produces: `request_retrieval_projection()`, `process_retrieval_projection_event()`, `revoke_retrieval_source()`, `activate_retrieval_source_version()` and `rollback_retrieval_profile()`.

- [x] **Step 1: Write RED lifecycle tests**

  Cover post-commit event references only, idempotent replay, stale event refusal, current authorized source reread, provider failure retaining old active version, dimension/profile drift failure, content-hash no-op, atomic new-version switch, permission contraction/revoke hiding old chunks before rebuild and rollback to the previous profile/version.

- [x] **Step 2: Run indexing tests and verify RED**

  Run: `python -m pytest -q tests/unit/test_retrieval_v2_indexing.py`

  Expected: FAIL because indexing lifecycle functions do not exist.

- [x] **Step 3: Implement reference-only outbox and lifecycle processing**

  Record/schema/link mutation transactions emit IDs, source version/hash and trace ID only. The worker re-reads current authorized state, builds projections, embeds batches, validates output, inserts a pending version and atomically activates it. Revoke/permission contraction marks sources unavailable synchronously before asynchronous vector deletion.

  Accepted TDR-019 refinement: Stage06 emits a generic reference-only
  `stage12.retrieval_source.changed`; an authorization-aware coordinator performs
  per-profile rereads and then emits the existing
  `stage12.retrieval_projection.requested`. This refinement is documentation-only
  after the authorization-aware reread. User confirmed this internal contract
  on 2026-07-30; implement and verify it before closing Step 3.

  Verified 2026-07-30: Stage06 table/field/record/link and field-permission
  mutations emit only when the workspace is explicitly allowlisted. Generic
  events carry references/version/hashed trace only; the authorization-aware
  fan-out accepts only materialized or explicitly registered visibility/scope
  profiles. Permission contraction revokes affected sources/chunks before
  rebuild events. Both event stages reject forged aggregate/source identities
  before authorized reads.

- [x] **Step 4: Run unit and PostgreSQL lifecycle tests**

  Run: `python -m pytest -q tests/unit/test_retrieval_v2_indexing.py tests/integration/test_stage12_retrieval_v2_postgres.py` with `STAGE06_LOCAL_DATABASE_URL` pointing to the explicitly disposable local Stage12 database.

  Expected: PASS; failed embedding attempts leave the prior active version retrievable and no partial active version exists.

  Verified 2026-07-30: lifecycle/security unit tests pass `22/22`; the
  PostgreSQL integration test passes `1/1`; the complete focused D suite through
  Task6 passes `60/60`. Stage06/Stage07 mutation regression passes `58/58`,
  unit+API passes `1888/1888`, and the full backend under the same four-file
  historical PostgreSQL exclusion boundary passes `1987`, with `134` existing
  environment-gated skips. `compileall` passes and Alembic has one head
  `20260729_0035`.

### Task 7: Implement objective-specific hybrid retrieval and EvidenceBundle assembly

**Current status (2026-07-30):** implemented and verified locally. The RED run failed because both services were absent; the GREEN Task7 suite passes `9/9`. The complete D unit set through Task7 passes `68/68`, the real disposable PostgreSQL D integration passes `1/1`, and the focused Stage12-C aggregate/query compatibility set passes `38/38`. No shadow, dispatch, deployment or real-workspace external embedding was enabled.

**Files:**
- Create: `backend/app/services/retrieval_v2_hybrid.py`
- Create: `backend/app/services/retrieval_v2_evidence.py`
- Create: `backend/tests/unit/test_retrieval_v2_hybrid.py`
- Create: `backend/tests/unit/test_retrieval_v2_evidence.py`

**Interfaces:**
- Consumes: one `RetrievalRequestV2`, current authorized context, exact entity results, Stage12-C query result reference, active index profile and structured relation edges.
- Produces: `retrieve_authorized_candidates()` and `assemble_evidence_bundle()`.

- [x] **Step 1: Write RED hybrid retrieval tests**

  Verify exact-ID band survives zero semantic similarity, hard workspace/table/field filters happen before scoring, unauthorized semantic hits never enter memory, schema and record quotas are objective-specific, relation candidates enter only through verified edges, 20/10/24 budgets are enforced, component scores/reasons are persisted, stable tie-breaking uses source identity and no candidate can be invented by reranking.

- [x] **Step 2: Write RED EvidenceBundle tests**

  Verify backend-issued `evidence_id`, safe field projection, relation proof, query result reference, record/source versions, aggregate pass-through, citation mapping, bundle hash, exact completeness and `truncated=true` on any budget cut. Confirm complete Stage12-C aggregate facts can remain exact without sending all contributing record text.

- [x] **Step 3: Run tests and verify RED**

  Run: `python -m pytest -q tests/unit/test_retrieval_v2_hybrid.py tests/unit/test_retrieval_v2_evidence.py`

  Expected: FAIL because hybrid/evidence services do not exist.

- [x] **Step 4: Implement bounded hybrid scoring**

  Use exact priority band first. For fuzzy candidates calculate versioned score `0.35 keyword + 0.35 semantic + 0.20 entity/schema + 0.10 freshness`; keep component values and `retrieval_reason`. Normalize within the already authorized candidate set and apply per-table quotas before linked expansion.

- [x] **Step 5: Implement EvidenceBundle assembly and verify GREEN**

  Run: `python -m pytest -q tests/unit/test_retrieval_v2_hybrid.py tests/unit/test_retrieval_v2_evidence.py`

  Expected: PASS with deterministic candidate/evidence hashes across repeated runs.

  Actual: `9 passed`. Authorization filters run before normalization; exact candidates retain their priority band; per-objective schema/record quotas, 20 primary / 10 relation / 24 evidence budgets, stable ties and reranker set equality are enforced. Evidence assembly revalidates current authority, field visibility, source/record versions and relation proofs; aggregate output keys are supplied explicitly from the Stage12-C plan binding because `StructuredQueryResultV1` intentionally retains only `aggregate_id`.

### Task 8: Add default-off D shadow, focused diagnostics and local acceptance

**Current status (2026-07-30):** completed and accepted locally. The config/shadow/evaluation RED tests failed before implementation; the completed D focused selection passes `91/91`. Real C+D PostgreSQL integration passes `2/2`, unit/API passes `1906`, and the full backend passes `2005` with `134` existing skips under the documented four-file historical boundary. The real synthetic-only OpenRouter run passed Recall@20 `1.0`, MRR@20 `0.9583333333`, forbidden `0`, P95 `2498.3266 ms`, with Provider calls `4` and all write/send counters `0`. The acceptance is `project-docs/08-implementation/STAGE_12_D_RETRIEVAL_EMBEDDING_ACCEPTANCE.md`.

**Files:**
- Create: `backend/app/services/retrieval_v2_shadow.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/api/routes/agent_runs.py`
- Create: `backend/tests/unit/test_retrieval_v2_shadow.py`
- Create: `backend/scripts/stage12_retrieval_v2_evaluation.py`
- Create: `backend/tests/unit/test_stage12_retrieval_v2_evaluation.py`
- Create: `project-docs/08-implementation/STAGE_12_D_RETRIEVAL_EMBEDDING_ACCEPTANCE.md`
- Create: `project-docs/08-implementation/evidence/stage12-d-retrieval-embedding-2026-07-29.md`
- Create: `project-docs/08-implementation/evidence/stage12-d-retrieval-embedding-2026-07-29.json`
- Modify: `project-docs/02-architecture/stage12-quality-v2/README.md`
- Modify: `project-docs/02-architecture/stage12-quality-v2/08_DELIVERY_TEST_AND_ACCEPTANCE.md`
- Modify: `project-docs/08-implementation/README.md`
- Modify: `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`
- Modify: `AGENTS.md`
- Modify: `HANDOFF.md`

**Interfaces:**
- Consumes: V1 retrieval candidate IDs and D V2 candidates for an allowlisted synthetic workspace.
- Produces: sanitized overlap/recall/rank/truncation observation and D acceptance evidence; no dispatch or response mutation.

- [x] **Step 1: Write RED config/shadow tests**

  Assert default `off`, empty allowlist, strict mode validation, fail-closed missing profile/key, no invocation outside allowlist, no answer/API/SSE changes, no raw query/text/vector/record values in logs and provider failure isolation.

- [x] **Step 2: Implement shadow and diagnostic runner**

  The runner materializes the frozen synthetic fixture, indexes only authorized projections, executes the focused retrieval corpus and reports Recall@20/MRR/forbidden/truncation plus safety counters: Provider calls, Action expansions, record writes after fixture setup and external sends.

- [x] **Step 3: Run focused and real PostgreSQL verification**

  Run the D unit set, A/B/C compatibility tests and `tests/integration/test_stage12_retrieval_v2_postgres.py`. Then run the full backend suite with the same historical PostgreSQL exclusions only if still required. Record exact commands, durations, passes/skips and exclusions; do not reuse planned numbers.

- [x] **Step 4: Run structural/security checks**

  Run `python -m compileall -q app scripts`, `python -m alembic heads`, `git diff --check`, JSON parsing, credential/developer-path scans and a migration upgrade/downgrade/upgrade in the authorized local PostgreSQL database. Run `ruff` only if installed; otherwise record it unavailable.

- [x] **Step 5: Write acceptance and update truth/handoff**

  Accept D only if the confirmed profile benchmark, focused recall/P95/data-minimization gates, fixed-dimension pgvector, revoke/rollback tests, hybrid retrieval, EvidenceBundle, shadow isolation and regression all have fresh evidence. State explicitly that production answers still do not improve until Stage12-E consumes these artifacts and an activation/deployment gate is approved.

## Self-Review Result

- Spec coverage: sections 9.1–9.10 and Stage12-D delivery steps 1–8 map to Tasks 1–8. Embedding responsibility, three-layer index, token-aware chunks, profile benchmark, hybrid quotas, EvidenceBundle, outbox lifecycle, canonical text, score explainability and rollout gates all have an implementation and test owner.
- Placeholder scan: every task names concrete files, interfaces, tests, commands and stop conditions. Runtime profile values intentionally stop at the explicit user confirmation gate rather than being guessed.
- Type consistency: `EmbeddingProfileV1`, `RetrievalProjectionV2`, `RetrievalChunkV2`, `RetrievalRequestV2`, `RetrievalCandidateV2` and `EvidenceBundleV2` are introduced in Task 1 and consumed consistently by Tasks 2–8.

## Execution Handoff

Plan was executed inline as previously confirmed. Tasks 1–8 are implemented and Stage12-D is accepted as a local technical gate. Continue with Stage12-E documentation and a separate code-level plan before implementation. Do not interpret local D acceptance as deployment, activation or improved production answers; Stage11 V1 remains the only dispatch authority.
