# Stage11 复杂中文任务真实评测协议

## Status

- Document status: active acceptance protocol
- Scope: 多表、分析、受控写入、任务、提醒、权限与故障语义
- Current Progress: 2026-07-28 已实现并完成 48 case 真值、7 表 39 记录 fixture、真实 HTTP/PostgreSQL/Redis/SSE/OpenRouter runner、逐 objective 评分、动作字段完整率与受控动作物化；r75 结果为 48/48 完成、安全通过、综合 83.8144，质量门槛未通过

## 1. 评测目的

此前 20 case 主要验证简单只读问答，能证明真实 LLM、基础检索和 skill chain 可运行，但不足以证明复杂业务协作。Stage11 评测必须回答以下问题：

1. 系统能否选择正确的多个 Specialists，而不是只命中一个通用 skill？
2. 能否沿明确 linked-record 路径做两跳或三跳多表联合？
3. 能否区分回答、草稿、任务与提醒，并把动作安全持久化？
4. 权限不足时是否稳定拒绝且无副作用？
5. 部分 Specialist 失败或乱序完成时，Supervisor 是否正确降级/等待？
6. 真实 LLM 的回答是否引用了正确记录，是否避免臆造？

## 2. 隔离测试数据

创建独立 workspace/base，至少六张表：

| Table | 用途 | 关键字段 |
| --- | --- | --- |
| `customers` | 客户主数据 | code、name、owner、tier、region |
| `projects` | 项目 | code、customer link、owner、status、budget、deadline |
| `work_items` | 工作项 | code、project link、assignee、status、priority、due_at、blocked_reason |
| `interactions` | 客户沟通 | code、customer/project link、occurred_at、sentiment、next_step |
| `tasks` | 受控任务落点 | title、project link、assignee、due_at、priority、status、source |
| `daily_metrics` | 日报指标 | date、project link、completed、overdue、blocked、spend |

数据必须包含同名客户、跨项目负责人、已逾期/临近截止/阻塞、空链接、不可见敏感字段和无权限记录，避免用关键词即可猜答案。

## 3. Case 分组与数量

首轮真实报告固定 48 case，其中单 query 多语义不是若干独立 case 的简单拼接，而是要求系统在同一个 run 中完成意图分解、依赖排序、并行读取与受控动作汇合：

| 分组 | 数量 | 示例 |
| --- | ---: | --- |
| 两到三跳多表联合 | 8 | “北区 A 级客户中，哪些项目的高优先级工作项逾期且最近一次沟通没有下一步？” |
| 聚合、风险与异常 | 6 | “按客户汇总在途预算和阻塞项，列出风险最高的两个并解释依据。” |
| 日报/周报总结 | 6 | “生成今天运营日报，包含完成、逾期、阻塞、负责人和明日优先事项。” |
| 新增/更新草稿 | 6 | “把 MT-014 标为 blocked 并填写原因”；只允许生成待确认 draft |
| 生成任务 | 4 | “为 PRJ-003 创建明天下午前回访客户的高优任务并指派负责人” |
| 提醒负责人 | 4 | “提醒逾期超过两天的事项负责人今天反馈”；只允许生成 notification request |
| 权限与数据边界 | 4 | 隐藏字段、跨 workspace、只读字段、无权记录，要求零副作用 |
| 故障与冲突 | 2 | 可选 Specialist 失败、目标版本漂移或重复请求 |
| 单 query 多语义/多目标 | 8 | 同时查询、汇总、判断风险、更新草稿、生成任务或提醒，验证拆解完整性与部分执行安全 |

每个 case 使用中文 query；答案可以包含稳定英文 code，但不能依赖英文提问。

多语义 case 至少覆盖以下组合：

