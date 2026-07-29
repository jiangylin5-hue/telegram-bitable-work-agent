# Stage11 多 Agent 协调中间层验收

## Status

- Status: implementation and safety accepted; quality remediation required
- Scope: 多语义 Task Gateway、版本化 capability registry、多 command fan-out/fan-in、受控 Tool Gateway、48 case 真实中文复杂任务
- Current Progress: 2026-07-29 r76 已部署；r75 的 48/48 真实 case 完成，运行与安全边界通过，检索、动作与综合质量门槛未通过；r76 仅补 required-failure sibling terminalization
- Production Artifact: `stage09-p1-20260729-r76-stage11-terminal-fan-in`
- Database Head: `20260728_0034`，本阶段无 schema migration
- Evidence: `evidence/stage11-r75-real-48case-report-2026-07-28.md` 与同名 JSON

## 1. 验收结论

Stage11 已完成并部署 read-side 协调中间层：一个中文 query 可以被 Task Gateway 拆成多个 objective；Agent Registry 固定 capability、command、schema、失败策略、工具边界与 execution skill；Supervisor 批量创建并汇合 child commands；表格、风险、日报读取使用独立 durable command/Redis stream；SSE 只投影 PostgreSQL 中已授权的安全事件。

本阶段安全边界通过。动作模型只接收权限过滤后的稳定 target code 与字段白名单；Tool Gateway 只能创建 `pending_confirmation` draft 或 `blocked` notification request，不能确认草稿、写最终业务记录或发送 Telegram。r75 真实轮次产生 9 个 pending drafts、7 个 blocked reminders，Telegram send 为 0。

质量验收未通过。48 个 case 全部得到可解析终态，但多表记录召回、动作字段/持久化准确率和综合分低于协议门槛。不得把“48/48 完成”“真实 LLM 调用成功”表述成回答质量达标，也不得删除失败 case 或修改 scorer 掩盖问题。

此外，公网 durable endpoint 当前只派发三个 read capabilities。`platform.action.propose` 在验收 runner 中由 post-read backend adapter 逐个已授权 action slot 调用并经 Tool Gateway 物化；它尚不是第四个 durable Redis command，也没有公网 UI action contract。因此本阶段不证明任意自然语言动作的自主 slot 解析和统一 durable action orchestration。

## 2. 已实现架构

1. `Task Gateway` 对多语义 query 做确定性 objective 分解，输出带依赖关系的 DAG，并识别风险、日报、任务、提醒、权限请求和冲突表达。
2. `Agent Registry` 注册 `platform.tabular.analyse`、`platform.risk.analyse`、`platform.daily.summarise`、`platform.action.propose`，并固定 Lark-derived execution skill、输入输出版本、风险等级、工具白名单与写入边界。
3. `Agent Orchestrator` 一次创建多个 child commands；只有 Supervisor 可以把 run 标为 terminal；必需失败为 failed，可选失败为 degraded，全部成功为 succeeded。
4. `Agent Specialist Runtime` 轮询多个 Redis Streams，复用 Stage08 授权、检索、OpenRouter 和 SafeView 服务，不给 Specialist ORM、SQL 或原始凭据。
5. `Agent Action Provider` 使用 OpenRouter strict JSON schema，只能在已授权候选中提出 create/update/task/reminder proposal，并拒绝空值、占位符、未知 target 或字段。
6. `Agent Tool Gateway` 重验 workspace、employee、action、record version 与字段权限，生成 execution ticket 后只持久化 pending/blocked 对象。
7. `SSE Projection` 支持 terminal failed/degraded 语义、advisory artifact 过滤与 Last-Event-ID 续传；内部 Agent 通信仍是 PostgreSQL + Redis Streams，不是 SSE。

## 3. 真实数据、身份与调用链

隔离 fixture 使用 1 个 test-only workspace、1 个 base、7 张表和 39 条虚构记录，覆盖 Projects、Work Items、Risks、Tasks、Owners、Daily Metrics 与 Interactions。关联包含 project -> work item、work item -> risk 等路径，并包含逾期、阻塞、空关联、同名对象、隐藏字段和不可见记录。

正式 r75 轮次调用链为：

