# Stage12 Grounded Answer P1 Attempt 02 Root Cause

- Status: `FAIL`（immutable baseline）
- Model: `qwen/qwen3-235b-a22b-2507`
- Shape: `(1, 2, 4, 7) × 3 = 12`
- HTTP: `12/12`
- Schema/Grounding/Real Provider: `7/12`
- Failure taxonomy: `provider_language_invalid=3`、`provider_schema_invalid=2`
- Fallback: `0`
- Attempts: `12`（没有 selective retry）
- Aggregate latency: `424050 ms`
- Maximum observation latency: `69364 ms`

失败主要集中在 4/7-claim shape。两个 Schema failure 都在高输出量下发生，其中至少一个达到 profile 的 `1600` output-token 上限；三次 language failure 表明模型没有稳定遵守中文可见文本/内部 handle 隔离约束。首轮报告只保留了 response diagnostic hash，缺少安全 shape/path 字段；runner 随后补充 `response_diagnostics`，不保存 raw output。

后续修复没有放宽 Schema 或 grounding validator：System prompt 增加最少必要 section/statement、每个 claim 只出现一次、禁止可见 handle 和无请求扩写。修复后的 4-claim 探针中，Qwen 235B、DeepSeek 和 Qwen Next 80B 均通过；Qwen Next 80B 延迟最低（`8900 ms`），因此 TDR-023 将下一完整 P1 的固定候选修订为 `qwen/qwen3-next-80b-a3b-instruct`。
