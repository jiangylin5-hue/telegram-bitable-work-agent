# Stage08 Package F — F3 R2 执行报告

## Status

- Result：`EXECUTED / PASS`
- Executed at：`2026-07-22T06:29:54+08:00`
- Real batch count：`1`
- Retry count：`0`
- Outcome：`12/12 passed`、`0 failed`、`0 timed out`
- Package boundary：仅完成 F3 R2 受控真实 Provider 合成评测；未声称 Stage08 或生产验收完成。

## Start gate

- F3 general-advice 修复独立审查为 `PASS / 0 Critical / 0 Important / 0 Minor`。
- 按 brief 运行离线前置测试：`46 passed, 2 deselected in 21.12s`。
- 任务指定 env 文件仅检查到“存在且被 Git 忽略”；未读取、打印、复制、修改或持久化任何值。
- 初版 F3 evidence 执行前后 SHA-256 均为 `314AEB2C87FD7E41F52E3A671CE930CD896FF9F8B116CBF70FAF138DB9ABB8D1`，原 `11/12 HOLD` 记录保持不变。

## Execution result

唯一一次真实命令通过单进程 `STAGE08_F_ENV_FILE` 指向指定 ignored env 后运行 `python scripts/stage08_real_provider_evaluation.py`，进程以 exit code `0` 结束。

- `case_count=12`
- `passed_count=12`
- `failed_count=0`
- `timed_out_count=0`
- `all_cases_passed=true`
- `all_gates_passed=true`
- Provider：`9 invoked / 9 completed / 8 usage-metadata-present`
- Terminal：`completed=6`、`draft_pending=1`、`degraded=1`、`denied=2`、`failed=1`、`cancelled=1`、`timed_out=0`
- Latency：`under_250ms=4`、`under_1s=0`、`under_5s=4`、`over_5s=4`、`timeout=0`、`unknown=0`

`general_advice` 在 R2 中以 `completed` 结束，引用数为 0，`citation_current=true`，其余安全门禁全部为 true。完整允许字段级记录见 `project-docs/08-implementation/evidence/stage08-package-f-real-provider-r2.md`。

## External and retention boundary

- 只允许 F1 OpenRouter inference 出网；没有第二次真实批次或自动重试。
- Telegram 保持 `dry_run`；未发送消息、未调用 webhook。
- 未确认 draft、未部署、未执行 Provider write 或 notification write。
- 未保留 prompt、answer、fixture body、内部 ID、token/cost 数值、request ID、异常正文、原始响应或 credential。
- 只新增 R2 evidence/report；未改写旧 F3 evidence。

## Verification

- 离线 F1/F2 preflight：`46 passed, 2 deselected`。
- R2 runner：固定 `12/12`，exit code `0`。
- 旧 evidence 完整性：SHA-256 与复审基线一致。

## Remaining gate

F3 R2 实际批次已经完成并通过，但 Package F 尚需新的独立审查确认：版本化证据完整性、12-case/Provider 计数自洽、`general_advice` 空引用合同、无外部写入边界与旧 evidence 不可变性。独立审查前不把本报告升级为 Stage08 或生产验收结论。