```text
real browser session identity
-> loopback HTTP POST /api/stage10/agent-runs
-> PostgreSQL run/command/event/checkpoint/outbox
-> Redis Streams + independent specialist workers
-> SSE safe terminal result
-> real OpenRouter google/gemini-2.5-flash
-> constrained action adapter
-> Tool Gateway pending/blocked artifact
-> database audit and scorer
```

生产公网 allowlist 未加入评测 workspace。评测只通过绑定 `127.0.0.1:18082` 的短生命周期 API 与 `/run/stage11-eval-r70.env` 执行；原始 session token 未写日志，session 在 runner `finally` 中 revoke。该隔离方式验证正式 identity dependency 与 fail-closed allowlist，同时不扩大公网 workspace 范围。

## 4. 48-case 结果

### 4.1 总体结果

| Metric | r75 result | Gate | Decision |
| --- | ---: | ---: | --- |
| Completed terminal cases | 48/48 | 48/48 | PASS |
| HTTP POST / SSE | 48×202 / 48×200 | 无 4xx/5xx | PASS |
| Capability precision | 1.0000 | >= 0.90 | PASS |
| Capability recall | 0.9688 | >= 0.90 | PASS |
| Plan exact match | 0.9375 | diagnostic | PASS |
| Objective precision | 0.7656 | diagnostic | NEEDS WORK |
| Objective recall | 0.9750 | >= 0.90 | PASS |
| Objective exact match | 0.3750 | diagnostic | NEEDS WORK |
| Record precision | 0.5660 | >= 0.85 | FAIL |
| Record recall | 0.6521 | >= 0.85 | FAIL |
| Retrieval readiness | 0.7917 | expected >= 0.90 | FAIL |
| Action / proposal field / persistence | 0.8229 | >= 0.90 | FAIL |
| Permission safety | 1.0000 | 1.00 | PASS |
| External-send safety | 1.0000 | 1.00 | PASS |
| Overall score | 83.8144 | >= 85 | FAIL |
| Average latency | 6548.5 ms | diagnostic | RECORDED |

5 个 read case 返回 `analysis_unavailable`；动作 provider 状态为 16 proposed、7 denied、4 unavailable。所有 unavailable 和错召回均保留在报告和分母中。

### 4.2 Case 覆盖

- 两到三跳多表联合：8 cases。
- 聚合、风险与异常：6 cases。
- 日报/周报总结：6 cases。
- 新增/更新草稿：6 cases。
- 生成任务：4 cases。
- 提醒负责人：4 cases。
- 权限与数据边界：4 cases。
- 故障与冲突：2 cases。
- 单 query 多语义/多目标：8 cases，其中 7 个包含动作，5 个包含两个或以上动作对象。

完整的 query、answer、skills/capabilities、召回记录、objective、动作对象、权限结论、延迟和逐 case 分数只保留在 r75 evidence，不在此文档重复制造第二份真源。

## 5. 失败轮次与修复轨迹

| Revision / round | 结果 | 证据意义或修复 |
| --- | --- | --- |
| r67 activation attempt 1 | rolled back | 远端 Base64 输入损坏且健康检查过早；自动恢复 r66 指针、env、unit 与服务 |
| r67-r69 | activated | 协调层、字段类型、fixture flush 依次修正；7 表 39 记录成功 |
| report auth rounds | HTTP 401 / 404 | 正式 identity 禁止 development header；生产 allowlist 拒绝隔离 workspace；均无 LLM/草稿/外发 |
| r70 | 48/48, 73.1988 | 首个完整真实 round；动作未物化，暴露 runner/action gap |
| r71 | 48/48, 62.2763 | 暴露 execution ticket/draft flush 缺陷，后续修复 |
| r73 | 43/48, 46.1198 | OpenRouter 额度耗尽，全部分析 unavailable；不得作为质量基线 |
| r74 | 48/48, 83.1331 | 有效基线；action/draft/field 0.7396，record P/R 0.5923/0.6667 |
| r75 | 48/48, 83.8144 | 最终同版轮次；真实模型恢复，安全通过，质量仍未达标 |

401/404 轮次证明正式身份和 workspace allowlist 均 fail closed。r71/r73 等失败轮次用于回归定位，不合并进 r75 指标。

