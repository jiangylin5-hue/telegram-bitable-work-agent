# Stage08 Package C2 — Task 6 最终独立复审包

## Status

- Review status：`PASS / C2 CLOSED / C3 HANDOFF ALLOWED`。
- Findings：0 Critical / 0 Important / 0 Minor。
- Date：2026-07-20。
- Scope：仅 C2 Tasks 1–6 最终独立复审与 C3/E handoff。

## 1. 独立审查面

本轮不信任 remediation 实现报告，直接读取并比对：

- C2 long-context design、D3 data contract、source-chat-type decision、C2 BDD 和 Tasks 1–5 报告/evidence。
- 首轮 Task 6 review/review-package 及 Important-findings fix brief。
- `backend/app/runtime/stage08_group_context_contracts.py`
- `backend/app/services/stage08_group_context.py`
- `backend/tests/unit/test_stage08_group_context_contracts.py`
- `backend/tests/unit/test_stage08_group_context_service.py`
- C2 model/migrations、Stage06 C2 UoW portions、trusted ingress/parser/schema/route portions、PostgreSQL integration tests 和 C1 regression tests。
- 实际 dirty/untracked 文件内容、symbol/static scans 和 scoped diff check；未把普通 git diff 当作完整变更面。

remediation 的实际生产行为只有：partial validator 加上 selected-fragment 门禁；window builder 的 zero-selected 分支改为 unavailable；private evidence category tuple 加入 `group`。对应 unit tests 与 source decision status 同步更新。未发现 schema/migration/UoW lock/C1/C3/API/network/Provider/Memory/RAG 等范围扩张。

## 2. 首轮 findings 关闭证据

### Important 1：零片段 partial

- `backend/app/runtime/stage08_group_context_contracts.py:89` 现同时拒绝 `selected_fragments == 0` 和 `omissions.total == 0` 的 partial。
- `backend/app/services/stage08_group_context.py:391` 在没有 selected fragment 时固定返回 `group_context_unavailable`，保留 count-only omission 但 usage 为零 selected/零 raw chars。
- `backend/tests/unit/test_stage08_group_context_contracts.py:198` 覆盖 zero-selected partial 被拒绝和 real-selected partial 继续有效。
- `backend/tests/unit/test_stage08_group_context_service.py:436` 覆盖只有 expired omission 时 unavailable。

Verdict：closed；D2/status fail-closed 语义与 BDD 一致。

### Important 2：D6 scope category 缺失

- `backend/app/services/stage08_group_context.py:131` 现精确生成 `("workspace", "group", "customer", "project")`。
- `backend/tests/unit/test_stage08_group_context_service.py:287` 检查精确 tuple，并检查 materialization repr 和 public safe view 仍不含正文/内部 projection ID。

Verdict：closed；D6 evidence shape 完整，且没有引入 scope value 或新序列化载体。

### Minor：source decision status drift

- `STAGE_08_C2_SOURCE_CHAT_TYPE_PROPOSAL.md` 现标记 implemented / Task 4 independently reviewed，并如实记录 Task 5 收口和 Task 6 最终 PASS。

Verdict：closed。

## 3. D1–D6 disposition

| Decision | Verdict | 实际结果 |
| --- | --- | --- |
| D1 | PASS | 只为当前 new/known-edit verified `group`/`supergroup` payload 建立 projection；source receipt 只读 `Message.id/trace_id`；旧 `raw_text/raw_caption/normalized_text` 不读、不回填、不删除。private/channel 排除。 |
| D2 | PASS | 30d/120/500/60k/latest-24/latest-12k/>24k/half-life-7d 与有界 SQL 选择保持；partial 现必须有安全片段，零片段 fail closed 为 unavailable。 |
| D3 | PASS | known edit、authorized purge、expiry 与并发当前状态证据存在；普通远端 delete/revoke 仍如实为 `best_effort_group_deletion`。 |
| D4 | PASS | 单一 active `chat_user` binding → 单一 same-workspace customer/project mapping；member/employee/record/table/base/link/version drift 均 fail closed。 |
| D5 | PASS | authority/handle/window 是 issuer-created、non-Pydantic、non-JSON private objects，repr/public safe view 不含正文或内部 ID。 |
| D6 | PASS | label/source type/`group_context:NN` 正确；scope 只暴露 `workspace/group/customer/project` category names。C3/E ownership 未被 C2 篡越。 |

