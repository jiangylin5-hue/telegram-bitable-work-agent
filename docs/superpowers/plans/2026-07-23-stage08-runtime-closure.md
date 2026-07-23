# Stage08 真实运行时收口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让真实 LLM 调用稳定产出受约束 JSON 和待确认草稿提议，并把当前用户可见的群聊—客户—项目—数字员工关系投影到 Mini App。

**Architecture:** 通用 OpenRouter adapter 负责严格 JSON Schema transport 与本地 object 解析；Stage08 provider 负责把模型结果收敛为现有 `AnalysisDecision`。Home service 作为授权投影边界，前端只消费其返回的安全 index，不访问 Telegram 或记录原文。

**Tech Stack:** Python 3.12、FastAPI、Pydantic v2、httpx、SQLAlchemy、React、TypeScript、Vitest、pytest。

## Global Constraints

- 不新增 migration、公开写接口、权限角色或 Telegram 外部调用。
- 所有关系均必须在当前 actor 的 `read_record_for_actor()` 结果上重新授权。
- Provider schema/解析失败必须 fail closed，不能返回模型原文。
- `draft_update` 仅生成现有 `pending_confirmation` 草稿；未持久化前不得使用完成态文案。

---

### Task 1: 强制通用 OpenRouter JSON Schema

**Files:**
- Modify: `backend/app/adapters/llm_openrouter.py`
- Modify: `backend/tests/unit/test_llm_adapters.py`

**Interfaces:**
- Consumes: `StructuredLLMRequest.response_schema: dict[str, object]`
- Produces: OpenAI-compatible `response_format.json_schema` request payload。

- [ ] **Step 1: Write the failing tests**

```python
assert http_client.calls[0]["json"]["response_format"] == {
    "type": "json_schema",
    "json_schema": {
        "name": "structured_llm_response",
        "strict": True,
        "schema": request.response_schema,
    },
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_llm_adapters.py -q`

- [ ] **Step 3: Implement the minimal request helper**

```python
def _strict_response_format(schema: dict[str, object]) -> dict[str, object]:
    return {"type": "json_schema", "json_schema": {"name": "structured_llm_response", "strict": True, "schema": schema}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_llm_adapters.py -q`

### Task 2: 约束 Stage08 草稿分析与未执行措辞

**Files:**
- Modify: `backend/app/services/stage08_openrouter_analysis_provider.py`
- Modify: `backend/app/agents/stage06_live_digital_employee.py`
- Modify: `backend/tests/unit/test_stage08_openrouter_analysis_provider.py`
- Modify: `backend/tests/unit/test_stage06_live_digital_employee_runtime.py`

**Interfaces:**
- Consumes: existing `AssistantQueryCommand.requested_action` and `AnalysisDecision`.
- Produces: existing one-field `DraftIntent` only for `draft_update`; Stage06 draft reply uses fixed proposal text.

- [ ] **Step 1: Write failing provider and wording tests**

```python
assert outcome.decision.action == "draft_update"
assert outcome.decision.draft_intent is not None
assert response["answer"] == "已提出一个待确认草稿。"
```

- [ ] **Step 2: Run focused tests and observe failure**

Run: `python -m pytest tests/unit/test_stage08_openrouter_analysis_provider.py tests/unit/test_stage06_live_digital_employee_runtime.py -q`

- [ ] **Step 3: Implement strict draft JSON model and validation**

```python
if command.requested_action == "draft_update":
    require action == "draft_update", nonempty citations, and draft.field_key/value
else:
    reject draft fields and draft_update action
```

- [ ] **Step 4: Verify focused tests pass**

Run: `python -m pytest tests/unit/test_stage08_openrouter_analysis_provider.py tests/unit/test_stage06_live_digital_employee_runtime.py -q`

### Task 3: 投影授权业务关系到 Home API

**Files:**
- Modify: `backend/app/services/stage07_mini_app.py`
- Modify: `backend/app/schemas/stage06_platform.py`
- Modify: `backend/tests/unit/test_stage07_mini_app.py` (create if absent)
- Modify: `backend/tests/api/test_stage06_platform_api.py` (or existing Home API test module)

**Interfaces:**
- Produces: `business_context_relations: list[MiniAppBusinessContextRelationResponse]` in existing workspace home payload.
- Entry accepts only an active current-user `chat_user` binding, one active Stage08 mapping, readable active employee/customer/project records.

- [ ] **Step 1: Write failing service/API tests**

```python
assert home["business_context_relations"] == [{"employee": ..., "group": {"label": "已授权群聊 1"}, ...}]
assert "telegram_chat_id" not in json.dumps(home)
```

- [ ] **Step 2: Run focused backend tests and observe failure**

Run: `python -m pytest tests/unit/test_stage07_mini_app.py -q`

- [ ] **Step 3: Implement fail-closed relation projection**

```python
visible = read_record_for_actor(uow, record.id, actor=actor)
if visible cannot be read: skip relation
```

- [ ] **Step 4: Verify focused backend tests pass**

Run: `python -m pytest tests/unit/test_stage07_mini_app.py -q`

### Task 4: 消费安全关系 DTO 并提供记录索引

**Files:**
- Modify: `mini-app/src/app/api.ts`
- Modify: `mini-app/src/app/WorkspaceHome.tsx`
- Modify: `mini-app/src/app/App.tsx`
- Modify: `mini-app/src/test/workspace-business-context.test.tsx` (create)

**Interfaces:**
- Consumes: `WorkspaceHome.business_context_relations`.
- Produces: employee/base and customer/project record callbacks; group label is non-clickable text until a real group detail route exists.

- [ ] **Step 1: Write failing UI test**

```tsx
fireEvent.click(screen.getByRole('button', { name: '打开客户记录 明日璀璨' }))
expect(onOpenRecordReference).toHaveBeenCalledWith(relation.customer)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm.cmd test -- --run src/test/workspace-business-context.test.tsx`

- [ ] **Step 3: Implement typed relation rail and callback**

```tsx
{home.business_context_relations.map((relation) => (
  <button onClick={() => onOpenRecordReference?.(relation.customer)}>{relation.customer.label}</button>
))}
```

- [ ] **Step 4: Verify UI test passes**

Run: `npm.cmd test -- --run src/test/workspace-business-context.test.tsx`

### Task 5: 回归、中文证据和提交

**Files:**
- Modify: `project-docs/08-implementation/STAGE_08_RUNTIME_CLOSURE_DESIGN_AND_PLAN.md`
- Modify: `project-docs/08-implementation/evidence/stage08-runtime-closure-2026-07-23.md` (create)

- [ ] **Step 1: Run focused backend and Mini App tests**

Run: `python -m pytest tests/unit/test_llm_adapters.py tests/unit/test_stage08_openrouter_analysis_provider.py tests/unit/test_stage06_live_digital_employee_runtime.py tests/unit/test_stage07_mini_app.py -q`

- [ ] **Step 2: Run full regressions and production build**

Run: `python -m pytest -q`, then `npm.cmd test -- --run`, then `npm.cmd run build`.

- [ ] **Step 3: Record only sanitized evidence**

Write exact commands/counts; omit raw prompts, Provider replies, keys and Telegram identifiers.

- [ ] **Step 4: Commit verified work**

```bash
git add backend mini-app project-docs docs/superpowers/plans/2026-07-23-stage08-runtime-closure.md
git commit -m "feat(stage08): close structured runtime and business context projection"
```
