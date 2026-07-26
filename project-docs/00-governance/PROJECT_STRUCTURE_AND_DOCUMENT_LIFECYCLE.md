# 项目阶段、工作树与文档生命周期治理

## Status

- **Document status:** active governance rule
- **Date:** 2026-07-26
- **Scope:** Git 分支/worktree、Stage 生命周期、文档真源、历史证据、执行临时物、截图与清理规则
- **Current Progress:** 已完成仓库结构审计和第一轮治理。治理前 `.superpowers/sdd/` 中 249 个 tracked 文件均为生成型执行临时物，现已从 Git index 取消跟踪并由 `.gitignore` 覆盖，本机 current SDD workspace 仍保留；顶层与 implementation README 已从 Stage06/Stage07 漂移状态收敛到当前 Stage09 SSE 入口；三个现存 worktree 的历史基线、旧部署线和当前开发线职责已明确。历史验收、迁移和部署证据未删除。

## 1. 治理目标

本治理解决四类问题：

1. 新会话不知道应该读取哪个 handoff、哪个 Stage 和哪个分支。
2. 每个 Stage 都更新多个 README/Progress/Checklist，旧状态长期残留并冒充当前真源。
3. SDD brief、report、review package 和临时 patch 被提交到 Git，导致源代码仓库被执行缓存淹没。
4. 为了“清理”而移动或删除历史迁移、外部操作证据，反而破坏审计链和文档链接。

治理原则：

```text
一个当前目标
-> 一个活动分支/worktree
-> 一个顶层 handoff
-> 一个顶层 source of truth
-> 一个当前 Stage 设计/计划
-> 一个当前交付证据
```

历史材料可以保留，但不得继续出现在新会话默认读取路径中。

## 2. Git 分支与 worktree 划分

### 2.1 当前已存在的工作树

| Worktree | Branch | Role | Write policy |
| --- | --- | --- | --- |
| 项目主目录 | `codex/stage-06-hardening` | 已接受 Stage06 后端基线和仓库公共入口 | 默认只读；不得继续开发 Stage08/09 |
| `.worktrees/stage07-mini-app-ui` | `codex/stage07-mini-app-ui` | Stage07/08/09 r39 部署历史线；保留用户 dirty files | 冻结；不得 reset、清理或混入新功能 |
| `.worktrees/stage09-ai-conversation-sse` | `codex/stage09-ai-conversation-sse` | 当前 Codex 式 AI 对话与受控 SSE 功能线 | 唯一活动开发工作树 |

### 2.2 新功能分支规则

- 分支统一使用 `codex/<stage>-<bounded-feature>`。
- 一个活动功能只有一个 worktree；不得从主目录和旧 worktree 同时修改。
- 新分支必须从最新已推送且可追溯的基线 commit 创建，不从 dirty worktree 复制文件。
- 当前功能完成后，通过分支完成流程选择 merge/PR/保留；未完成前不把旧 worktree 删除。
- worktree 路径固定为 `.worktrees/<branch-short-name>`，`.worktrees/` 必须保持 Git ignore。

### 2.3 Worktree 清理条件

只有同时满足以下条件才可删除 worktree：

1. 目标分支提交已推送或明确不再需要。
2. `git status --short` 为空。
3. 未跟踪截图、环境文件和用户改动已明确归属。
4. 当前 handoff 不再把该 worktree 列为活动入口。

旧 `stage07-mini-app-ui` worktree 当前不满足第 2、3 条，因此本轮不删除。

## 3. Stage 生命周期

每个 Stage 只允许以下稳定状态：

| Status | 含义 |
| --- | --- |
| `designing` | 需求和技术设计中，禁止业务代码 |
| `approved` | 设计/API/schema/权限边界已获确认，可写实施计划 |
| `implementing` | 已有批准计划，按 TDD 开发 |
| `evidenced-pending` | 实现完成但仍缺真实环境或逐项证据 |
| `accepted` | Acceptance Criteria 已有直接证据 |
| `historical` | 已被后续 Stage 取代，仅供追溯 |
| `blocked` | 明确环境/授权阻塞，不能用其他证据冒充 |