## 4. PostgreSQL、隐私和并发

- source graph 只有 `20260720_0031 (head)`；`source_chat_type` 只允许 `group|supergroup|unknown`，`unknown` 在 initial/fresh SQL body eligibility 前 fail closed。
- fresh eligible materialization 的 PostgreSQL shared row lock 仍只位于 body re-read，并与 purge writer `FOR UPDATE` 冲突；双 session `pg_blocking_pids` 测试证明 reader 等待已提交当前结果，不输出 stale body。
- 该锁依赖 PostgreSQL baseline；InMemory UoW 不仿真 DB lock。C3/E 仍必须设计明确事务消费边界并在每次 LLM/tool invocation 前重验。
- `content_fragment` 仅位于 C2 private model/UoW/ingress/service 与 focused tests；公开 DTO、API、audit/outbox、Memory/RAG/vector、Redis、Provider、AgentRun、LangGraph/checkpoint 均无载体。
- 没有 persistent digest、C1/C2 merge、Provider compression 或 Telegram outgoing behavior。

## 5. 新鲜独立验证

### Focused remediation

```text
36 passed in 1.19s
```

### Disposable PostgreSQL + C2/C1

运行 brief 指定命令：在子进程内保存 `DATABASE_URL`，临时指向已批准 `STAGE06_LOCAL_DATABASE_URL`，命令后恢复。首次尝试被命令层 10 秒超时提前终止，不计作证据；检查无残留 pytest 进程后用 120 秒上限原样重跑。

```text
alembic upgrade head: exit 0
alembic heads: 20260720_0031 (head)
pytest: 151 passed in 28.60s
combined exit: 0
```

测试包含 C2 contract/ingress/service/real PostgreSQL 及 C1 contract/service。

### Compile/static/diff

```text
compileall: exit 0
historical-raw/prohibited dependency scan: exit 1 (zero matches)
public/persistent content_fragment carrier scan: exit 1 (zero matches)
Telegram/Provider/Redis/vector/LangGraph/Memory boundary scan: exit 1 (zero matches)
git diff --check -- backend project-docs/08-implementation docs/superpowers: exit 0
```

diff check 仅有 dirty worktree 既有 LF -> CRLF warning，无 whitespace error。

## 6. Scope、清理和风险

- remediation 没有修改 PostgreSQL tests、schema/migrations、UoW/locking、C1/C3、route/API、Telegram networking、Provider/LLM、Memory/RAG/vector、Redis、LangGraph、audit/outbox、Mini App 或 deployment。
- 本 review 只更新 C2 completion/handoff 文档；未运行任何 Telegram/Provider/外部调用，未 stage/commit/reset/checkout/clean。
- 默认 `DATABASE_URL` 的历史 orphan revision 仍是 deployment-preflight 风险；本轮未读取、stamp、删除或修复它。
- `source_chat_type` 的语义不可变性由内部写边界、无公开 mutation surface 和 read-time fail-closed 维护；DB 只有 enum CHECK，无 update trigger，仍保留为已知轻微风险。
- 普通 Telegram 群远程 delete/revoke 仍为 `best_effort_group_deletion`。
- 无临时脚本、外部资源或残留 task pytest 进程。

## 7. C3 / Package E handoff

- C2 已关闭，C3 允许开始。
- C2 向 C3 交付的仅是 private long window 和 `compression_required`。
- C3 必须独立实现 C1/C2 merge、跨 source 总预算和 renderer，不得将 C2 private carrier 暴露为新公开 API。
- Package E 才可通过已批准 Provider 路径调用 `ContextCompressor`；digest 只能 invocation-local，失败时只降级到仍符合预算的最新安全片段。
- 本 handoff 不标记 Package C、Stage08、真实 Provider 评测、Telegram 外部活动、deployment 或 production readiness 完成。
