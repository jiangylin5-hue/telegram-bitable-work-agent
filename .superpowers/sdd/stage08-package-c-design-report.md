# Stage08 Package C Context Engineering 设计报告

## Status

- Status：`DONE — documentation-only`。
- Date：2026-07-18。
- Scope：Package C 详细 BDD/验收、完整实施计划与 C1 task brief；未实现生产代码或测试。
- User direction：开发优先。B5 package-level closure 保持 pending，但不阻塞 C 的技术设计/C1 开发；不得据此宣称 Package B 已关闭。
- Operations：未进行外部调用、Provider/Telegram/network 操作或 git 操作。

## 1. 已核对真源与当前实现

本设计基于以下已读材料与接口：

- Stage08 source、architecture、SDD、data/API/security、test、acceptance、implementation 文档；
- `docs/superpowers/specs/2026-07-16-stage08-complex-agent-runtime-design.md`；
- Package A `ExecutionBudget`、`ExecutionPlan`、`ToolInvocation`、`RedactedToolResult`、PolicyGate、Tool Gateway、runtime service/API 与 evaluator isolation；
- Package B BDD/plan、B1-B4 brief/report/review，尤其 B4 的 exact group boundary；
- `MemoryScopeProjection`、`MemorySourceRef`、`MemoryMaterializationProjection`、`read_memory_projection`、`list_memory_projections` 与 group source validator；
- Stage06 `authorize_workspace_action`、digital employee scope、`list_view_records`、`read_record_for_actor`、relation safe-cell 与 field/view permission 投影；
- `Stage06TelegramBinding` 与历史 `Message` 模型；
- Stage08/Stage06 live evaluator 的 per-case process isolation 与 parent-side redacted DTO validation。

关键现状结论：

1. `RedactedToolResult` 故意只保留 refs/counts/visible keys，不包含业务事实；C1 不应破坏 A 的脱敏合同来承载上下文。
2. Stage06 已有安全的 view/record/relation 投影，可作为实时表格证据读取边界；直接 ORM `record.values` 不能作为 C1 evidence 来源。
3. B2 `read_memory_projection` 已重验 membership、TTL、source version、field visibility 与 scope，是 C1 复用 Memory 的正确入口。
4. B4 只允许 `telegram_message + group_candidate_projection + stage06-binding:<uuid>`，且不保存原文；但历史 `Message` 仍有 raw columns，B4 明确不读取或修复它们。
5. `Stage06TelegramBinding` 没有群消息内容版本/群类型持久化；B4 的 group/supergroup 证明只存在于短命 trusted adapter。C1 因此不能凭 binding 自行构建历史窗口。
6. 当前 Stage08 evaluator 已能隔离真实 Provider case，但 C1 无需也不得调用 Provider；其设计仅借鉴 strict/redacted DTO 与 bypass revalidation 原则。

## 2. 方案比较

### 方案 A：扩展 Tool Gateway 的 `RedactedToolResult` 为事实载体

优点：表面上复用 Package A 调用链。缺点：会改变已复审的 A 脱敏合同；counts/refs 与完整事实的安全级别不同；混合 Memory/general advice 也没有现成 tool action。该方案会引入 API/ticket 合同连锁变化，未获授权。

### 方案 B：纯内部 typed context compiler（采用）

新增 strict contracts 与 internal service，复用现有安全读 service；plan 只冻结选择/上限，compose 时重读；返回调用栈内 evidence pack，不持久化、不注册 API。该方案能在不改变 schema/API/permission 的情况下验证 C1 核心算法，并为 E 的正式 ticket/Coordinator 集成提供类型化边界。

### 方案 C：一次性建立持久化 context snapshot + query API + 群历史

优点：表面完整。缺点：立即触发 schema/API/permission/retention/Telegram ingestion 变化，也会把历史 raw Message 风险带入新路径，违反用户指定的 C1 边界。该方案被拆为未来独立门禁：C2 只讨论群窗口/历史合同，持久化/API 是否需要仍须单独确认。

## 3. 最终 C1 架构决定

```text
verified Actor + ContextPlanningRequest
  -> current employee/member eligibility
  -> customer/project visible single-hop relation resolver
  -> view/source selection + strict ContextBudget
  -> ContextPlan (not authority, not ticket)
  -> consumption-time authority/relation/version reread
      -> list_view_records + read_record_for_actor
      -> read_memory_projection (non-group, platform-record source only)
      -> general_advice policy marker
  -> deterministic normalize / budget / omission
  -> typed ContextPack
  -> ID-free evidence label renderer
```

