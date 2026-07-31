# Stage12 Grounded Answer P1 Attempt 05 Root Cause

- Status: `FAIL`（immutable baseline）
- Model: `deepseek/deepseek-v3.2`
- Experiment: `temperature=0.0`、`reasoning.effort=none`、`seed=0`
- HTTP: `12/12`
- Schema/Grounding/Real Provider: `9/12`
- Failure taxonomy: `provider_schema_invalid=3`
- Fallback: `0`
- Aggregate latency: `161304 ms`
- Maximum observation latency: `24088 ms`

三次失败均为 HTTP `200` 后达到 `1600` output-token 上限并形成 `invalid_json`：round 1 的 1-claim、round 1 的 7-claim、round 2 的 7-claim。该结果比 attempt 04 的 `11/12` 更差，说明固定 seed 放大了特定请求的退化输出；seed/temperature 实验已撤销，不进入候选实现。

剩余稳定性问题不能再靠选择性重跑或随机参数掩盖。下一建议是缩短 private Provider reference handle 并实现真实 wall-clock deadline；两者分别涉及 private schema contract 和 Gateway transport 行为，必须先写明影响并按项目确认规则执行。
