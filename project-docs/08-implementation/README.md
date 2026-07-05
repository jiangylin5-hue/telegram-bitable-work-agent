# Stage 02 Implementation Docs

## Status

- Document status: active implementation index
- Scope: Stage 02 后端内核与垂直切片开发入口
- Current Progress: 2026-07-05 Stage 02 实施文档仍为当前已开发阶段入口；新增 Stage 03 candidate 文档入口，用于下一阶段真实集成与运行时基础，等待用户确认后转 active。

## 1. Read Order

Stage 02 开发只需要按这个顺序阅读：

1. [Stage 02 Source Of Truth](STAGE_02_SOURCE_OF_TRUTH.md)
2. [Stage 02 Backend Kernel And Vertical Slices Implementation Plan](STAGE_02_BACKEND_KERNEL_AND_VERTICAL_SLICES_PLAN.md)
3. [Stage 02 SDD](STAGE_02_SDD.md)
4. [Stage 02 BDD](STAGE_02_BDD.md)
5. [Stage 02 Module Index](STAGE_02_MODULE_INDEX.md)
6. [Stage 02 Progress](STAGE_02_PROGRESS.md)
7. [Stage 02 Final Acceptance Report](STAGE_02_FINAL_ACCEPTANCE_REPORT.md)

其他产品、架构、Agent、数据库文档只作为引用，不作为日常执行入口。

Stage 03 进入前按这个顺序阅读：

1. [Stage 03 Source Of Truth](STAGE_03_SOURCE_OF_TRUTH.md)
2. [Stage 03 Backend Integration Plan](STAGE_03_BACKEND_INTEGRATION_PLAN.md)
3. [Stage 03 SDD](STAGE_03_SDD.md)
4. [Stage 03 BDD](STAGE_03_BDD.md)
5. [Stage 03 Acceptance Checklist](STAGE_03_ACCEPTANCE_CHECKLIST.md)
6. [Stage 03 Progress](STAGE_03_PROGRESS.md)

Stage 03 当前是 candidate，需要用户确认后才能开始代码实现。

## 2. Stage 02 Scope

Stage 02 范围已经确认：

- 充值闭环。
- 账户库存。
- 客户日报和公司日报。
- Mock Telegram webhook。
- Mock/sandbox provider。
- 不做 `tenant_id`。
- 使用 outbox table。

## 3. Development Rule

开发时必须先确认当前任务属于 [Stage 02 Source Of Truth](STAGE_02_SOURCE_OF_TRUTH.md) 的范围。

如果任务不在 Stage 02 范围内：

- 不顺手实现。
- 记录为后续候选。
- 需要用户确认后才能变更阶段范围。

进入 Stage 03 代码开发前必须：

- 先提交或明确保留 Stage 02 hardening batch，避免两个阶段混在同一批未提交变更里。
- 用户确认 [Stage 03 Source Of Truth](STAGE_03_SOURCE_OF_TRUTH.md) 从 candidate 转 active。
- 第一批只选择一个主线，推荐 Real Telegram ingress + durable worker runtime。
