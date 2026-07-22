# Stage08 E4 幂等安全重放投影决定

## Status

- Decision status：`implementation correction`
- Date：2026-07-22
- Scope：`POST /api/stage08/assistant/query` 的同键同语义 idempotency replay
- Trigger：E4 独立审查复现首次 `completed` safe view 有 answer/citations，但现有 response reference 仅保存 status/draft ref，重放会错误丢失前述安全结果。

## 决定

同一语义、完成态的重放必须返回首次的**完整安全视图**，且不得重新运行图。

为此，idempotency `response_ref` 可持久化一个 versioned、严格可重建的
`AssistantQuerySafeView` replay projection，仅含：

- `version`；
- terminal `status`；
- 已有 max-2000 的安全 `answer`；
- 每条 citation 的稳定 `ordinal + label`；
- 固定 `degradation_codes`；
- 可选既有 `draft_id`。

它不得含 query、C1/C2/C3/D4 material、群正文/digest、Memory/RAG payload、
source/chunk/record/table/field UUID、provider raw output/error、authority、tool
input/output、audit payload、token、score/vector 或 CoT。`draft_id` 是已存在的
公开 safe-view reference；除此以外不得增加内部标识。

重放前仍按 E4 合同重新验证 active member、employee、`digital_employee.invoke`
和 target read scope。投影 shape/version 不合法时返回 409，绝不降级为猜测的
空 answer 或重新运行 graph。

## 不变项

- 不新增 schema/migration、public request/response field、权限角色、Provider、
  Telegram、Webhook 或部署行为；
- `AgentRun`、audit、outbox、log 仍绝不记录 answer/citation 内容；
- response projection 不是 Memory、RAG index 或长期知识源，不能作为后续
  Agent context；
- 仅修复同键重放语义，不改变不同语义 409 或 current-scope revoke deny。

## 验收

1. 首次与同键同语义重放返回完全相同、严格重建的 safe view，且图只运行一次；
2. response reference 纯白名单投影；查询/私有内容/内部 ID 扫描不到；
3. revoke 后重放仍 403；同键异语义仍 409；投影 forge/shape drift 409；
4. API、E1-E4 collaboration 和 disposable local PostgreSQL 主路径回归通过。
