# Stage08 Package A Task 6：真实 Provider 评测隔离

## Status

- Task status：ready for implementation
- Scope：只把既有 Stage06 合成数据 Live LLM 评测器改为按 case 的子进程隔离与脱敏聚合。

## 目标

在 `backend/scripts/stage06_live_llm_skill_quality_eval.py` 新增：

```python
run_case_isolated(case, timeout_seconds) -> RedactedCaseResult
run_batch(cases, max_parallelism, timeout_seconds) -> RedactedBatchResult
```

每个 case 在独立子进程中执行；超时时父进程终止子进程并继续其他 case。默认并发上限为 2。父进程结果只能含固定 case ID、布尔/计数、状态和静态 failure label，不能保存或输出 prompt、response、citation 内容、record ID、provider key、Telegram ID、traceback 或任何原始 provider 内容。

## 输入、输出与安全合同

- `RedactedCaseResult` 只允许 case ID、terminal status、固定 `failure_labels`、布尔安全指标和整数计数；禁止自由文本字段。
- `RedactedBatchResult` 只允许 case count、成功/超时/失败计数、聚合安全指标和 per-case `RedactedCaseResult`；禁止原始 case 输入/输出。
- 子进程可在内存中处理既有 case prompt 与 provider response；向父进程传递前必须投影为上述 DTO。
- 子进程启动失败、无结果、结果形状错误、非零退出或超时均 fail closed 为静态 label；不能阻断后续 case。
- 超时后的 `terminate`、可选 `kill` 与 `join` 清理都必须使用短且有界的 grace timeout；清理本身不得无限等待或突破父进程的 hard-timeout 语义。
- 父进程必须只接受**精确** `RedactedCaseResult` 类型；以无 extra field 的 JSON-compatible dump 重新 `model_validate`，并要求 case ID 属于既有 12 个固定 case label 且与发起 case 相同。`model_construct`、子类或额外字段均必须作为 `child_result_invalid` 拒绝。
- `max_parallelism` 必须受限到 `1..2`；`timeout_seconds` 必须是正的有限边界。
- `TELEGRAM_SEND_MODE=dry_run`、provider write disabled 和 notification disabled 继续由 `_force_runtime_safety` 强制；该任务不触发新的 Provider/Telegram 调用。真实 Provider 运行属于后续用户明确安排的真实 LLM 评测阶段。
- `finally` 必须关闭 queue/process/executor 临时资源；不落盘 raw result。

## TDD 与文件范围

- 修改 `backend/scripts/stage06_live_llm_skill_quality_eval.py`。
- 修改 `backend/tests/unit/test_stage06_live_llm_skill_quality_eval.py`：先验证导入缺失/断言失败，再覆盖超时静态标签无 raw、批次在一个 timeout 后继续、并发上限/输入校验和 child 结果脱敏。
- 修改 `project-docs/08-implementation/evidence/stage06-live-llm-skill-quality-2026-07-16.md`：记录旧串行风险、新隔离合同、合成数据边界、无 raw 留存和“未执行 Provider”事实。
- 在 `.superpowers/sdd/stage08-task-6-report.md` 写 RED/GREEN、回归、扫描、未做事项和风险。

## 明确不做

- 不运行真实 OpenRouter/Telegram/notification/provider write，不读真实业务数据。
- 不改变既有 12 个 case 的业务断言、技能匹配规则、Live LLM 协议或数据库 schema。
- 不实现 Runtime API、Memory/RAG、群历史、LangGraph coordinator 或部署。
- 不 stage、commit、reset、checkout 或 clean 当前 dirty worktree。

## 验收标准

1. 一个 child timeout 的 batch 仍返回每个 case 的脱敏结果，且后续 case 完成。
2. timeout 和 child error 只使用固定 failure label；`model_dump_json()` 不含 prompt/response/raw/secret/record ID/traceback。
3. 运行参数越界 fail closed；并发最多为 2。
4. 单元测试通过；测试期间没有 Provider/Telegram/network 真实调用。