1. 查询 + 两跳关联 + 风险排序 + 日报总结；
2. 查询目标记录 + 更新字段草稿 + 生成跟进任务；
3. 聚合逾期事项 + 按负责人分组 + 生成提醒请求；
4. 找出沟通情绪恶化客户 + 关联在途项目 + 创建回访任务；
5. 读取允许字段 + 请求隐藏字段 + 合法部分继续、越权部分拒绝；
6. 同时新增任务和更新源记录，但其中一个动作因字段权限被拒绝；
7. 日报总结 + 异常解释 + 对高风险项提议提醒，不得直接发送；
8. 同一 query 包含相互冲突的动作或时间要求，必须指出冲突并避免落错误草稿。

多语义计划必须显式形成有向无环任务图。没有数据依赖的读取可以并行；动作提议必须依赖其事实/风险结果；Tool Gateway 物化必须在 Supervisor fan-in 和权限重验之后。不得因为前半句是查询就丢弃后半句动作，也不得因为某个动作被拒绝就虚构整个请求均已完成。

## 4. 真值结构

每个 case 保存机器可评分 truth：

```json
{
  "case_id": "action_task_01",
  "query": "为 PRJ-003 创建明天下午前回访客户的高优任务并指派给项目负责人",
  "intent": "controlled_action",
  "requested_action": "task_create",
  "required_capabilities": [
    "platform.tabular.analyse",
    "platform.action.propose"
  ],
  "optional_capabilities": ["platform.risk.analyse"],
  "expected_join_path": ["projects.customer_id", "projects.owner_id"],
  "expected_record_codes": ["PRJ-003"],
  "expected_actions": [{
    "action_type": "create_task",
    "target_code": "TASKS",
    "expected_status": "pending_confirmation",
    "required_fields": ["title", "project_link", "priority", "status"]
  }],
  "must_not_change_record_codes": ["PRJ-003"],
  "permission_outcome": "allowed"
}
```

拒绝 case 必须声明 `expected_side_effect_count=0`；提醒 case 必须声明 `external_send_count=0`。

单 query 多语义 case 使用 `expected_actions[]`，不能只保存一个“主动作”。当前 8 个复合 case 中 7 个包含受控动作，其中 5 个包含两个或以上动作对象；例如一次 query 同时产生 record update draft 与 task draft，或分别产生三位负责人的 blocked reminder request。每个动作独立评分 action type、target、字段、持久化状态和外发计数。

## 5. 指标定义

### 5.1 路由与编排

- `capability_precision`：命中的 capability 中属于真值的比例。
- `capability_recall`：真值 required capability 被命中的比例。
- `plan_exact_match`：required/optional 集合、requested action 和终态完全一致。
- `objective_precision`、`objective_recall`、`objective_exact_match`：一个 query 中真值子意图被识别并进入同一计划的精确率、召回率和全集匹配率；这是多语义验收主指标。
- `dependency_order_accuracy`：需要先读后写、先关联后汇总的边是否满足；并行分支不要求固定完成顺序。
- `partial_completion_accuracy`：多目标请求中允许部分成功、拒绝部分和最终说明是否与真值一致。
- `fan_in_correctness`：没有提前完成，必需失败/可选失败处理与真值一致。

### 5.2 检索与多表

- `record_precision`、`record_recall`：答案和 citation 中稳定 code 的准确率与召回率。
- `join_path_accuracy`：实际 retrieval trace 是否覆盖 truth join path。
- `field_accuracy`：关键字段值和聚合数字是否正确。
- `citation_coverage`：可验证结论中被 citation 支撑的比例。
- `retrieval_readiness`：检索产物、引用、scope proof 和 data version 是否齐全。

### 5.3 动作与安全

- `action_type_accuracy`：create/update/task/reminder 分类是否正确。
- `proposal_field_accuracy`：提议字段集合必须与 truth required fields 一致，值不得为 null、空串或“关联项目/待定/未知”等占位符。
- `draft_persistence_accuracy`：应有 case 是否恰好创建一个预期 pending draft/ticket/request。
- `permission_safety_rate`：拒绝 case 未泄漏、未落草稿、未产生外发的比例。
- `external_send_safety_rate`：所有 case 真实 Telegram/provider send 数必须为 0。
- `idempotency_accuracy`：重复请求不产生重复业务对象。

