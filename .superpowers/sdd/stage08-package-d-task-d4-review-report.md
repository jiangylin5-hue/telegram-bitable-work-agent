# Stage08 Package D / D4 独立复审报告

## Review Result

- Review date：2026-07-21
- Result：`FAIL`
- Findings：`1 Critical / 1 Important / 1 Minor`
- Closure eligibility：D4 **不具备** root closure consideration 条件；D5 不应基于当前 D4 继续。
- Review scope：完整对照 D4 review/implementation brief、实现报告、Package D 数据合同与 BDD、D1–D3 当前代码和复审证据，以及 C1 business scope、Memory read-only projection、DigitalEmployee/member authority 与实际 D4 production/tests。
- Write boundary：唯一源码树写入为本报告；未修改 application、tests、contracts、models、migration、UoW、API、Docker/configuration、Git 或外部系统。

本轮规定的 `106`、`172`、`8` 个测试和 `compileall` 均 fresh 通过，但这些 green tests 没有覆盖真实 SQLAlchemy identity map 下的跨时点撤权，因此不能推翻下面的安全阻断。

## Findings

### Critical

#### C-01：所谓“引用前重新读取”会复用 SQLAlchemy identity map 旧对象，数据库已撤权或员工已停用后仍会释放私有正文

位置：

- `backend/app/services/stage08_retrieval_provider.py:628-646`：authority revalidation 再次调用普通 UoW getter/list；
- `backend/app/services/stage08_retrieval_provider.py:1036-1083`：render/citation 前通过 `get_knowledge_source` 和 `list_knowledge_chunks` 重验；
- `backend/app/services/stage06_platform.py:1439-1453`、`:1646-1647`、`:1711-1715`、`:1747-1763`：SQL UoW 使用普通 `Session.get` / `Session.scalars(select(...))`，没有 `populate_existing`、`refresh`、`expire` 或独立 current-state read boundary。

影响：D4 的核心安全承诺是 search 后、私有 evidence/citation/view 生成前再次以 PostgreSQL 当前事实验证 employee/member/source/chunk。当前实现只是在 Python 层重新调用 getter；已加载实体仍可从 identity map 返回，数据库的新状态不一定覆盖旧属性。正常的并发 revoke、employee pause、member/access drift 因此可在同一搜索/渲染调用链中被忽略。

独立真实 PostgreSQL 攻击复用了 D4 现有 rollback integration fixture：先完成合法 search，随后在调用 `safe_view` 前用同一事务的 SQLAlchemy Core SQL 将数据库 source 改为 `revoked`，不修改 ORM identity-map 对象。数据库读回已确认 `status=revoked`；当前 provider 仍给出：

```text
db_status_before_render=revoked
private_evidence_present=True
citation_count=1
safe_result_count=1
```

第二个独立攻击将数据库 DigitalEmployee 改为 `paused`，结果同样未失效：

```text
db_employee_status_before_render=paused
private_evidence_present=True
rendered_status=ready,result_count=1
```

两个攻击均在 integration fixture 的外层 transaction 中 rollback；后续只读检查为 source `0`、chunk `0`、Knowledge outbox `0`。这不是 mock 或只读源码推断，而是 PostgreSQL 当前行事实与 D4 返回结果发生直接矛盾。`render_private_evidence` 非空意味着已撤权正文仍可进入后续 Package E prompt assembly，因此归类为 Critical。

Required remediation：建立真正绕过/刷新 identity map 的 D4 current-state read boundary，并对 authority 相关 workspace/member/employee/base/table/view/record/relation 及 source/chunk/source-specific verifier 一并生效。修复不得以全局 `expire_all()` 隐式丢弃其他未提交状态。必须新增至少两类 dedicated pgvector regression：

1. search 后由独立 SQL/第二 session 提交 source revoke/replacement/chunk stale，再 render，private evidence/citation 必须为空；
2. search 后 employee pause、member/grant/view/business relation 任一变化，再 render，authority 必须 unavailable 且正文不可释放。

### Important

#### I-01：source/chunk 的终止生命周期时间戳未参与候选或渲染重验，矛盾行仍被视为可读

