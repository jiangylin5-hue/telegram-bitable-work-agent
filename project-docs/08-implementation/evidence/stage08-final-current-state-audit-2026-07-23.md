# Stage08 当前状态真实验收记录（2026-07-23）

## Status

- Evidence status: `executed`
- Scope: Stage08 A–F 的本地非生产验收复跑；不将本记录表述为 Telegram 生产发送、公开 HTTPS 或 Stage07 UI 验收。
- External action: 已执行真实 OpenRouter 分析调用；Telegram、webhook、表格写入、通知和 Provider 写入均保持禁用。
- Result: `PASS`

## 本轮可复现命令与结果

| 层级 | 命令范围 | 本轮结果 |
| --- | --- | --- |
| Unit / API | `tests/unit/test_stage08_*.py` + `tests/api/test_stage08_*.py` | `796 passed in 46.80s` |
| PostgreSQL / pgvector | 7 个 Stage08 integration 模块，逐模块连接 disposable `pgvector/pg17` 数据库 | `79 passed`：8 runtime、13 memory、20 group context、6 context、12 composition、17 retrieval、3 collaboration |
| 真实 Provider | `python scripts/stage08_real_provider_evaluation.py`，受控 ignored env 文件仅向分析 Provider 注入凭据 | `12/12 passed`、0 timeout、9/9 invocation/completion、8 usage metadata present |

数据库组令 `STAGE06_LOCAL_DATABASE_URL` 与 `STAGE08_RAG_DATABASE_URL` 指向同一个仅本机、可丢弃的 pgvector 数据库。模块逐一执行的原因是旧 Stage07 fixture 会复用 `public` schema；逐模块方式仍会真实执行迁移、PostgreSQL 和 pgvector 路径，同时避免测试夹具在不同模块之间相互清理。

## Requirement ID 逐项结论

| Requirement | Verdict | 本轮验证依据 |
| --- | --- | --- |
| A-01 | accepted | 运行时 contracts / Tool Gateway 单元回归；未知 tool、raw content、预算拒绝 |
| A-02 | accepted | 运行时 service / API deny matrix；employee、caller、chat、field 交集先于 dispatch |
| A-03 | accepted | runtime PostgreSQL 8 passed；ticket 约束、trace、并发锁、重放和终态 |
| A-04 | accepted | Tool Gateway allowlist / adapter contract 单元回归 |
| A-05 | accepted | runtime service + PostgreSQL 草稿 confirm race；源记录保持不变 |
| A-06 | accepted | runtime API / gateway redaction 回归；公开 DTO 与 audit 不含 raw carrier |
| A-07 | accepted | evaluator isolation / timeout 单测；真实 12-case 0 timeout |
| B-01 | accepted | Memory contracts + PostgreSQL 13 passed；source、scope、version、confidence、TTL、audit |
| B-02 | accepted | confirmed-record 与 PostgreSQL outbox 并发幂等回归 |
| B-03 | accepted | group context ingress / projection / security 及 group-candidate PostgreSQL 回归 |
| B-04 | accepted | Memory version / conflict / lifecycle 单元与 PostgreSQL 并发回归 |
| B-05 | accepted | TTL、deleted source、revoke 读前重校验 PostgreSQL 回归 |
| C-01 | accepted | Context Planner 的事实、retrieval、群窗口、general advice 分支单元与 PostgreSQL 回归 |
| C-02 | accepted | C1/C2/C3 strict contracts 的窗口、chunk、item、总预算及 private carrier 拒绝 |
| C-03 | accepted | composition / collaboration API 回归；真实 Provider general_advice case 无业务 citation |
| D-01 | accepted | chunk、migration、worker、reindex、cleanup、recovery pgvector 回归 |
| D-02 | accepted | RetrievalProvider 过滤与 pgvector 17 passed；权限读前后重校验 |
| D-03 | accepted | retrieval API / pgvector current citation、version、field 可访问性回归 |
| D-04 | accepted | Provider contract + PostgreSQL authority / retrieval fallback 回归 |
| E-01 – E-05 | accepted | collaboration contracts / graph / service / API 及 PostgreSQL 3 passed；实际 fan-out、取消、deadline、policy、ticket、draft、redaction |
| F-01 – F-04 | accepted | 固定 12-case 真实 Provider；脱敏 telemetry；pgvector 保持当前技术真源，Milvus 延后门槛不变 |

## 真实 Provider 脱敏结论

12 个 fixed synthetic cases 均通过：visible fact、hidden field、revoked scope、general advice、group freshness、RAG lifecycle、provider unavailable、policy deny、draft pressure、budget cancel、safe replay、multilingual。全部满足 `no_hidden_leak`、`citation_current`、`no_direct_write`、`no_external_side_effect`、`terminal_safe`、`fixture_fresh`。真实调用只用于分析，未保存完整 prompt / response、密钥、业务 ID、provider request ID 或 token/cost 原值。

## 仍不由本验收替代的生产门禁

- Stage09 公网 hostname / DNS / TLS、外网健康检查和回滚演练。
- 在明确测试群和受控发送边界后，真实 Telegram 收消息、写审计、回执的 smoke。
- Stage07 Mini App 浏览器视觉与端到端交互验收。
