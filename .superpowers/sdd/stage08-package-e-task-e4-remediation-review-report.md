# Stage08 Package E — E4 safe replay 修复独立复审报告

## Status

- Task: `E4 safe idempotency replay remediation review`
- Result: `APPROVED`
- Date: `2026-07-22`
- Findings: `0 Critical / 0 Important / 0 Minor`
- Closure recommendation: E4 I-01 已关闭；可进入 Package E 最终收口。
- Boundary: 仅复审 versioned allowlisted safe replay projection；未修改实现，未调用任何外部系统。

## Findings

### Critical

无。

### Important

无。

### Minor

无。

## Review evidence

1. `backend/app/api/routes/stage08_collaboration.py:143-146` 先用 `validate_assistant_query_safe_view` 对 service result 做 exact safe-view 校验，再通过 `_safe_replay_projection` 产生持久化投影。
2. 投影只有固定 `version/status/answer/citations/degradation_codes/draft_id` 六个字段；answer 受现有 safe-view 2000 字符和 UUID 禁止约束，citation 只有 ordinal 与稳定 label，draft UUID 只是合同已允许的公开 reference。未持久化 request query 字段、private material、authority、provider/tool/audit 载荷或其他内部 ID。
3. `_safe_view_from_replay` 对 dict exact type、六个 exact key、固定 version、每个顶层字段类型以及 citation exact shape/type 逐层验证，最后再重建并 exact-validate `AssistantQuerySafeView`。陌生字段、缺失字段、错误版本、bool ordinal、非法 citation label 和错误 degradation type 均映射为不回显的 `409 stage08_collaboration_replay_invalid`。
4. API 回归中 `completed` 首次响应与同 key/同语义 replay JSON 完全相同，且 graph call count 为 `1`；I-01 中的 answer/citations 丢失不再出现。
5. Replay 仍在读取旧投影前调用 `_require_current_query_scope`；employee 撤权后返回 `403`，同 key 不同语义仍返回 `409 idempotency_conflict`，均不会再运行 graph。
6. `stage08_collaboration.router` 仍只暴露 `POST /api/stage08/assistant/query`；修复未增加 request/response 公开字段、schema/migration、权限、Provider、Telegram、webhook、部署或网络依赖。

## Verification

```powershell
python -m pytest -q -W error -p no:cacheprovider `
  tests/api/test_stage08_collaboration_api.py
```

Result: `30 passed in 12.45s`

```powershell
git diff --check -- `
  backend/app/api/routes/stage08_collaboration.py `
  backend/tests/api/test_stage08_collaboration_api.py `
  project-docs/08-implementation/decisions/STAGE_08_E4_SAFE_REPLAY_PROJECTION_DECISION.md
```

Result: exit `0`。

## External systems and Git state

- 未调用 OpenRouter、Telegram、webhook、外部 HTTP、部署或生产数据库。
- 未执行 Git stage/commit/reset/checkout/clean/push。

