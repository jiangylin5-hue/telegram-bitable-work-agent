### Task 4：实现固定 allowlist Tool Gateway

**Files：** 创建 `backend/app/runtime/stage08_tool_gateway.py`；修改 `backend/app/services/stage06_digital_employees.py`；测试 `backend/tests/unit/test_stage08_tool_gateway.py`。

**Produces：** `Stage08ToolGateway.execute(uow, ticket, invocation) -> RedactedToolResult`；adapter 统一使用 `(uow, employee_id, actor, input)`。

#### 已确认的任务草稿语义（2026-07-18）

`task.create_draft` 不引入独立 `Task`、`TaskDraft` 表或新的业务垂类。它只接受一个调用者和数字员工都已获授权的任务表 `table_id` 与 `proposed_values`，在既有 `RecordChangeDraft` 中创建 `draft_type="create_record"`、`record_id=null`、`status="pending_confirmation"` 的草稿。草稿创建本身不得写入 `PlatformRecord`。

确认 `create_record` 草稿时，既有 Stage06 服务必须先按确认者的字段权限和表校验调用 `create_record`，再把新 record ID 回写到该草稿并把状态置为 `confirmed`，同时留下不含 `proposed_values` 的审计摘要。更新草稿继续沿用既有 `draft_type="update_record"` 路径。拒绝路径不创建记录。此为用户明确确认的实现边界；不改变 Package A 禁止直接写入和禁止发送的规则。

- [ ] **步骤 1：写失败测试**

```python
def test_record_query_returns_visible_field_keys_and_count(uow, ticket):
    result = gateway.execute(uow, ticket, ToolInvocation(
        tool_name="record.query", input={"view_id": str(view.id)}))
    assert result.field_keys == ("status",)
    assert result.counts["record_count"] == 1

def test_unknown_tool_fails_closed_without_service_call(uow, ticket):
    with pytest.raises(Stage08ToolGatewayError, match="tool_not_registered"):
        gateway.execute(uow, ticket, unknown_invocation)
```

草稿 adapter 还必须证明：仅生成一个 `pending_confirmation`、源记录不变、结果不含 `proposed_values`。

- [ ] **步骤 2：确认失败；步骤 3：实现 adapter**

运行：`python -m pytest -q tests/unit/test_stage08_tool_gateway.py`  
预期：模块不存在。  
实现固定 dictionary dispatcher，禁止反射和用户控制 import path；每个 adapter 只能调用 Stage06 service boundary，并将输出映射为 `executing` 后的 `succeeded`、`denied`、`failed`、`cancelled` 或 `timed_out`。

- [ ] **步骤 4：回归与无发送扫描**

运行：`python -m pytest -q tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage06_live_digital_employee_runtime.py tests/unit/test_stage06_skill_matching.py`  
预期：PASS。  
运行：`rg -n "sendMessage|notification_request.confirm|Telegram.*send" backend/app/runtime/stage08_tool_gateway.py backend/app/services/stage08_runtime.py`  
预期：无匹配。

