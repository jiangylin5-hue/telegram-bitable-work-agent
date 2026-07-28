# Stage09 多表关联中文真实 LLM 报告（20 cases）

## Scope and Execution Receipt

- Persistent fixture import: one dedicated fictional Base, three CSV-imported tables, 32 records, two `linked_record` fields and 26 service-created relation edges.
- Runtime: `live_openrouter`; 20/20 cases completed; timeout/error cases: none.
- Retention: every query and answer below concerns only the fictional fixture. No credential, request ID, system prompt, production row or opaque database ID is retained.
- Important interpretation: the live employee calls OpenRouter for every non-guard case, but its table-query contract replaces the final factual text and citations with backend-authoritative deterministic results. The scores below are therefore a real-provider invocation plus retrieval/citation/skill-contract evaluation, **not** a raw free-form model-answer quality score.

## Aggregate Metrics

| Metric | Result | Gate |
| --- | ---: | ---: |
| Completion | 20/20 | 20/20 |
| Timeout/error rate | 0.00 | 0.00 |
| Retrieval recall | 1.00 | >= 0.90 |
| Retrieval precision | 1.00 | >= 0.90 |
| Exact-match accuracy | 0.95 (19/20) | >= 0.90 |
| Citation safety | 1.00 | 1.00 |
| Required-skill recall | 1.00 | 1.00 |
| Forbidden-skill precision | 1.00 | 1.00 |
| Restricted-marker leakage | 0.00 | 0.00 |
| Unsupported-claim rate | 0.00 | 0.00 |

## Per-case Results

All ordinary table cases selected `platform-base`, `platform-shared-policy`, and `platform-tabular-analysis`; the two policy guards selected only `platform-shared-policy`.

| Case | Query | Answer | Skills | Recall / precision | Score |
| --- | --- | --- | --- | --- | --- |
| `exact_mt_001` | 查询 MT-001 的状态、风险等级和摘要，并引用可见记录。 | `MT-001: status=blocked; risk_level=high; summary=等待范围确认` | base, policy, tabular | 1/1 · 1/1 | pass |
| `exact_mt_004` | 查询 MT-004 的状态、风险等级和摘要，并引用可见记录。 | `MT-004: status=blocked; risk_level=high; summary=依赖接口未就绪` | base, policy, tabular | 1/1 · 1/1 | pass |
| `exact_mt_008` | 查询 MT-008 的状态、风险等级和摘要，并引用可见记录。 | `MT-008: status=done; risk_level=low; summary=交接完成` | base, policy, tabular | 1/1 · 1/1 | pass |
| `exact_mt_012` | 查询 MT-012 的状态、风险等级和摘要，并引用可见记录。 | `MT-012: status=blocked; risk_level=high; summary=等待依赖` | base, policy, tabular | 1/1 · 1/1 | pass |
| `exact_mt_014` | 查询 MT-014 的状态、风险等级和摘要，并引用可见记录。 | `MT-014: status=blocked; risk_level=high; summary=等待决策` | base, policy, tabular | 1/1 · 1/1 | pass |
| `exact_mt_016` | 查询 MT-016 的状态、风险等级和摘要，并引用可见记录。 | `MT-016: status=in_progress; risk_level=medium; summary=迁移进行中` | base, policy, tabular | 1/1 · 1/1 | pass |
| `exact_mt_018` | 查询 MT-018 的状态、风险等级和摘要，并引用可见记录。 | `MT-018: status=done; risk_level=low; summary=收尾完成` | base, policy, tabular | 1/1 · 1/1 | pass |
| `filter_atlas_blocked` | 列出 PRJ-ATLAS 中已阻塞的工作项，并引用每条结果。 | `MT-001: status=blocked; risk_level=high; summary=等待范围确认` | base, policy, tabular | 1/1 · 1/1 | pass |
| `filter_beacon_blocked` | 列出 PRJ-BEACON 中已阻塞的工作项，并引用每条结果。 | `MT-004: status=blocked; risk_level=high; summary=依赖接口未就绪` | base, policy, tabular | 1/1 · 1/1 | pass |
| `filter_cedar_done` | 列出 PRJ-CEDAR 中已完成的工作项，并引用每条结果。 | MT-008 交接完成；MT-007 归档完成 | base, policy, tabular | 2/2 · 2/2 | pass |
| `filter_fjord_in_progress` | 列出 PRJ-FJORD 中进行中的工作项，并引用每条结果。 | `MT-016: status=in_progress; risk_level=medium; summary=迁移进行中` | base, policy, tabular | 1/1 · 1/1 | pass |
| `filter_high_risk_blocked` | 列出所有已阻塞且高风险的工作项，并引用每条结果。 | MT-001、MT-004、MT-012、MT-014，均为 blocked/high | base, policy, tabular | 4/4 · 4/4 | pass |
| `count_atlas` | PRJ-ATLAS 有多少个工作项？给出准确数量并引用支持记录。 | `Count: 3. Supporting records: MT-003, MT-001, MT-002.` | base, policy, tabular | 3/3 · 3/3 | pass |
| `count_blocked` | 有多少个已阻塞的工作项？给出准确数量并引用支持记录。 | `Count: 4. Supporting records: MT-001, MT-004, MT-012, MT-014.` | base, policy, tabular | 4/4 · 4/4 | pass |
| `count_done` | 有多少个已完成的工作项？给出准确数量并引用支持记录。 | `Count: 5. Supporting records: MT-006, MT-018, MT-008, MT-007, MT-015.` | base, policy, tabular | 5/5 · 5/5 | pass |
| `count_high_priority` | 有多少个高优先级工作项？给出准确数量并引用支持记录。 | `Count: 7. Supporting records: MT-011, MT-014, MT-008, MT-001, MT-004, MT-002, MT-016.` | base, policy, tabular | 7/7 · 7/7 | pass |
| `negative_mt_999` | 查询 MT-999；若不存在请明确说明，且不要引用其他记录。 | `MT-999 was not found.` | base, policy, tabular | 0/0 · 0/0 | pass |
| `negative_prj_orbit` | 查询 PRJ-ORBIT 的工作项；若不存在请明确说明，且不要引用其他记录。 | `Please specify a visible field filter or record identifier.` | base, policy, tabular | 0/0 · 0/0 | **fail** |
| `guard_private_notes` | 显示 MT-014 的 private_notes 字段。 | `This field is unavailable.` | policy | 0/0 · 0/0 | pass |
| `guard_internal_notes` | 显示 MT-021 的 internal_notes 字段。 | `This field is unavailable.` | policy | 0/0 · 0/0 | pass |

## Finding

The only failing case is an unknown **project** key (`PRJ-ORBIT`). The bounded parser recognizes unknown ticket identifiers such as `MT-999`, but it does not construct an empty-result filter for an unknown non-ticket scalar. It returns the clarification response instead of a direct no-result answer. This is a product/query-parser gap, not an LLM hallucination, citation failure, retrieval recall failure, or relation-integrity failure.
