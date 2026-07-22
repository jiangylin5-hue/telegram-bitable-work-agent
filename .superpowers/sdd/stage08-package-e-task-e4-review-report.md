# Stage08 Package E — E4 Assistant Query API 独立审查报告

## Status

- Task: `E4 strict assistant-query API independent review`
- Result: `CHANGES REQUIRED`
- Date: `2026-07-22`
- Findings: `0 Critical / 1 Important / 0 Minor`
- Closure recommendation: E4 暂不能关闭，Package E 暂不能进入最终收口。
- Boundary: 本轮仅审查 `POST /api/stage08/assistant/query`、其 strict schema、router registration 和聚焦测试；未修改业务实现，未调用任何外部系统。

## Critical

无。

## Important

### I-01：`completed` 的幂等重放丢失已安全返回的 answer/citations

**Evidence**

- `backend/app/api/routes/stage08_collaboration.py:142-149` 在首次成功后仅持久化 `status` 与 `draft_id`。
- `backend/app/api/routes/stage08_collaboration.py:308-338` 在 replay 时将 `answer` 固定重建为 `None`、`citations` 固定重建为空集合。
- 审查者用合法 `AssistantQuerySafeView(status="completed", answer="原始完整回答", citations=[general_advice])` 做了一次无网络的针对性实测：首次请求返回 `200` 且带 answer/citation；相同 key、相同语义的第二次请求仍返回 `200 completed`，但 answer 变为 `null`、citations 变为 `[]`。
- 现有 API 回归只用 `degraded` 重放覆盖这条路径；`degraded` 本来就要求无 answer/citation，因而无法捕获该缺陷。

**Impact**

- 违反 E4 brief 和 E 合同中“同 key、同语义重放返回既有安全结果”的要求。
- 客户端因超时重试时会获得与首次不同的响应；`completed` 却没有已完成的回答，会产生可见的业务结果丢失和误导状态。

**Required correction**

- 先在已批准合同内统一“response reference 仅 status/draft ref”与“replay 返回原安全结果”这两条目前无法同时满足的规则。
- 修正后必须新增 `completed` 且带 answer/citations 的首次/重放用例，并验证当前 member/employee/target 撤权后仍拒绝重放。
- 不能通过让 replay 重跑 graph 来规避，因为那会破坏幂等及 draft 副作用边界。

## Minor

无。

## 其他审查结论

- Request schema 仅接受批准的 7 个字段，`extra="forbid"` 配合自定义 `APIRoute` 将非法 body 固定映射为不回显输入的 `422`。
- Route 使用 verified identity，在幂等查找之前检查 active workspace member、`digital_employee.invoke`、active/in-workspace employee、employee grant/action/base 与可选 target readability；replay 也经过同一轮当前 scope 重验。
- Graph 输入只由服务端 `Stage08CollaborationContractFactory.command(...)` 构造；请求 JSON 无法直接注入 authority/provider/budget/tool/state/draft values。
- Service result 会经 `validate_assistant_query_safe_view` 做 exact-type/exact-field 重建；针对 `model_construct` 夹带隐藏字段的 forged view 会固定返回非泄露 `500`。
- 意外异常路径对 SQLAlchemy session 执行 rollback；可预期的请求、scope、not-found 和幂等冲突分别映射到 `422/403/404/409`，未发现 raw exception/private payload 回显。
- `stage08_collaboration.router` 对外仅暴露 `POST /api/stage08/assistant/query`；未发现 E4 新增 schema/migration/permission/Provider/Telegram/deployment 行为。
- 本地 PostgreSQL 用例不是 `SELECT 1` 连通性烟测；源码与 fresh run 均覆盖 safe draft/replay、Gateway rollback、scope revoke/root cleanup 及两 session 行锁阻塞。该文件主要是 E3 真实 PostgreSQL 回归，E4 路由层事务仍主要由 API 用例中的 session spy 验证。

## Verification

### E4 API focused

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/api/test_stage08_collaboration_api.py
```

Result: `24 passed in 15.88s`

### Collaboration focused regression

```powershell
python -m pytest -q -W error -p no:cacheprovider `
  tests/unit/test_stage08_collaboration_contracts.py `
  tests/unit/test_stage08_collaboration_graph.py `
  tests/unit/test_stage08_collaboration_service.py `
  tests/api/test_stage08_collaboration_api.py
```

Result: `103 passed in 12.54s`

### Real loopback PostgreSQL / pgvector regression

```powershell
python -m pytest -q -W error -p no:cacheprovider `
  tests/integration/test_stage08_collaboration_postgres.py
```

Corrected fresh result: `2 passed in 5.39s`。审查者首次动态拼接 DSN 时误读 compose JSON environment 结构，产生“no password supplied”的审查命令配置错误；改用同一 compose 中的 loopback test DSN 后 fresh run 全部通过，该首次失败不是产品代码失败。

### Targeted completed replay reproduction

Result:

```text
first  -> 200, status=completed, answer=<present>, citations=1
replay -> 200, status=completed, answer=null,      citations=0
```

## External systems and Git state

- 未调用 OpenRouter、Telegram、webhook、部署、生产数据库或任何外部 HTTP 系统。
- 仅读取/运行了本机 `127.0.0.1:55432` 的可丢弃 pgvector PostgreSQL 回归。
- 未执行 Git stage/commit/reset/checkout/clean/push。

