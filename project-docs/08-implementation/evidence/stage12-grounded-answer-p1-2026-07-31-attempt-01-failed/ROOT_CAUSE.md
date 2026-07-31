# Stage12 Grounded Answer P1 Attempt 01 Root Cause

- Status: `FAIL`（immutable baseline）
- Model: `google/gemini-2.5-flash`
- Shape: `(1, 2, 4, 7) × 3 = 12`
- Result: HTTP `0/12`、Schema `0/12`、Grounding `0/12`、Real Provider `0/12`
- Failure taxonomy: `provider_http_error=12`
- Selective retry: `0`
- Fallback: `0`

一次额外的单请求 root-cause probe（不计入 P1）读取了 OpenRouter/上游安全错误分类：HTTP `400`、Provider `Google AI Studio`、status `INVALID_ARGUMENT`。上游说明完整 `GroundedAnswerPlanV2` Schema 产生的 serving states 过多。没有保存 raw prompt、raw model output、secret 或完整上游响应。

TDR-023 随后使用同一完整 Schema 对国产候选做一次兼容探针：Qwen 与 DeepSeek 完成，GLM HTTP 失败。用户授权使用国内模型后，Stage12 Grounded Composer P1/P2/P3 固定为 `qwen/qwen3-235b-a22b-2507`。Schema 和后端 grounding contract 未降级。
