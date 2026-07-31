# Stage12 Grounded Answer P1 Attempt 04 Root Cause

- Status: `FAIL`（immutable baseline）
- Model: `deepseek/deepseek-v3.2`
- HTTP: `12/12`
- Schema/Grounding/Real Provider: `11/12`
- Failure taxonomy: `provider_schema_invalid=1`
- Fallback: `0`
- Aggregate latency: `349087 ms`
- Maximum observation latency: `77478 ms`

唯一失败是 round 1 的 2-claim shape：HTTP `200`，输出达到 `1600` token 上限，安全 fingerprint 为 `invalid_json` / `json_invalid` / `$`。其余 11 个输出全部通过完整 Schema、引用闭包、事实 atom、中文和 grounding 校验。

后续稳定性修复固定 `temperature=0.0`、`reasoning.effort=none` 和 `seed=0`，并把 `reasoning`、`seed` 纳入 P0 capability gate。Schema、grounding validator、零 fallback 和 12-call 形状均未放宽。
