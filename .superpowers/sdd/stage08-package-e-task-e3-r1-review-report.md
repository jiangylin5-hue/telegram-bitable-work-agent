# Stage08 Package E / E3-R1 独立任务复审报告

## Status

- Review type: focused spec-compliance + code-quality re-review
- Scope: E3-R1 私有 safe context、单字段 `DraftIntent`、ticket/Gateway/Stage06 draft/AgentRun/audit 安全端口及其最小测试
- Result: `0 Critical / 1 Important / 0 Minor`
- Spec verdict: **FAIL**
- Code-quality verdict: **FAIL**

## Read evidence

已按指定顺序完整读取：

1. `.superpowers/sdd/stage08-package-e-task-e3-r1-brief.md`
2. `.superpowers/sdd/stage08-package-e-task-e3-r1-report.md`
3. `.superpowers/sdd/stage08-package-e-task-e3-r1-review-package.patch`（5175 行，完整遍历）
4. `project-docs/08-implementation/decisions/STAGE_08_E3_SAFE_EXECUTION_ADAPTER_DECISION.md`

并读取 brief 指向的 Task R1 与 `STAGE_08_E_LANGGRAPH_COLLABORATION_CONTRACT.md` 相关完整合同。

## Critical

无。

## Important

### I-1 Safe mode 可 replay 既有 default-mode ticket，导致同一 hash trace 保留默认 UUID audit

- Production location: `backend/app/services/stage08_runtime.py:70-73`；同类 idempotency replay 返回点见 `backend/app/services/stage08_runtime.py:84-96`。
- Test gap: `backend/tests/unit/test_stage08_tool_gateway.py:227-301`。

`begin_execution_plan()` 虽在 48-57 行校验 safe context 与本次 plan 的 trace 一致，但 70-73 行只按 `trace_id + request_fingerprint` 复用既有 ticket，没有证明该 ticket 是在 `stage08_e3_safe` 下创建的。可复现序列：先用一个合法 hash trace 按默认模式调用 `begin_execution_plan(uow, plan)`，再用同一 plan 和 factory-issued safe context 调用；第二次直接返回第一个 ticket。该 trace 已经有默认 `stage08.execution_ticket_created` audit，其中 `entity_id` 和 `after_state.ticket_id` 都是 ticket UUID，因此后续调用 safe Gateway 不能使“完整 safe trace 无 UUID”成立。

实测输出：

```text
same_ticket= True
[{"after": {"ticket_id": "a7c12dee-2032-4dce-95e8-b3b90814b72d", ...},
  "entity_id": "a7c12dee-2032-4dce-95e8-b3b90814b72d",
  "trace_id": "stage08:collaboration:cccccccccccccccccccccccccccccccc"}]
```

这不是事后清理问题，而是 safe/default provenance 未被 replay 分支验证。当前 trace-wide 测试在 227 行先记切片点，并只扫描 `audit_events[audit_start:]`（279、301 行），所以会漏掉同 trace 已存在的默认 audit，也不能证明报告所称的“完整 trace”安全。

建议在 R1 安全端口处 fail closed：safe context 下不得复用无法证明为 safe-mode 创建的 ticket；若 safe replay 的 provenance 证明要由 R2 的专用执行边界提供，则 R1 应在 R2 接线前拒绝该 replay，而不是静默返回 default ticket。补充测试应先制造同 trace 的 default ticket，再从所有 `event.trace_id == trace_hash` 的 audit/AgentRun 扫描禁止 corpus。

影响：违反“safe mode 只影响 E3 且 ticket 内部审计使用同一白名单摘要”“完整 safe trace 不含 ticket UUID”的合同，因此 spec 与 code-quality 均不能通过。

## Minor

无。

## Required checks

| Check | Result | Evidence |
| --- | --- | --- |
| Safe context 不能由 JSON/plan/tool forge | PASS | `ExecutionPlan` / `ToolInvocation` 为 `extra="forbid"`；测试覆盖 extra JSON、direct construction、裸 `object.__new__`、pickle 与非法 mode/UUID trace。 |
| Sealed intent 恰好一个 field/value 且不可序列化 | PASS | `stage08_collaboration_contracts.py:512-529,846-861`；测试覆盖非空 field、敏感 key、递归 JSON-safe、NaN/Infinity、JSON/pickle。 |
| Safe mode 仅内部、默认路径无语义变化 | PARTIAL | keyword-only `safe_context=None` 与 89 项默认回归通过；但 I-1 证明 default ticket 可进入 safe replay，模式隔离不完整。 |
| Ticket/Gateway/Stage06 draft/AgentRun/audit 写入点无 query/answer/private/field/value/entity UUID | PASS for newly-created safe path; FAIL for replay-complete trace | 新建 safe path 的各写入点直接调用统一白名单 helper，`entity_id=None`、refs/field keys 清空；I-1 的 replay trace 仍含先前 default ticket UUID。 |
| 写入时安全摘要，而非事后删除 | PASS | 未发现 post-execution audit cleanup；safe 分支在各 `record_audit_event` / `AgentRun` / `tool_summary` 写入点直接构造摘要。 |
| Trace ID hash-only | PASS | `_SAFE_TRACE_HASH_RE.fullmatch()` 仅接受 32-64 lowercase hex 及固定 `stage08:collaboration:` 前缀；UUID trace 被拒绝，草稿 safe trace 直接使用该 hash。 |

## Verification

执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py tests/unit/test_stage08_collaboration_service.py
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/runtime/stage08_contracts.py app/services/stage08_runtime.py app/runtime/stage08_tool_gateway.py app/services/stage06_digital_employees.py
```

结果：

```text
89 passed in 1.89s
compileall: exit code 0, no output
```

另运行只读最小复现，确认 I-1：第二次 safe `begin_execution_plan()` 返回第一次 default ticket，且同 hash trace 的既有 audit 包含 ticket UUID。

- Network / Telegram / Provider / deployment: 未调用。
- Production/test code modifications: 无。
- Review artifact only: 本报告。

## Verdict

- Spec compliance: **FAIL — 1 Important**。新建 safe 路径的封装、白名单写入和 hash-only trace 符合 R1，但 replay 不能证明 safe provenance，完整 trace 可含默认 UUID audit。
- Code quality: **FAIL — 1 Important**。生产 replay 分支缺少模式隔离，现有 trace-wide 测试使用新增事件切片，未覆盖同 trace 历史事件。
