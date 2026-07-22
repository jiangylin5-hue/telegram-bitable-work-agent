# Stage08 Package C Task C2 设计报告

## Status

- Design status：completed-design-only / implementation blocked pending explicit user confirmation。
- Code/test/migration/API/external status：未实施、未执行、未调用。
- Overall：Package B 已关闭；C1 已 task-level PASS；C2、C3、Package D–F、真实 Provider 评测和生产部署仍未完成。

## Read Sources

本设计核对了 Stage08 真源、复杂 Agent 架构、SDD、数据/API/安全合同、测试/验收文档、Package C BDD、C1 brief/report/review、Stage03 ingress/binding、Stage07 Telegram identity/binding 文档及 B4 group Memory source/brief/report。

## Current-State Findings

1. Message 持有 raw text/caption/normalized text 与 received_at，但无 content version、edit/delete/revoke/retention；历史安全 reread 没有必需事实。
2. Stage06TelegramBinding 能支持 B4 的 active chat_user/member 验证，却没有 version、durable group type 或 C1 customer/project mapping。
3. B4 TrustedGroupMessageInput 仅为高置信 Memory candidate 建立短命 opaque source，明确不读历史 Message，不能成为 C2 history adapter。
4. C1 被复审为 Message-free、group-free、read-only Memory；C2 必须独立，不能扩大 C1。
5. Stage03/07 的 webhook/历史 raw retention 不构成 Stage08 群上下文治理同意。

## Design Decisions

- C2 保持独立 GroupContextPlan/Pack，C3 后续决定如何与 C1 合并。
- 在无 query contract 和 Package D 索引前，history 只按 deterministic time decay；不做语义/关键词/LLM relevance。
- 正文只作为短命 fragment；observability 只记录固定状态与计数桶。
- D1–D6 都是用户 gate，尤其 D3 不能由 service 或 fixture 弥补。

## Consistency Check

设计满足 Stage08 的“最近窗口 + 必要时历史时间衰减”目标，同时拒绝全群注入、默认 raw retention、跨 scope、无版本旧文与外部写入。未引入 Milvus、pgvector、RAG、LangGraph、Provider、Telegram network 或 API；没有以 C2 设计替代 C3/Package C/Stage08 验收。

## Created Files

- project-docs/08-implementation/STAGE_08_PACKAGE_C2_GROUP_HISTORY_BDD_AND_ACCEPTANCE.md
- docs/superpowers/plans/2026-07-19-stage08-package-c2-group-history.md
- .superpowers/sdd/stage08-package-c-task-c2-brief.md
- .superpowers/sdd/stage08-package-c-task-c2-design-report.md

本设计任务未修改生产代码、测试、migration、route、配置、外部状态或 git history。
