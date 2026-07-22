# Stage08 Package C Task C2：群最近窗口与历史上下文任务简报

## Status

- Task status：proposed / requires explicit user confirmation before implementation。
- Authority：只有用户确认 C2 BDD 的 D1–D6 和独立 D3 schema/data-contract 后，本 brief 才能转为 implementation authority；当前不授权代码。
- Current Progress：本 brief、BDD 和 plan 已完成设计；未创建业务代码、测试、migration、API、外部调用或 git 变更。

## Objective

在 active chat_user binding、workspace member、employee/caller scope 与 C1 customer/project scope 的交集内，从 D1/D3 批准的本地 message projection 生成独立、短命的 GroupContextPlan/GroupContextPack，提供 bounded recent window 和无 query 的 deterministic time-decay history。

## Mandatory Preconditions

1. 用户确认 D1 原文治理、D2 数值/retention 与 unavailable/partial/available status/omission matrix、D3 version/edit/retention schema、`received_at` initial event-time 语义、普通群 `best_effort_group_deletion` 或 `strict_group_lifecycle` 与旧行策略、D4 mapping、D5 唯一 authority producer 与不可序列化/re-read 边界、D6 label/type/evidence-ID/scope category/C3 merge。
2. D3 migration 在 disposable local PostgreSQL 已验证；缺 lifecycle/version 的旧行默认不可读。
3. 确认后的 task brief 必须写入最终值；实施者不得从推荐 profile 猜测值。

## Fixed Boundaries

- 不读 Telegram 网络、export、webhook/outbox/audit/log 补齐消息；不调用 Telegram、Provider/LLM、HTTP、RAG、Redis、LangGraph。
- 不修改 C1 v1 或偷渡 group evidence 到现有 label；C3 才能合并。
- 不写 Memory/candidate/outbox/AgentRun/cache、API route、role/action、前端或原始内容。
- 不输出/记录 raw text/caption/normalized text、Telegram/chat/message/update ID、binding/source ref、UUID fragment、content hash、prompt/response。
- scope/lifecycle/version/retention 缺失或漂移即 unavailable/omission；不回退其它群、workspace 或全历史。

## Expected Files Only After Approval

- backend/app/runtime/stage08_group_context_contracts.py
- backend/app/services/stage08_group_context.py
- D3-approved model/migration files
- backend/tests/unit/test_stage08_group_context_contracts.py
- backend/tests/unit/test_stage08_group_context_service.py
- backend/tests/integration/test_stage08_group_context_postgres.py
- project-docs/08-implementation/evidence/stage08-package-c2-group-history.md
- .superpowers/sdd/stage08-package-c-task-c2-report.md

## Acceptance

- 未确认路径无 raw-column read、无 external call、无持久化写；
- confirmed path 的 count/age/decay/chars/order 完全确定；
- version/delete/retention/binding/member/relation drift 在 real local PostgreSQL fail closed；
- evidence/renderer/audit/log 无正文或 identity/source carrier；
- C1 focused regression 保持；C2 PASS 不表示 C3、Package C、Stage08、真实 LLM 评测或部署完成。
