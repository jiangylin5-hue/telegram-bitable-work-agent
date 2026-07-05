# Stage 02 Source Of Truth

## Status

- Document status: frozen stage source of truth (Stage 02 closed)
- Scope: Stage 02 后端内核、充值闭环、账户库存、客户/公司日报的阶段边界、执行规则和验收原则
- Current Progress: 2026-07-06 Stage 02 正式关闭。验收证据以 `STAGE_02_FINAL_ACCEPTANCE_REPORT.md` 为准（fresh online smoke 17 passed、全量 102 passed、迁移至 `20260705_0009`），成果已提交至 `stage-02-backend`（`a709f2c`）。本文件转为历史真源，不再扩展 scope；后续方向见 `STAGE_03_DIRECTION_PROPOSAL.md`。2026-07-05 完成 Stage 02 最终收束审计：`STAGE_02_FINAL_ACCEPTANCE_REPORT.md` 汇总真源、计划、SDD、BDD 和验收清单证据；`STAGE_02_BDD.md` 已补齐每个 scenario 的 `Test mapping`；fresh online smoke 为 17 passed，全量 `pytest tests -v` 为 102 passed。Stage 02 可冻结提交；真实 Telegram/provider/OpenRouter、生产 worker、托管数据库演练和视图分页 hardening 继续保持 Stage 02 out of scope，并进入 Stage 03 candidate 文档。

## 1. Stage Goal

Stage 02 的目标是搭建一个可运行、可测试、可审计的后端内核，并完成三条业务垂直切片：

```text
Backend Kernel
-> Recharge Vertical Slice
-> Account Inventory Vertical Slice
-> Customer And Company Daily Reporting Vertical Slice
```

这里的“完成”不是口头完成，而是每条切片都必须：

- 有 PostgreSQL 记录。
- 有 Bitable view API 可查询。
- 有权限过滤。
- 有 audit event。
- 有 outbox event 或明确同步边界。
- 有测试命令和测试结果。

## 2. Confirmed User Choices

用户确认的选项是 `ABC A A A A`：

| Question | Decision | Stage 02 Meaning |
| --- | --- | --- |
| 第一阶段主闭环 | A+B+C | 充值闭环、账户库存、客户/公司日报都进入 Stage 02 |
| Telegram 接入 | A | 先 mock webhook |
| 外部执行 | A | 先 mock/sandbox provider |
| 多租户 | A | 第一版不做 `tenant_id` |
| DB 与 Redis 一致性 | A | 采用 outbox table |

## 3. In Scope

Stage 02 必做：

- 初始化有效 Git 仓库。
- 创建 `backend/` 后端项目骨架。
- FastAPI 应用入口。
- SQLAlchemy 2.x model base。
- Alembic migration setup。
- PostgreSQL schema for Stage 02 core tables。
- Bitable view API。
- Permission and field masking kernel。
- Audit event service。
- Outbox event table and dispatcher。
- Mock Telegram ingestion API。
- Mock message router agent。
- Service draft and human confirmation state machine。
- Execution ticket service。
- Mock recharge execution and readback。
- Account inventory and assignment flow。
- Customer/company daily report generation。
- Stage 02 end-to-end tests and acceptance checklist。

## 4. Out Of Scope

Stage 02 不做：

- 真实 Telegram Bot webhook。
- 真实 Meta/BM/卡台/充值 provider 写入。
- 真实资金或账户操作。
- Telegram Mini App 前端。
- 完整 Web 管理台。
- 多租户 `tenant_id`。
- Temporal。
- 完整向量检索系统。
- 完整财务账本、发票、对账单、结算。
- AI 自动投放优化。
- raw card number / CVV / 完整卡图存储。

## 5. Stage Boundaries

开发人员不得越界：

- 如果某个需求需要真实 Telegram、真实 provider、真实资金账户动作，必须停止并记录为后续阶段。
- 如果某个需求需要 `tenant_id`，必须停止并记录为后续阶段。
- 如果某个功能无法落到 Bitable table/view/status/audit，不得实现。
- 如果 Agent 需要确认动作，必须通过 human confirmation 和 `execution_ticket`，不能让 Agent 自己确认。

## 6. Progress Update Rule

每完成一个子阶段，必须更新：

1. 本文档的 `Current Progress`，只写阶段级进展。
2. [Stage 02 Progress](STAGE_02_PROGRESS.md)，写具体子阶段总结。
3. 对应实现计划里的 checkbox 状态。

子阶段总结必须包含：

- Completed。
- Changed files。
- Tests run。
- Test result。
- Not done。
- Risks / follow-up。

## 7. Acceptance Rule

不允许说“已完成”除非有证据：

- 对应测试命令已运行。
- 输出已检查。
- 验收标准逐项核对。
- 未测试项说明原因。

Stage 02 最终验收必须引用：

- pytest 命令。
- Alembic migration smoke result。
- Bitable view API integration result。
- E2E test result。
