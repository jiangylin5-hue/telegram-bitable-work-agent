# Stage08 Package C2 Long Context — Task 1 Report

## Status

- Status：DONE_WITH_CONCERNS
- Task：D3 Decision Record and Contract Reconciliation（仅中文文档合同收口）
- Date：2026-07-19
- Worktree：`D:\telegram多维表格和工作智能体的开发\.worktrees\stage07-mini-app-ui`

## Changed Files

Created：

- `project-docs/08-implementation/decisions/STAGE_08_C2_D3_GROUP_CONTEXT_DATA_CONTRACT.md`
- `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-1-report.md`

Modified：

- `project-docs/08-implementation/STAGE_08_PACKAGE_C2_GROUP_HISTORY_BDD_AND_ACCEPTANCE.md`
- `project-docs/08-implementation/STAGE_08_SOURCE_OF_TRUTH.md`
- `project-docs/08-implementation/STAGE_08_IMPLEMENTATION_PLAN.md`
- `project-docs/08-implementation/STAGE_08_DATA_API_SECURITY_CONTRACT.md`
- `docs/superpowers/plans/2026-07-19-stage08-package-c2-group-history.md`

## What Changed

- 新 D3 decision record 固定了 D1–D6：新/edited authorized group/supergroup controlled projection；30 天、120 fragments、500 code points/item、60,000 raw、24,000 final、最新 24/12,000、ephemeral digest 12,000、7-day half-life；`best_effort_group_deletion`；唯一 D4 mapping；private authority factory；D6 label/type/id/scope/C3 ownership。
- 决策记录列出 `Stage08GroupBusinessContextBinding` 和 `Stage08GroupMessageProjection` 的精确合同字段、唯一性、版本、UTC `event_at`、edit、retention、purge 和 lifecycle 语义。
- 五个既有文档已移除旧短窗口激活值和 D3 待选表述，改为已确认的长 Context 合同。
- “不新增 ingestion”已收窄为：不新增 Telegram network、webhook endpoint、polling、outgoing request 或 historical raw read；允许既有 verified local ingress transaction 在同一本地事务写 new/edited controlled projection。
- 固定 `compression_required = raw_selected_chars > 24000`；C2 不调用 Provider、不生成 digest。C3 拥有 C1/C2 merge/global budget/renderer，Package E 是唯一未来 `ContextCompressor` Provider 调用所有者。
- 增加“表格事实 / Context / Memory / 知识库”分层：`GroupContextWindow` 和临时 `GroupContextDigest` 只是当前 invocation Context，不得进入 Memory/RAG/任何持久化载体；长期结论必须经 Package B。
- 全部 active status 均明确 Task 1 文档正在 review，C2 code/schema/migration/UoW/tests/API/external calls 仍 unimplemented。

## Verification

### 1. Required stale-value scan

Command：

```powershell
rg -n "recent 20|history 12|group 6000|即时删除|D3.*未确认|TODO|TBD" project-docs/08-implementation/STAGE_08_PACKAGE_C2_GROUP_HISTORY_BDD_AND_ACCEPTANCE.md project-docs/08-implementation/STAGE_08_SOURCE_OF_TRUTH.md project-docs/08-implementation/STAGE_08_IMPLEMENTATION_PLAN.md project-docs/08-implementation/STAGE_08_DATA_API_SECURITY_CONTRACT.md docs/superpowers/plans/2026-07-19-stage08-package-c2-group-history.md
```

Output：

```text
RG_EXIT=1
```

Interpretation：无匹配，符合预期。目标文档中无需保留的历史短窗口值。

### 2. Required diff check

Command：

```powershell
git diff --check -- project-docs/08-implementation docs/superpowers/specs docs/superpowers/plans .superpowers/sdd
```

Output：

```text
DIFF_CHECK_EXIT=0
warning: multiple pre-existing Stage06/Stage07 files report "LF will be replaced by CRLF the next time Git touches it"
```

Interpretation：无 whitespace error，命令成功。警告均指向本 Task 未修改的 Stage06/Stage07 文件。

### 3. Supplemental untracked-file whitespace scan

由于六个目标文档在共享 dirty worktree 中均为 untracked，`git diff --check` 不会检查其内容，因此额外执行：

```powershell
rg -n "[ \t]+$" project-docs/08-implementation/decisions/STAGE_08_C2_D3_GROUP_CONTEXT_DATA_CONTRACT.md project-docs/08-implementation/STAGE_08_PACKAGE_C2_GROUP_HISTORY_BDD_AND_ACCEPTANCE.md project-docs/08-implementation/STAGE_08_SOURCE_OF_TRUTH.md project-docs/08-implementation/STAGE_08_IMPLEMENTATION_PLAN.md project-docs/08-implementation/STAGE_08_DATA_API_SECURITY_CONTRACT.md docs/superpowers/plans/2026-07-19-stage08-package-c2-group-history.md
```

Output：

```text
TRAILING_WS_EXIT=1
```

Interpretation：无行尾空白匹配。

## No-Code / No-External Scope Statement

- 未修改任何 Python、migration、test、API route、schema implementation、secret、Telegram configuration 或其他生产代码。
- 未运行 pytest、Alembic、compile、Provider、Telegram、网络、数据库、外部系统或外部写入。
- 未执行 git stage/commit/reset/checkout/clean，未修改 git index/HEAD。
- 未读取或修改 secrets。

## Self-Review

- Scope review：仅创建/修改 brief 指定的六个文档和本 report；未扩大到 Task 2 或代码。
- Contract review：D1–D6、D2 所有固定值、D3 lifecycle、D4 mapping、D5 factory、D6 evidence/C3 owner 已在 decision/BDD/source/plan/security 文档中一致。
- Lifecycle review：明确只有 known edit、server-authorized purge 与 expiry 是可靠失效事实；没有将普通群远端 delete/revoke 写成可靠事件。
- Ordering review：`event_at` 仅来自 Telegram `message.date` UTC，late delivery 不改变事件顺序，同时间仅用不输出的内部 tiebreak。
- Privacy review：正文只允许存在于受控 projection 与当前调用的 private window/digest；公开/可观测投影只含 status/count/budget/signal。
- Status review：没有声称 schema、migration、tests、PostgreSQL evidence、Provider 或 production readiness 已完成。

## Skipped Tests

- 未运行代码测试。Task 1 明确为 documentation-only，且 brief 禁止修改/执行 C2 code、migration、tests 或外部系统。

## Temporary Cleanup

- 未创建临时脚本、测试数据、数据库状态、网络状态或外部 artifact，无需清理。

## Concerns / Remaining Risks

- 六个目标文档在该共享 dirty worktree 中均显示为 untracked。本 Task 按要求未 stage/commit；因此 required `git diff --check` 不检查这些 untracked 内容，已以独立 trailing-whitespace scan 补足。
- `git diff --check` 输出了与本 Task 无关的 Stage06/Stage07 LF→CRLF 警告；退出码仍为 0，本 Task 未修改这些文件。
- 当前仅文档合同可供 review。C2 schema/code/tests 仍不存在，不能解读为 implementation readiness、Provider readiness 或 production readiness。
