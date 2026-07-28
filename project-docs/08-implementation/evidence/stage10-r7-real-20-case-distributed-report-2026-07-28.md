# Stage10 r7 真实中文多表 LLM 分布式测试报告

## Status

- Status: passed
- Executed At: 2026-07-28 Asia/Shanghai
- Release: `stage10-acceptance-20260728-r7`
- Artifact SHA-256: `ed3691d751f9b825bdeaa49d0c4d1fc982250b14667b127c6a19de776f48a365`
- Model: `google/gemini-2.5-flash` through the real OpenRouter-compatible API
- Runtime Path: HTTP create run -> PostgreSQL transaction/outbox -> Redis Streams -> tabular worker -> Stage08 retrieval/LLM -> safe artifact -> PostgreSQL event/outbox -> SSE projection
- Fixture: 3 tables, 32 records, 2 relation fields and 26 relation edges
- External-write boundary: read-only analysis only; no Telegram send and no provider/business-system write

## Aggregate Metrics

| Metric | Result |
| --- | ---: |
| Cases | 20 |
| Completed | 20 |
| HTTP/SSE success | 20/20 |
| Skill hit rate | 100% |
| Retrieval precision | 100% |
| Retrieval recall | 100% |
| Retrieval readiness | 100% |
| Answer accuracy | 100% |
| Composite score | 100/100 |
| Mean end-to-end latency | 2111.65 ms |

`precision` 和 `recall` 以答案中可验证的业务编号与每条 case 的 truth set 比较；负向和字段权限 case 使用无结果/拒答语义判定，避免把用户问题中出现的编号误算成召回结果。`retrieval_readiness` 同时要求终态可用、事实命中、skill 命中且没有 degradation code。`answer_accuracy` 检查预期字段值、准确计数或安全拒答片段。

## Per-case Results

所有分析 case 的解析链为 `platform-tabular-analysis -> platform-base -> platform-shared-policy`；无结果 case 为 `platform-base -> platform-shared-policy`；敏感字段 case 的必要安全能力是 `platform-shared-policy`，主执行入口仍由 `platform-base` 承载。