### 3.1 权限策略

- employee configured workspace/table/view/action scope、caller active membership 与 assigned grant 全部重验；
- customer/project ID 只收窄。两者同时出现时，必须能在当前 actor 安全投影里看到单跳 `linked_record` 关系；
- view 必须位于 employee scope，且当前 actor 可读；
- plan 不是 capability。compose 再次解析 actor/employee/business scope/view version；
- 单个 record/Memory 漂移只产生固定 omission；authority/relation 漂移使 plan 整体 fail closed。

### 3.2 数据策略

- table evidence：仅现有 view projection，保持 view order 与 limit；记录再重读 current version/visible fields；
- Memory evidence：逐项调用现有安全读取，严格匹配请求的 customer/project 维度；C1 排除 group-scoped/source Memory；
- general advice：只生成 `{"internal_evidence":false}` policy marker，不生成回答；
- C1 不读取文件、retrieval chunk、Message 或群聊窗口。

### 3.3 预算与可解释性

- 硬上限：table 20、Memory 12、evidence 24、单 item 2000 chars、总 12000 chars；
- canonical JSON：sorted keys、compact separators、Unicode、拒绝 NaN；
- string/list/depth 固定限制；只加入完整 JSON item；
- evidence ID 是运行内 label ordinal，不含数据库 ID；
- omission 只含固定 reason/count；renderer 不输出 UUID scope 值、source refs 或 permission snapshot。

### 3.4 与 Package A/E 的关系

C1 不增加新的 ticket action，也不绕过 Stage08 “read-only 最终应有 ticket”的阶段合同。它是可独立测试的 compiler 内核；正式的 ticket/run/Coordinator 调用归 Package E 集成。任何面向用户 API 也不在 C1 建立。这样避免为了测试 context algorithm 提前改变 API/permission contract。

## 4. C2 独立合同门禁

C2 在任何代码前必须确定：

- trusted current-window adapter 的生产者与输入 DTO；
- active binding/member/workspace 与 group/customer/project scope 交集；
- message ordering、duplicate、edit/delete、source version；
- current window 与 history 的 item/age/char 上限；
- 时间衰减的精确公式与稳定 tie-break；
- raw text 的短命处理、禁止持久化、历史 `Message` raw retention 治理；
- 删除/撤权/TTL 的消费前重读；
- 是否需要 schema/API/permission/ingestion 变化及对应独立用户确认；
- local PostgreSQL、脱敏与 no-external-call evidence。

在此门禁前，C1 与任何 C1 测试不得 import/query `Message` 来读取上下文，也不得建立 group context API。

## 5. 交付文档

- `project-docs/08-implementation/STAGE_08_PACKAGE_C_CONTEXT_BDD_AND_ACCEPTANCE.md`
- `docs/superpowers/plans/2026-07-18-stage08-package-c-context-engineering.md`
- `.superpowers/sdd/stage08-package-c-task-c1-brief.md`
- `.superpowers/sdd/stage08-package-c-design-report.md`

没有修改现有文档、生产代码或测试。

## 6. Verification

文档级核对项：

- 四个要求路径均已创建，且仅这四个新文件属于本任务；
- C1 files/interfaces、source/label/type/scope/version、RED/GREEN cases 与精确 PowerShell 命令均已给出；
- C2 明确为独立 contract gate；
- 文档明确禁止 C1 读取 Message raw text/history 或新增 API；
- 文档明确 B5 pending 风险与 development-first 非阻塞决定；
- 文档明确无 migration/permission/API/Telegram/LLM/RAG/LangGraph 变化；
- 无未决占位符或虚构测试通过数量。

## 7. Skipped tests、风险与清理

- Skipped tests：本任务只写设计文档，未实现或运行 C1 测试；不得把文档检查当作 backend 验收。
- Remaining risks：B5 未关闭；C2 raw-retention/群版本合同未确认；C1 尚未纳入正式 read-only ticket/Coordinator；真实 Provider 与最终 API evidence label 均未验证。
- Temporary cleanup：无临时脚本、测试数据、数据库对象或 artifacts；无需清理。
- Git：未执行 stage、commit、reset、checkout、clean 或其他 git 操作。