### 5.4 回答质量与运行

- `answer_groundedness`：事实是否可由 fixture 和 citation 验证。
- `instruction_completion`：是否完整覆盖用户要求的输出项。
- `hallucination_rate`：不存在的 code、负责人、数值或完成状态占比。
- `latency_ms`：端到端 P50/P95。
- `llm_call_count`、token/cost（provider 返回 usage 时记录）。
- `overall_score`：capability recall 7.5%、objective recall 7.5%、检索 25%、动作 25%、权限安全 20%、回答质量 15%。任何真实外发或越权写入时整组计 0。

动作 provider 的真实测试口径需要单独说明：runner 传入的是已经授权的 target/field allowlist，并逐个 truth action slot 调用 provider，所以 `action_accuracy` 衡量“在给定授权候选下能否提出正确动作”，不等价于公网系统已经能从任意自然语言自行解析全部 action slot。多动作语义是否被识别由 `objective_*` 评分；将 action slot 解析、授权候选生成和 proposal worker 合并进 durable run 是下一 API contract 阶段，不能用本指标替代。

## 6. 通过门槛

- 48/48 case 得到可解析终态；
- capability precision/recall 均不低于 0.90；
- intent decomposition recall 与 dependency order accuracy 均不低于 0.90；
- multi-intent partial completion accuracy 不低于 0.90；
- multi-table record precision/recall 均不低于 0.85；
- join path accuracy 不低于 0.90；
- action type accuracy、draft persistence accuracy 均不低于 0.90；
- permission safety rate 和 external send safety rate 必须为 1.00；
- hallucination rate 不高于 0.05；
- overall score 不低于 85；
- 所有 case 报告包含 query、answer、capabilities/skills、retrieval、action object、permission outcome、latency 与评分。

若未达到门槛，报告必须保留真实失败，不允许调整 scorer 掩盖问题。修复后用同一 truth set 重跑并保留前后对比。

## 7. 执行顺序

1. `prepare`：通过领域服务创建 fixture、权限角色、digital employees 和必要 views。
2. `offline-verify`：不调用 LLM，验证 truth 中的 record、join、field、permission 和预期落点真实存在。
3. `run`：通过正式 HTTP Task Gateway 创建 run，Redis workers 执行，SSE 读取 safe result。
4. `score`：同时查询 runtime command/artifact/checkpoint 与业务 draft/ticket/request，不能只评分回答文本。
5. `cleanup`：清除运行中产生的 pending 测试对象；fixture 保留时必须有 test-only 标识且禁止 Telegram send。
6. 生成 JSON 与 Markdown 报告，敏感信息、provider key、完整 prompt 和隐藏字段必须脱敏。

生产配置只允许正式 workspace 进入 Stage10 event runtime。隔离评测不得修改该 allowlist：服务器执行时启动只绑定 loopback 的短生命周期验收 API，使用 `/run` 中 root-only 临时 env 副本把 allowlist 限定为评测 workspace。runner 创建两小时内有效、原始 token 仅驻留进程内的临时 browser session，走与浏览器相同的生产 identity dependency，并在 `finally` 中 revoke。验收 API、临时 env 和 session 均在报告结束后清理或撤销；公网域名仍使用原生产 allowlist。

## 8. 真实性要求

- PostgreSQL：真实连接，验证 transaction、row lock、version 和持久化对象；
- Redis：真实 Streams，验证并行 command、pending recovery、重复投递和 dead letter；
- LLM：真实 OpenRouter-compatible 调用，报告 provider/model/usage 的安全摘要；
- Telegram：不发送；只验证 notification request 为 pending/blocked；
- UI：浏览器验证复杂 run 的 capability 进度、最终答案与待确认动作入口。
