# Stage08 Package A Task6 Review

## Critical

无。

## Important

1. **硬超时不能保证 batch 会继续。** `run_case_isolated` 在检测到超时后调用 `process.terminate()`，随后在第 409 行执行无超时的 `process.join()`；`finally` 的第 428 行也一样。若终止后的子进程未及时退出，调用会无限等待，`run_batch` 的 worker 因此卡住，违背“父进程硬超时、batch timeout/失败不中断后续 case”的核心契约。应为终止后的 join 设置一个很短且有界的清理期限；超过期限时记录固定失败标签并返回，且清理路径自身不得破坏超时上界。

2. **父进程没有重新验证收到的 DTO，无法拒绝构造型/子类化的非静态字段。** 第 420 行仅以 `isinstance(payload, RedactedCaseResult)` 判断后直接返回。Pydantic 的 `model_construct()` 可绕过字段验证，且 `RedactedCaseResult` 的子类也满足该判断；因此来自 child queue 的对象可包含未经过 `case_id`/`failure_labels` 验证的值（或附加可序列化字段），随后由父进程保留、聚合或输出。这不满足“父进程只接收 Pydantic 脱敏 DTO，拒绝 malformed/non-static raw”的硬边界。应只接受精确 DTO 类型，并在父进程通过一个无额外字段的序列化表示重新 `model_validate`；同时将 `case_id` 限制为既有 12 个固定 label，而不是当前的通用正则。

## Spec compliance verdict

**不通过（需修复上述 Important 项后再验收）。** 其余限定项的静态实现符合范围：每 case 使用 `spawn`、并行度限制为 1..2、失败使用固定标签、批量聚合在正常终止情形下继续后续 case、并在父/子进程强制 dry-run/provider-write disabled/notification disabled，且未见 schema/API 或 12 个 case 的扩展。

## Task quality verdict

**需要返修。** 实现方向正确、DTO 字段设计克制，但硬超时与父进程边界验证属于本任务的安全关键验收条件，不能以当前形式签收。

## Fix Round 1 / 2 narrow re-review

### Critical

无。

### Important

无新增 Important。

### Review conclusion

**两项原 Important 已修复，Fix Round 1 / 2 通过。**

- **超时 cleanup 有界：** timeout 分支及 `finally` 都改为 `_stop_process_with_bounded_grace`；terminate/可选 kill 后的 `join` 固定使用 `0.05s` grace，不再有无参或无限 `process.join()`。stubborn-child 测试覆盖了 child 仍存活时不关闭该 process 且所有 join 均有 timeout 的行为。
- **父端 exact DTO 重验证：** 仅接受 `type(payload) is RedactedCaseResult`，拒绝 subclass；字段集合、extra 状态和 JSON-compatible dump 都被检查，随后重新 `model_validate`，并要求返回 case label 与发起 case 相同。测试覆盖 `model_construct` forged 值、子类和注入 extra field，均固定失败为 `child_result_invalid` 且不保留 secret。
- **12 个固定 case_id：** `RedactedCaseResult` validator、`run_case_isolated` 与 `run_batch` 都以 `_FIXED_CASE_IDS` 约束；`other_static_label` 已被测试为拒绝。固定集合由现有 `default_live_eval_cases()` 的 12 个 label 生成，未扩展 case。

本复审为静态核对，未运行 Provider/Telegram/notification，也未重复实施者报告的测试。