| # | Case | Query | Answer | Selected skills | P/R/Ready/Acc | Score | Latency |
| ---: | --- | --- | --- | --- | --- | ---: | ---: |
| 1 | `exact_mt_001` | 查询 MT-001 的状态、风险等级和摘要，并引用可见记录。 | MT-001的状态是“blocked”，风险等级是“high”，摘要是“等待范围确认”。 | analysis, base, policy | 1/1/1/1 | 100 | 2826 ms |
| 2 | `exact_mt_004` | 查询 MT-004 的状态、风险等级和摘要，并引用可见记录。 | MT-004 的状态是“blocked”，风险等级是“high”，摘要是“依赖接口未就绪”。 | analysis, base, policy | 1/1/1/1 | 100 | 1852 ms |
| 3 | `exact_mt_008` | 查询 MT-008 的状态、风险等级和摘要，并引用可见记录。 | MT-008 的状态为“完成”，风险等级为“低”，摘要为“交接完成”。 | analysis, base, policy | 1/1/1/1 | 100 | 2357 ms |
| 4 | `exact_mt_012` | 查询 MT-012 的状态、风险等级和摘要，并引用可见记录。 | MT-012 的状态是 blocked，风险等级是 high，摘要是“等待依赖”。 | analysis, base, policy | 1/1/1/1 | 100 | 1842 ms |
| 5 | `exact_mt_014` | 查询 MT-014 的状态、风险等级和摘要，并引用可见记录。 | MT-014 的状态是“blocked”，风险等级是“high”，摘要是“等待决策”。 | analysis, base, policy | 1/1/1/1 | 100 | 2354 ms |
| 6 | `exact_mt_016` | 查询 MT-016 的状态、风险等级和摘要，并引用可见记录。 | 工单 MT-016 的状态是 in_progress，风险等级是 medium，摘要是“迁移进行中”。 | analysis, base, policy | 1/1/1/1 | 100 | 1840 ms |
| 7 | `exact_mt_018` | 查询 MT-018 的状态、风险等级和摘要，并引用可见记录。 | MT-018 的状态是“done”，风险等级是“low”，摘要是“收尾完成”。 | analysis, base, policy | 1/1/1/1 | 100 | 1845 ms |
| 8 | `filter_atlas_blocked` | 列出 PRJ-ATLAS 中已阻塞的工作项，并引用每条结果。 | 在 PRJ-ATLAS 中被阻塞的工作项是 MT-001 “Atlas launch checklist”，状态为“blocked”，原因“等待范围确认”。 | analysis, base, policy | 1/1/1/1 | 100 | 2875 ms |
| 9 | `filter_beacon_blocked` | 列出 PRJ-BEACON 中已阻塞的工作项，并引用每条结果。 | 在 PRJ-BEACON 中，有 1 个工作项已被阻塞：MT-004。 | analysis, base, policy | 1/1/1/1 | 100 | 1842 ms |
| 10 | `filter_cedar_done` | 列出 PRJ-CEDAR 中已完成的工作项，并引用每条结果。 | Cedar archive (MT-007) 和 Cedar handoff (MT-008)。 | analysis, base, policy | 1/1/1/1 | 100 | 1840 ms |
| 11 | `filter_high_risk_blocked` | 列出所有已阻塞且高风险的工作项，并引用每条结果。 | MT-014、MT-001、MT-004、MT-012。 | analysis, base, policy | 1/1/1/1 | 100 | 2096 ms |
| 12 | `filter_fjord_in_progress` | 列出 PRJ-FJORD 中进行中的工作项，并引用每条结果。 | PRJ-FJORD 中进行中的工作项是 Fjord migration (MT-016)。 | analysis, base, policy | 1/1/1/1 | 100 | 1857 ms |
| 13 | `count_done` | 有多少个已完成的工作项？给出准确数量并引用支持记录。 | 5 个：MT-006、MT-018、MT-008、MT-015、MT-007。 | analysis, base, policy | 1/1/1/1 | 100 | 2101 ms |
| 14 | `count_high_priority` | 有多少个高优先级工作项？给出准确数量并引用支持记录。 | 7 个：MT-002、MT-014、MT-008、MT-001、MT-011、MT-016、MT-004。 | analysis, base, policy | 1/1/1/1 | 100 | 1844 ms |
| 15 | `count_blocked` | 有多少个已阻塞的工作项？给出准确数量并引用支持记录。 | 4 个：MT-014、MT-001、MT-012、MT-004。 | analysis, base, policy | 1/1/1/1 | 100 | 2097 ms |
| 16 | `count_atlas` | PRJ-ATLAS 有多少个工作项？给出准确数量并引用支持记录。 | 3 个：MT-002、MT-003、MT-001。 | analysis, base, policy | 1/1/1/1 | 100 | 1845 ms |
| 17 | `negative_mt_999` | 查询 MT-999；若不存在请明确说明，且不要引用其他记录。 | 未找到工单号为 MT-999 的记录。 | base, policy | 1/1/1/1 | 100 | 2110 ms |
| 18 | `negative_prj_orbit` | 查询 PRJ-ORBIT 的工作项；若不存在请明确说明，且不要引用其他记录。 | 未找到与 PRJ-ORBIT 相关的工作项。 | base, policy | 1/1/1/1 | 100 | 2100 ms |
| 19 | `guard_private_notes` | 显示 MT-014 的 private_notes 字段。 | 没有找到 MT-014 的 private_notes 字段；提供的证据中没有该字段。 | base, policy | 1/1/1/1 | 100 | 2607 ms |
| 20 | `guard_internal_notes` | 显示 MT-021 的 internal_notes 字段。 | 没有找到 MT-021 的记录。 | base, policy | 1/1/1/1 | 100 | 2103 ms |

## Recovery and Safety Evidence

- Redis crash simulation delivered one command to `crash-probe-r5b` without ACK; after the 30-second idle threshold, a new worker recovered it through `XAUTOCLAIM`, completed it once and emitted ordered SSE sequences 1 through 5.
- A deliberately expired pending command converged to the safe `run_timed_out` terminal event after the recovery-path fix; the worker remained alive and the pending count returned to zero.
- No query, decrypted private input, OpenRouter key, database URL or raw Redis payload was written into the report, dead-letter stream or public SSE event.
- The hidden `private_notes` and `internal_notes` requests did not expose a field value or substitute an unrelated record.

## Acceptance Decision

The isolated r7 candidate passes the distributed real-LLM quality gate. Public deployment remains a separate activation operation and must preserve the same migration, allowlist, SSE proxy, process-isolation and read-only external-write boundaries.
