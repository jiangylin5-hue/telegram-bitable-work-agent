# Stage08 Package E — E4 Assistant Query API 实施报告

## Status

- Task: `E4 strict assistant-query API implementation`
- Result: `IMPLEMENTED + SAFE REPLAY REMEDIATED — pending independent re-review`
- Date: `2026-07-22`
- Boundary: 仅实现 `POST /api/stage08/assistant/query`；未新增 GET/list/admin/webhook/Provider 配置、schema migration 或权限角色。

## Changed files

| 文件 | 变更 |
| --- | --- |
| `backend/app/schemas/stage08_collaboration.py` | 新增 strict request schema；仅接受已批准的 7 个请求字段，extra 一律拒绝；response 直接复用 E1 `AssistantQuerySafeView`。 |
| `backend/app/api/routes/stage08_collaboration.py` | 新增唯一 POST route、redacted validation wrapper、verified identity、current member/employee/target 重验、hash-only 幂等、versioned safe replay projection 重建、commit/rollback 与固定错误映射。 |
| `backend/app/main.py` | 仅注册 `stage08_collaboration_router`；保留工作树中已有 Stage08 routers。 |
| `backend/tests/api/test_stage08_collaboration_api.py` | 新增 30 个聚焦 API 用例，包含 completed answer/citations 完整 replay 与伪造 projection 409。 |
| `.superpowers/sdd/stage08-package-e-task-e4-report.md` | 本报告。 |

## API behavior matrix

| 场景 | 行为 |
| --- | --- |
| 合法 active member + active in-workspace employee + `digital_employee.invoke` | 服务端构建 opaque command，仅调用 E1–E3 `run_stage08_collaboration` |
| 默认 unavailable Analysis Provider | `200` + 无 answer/citation/draft 的 `degraded` safe terminal，不网络调用 |
| extra/client scope/provider/budget/tool/draft/audit 字段 | redacted `422 stage08_collaboration_request_invalid`，不回显字段名或原值 |
| 未验证身份 | 现有 identity dependency 返回 `401` |
| 无 active member / 无 invoke action / inactive 或 unassigned employee | 固定 `403` |
| workspace/employee/target 不存在 | 固定非泄漏 `404` |
| target 不在 employee table scope 或 actor 不可读 | 固定 `403` |
| 同一 key + 同一语义 | 重验当前 member/employee/target 后严格重建首次完整 `AssistantQuerySafeView`，不重跑 graph |
| 同一 key + 不同语义 | `409 idempotency_conflict` |
| replay projection 未知/缺失字段、错误版本、错误类型或非法 citation | `409 stage08_collaboration_replay_invalid`，不重跑 graph |
| forged/model-construct safe view 或 unexpected service exception | rollback，固定 `500 stage08_collaboration_internal_failure`，不暴露 exception/private payload |

## Idempotency and privacy

- fingerprint 只持久化 SHA-256；query 先归一化再 hash，actor 也只进入 hash。
- `response_ref` 仅保存 `stage08-assistant-query-replay.v1` 白名单投影：`version/status/answer/citations/degradation_codes/draft_id`。其中 answer 和 citations 必须已经 `validate_assistant_query_safe_view` 验证，且受 E1 的 2000 字符、12 citations、固定 label/code 限制。
- projection 不含 query、C1/C2/C3/D4 material、Memory/RAG/group 内容、provider raw output/error、scope/authority/tool payload 或内部 ID；唯一允许的 ID 是已存在的公开 `draft_id`。
- replay 在读取旧结果之前重验 active workspace member、employee access mode/grant/action/base 与 target readability。
- API 对 service result 调用 `validate_assistant_query_safe_view`，拒绝 `model_construct` 夹带的隐藏字段。

## Verification

### E4 API focused

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/api/test_stage08_collaboration_api.py
```

Result after safe replay remediation: `30 passed in 13.20s`

### Collaboration focused regression

```powershell
python -m pytest -q -W error -p no:cacheprovider `
  tests/unit/test_stage08_collaboration_contracts.py `
  tests/unit/test_stage08_collaboration_graph.py `
  tests/unit/test_stage08_collaboration_service.py `
  tests/api/test_stage08_collaboration_api.py
```

Result after safe replay remediation: `109 passed in 14.11s`

### Real loopback PostgreSQL / pgvector regression

Docker Compose 中 `pgvector/pgvector:pg17` 容器为 `healthy`，绑定 `127.0.0.1:55432`。DSN 仅从 compose 环境动态组装到临时进程环境，未输出。

```powershell
python -m pytest -q -W error -p no:cacheprovider `
  tests/integration/test_stage08_collaboration_postgres.py
```

Result after safe replay remediation: `2 passed in 5.31s`

### Static checks

```powershell
python -m compileall -q `
  app/runtime/stage08_collaboration_contracts.py `
  app/agents/stage08_collaboration.py `
  app/services/stage08_collaboration.py `
  app/services/stage08_context_composition.py `
  app/schemas/stage08_collaboration.py `
  app/api/routes/stage08_collaboration.py
git diff --check -- backend/app/main.py
```

Result: exit `0`；新建 E4 文件额外扫描了行尾空白，无命中。生产 route/schema 无 `requests`/`httpx`/OpenRouter/Telegram/Milvus/Redis/webhook import。

### Initial corrected test issue

首次 API collection 因 warning filter 放在 `TestClient` import 之后，`-W error` 把 Starlette deprecation warning 升格为 collection error。已将 filter 移到 import 之前，之后两次 API fresh run 均通过（`22 passed`，补强后 `24 passed`）。

### Independent review remediation

E4 首轮独立审查发现 `1 Important`：completed 首次响应含已验证 answer/citations，旧 replay 仅根据 status/draft ref 重建，导致结果不完整。根据 `STAGE_08_E4_SAFE_REPLAY_PROJECTION_DECISION.md` 已修复为 versioned allowlisted safe projection；新增回归证明首次/replay JSON 完全相同、graph 只调用一次，并对六类 forged/shape/version 漂移固定返回 409。

## Skipped / out of scope

- 未调用 OpenRouter 或任何真实 Analysis Provider。
- 未调用 Telegram、webhook、外部 HTTP、部署或生产环境。
- 未新增 migration/model/permission role/Provider config。
- 未执行 broader full-backend / Package E 包级验收；依 brief 留给后续独立 review。
- 未进行 Git stage/commit/reset/checkout/clean/push。

## Remaining review points

- 独立 reviewer 需复核 versioned replay projection 的 exact allowlist、严格重建、current-scope 重验与 forged projection 409，并确认本轮 `1 Important` 已关闭。
- 本报告只建议 E4 进入 independent review，不宣布 Package E 关闭、真实 Provider 完成或生产就绪。
