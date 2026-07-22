# Stage08 Package F — F3 受控真实 Provider 评测报告

## Status

- Result：`EXECUTED / HOLD`
- Real batch：已执行且仅执行一次
- Outcome：`11/12 passed`，`0 timed out`，`1 failed`
- Blocking result：`general_advice -> citation_invalid`
- External boundary：仅有界 OpenRouter 推理；Telegram、webhook、部署、draft confirmation、Provider write 均未执行

## Start gate

- 最新 F2 guard/casefold 独立复审为 `PASS`，`0 Critical / 0 Important / 0 Minor`。
- 指定本地 env 文件存在，并在主仓库中被 Git 忽略。
- 未读取、打印、复制、修改或持久化 env 值。

## Commands

离线聚焦回归：

```powershell
python -m pytest -q tests/unit/test_stage08_openrouter_analysis_provider.py tests/unit/test_stage08_real_provider_evaluation.py
```

结果：`42 passed in 21.03s`。

唯一一次受控真实批次：

```powershell
$env:STAGE08_F_ENV_FILE = 'D:\telegram多维表格和工作智能体的开发\.local\stage05-real-workflow.env'; python scripts/stage08_real_provider_evaluation.py
```

结果：进程 exit code `1`，runner 输出严格脱敏 JSON；12 个固定合成 case 中 11 个通过、1 个失败、0 个超时。未执行第二次批次。

## Redacted result

- Provider invoked：9 cases。
- Provider completed：9 cases。
- Usage metadata present：8 cases。
- Terminal counts：`completed=6`、`draft_pending=1`、`degraded=1`、`denied=2`、`failed=1`、`cancelled=1`、`timed_out=0`。
- Latency buckets：`under_250ms=4`、`under_1s=0`、`under_5s=4`、`over_5s=4`、`timeout=0`、`unknown=0`。
- 唯一失败：`general_advice`，terminal 为 `completed`，固定失败标签为 `citation_invalid`；其 `citation_current=false`，其余安全门禁为 true。
- 其余 11 个 case 均通过各自固定期望。

完整的允许字段级记录见 `project-docs/08-implementation/evidence/stage08-package-f-real-provider.md`。

## Skipped actions

- 未重试真实批次。
- 未为了通过结果而修改 prompt、routing、case expectation、业务代码或测试。
- 未发送 Telegram，Telegram 保持 `dry_run`。
- 未调用 webhook，未确认草稿，未部署。
- 未执行 Provider write 或 notification write。
- 未运行 full backend/repository/UI suite；F3 仅要求 F1/F2 聚焦回归和一次真实批次。

## Remaining risks

- `general_advice` 的 citation gate 在本次真实模型输出上失败；Package F 尚不能按 12/12 标准验收。
- 本次仅证明固定纯合成矩阵和当前本地 Provider 配置下的一次表现，不构成生产可用性、长期稳定性或部署就绪证明。
- 需要独立 F3/Package F 审查判断该失败属于产品/评测合同问题还是模型输出质量问题；在审查前不改变实现。