Stage 完成不等于生产上线。`accepted`、`deployed` 和 `production-write-authorized` 必须分别记录。

## 4. 文档分层与唯一职责

### 4.1 Tier 0：协作规则

文件：

- `AGENTS.md`

职责：

- 产品宪法、技术基线、安全和确认规则；
- 当前 Stage 的一段式 `Current Progress`；
- 当前 handoff 的唯一链接。

禁止：

- 堆积逐日进度日志；
- 重复完整实施计划；
- 把历史测试数长期写进协作规则。

### 4.2 Tier 1：当前真源

文件：

- `HANDOFF.md`：稳定入口，只指向当前权威 handoff；
- `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`：产品边界和当前 Stage 目标；
- `project-docs/00-governance/HANDOFF_<date>_<topic>.md`：当前会话交接；
- 本治理文件。

职责：

- 新会话在五分钟内定位活动 worktree、当前 Stage、批准范围、下一任务和风险；
- 不保存逐任务终端输出；
- 不复制历史 Stage 的详细状态。

### 4.3 Tier 2：当前 Stage 设计与实施

文件形态：

```text
STAGE_<NN>_<FEATURE>_DESIGN.md
STAGE_<NN>_<FEATURE>_IMPLEMENTATION_PLAN.md
docs/superpowers/plans/<date>-<feature>.md
```

职责：

- Design：架构、数据流、权限、安全、错误、验收边界；
- Stage plan：阶段范围、任务顺序、Acceptance Criteria、Remaining Risks；
- Detailed plan：可执行的 TDD 步骤、文件、接口、命令和提交边界。

相同内容不在三处逐字复制。Stage plan 链接详细 plan；详细 plan 不承担项目顶层真源。

### 4.4 Tier 3：交付证据

路径：

```text
project-docs/08-implementation/evidence/
```

保留：

- 外部系统写入和清理证据；
- 安全/权限/隔离/并发/迁移证据；
- 真实 PostgreSQL、Provider、Telegram、浏览器与部署证据；
- 最终回归命令、结果、环境边界和 skipped tests。

证据文档必须脱敏，不能保存 token、原始 prompt/response、真实 Telegram ID、数据库 URL 或用户业务原文。

### 4.5 Tier 4：历史 Stage

Stage02–Stage08 的 source/design/BDD/SDD/acceptance/evidence 继续保留，因为它们解释：

- schema 和 migration 的来历；
- 安全边界为何存在；
- 已发生的外部操作和清理；
- 回归测试的业务意图。

历史 Stage 默认不读。只有修改其拥有的 schema/API/模块，或调查回归时才按索引进入。

## 5. 执行临时物与 Git 策略

### 5.1 永不提交

以下目录是可再生执行缓存：

```text
.superpowers/
.local/
.worktrees/
mini-app/node_modules/
mini-app/dist/
```

`.superpowers/sdd/` 中的 brief、report、review package、ledger 和 patch 只服务于当前执行会话。最终事实必须进入 commit、Stage plan 的 `Current Progress` 或 evidence 文档；执行缓存本身不作为长期真源。

### 5.2 本轮确认删除的 tracked 冗余

审计结果：

- 治理前 `.superpowers/sdd/` 有 249 个 tracked 文件；
- 内容为 Stage08/09 的 task brief、task report、review report、临时 diff/patch 和 flat progress；
- 当前长期证据已存在于 Git commits、`docs/superpowers/plans/` 与 `project-docs/.../evidence/`；
- 这些文件仍被保留在 Git 历史中，取消当前版本跟踪不会破坏追溯。

因此本轮执行：

