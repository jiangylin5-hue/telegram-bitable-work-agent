# Stage08 Package E / E3-R1 I-1 修复复审报告

## Status

- Review scope: 仅复核 I-1 safe/default ticket provenance remediation
- Result: `0 Critical / 0 Important`
- I-1 verdict: **PASS / CLOSED**

## Focused findings

无新的 Critical 或 Important。

## Verification of I-1

1. **同 trace 的 default-mode ticket 在 safe context 下 fail closed：PASS**
   - `backend/app/services/stage08_runtime.py:70-76` 的 same-trace replay 经 `_return_replayed_ticket` 返回。
   - `backend/app/services/stage08_runtime.py:84-99` 的 idempotency replay 使用同一 helper。
   - `backend/app/services/stage08_runtime.py:189-200` 在 `safe_context is not None` 时稳定抛出 `stage08_safe_execution_ticket_provenance_unavailable`，不返回既有 ticket。
   - `backend/tests/unit/test_stage08_tool_gateway.py:312-366` 先创建含 UUID audit 的 default ticket，再以 factory-issued safe context 调用；断言 fail closed，且未新增 ticket/audit。

2. **Safe 新建路径仍正常：PASS**
   - `backend/tests/unit/test_stage08_tool_gateway.py:191-309` 完成 safe ticket → Gateway → draft，结果 `succeeded`，draft 保持 `pending_confirmation`，安全摘要与 hash trace 正常。

3. **Default replay 仍正常：PASS**
   - `_return_replayed_ticket` 在 `safe_context is None` 时原样返回 ticket。
   - runtime replay 聚焦测试 fresh 通过：`3 passed, 12 deselected`。

4. **Trace-wide scan 不再使用创建前切片：PASS**
   - `backend/tests/unit/test_stage08_tool_gateway.py:256-309` 对全部 UoW `AgentRun`、audit 和 execution ticket 按 `trace_id == trace_hash` 过滤扫描；不再依赖 `audit_start/run_start` 切片。

## Test evidence

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_tool_gateway.py -k "safe_execution"
# 2 passed, 17 deselected in 1.32s

python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_runtime_service.py -k "replay"
# 3 passed, 12 deselected in 1.60s

python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py tests/unit/test_stage08_collaboration_service.py
# 90 passed in 2.55s
```

- Network / Telegram / Provider / deployment: 未调用。
- Production/test code modifications: 无。

## Verdict

I-1 已按预期修复并关闭。safe context 无法静默复用既有 default ticket；safe 新建与 default replay 均保持正常；trace-wide 测试已覆盖同 trace 的全部持久化摘要对象。`0 Critical / 0 Important`。
