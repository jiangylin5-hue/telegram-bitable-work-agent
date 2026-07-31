# Stage12-F Durable Action 与确认 UI 实施计划

## Status

- Status: completed locally; production activation and final Stage12 campaign remain closed
- Scope: strictly Stage12-F
- Source of truth: `project-docs/08-implementation/STAGE_12_F_DURABLE_ACTION_UI_SOURCE_OF_TRUTH.md`
- Rule: TDD；每项完成后勾选并记录验证证据；若需偏离已批准 schema/API/权限/Tool Gateway 边界，立即暂停并向用户确认

## Tasks

- [x] 1. 新增 Stage12-F contracts、`agent_objective_runs` / `agent_action_slots` models、repository 与 `20260730_0036` migration；覆盖状态、JSON/hash/FK/unique/index、upgrade/downgrade 和 Alembic single head。
- [x] 2. 实现 AuthorizedCandidateSet resolver 与数据依赖 ActionSlot expansion；覆盖空候选、多候选、字段权限、required fields、current record version、多个提醒和局部冲突。
- [x] 3. 实现 encrypted action private payload、独立 durable action command/outbox/topic/worker、lease/retry/deadline/idempotent proposal persistence；embedded 与 in-memory Redis Streams recovery/ack-once 证据通过，真实 Redis 因本机无 listener/URL 明确跳过。
- [x] 4. 将 Action worker 接入现有 `AgentControlledToolGateway`；只生成 pending draft 或 blocked/pending notification，确认前 Record mutation 与 Telegram send 均为 0。
- [x] 5. 实现 objectives/actions/evidence/confirm/reject API；每次读取和确认重新授权，confirm 校验 proposal/record version、editable fields 和新幂等键，reject 安全终止。
- [x] 6. 扩展 safe SSE contracts/projector，保证 Objective/Action 事件最小化、严格顺序、Last-Event-ID 恢复和 terminal 后无业务事件。
- [x] 7. 扩展 Mini App agent-run parser/reducer/API/CollaborationWorkbench，显示 Objective timeline 和 proposal review/edit/confirm/reject；覆盖错误恢复、无伪完成、桌面/Telegram Mini App 响应式与可访问性。
- [x] 8. 在隔离 workspace 执行真实 LLM Action proposal、PostgreSQL 和授权浏览器点击验收；真实 Redis 经检查不可用并记录为激活前风险；未执行真实业务/生产写入或 Telegram 发送。
- [x] 9. 运行 Stage12-F focused、backend unit/API、full backend、Mini App unit/build、Black、compileall、Alembic、diff/credential scan；记录 skipped tests 与 remaining risks。
- [x] 10. 新增 Stage12-F acceptance/evidence，并同步 `AGENTS.md`、`HANDOFF.md`、implementation truth、Stage12 index 和 `Current Progress`。

## Required Evidence

```text
blind_action_slot_exact
authorized_candidate_resolution
objective_action_persistence
private_payload_redaction
action_worker_retry_and_recovery
pending_confirmation_only
record_version_conflict
scope_drift_denied
confirm_reject_idempotency
sse_resume_and_terminal_order
mini_app_click_acceptance
real_provider_action_proposal
telegram_send_count = 0
pre_confirmation_record_mutation_count = 0
```