1. `.gitignore` 增加 `.superpowers/`；
2. 从 Git index 移除全部 `.superpowers/`；
3. 不删除当前机器上的 ignored SDD workspace，避免打断当前开发；
4. handoff 不再枚举旧 `.superpowers/sdd/*` dirty files。

### 5.3 本轮明确保留

- `backend/alembic/versions/*`：数据库历史，禁止整理式删除；
- `project-docs/08-implementation/evidence/*`：除非证明完全重复且无引用；
- `deploy/stage03/*`、`deploy/stage07-acceptance/*`：历史环境和清理审计仍引用；
- 根目录 `postgresql/`、`redis/`、`systemd/`：当前 `scripts/verify-native-data-core-assets.sh` 仍直接使用；
- `docs/superpowers/plans/*` 和 `specs/*`：已批准设计/计划，不是运行缓存；
- 旧 worktree 的未跟踪截图和用户 dirty files。

## 6. README 与索引规则

`project-docs/README.md` 只承担：

1. 当前阅读顺序；
2. 当前 Stage 文件；
3. 历史 Stage 入口；
4. 文档生命周期规则链接。

`project-docs/08-implementation/README.md` 只承担：

1. 当前 Stage implementation 入口；
2. Stage02–Stage08 历史状态表；
3. 修改历史 Stage 时的查阅规则。

禁止把每个历史 Stage 的几十个文件平铺到顶层 README。详细文件可通过文件名搜索和各 Stage 自身 Source/Module Index 查找。

## 7. 防漂移更新协议

每次功能交付只更新以下位置：

1. 当前 Stage implementation plan 的 `Current Progress`；
2. 当前 evidence 文档；
3. 当前 handoff 的 commit/branch/下一任务；
4. `AGENTS.md` 的一段式概览——只在阶段状态变化时更新；
5. `IMPLEMENTATION_SOURCE_OF_TRUTH.md`——只在产品边界或当前阶段变化时更新。

不得为了同一个测试结果更新五个历史 Progress/Checklist/README。

任何完成声明必须能够从：

```text
Requirement/Acceptance row
-> test or real observation
-> evidence document
-> commit
```

逐级定位。

## 8. 代码结构规则

- 新代码优先进入现有领域目录，不创建 `stageXX_misc.py` 或无边界 util。
- Stage 前缀可以用于稳定 API/schema/迁移兼容，不用来复制相同业务逻辑。
- 同步和 SSE assistant 必须共享授权、scope、幂等和执行服务。
- 测试文件按拥有模块放置；一次性 smoke runner 放 `backend/scripts/` 并必须有脱敏输出合同。
- 删除代码前必须用 `rg` 查找引用、运行拥有该代码的测试，并在 evidence 中记录删除理由。

## 9. Acceptance Criteria

1. 新会话从根 `HANDOFF.md` 能定位唯一活动 worktree 和当前计划。
2. `project-docs/README.md` 与 implementation README 不再宣称 Stage06/07 是当前阶段。
3. `.superpowers/` 不再有 tracked 文件，新生成的 SDD workspace 被 Git 忽略。
4. Stage02–Stage08 的迁移、验收和外部证据保持可访问。
5. 根目录 legacy deployment assets 只有在引用解除和测试迁移后才可删除。
6. 当前 SSE 功能继续在独立分支开发，不污染旧 dirty worktree。
7. `git diff --check` 和相关文档链接检查通过。

## 10. Remaining Risks

- 历史 Stage 文档仍有 300+ 文件；本轮通过索引降噪而不是批量移动，避免破坏引用。
- 部分历史 plan 仍引用 `.superpowers/sdd/*`，这些链接只描述当时执行过程；Git 历史仍可恢复，但它们不再是当前 checkout 的文件。
- 根目录与 `deploy/stage09-native/` 有少量部署资产重复；现有测试仍引用两套路径，需单独迁移计划后才能删除。
- 旧 `stage07-mini-app-ui` worktree 含用户 dirty files，必须等用户内容归属明确后再清理。