## 6. 自动化与生产验证

- Backend Unit + API：最终 fresh 验证拆成互补集合执行：真实子进程矩阵 `1 passed in 49.47s`；其余 Unit/API `1560 passed, 1 deselected in 199.64s`，合计覆盖 1561/1561，无 skip/xfail。首次合并运行因 Windows `spawn` 并发冷启动在 10 秒测试预算处出现 2 个 timeout；连续复现确认是矩阵测试调度抖动后，仅把该集成测试改为串行 fresh child 和正式默认 30 秒预算，生产 runner 与 hard-timeout 逻辑未改。
- Stage11 focused：最终实现后已完成 `11 passed in 1.77s`；full suite 会覆盖全部 Stage11 tests。
- Mini App：`79 files / 411 tests passed in 216.39s`；Stage11 无 frontend diff。
- Production build：`1853 modules transformed`；静态资源与此前验收 hash 一致，Stage11 未修改 UI bundle。
- Public browser：域名可打开；无 Telegram browser session 时显示“无工作区访问权限”，符合 fail-closed 设计；application log 无错误。由于没有用户 Telegram session，未执行授权后的复杂 run 点击验收。
- Release/native service/static parity/readiness：r76 bounded activation PASS；6 个原生服务 active，公网/回环 health 为 `ok`，本地/服务器 orchestrator SHA-256 一致，Alembic current 为 `20260728_0034 (head)`，近 15 分钟目标 journal 无 warning。
- Skipped/unavailable：Stage11 无 frontend diff，因此未重复执行 411 项 Mini App 测试和 production build；授权后复杂 run 的浏览器点击验收因没有用户 Telegram browser session 未执行；本机未安装 `ruff`，因此 lint 未运行，使用 `compileall`、全量 pytest 与 `git diff --check` 代替但不宣称 lint 通过。

## 7. 安全审计、清理与保留物

最终提交前验证并记录：

- `telegram_send_count == 0`；
- r75 新增 9 个 draft 与 7 个 reminder；数据库最终审计显示隔离 workspace 累计 12 个 draft 全为 `pending_confirmation`、14 个 reminder 全为 `blocked`（包含保留的早期有效轮次证据）；
- denied case 不产生未授权业务写入或外发；
- 临时 browser session 已 revoke；
- loopback eval API 已停止，`18082` 无监听；
- `/run/stage11-eval-r70.env`、上传脚本、overlay、诊断文件和本机临时 SSH key 已删除；
- 公网 production allowlist、Telegram 配置和 provider secret 未改变；
- 仅保留 r73/r74/r75/r76 作为额度失败、有效质量基线、报告同版和当前/回滚证据；r67-r72 release/venv/static candidate 已清理；
- 隔离 7 表/39 记录 fixture 与 pending/blocked 测试对象作为可复现实测证据保留；它不在公网 allowlist 中，且没有发送权限。

## 8. Remaining Risks 与下一阶段顺序

1. 先修复 retrieval：按 objective 构造 candidate set，显式执行 linked-record traversal，先做 deterministic aggregation，再把小而完整的 evidence pack 交给 LLM。
2. 降低 objective over-segmentation：引入 objective normalization/merge policy，并单独评估 DAG edge、partial completion 与 conflict resolution。
3. 定义新的 action contract：`ActionSlot[] -> authorized candidates -> proposal -> durable command -> Tool Gateway`，明确 schema、权限、幂等、失败和 UI 确认语义后再实现 action worker。
4. 对 5 个 `analysis_unavailable` 增加 provider 分类、预算、退避和可观测性；不得用 fallback 假装真实模型成功。
5. 为授权后的浏览器工作台补 capability 进度、degraded/failed、pending action 入口的真实点击验收；当前 Stage11 没有前端实现。

## 9. Acceptance Decision

Decision: **PARTIAL — runtime and safety PASS; quality FAIL**。

实现、部署、真实调用、安全边界和报告完整性可以进入代码审查；检索/回答质量、动作准确率及统一 durable action 链路不能标记为 accepted。现有 PR 应保持 Draft，下一次质量修复必须沿用同一 truth set 并保留 r75 对比基线。
