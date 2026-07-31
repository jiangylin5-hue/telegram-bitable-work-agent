# Stage12 Grounded Answer P1 Attempt 03 Root Cause

- Status: `FAIL`（immutable baseline）
- Model: `qwen/qwen3-next-80b-a3b-instruct`
- HTTP: `12/12`
- Schema/Grounding/Real Provider: `2/12`
- Failure taxonomy: `provider_language_invalid=5`、`provider_schema_invalid=5`
- Fallback: `0`
- Attempts: `12`
- Aggregate latency: `141191 ms`
- Maximum observation latency: `21497 ms`

五个 Schema failure 都返回 HTTP `200`，但输出达到 `1600` token 上限并形成 `invalid_json`；五个 language failure 都是结构有效对象，但在 statement text 命中 `grounded_answer_text_language_invalid`。安全 response fingerprint 已记录 top-level shape、section/statement count、validation type/path、长度和 hash，没有保存 raw output。

该模型因此被拒绝。随后在相同 tightened prompt、完整 Schema、零 fallback 下进行四 shape 候选比较：DeepSeek V3.2 与 Qwen 235B 都为 `4/4`；DeepSeek 7-claim 输出更短、最坏测量延迟更低，因此 TDR-023 固定下一完整 P1 为 `deepseek/deepseek-v3.2`。
