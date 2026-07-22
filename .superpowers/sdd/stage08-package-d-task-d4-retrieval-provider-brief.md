# Stage08 Package D / Task D4 Private Authority, Hybrid Search & Safe Citations Brief

## Status and Scope

- Status: `approved task-level implementation boundary after D3 closure`
- Consumes: D1 source/chunk schema, D2 safe Memory lineage/reference events, D3 indexed/tombstoned chunks, existing `Actor`/DigitalEmployee/member eligibility, C1 `resolve_business_scope`, and read-only Memory verification.
- Produces: opaque retrieval authority, PostgreSQL-first structured candidate narrowing, keyword/vector hybrid ranking, source revalidation, private evidence handles, and safe citation/safe-view contracts.
- This is an internal provider layer only. It does not create public query API, Mini App behavior, LLM prompt content, LangGraph orchestration, external embedding/LLM calls, Telegram/group access, document transport, Milvus, deployment, migration, or new permissions.

## Allowed Files

- Create: `backend/app/services/stage08_retrieval_provider.py`
- Modify: `backend/app/runtime/stage08_retrieval_contracts.py`
- Create: `backend/tests/unit/test_stage08_retrieval_provider.py`
- Modify: `backend/tests/integration/test_stage08_retrieval_pgvector.py`
- Create: `.superpowers/sdd/stage08-package-d-task-d4-report.md`

Do not modify models, migrations, UoW interfaces, `stage08_retrieval.py`, Memory/C1/C2 behavior, API/routes, Docker/configuration, runtime defaults, Git state, or any external system. The D0 dedicated local Docker PostgreSQL may be changed only by D4 integration tests and must not fall back to default/native database URLs.

## Authority Boundary

Create a module-private, slots-only, non-serializable retrieval authority and `Stage08RetrievalAuthorityFactory`. The factory is the only valid issuer; direct construction, copied fields, malformed actor, stale authority, different workspace/employee/caller, invalid employee member grant, inactive employee/workspace/base/table/view, or any scope drift must fail closed with no private evidence.

Factory inputs are internal typed values: `uow`, verified `Actor`, `workspace_id`, `employee_id`, and optional `customer_record_id`/`project_record_id`. It must:

1. revalidate current workspace membership and the active digital employee using the same effective authority model as C1;
2. validate the actor against employee `access_mode`/member grant and `query` capability;
3. resolve the optional customer/project pair with existing `resolve_business_scope`, including current visible linked-record relationship;
4. capture only private typed IDs/version facts needed for revalidation; no raw Telegram/group, Message, prompt, field value, memory payload, URL, credential, query text, or score may enter authority `repr`/serialization.

An unavailable authority may exist only as an opaque fail-closed object. Its `repr` is a fixed opaque marker and it offers no publicly readable attributes. D4 must not add Telegram chat scope; group context remains C2 Context-only, never a RAG candidate.

## Retrieval Contracts and Safe Outputs

Extend `stage08_retrieval_contracts.py` only with strict frozen safe DTOs required for D4. A safe citation may contain exactly a display ordinal, `label="retrieved_material"`, source-type category, and scope category. It must not include source/chunk/record/field/workspace/customer/project UUIDs, names, URLs, scores, vectors, query, text, payload, actor, authority, profile, or provider data. Validate constructed-model shape as rigorously as the existing `RetrievalSafeView`.

Private evidence/hits may retain required current chunk text only in a module-private slots object. Its `repr` is fixed opaque, it must not be Pydantic/dataclass serializable, and it must be revalidated before internal rendering. `safe_citations(...)` and `safe_view(...)` return strict safe models only.

## Candidate and Ranking Rules

1. Search accepts only a valid opaque authority, a short in-memory query (`1..500` Unicode code points after canonicalization), `limit 1..12`, and `now`. Query is never persisted, logged, audited, included in exception text, or exposed by result/citation.
2. First narrow candidates by workspace, `source.status="active"`, current source version/hash, `chunk.status="indexed"`, source/chunk scope, employee accessible base/table/view constraints, and resolved customer/project scope. Sources with unknown/malformed/group/chat/identity fields, missing/inactive related objects, base/table/view mismatch, relation mismatch, or no explicitly authorized scope are dropped before ranking.
3. `memory_item` candidates must call `read_memory_projection(..., lifecycle_mode="read_only")` at consumption and verify active current version, safe scope, source reference, canonical projection hash and source-specific conditions. It must never read `item.payload` directly. The first valid source read does not replace this post-candidate re-read.
4. Extract query terms by reusing D2 deterministic chunk rules. Keyword score is deterministic normalized term overlap. Vector score is permitted only when a caller-injected **test-only** profile-compatible embedding adapter is explicitly supplied and output is valid; default runtime has no real embedding provider and must return `keyword_only` degradation without inventing a vector score. Do not instantiate/select `TestHashEmbeddingProvider` as a default.
5. When both scores exist, combine normalized keyword/vector scores deterministically. Apply a stable internal tie order without returning IDs/scores. Return at most 12 private hits.
6. Before a hit can be rendered as private evidence or citation, revalidate authority, source status/version/hash, source/chunk indexed state, exact scope, current business relation, and source-specific verifier again. Any drift drops the hit; no stale/revoked/replaced/deleted evidence is returned.
7. PostgreSQL integration must demonstrate real vector + keyword candidate path on D0 database and the same deny/re-read behavior. It may use SQLAlchemy through the existing backend service/UoW boundary; do not add raw SQL, credentials, or direct database access outside the service.

## TDD Required Cases

Write RED tests before implementation for at least:

1. Factory rejects forged/stale/cross-workspace/employee-inactive/member-grant/base/table/view/business-relation drift authority; authority/result repr never contains UUID/raw data.
2. Prefilter denies workspace/employee/caller/customer/project/base/table/view/scope mismatch and malformed/group/Telegram source metadata before ranking.
3. Read-only Memory revalidation drops revoked/expired/superseded/version/hash/scope/source-relation drift after candidate selection, without lifecycle/audit side effect.
4. Explicit test adapter gives deterministic keyword+vector order; unavailable default produces only keyword candidates and explicit `keyword_only`, never a synthetic vector score. Cap is 12.
5. Rendering/citation after revoke/replacement/chunk stale/authority drift returns no evidence for that hit. Safe citations and safe views contain no UUID/raw text/query/score/vector/profile/actor data, including constructed DTO/repr/exception paths.
6. Dedicated pgvector covers actual indexed chunks, profile-compatible vector/keyword ranking, structured narrowing, post-search drift drop, HNSW/GIN presence, and no `DATABASE_URL`/`STAGE06_LOCAL_DATABASE_URL` fallback.

## Required Verification

Run from `backend` with cache disabled and warnings as errors:

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_provider.py tests/unit/test_stage08_retrieval_service.py
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py tests/unit/test_stage08_retrieval_provider.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
python -m compileall -q app/runtime/stage08_retrieval_contracts.py app/services/stage08_retrieval_provider.py
```

Perform static scans for direct Memory payload/Message reads, raw query/candidate persistence, UUID/raw private evidence leak, external provider/network/Telegram/LLM/LangGraph/Milvus import, default TestHash selection, and `git diff --check`. Record RED/GREEN commands/counts, pgvector image/extension/head, skip/external-action status, risks, and cleanup in the D4 report. Do not claim D4, Package D, Stage08, semantic quality, external provider readiness, or production completion pending fresh independent review.