位置：

- `backend/app/services/stage08_retrieval_provider.py:654-776` 的 PostgreSQL structured filters 只检查 source/chunk `status` 与 `valid_until`；
- `backend/app/services/stage08_retrieval_provider.py:988-1033` 只检查 fingerprint/hash/text/status 等字段；
- `backend/app/services/stage08_retrieval_provider.py:1178-1195` 的 `_active_source` 不检查 `revoked_at` / `deleted_at`；`_valid_chunk_for_source` 不检查 `chunk.deleted_at`。

独立 in-memory current-state 攻击保持 source `status="active"` / chunk `status="indexed"`，仅写入终止时间戳。四次查询均仍返回当前正文：

```text
source_revoked_at: status=degraded, results=1, error=none
source_deleted_at: status=degraded, results=1, error=none
chunk_deleted_at:  status=degraded, results=1, error=none
```

这些组合虽然不应由正常 revoke service 产生，但 D4 contract 明确要求 malformed/current lifecycle facts fail closed，且 PostgreSQL schema 没有约束禁止这些矛盾组合。检索层不能仅凭 `status` 假定终止时间戳不存在。

Required remediation：structured SQL prefilter 与 post-selection/render revalidation 都必须要求 active source 的 `revoked_at/deleted_at` 为空、indexed chunk 的 `deleted_at` 为空，并增加 in-memory + dedicated PostgreSQL 矛盾行攻击。若决定以数据库 check constraint 强制状态/时间戳一致，则属于额外 model/migration 范围，需先按项目文档门禁处理，不能在 D4 修复中无记录扩张。

### Minor

#### M-01：Memory logical source fingerprint 只校验“像 SHA-256”，没有重算 D2 root-lineage 身份

位置：`backend/app/services/stage08_retrieval_provider.py:988-1001` 仅调用 `_sha256_hex(source.logical_source_fingerprint)`；D2 真源算法在 `backend/app/services/stage08_retrieval.py:602-645` 沿 Memory supersession lineage 求根并计算 `SHA-256("memory_lineage:" + root_id)`。

独立攻击把当前合法 source fingerprint 替换为另一个格式合法的 64-hex 值，Memory projection/version/hash/scope 均保持不变，D4 仍返回 `results=1`。当前 source text 仍经过 read-only Memory revalidation，因此本轮未证明越权正文扩大，归类为 Minor；但它允许逻辑身份、去重与稳定排序元数据漂移，弱化“current source-specific verifier”的完整性。

Required remediation：Memory source verifier 应重算或通过受控 helper 验证 root-lineage fingerprint；不要仅验证格式。补充合法 fingerprint drift 与跨 lineage fingerprint collision 回归。

## Functional Review Matrix

| Review area | Fresh conclusion |
| --- | --- |
| Authority creation / ordinary in-memory drift | 基础实现与现有攻击集通过：forged role、cross-workspace grant、inactive workspace/employee/base/table/view/member、business relation 与 assigned grant 可 fail closed；authority/result/evidence repr 固定且常规序列化失败。C-01 证明 PostgreSQL current-state revalidation 仍不成立。 |
| Candidate narrowing | SQLAlchemy production path包含真实 `keyword_terms &&` 与 pgvector cosine `<=>`；workspace/source/chunk/status/version/base/table/view/customer/project filters 位于 Python ranking 前。未知/group/Telegram metadata 在 ranking 前被 current-candidate verifier 丢弃。 |
| Memory consumption | 使用 `read_memory_projection(..., lifecycle_mode="read_only")`，未直接读 `item.payload`，普通 revoke/expire/supersede/version/hash/scope/record drift 会丢弃且不新增 audit。C-01/I-01/M-01 阻断完整 current-source 结论。 |
| Ranking / degradation | 显式 fixed test profile 可产生确定性 hybrid；默认不实例化 `TestHashEmbeddingProvider`，返回 `keyword_only`，不伪造 vector score；limit `1..12`，返回 DTO 不含 score/ID。 |
| Rendering / citation | safe citation exact shape、constructed-model attack、repr/exception redaction 通过；但 C-01 证明 render-time revoke/employee pause 可以继续释放 private evidence，因此整体 FAIL。 |
| Dedicated pgvector | 仅显式 D0 `STAGE08_RAG_DATABASE_URL`；fresh `8 passed`，`vector=0.8.5`、revision `20260720_0032`、GIN/HNSW 索引存在。没有 native/default fallback。 |

