# Stage 02 Implementation Docs

## Status

- Document status: active implementation index
- Scope: Stage 02 后端内核与垂直切片开发入口
- Current Progress: 2026-07-04 建立 Stage 02 实施文档入口，后续开发以本目录为第一阅读入口。

## 1. Read Order

Stage 02 开发只需要按这个顺序阅读：

1. [Stage 02 Source Of Truth](STAGE_02_SOURCE_OF_TRUTH.md)
2. [Stage 02 Backend Kernel And Vertical Slices Implementation Plan](STAGE_02_BACKEND_KERNEL_AND_VERTICAL_SLICES_PLAN.md)
3. [Stage 02 SDD](STAGE_02_SDD.md)
4. [Stage 02 BDD](STAGE_02_BDD.md)
5. [Stage 02 Module Index](STAGE_02_MODULE_INDEX.md)
6. [Stage 02 Progress](STAGE_02_PROGRESS.md)

其他产品、架构、Agent、数据库文档只作为引用，不作为日常执行入口。

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

