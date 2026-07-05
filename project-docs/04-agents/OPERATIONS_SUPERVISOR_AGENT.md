# Operations Supervisor Agent

## Status

- Document status: agent draft
- Scope: 全局调度、Agent 协作、workflow state、人工确认和 execution ticket
- Current Progress: 2026-07-04 新增运营主管 Agent 设计。

## 1. Business Role

Operations Supervisor Agent 是整个工作智能体系统的调度主管。它不直接替代某个岗位，而是负责把消息、账户库存、充值绑卡、财务核对、卡资源和日报 Agent 串成可执行流程。

## 1.1 Bitable Endpoint

Operations Supervisor Agent 负责保证每个 workflow 都有多维表格终点：

| Output | Table / View |
| --- | --- |
| workflow 状态 | workflow/service record table / 服务看板 |
| 人工确认请求 | confirmation queue / AI 草稿队列 |
| execution ticket | `execution_tickets` / 审计视图 |
| 执行状态合并 | service/recharge/account/report views |
| 异常升级 | blocked/manual_review view |

## 2. Problems It Solves

- 一个 Telegram 请求可能涉及多个岗位 Agent。
- 充值绑卡需要财务、账户、卡资源、执行多个步骤。
- 真实执行必须知道在哪里停下来等待人工确认。
- 执行后需要回写日志、回读状态、回传客户和进入日报。

## 3. Architecture

```text
Supervisor Graph
-> load workflow state
-> classify next required agent
-> dispatch sub-agent
-> merge agent task state
-> evaluate risk and missing fields
-> request human confirmation if needed
-> validate execution ticket
-> trigger controlled execution
-> close workflow or continue
```

## 4. State

Supervisor 维护 `WorkflowState`：

- `workflow_id`
- `trace_id`
- `source_message_id`
- `customer_id`
- `account_ids`
- `current_stage`
- `required_agents`
- `completed_agents`
- `blocked_reason`
- `human_confirmation_required`
- `execution_ticket_id`
- `final_status`

## 5. Tools

Read:

- `query_workflow_state`
- `query_pending_agent_tasks`
- `query_service_record`

Mutation:

- `create_workflow`
- `update_workflow_state`
- `create_task_assignment`
- `request_execution_confirmation`

Execution:

- `validate_execution_ticket`
- `dispatch_controlled_execution_job`

## 6. LLM Usage

允许：

- 判断下一步应该交给哪个 Agent。
- 总结当前流程状态。
- 生成给人类确认的摘要。

禁止：

- 自己确认执行。
- 修改权限。
- 跳过缺失字段和风险。

## 7. Required Skills

- workflow orchestration。
- state merging。
- risk routing。
- human-in-the-loop planning。
- evidence summarization。

## 8. Acceptance Criteria

- 能说明每个任务当前由哪个 Agent 负责。
- 能在真实执行前停在人工确认点。
- 能生成 execution ticket 请求摘要。
- 能把执行结果重新合并进 workflow state。