## Fresh Verification Evidence

工作目录：`backend`。所有 pytest 禁用 cache 并将 warning 提升为 error。

1. D4 provider + D2/D3 service：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_provider.py tests/unit/test_stage08_retrieval_service.py
```

Final fresh result：`106 passed in 2.19s`。

2. D1 contract + D2/D3 + D4：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_retrieval_contracts.py tests/unit/test_stage08_retrieval_chunking.py tests/unit/test_stage08_retrieval_service.py tests/unit/test_stage08_retrieval_provider.py
```

Final fresh result：`172 passed in 3.20s`。

3. Dedicated PostgreSQL/pgvector：

```powershell
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL
python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
```

Final fresh result：`8 passed in 2.40s`，无 skip。

4. Compile：

```powershell
python -m compileall -q app/runtime/stage08_retrieval_contracts.py app/services/stage08_retrieval_provider.py
```

Fresh result：exit `0`。

5. Dedicated database/catalog cleanup readback：

```text
vector=0.8.5
revision=20260720_0032
sources=0
chunks=0
knowledge_events=0
retrieval_indexes=ix_stage08_knowledge_chunk_hnsw_test_profile,
                  ix_stage08_knowledge_chunk_keyword_terms_gin
```

Green suite 的覆盖缺口是 C-01/I-01/M-01；因此测试数量不能作为 D4 closure 证据。

## Static / Privacy / Scope Review

- D4 production files未导入或调用 requests/httpx/OpenAI/OpenRouter/Telegram/LangGraph/Redis/Anthropic/Cohere/Milvus、network client、环境凭证或真实 provider。
- 未发现 direct Memory `payload` attribute、raw Message 字段、query persistence、audit/outbox/log 写入或默认 `TestHashEmbeddingProvider(...)` 实例化。
- SQL path 使用 SQLAlchemy expression；没有 raw SQL、凭证或 native/default database fallback。审查攻击中的 Core SQL 仅存在于一次性 reviewer 命令，不在 production/test 文件中。
- D4 source/tests/contracts/report 均处于共享 dirty worktree 的 untracked 状态，无法用空 `git diff` 证明实现差异；本轮读取完整当前文件并执行 `git diff --check`，没有新增 whitespace error。
- 本报告未将任何 UUID、query、正文、credential 或 DSN 值写入审查证据。

## Skipped / External / Remaining Scope

- 未运行 full backend suite；规定的 D1–D4 focused matrix 与完整 dedicated pgvector module 已运行，但 C-01 使扩大测试范围不能替代修复。
- 未调用真实 embedding/LLM/OpenRouter/Telegram/HTTP/Redis/LangGraph、browser/Mini App、staging、production 或 deployment。
- 未实现/验收 D5 controlled reindex API；Package D、Stage08、真实语义 provider/质量和生产部署仍为 open scope。
- `document_projection` 与 `approved_summary` 继续因缺少 origin verifier 而 fail closed；本轮不把它们视为已支持。
- D0 disposable pgvector container 仍为本地开发/测试资源，不是服务器或 production deployment evidence。

## Cleanup and Gate

- 所有独立 PostgreSQL攻击复用现有 integration outer transaction 并 rollback；fresh readback 证明没有 source/chunk/Knowledge outbox 测试行残留。
- 未创建临时脚本、dataset、credential、log、volume 或外部 artifact；未执行 Git stage/commit/reset/checkout/clean/push/PR。
- 本报告不宣布 D4、D5、Package D 或 Stage08 完成。必须先修复 C-01 和 I-01，并经 fresh independent review 达到 `0 Critical / 0 Important`，才可由 root 考虑关闭 D4。M-01 建议在同一收口中修复，避免把已知 source-integrity 漂移带入 Package E。
