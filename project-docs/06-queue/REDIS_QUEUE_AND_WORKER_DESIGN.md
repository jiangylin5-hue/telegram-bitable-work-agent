# Redis Queue And Worker Design

## Status

- Document status: queue design draft
- Scope: Redis queue、job id、重试、失败处理、worker、幂等
- Current Progress: 2026-07-04 完成第一版 Redis 队列和 worker 设计。

## 1. Queue Purpose

Redis 队列用于承载不适合在 HTTP 请求中同步完成的任务：

- Telegram 消息意图识别。
- AI 草稿生成。
- Telegram 通知回传。
- 日报生成。
- provider execution。
- readback polling。
- 风险统计。

## 2. Queue Technology

第一阶段采用 Redis。

推荐模式：

- Redis Streams 或可靠 job queue。
- 每个任务有明确 payload schema。
- 每个 worker 幂等。
- 失败进入 retry，超过阈值进入 dead letter。

Temporal 作为后续升级候选，不作为第一阶段强依赖。

## 3. Job Envelope

所有 job 使用统一 envelope：

```text
job_id
job_type
trace_id
idempotency_key
entity_type
entity_id
payload
attempt_count
max_attempts
status
created_at
scheduled_at
started_at
finished_at
last_error
```

## 4. Job Types

| Job Type | Worker | Purpose |
| --- | --- | --- |
| `telegram.notify` | notification worker | Telegram 回传消息 |
| `agent.intent_extract` | agent worker | 消息分类和路由 |
| `agent.generate_draft` | agent worker | 生成服务草稿 |
| `agent.daily_report` | reporting worker | 生成日报 |
| `execution.recharge` | execution worker | 受控充值执行 |
| `execution.bm_invite` | execution worker | 受控 BM invite |
| `execution.card_binding` | execution worker | 受控绑卡 |
| `readback.balance` | readback worker | 余额回读 |
| `risk.scan` | risk worker | 风险扫描 |

## 5. Idempotency

每个 job 必须有 `idempotency_key`。

示例：

- Telegram intent: `intent:{message_id}`。
- Recharge execution: `recharge:{service_record_id}`。
- BM invite: `bm_invite:{account_id}:{email}:{draft_id}`。
- Card binding: `card_binding:{account_id}:{payment_profile_id}:{draft_id}`。
- Daily report: `daily_report:{role}:{date}`。

Worker 开始前必须检查：

- job 是否已完成。
- 对应 execution 是否已存在。
- service record 状态是否仍允许执行。

## 6. Retry Policy

默认：

- max attempts: 3。
- backoff: exponential。
- retryable errors: timeout、provider_unavailable、temporary_network、rate_limit。
- non-retryable errors: permission_denied、validation_failed、state_conflict、risk_blocked。

## 7. Dead Letter

超过重试次数后：

- job status = dead_letter。
- 写 `ops_audit_events`。
- 关联业务记录进入 failed 或 manual_review。
- 通知相关角色。

## 8. Worker Boundaries

Worker 可以：

- 调用 service layer。
- 调用 Agent runtime。
- 调用 controlled execution gateway。
- 写 job log。

Worker 不可以：

- 绕过 service layer 直接改核心表。
- 在没有 confirmation 的情况下执行真实写入。
- 忽略 idempotency。

## 9. Execution Worker

Execution worker 只处理已确认且通过 execution gate 的任务。

执行前检查：

- service_record status。
- idempotency。
- permission snapshot。
- risk flags。
- provider availability。

执行后写：

- execution_log。
- service status。
- audit event。
- next readback job。

## 10. Agent Worker

Agent worker 处理：

- intent extraction。
- draft generation。
- daily report。

Agent worker 输出必须由 schema validator 验证。验证失败时进入 manual review，不创建可执行草稿。

## 11. Acceptance Criteria

- 所有 job 有 job_id、trace_id、idempotency_key。
- Worker 幂等。
- 重试和 dead letter 明确。
- 真实执行只由 execution worker 在确认后触发。
- 失败能回写业务状态和 audit。

