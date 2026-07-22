# Stage08 Package C Task C1 实施报告

## Status

- Task status：`completed-task-level / independently-reviewed PASS (Fix Round 3)`
- Package status：Package C 未完成；C2/C3 未实施。Package B B5 已在后续独立复审后关闭，不再构成 C3 的前置风险。
- Review closure：三轮独立审查已收口。首轮 `1 Critical / 4 Important / 1 Minor` 与第二轮 `0 Critical / 2 Important / 1 Minor` 均已最小修复；Fix Round 3 为 `PASS / 0 Critical / 0 Important / 1 Minor`。该状态仅表示 C1 任务级完成，不表示 Package C 或 Stage08 验收完成。
- Scope compliance：C1 仅新增上下文合同、服务、测试和证据；按确认后的设计文档，仅在既有 `stage08_memory.py` 增加内部 `read_only` 读取模式。未新增 API、router、migration、schema、permission、Telegram/Message、LLM/RAG 或外部调用。

## Changed files

| 文件 | 变更 |
| --- | --- |
| `backend/app/runtime/stage08_context_contracts.py` | 新增 strict/frozen 的 planning request、budget、scope、source、plan、evidence、omission、usage、pack 合同及 service-boundary 重校验；补齐 intent/source 精确矩阵和证据安全约束。 |
| `backend/app/services/stage08_context.py` | 新增关系解析、确定性 planner、消费时重读 composer、预算 canonicalizer 和 ID-free renderer；修复多 view 总预算、精确 Memory scope 和敏感元数据 fail-closed。 |
| `backend/app/services/stage08_memory.py` | 为 C1 内部读取增加默认保持原行为的 `lifecycle_aware` 与无副作用 `read_only` 模式；`read_only` 仍校验成员、TTL、source、scope，但不改变生命周期、不写 audit。 |
| `backend/tests/unit/test_stage08_context_contracts.py` | 覆盖 intent/source 矩阵、优先级/原因、最多三个 view、总预算、pack-plan 绑定、构造绕过、UUID 与敏感 metadata。 |
| `backend/tests/unit/test_stage08_context_service.py` | 覆盖 resolver/planner/composer/reread、精确 Memory scope、多 view 全局预算、canonicalization、renderer 与真实组合路径攻击。 |
| `backend/tests/unit/test_stage08_memory_service.py` | 覆盖 `read_only` TTL/source drift 不改变 item 状态且不新增 audit，并保留默认 lifecycle 回归。 |
| `backend/tests/integration/test_stage08_context_postgres.py` | 覆盖真实本地 PostgreSQL 关系、字段撤权、漂移、Memory 只读无副作用与 group/Message 隔离。 |
| `project-docs/08-implementation/evidence/stage08-package-c-context.md` | 更新首轮修复、RED/GREEN、fresh commands、真实 PostgreSQL、安全边界、skips、risks 与 cleanup 证据。 |
| `.superpowers/sdd/stage08-package-c-task-c1-report.md` | 本任务交付报告。 |

## Fix Round 1

1. `ContextPlan` 现在执行精确 intent/source matrix：`business_fact` 必须包含 table，`memory_lookup` 必须包含 Memory，`mixed` 必须同时包含 table 与 Memory，`general_advice` 只能包含 advice；table 最多三个唯一 view。
2. source 的 `priority`、`reason` 与 intent 精确绑定；多个 table source 和 Memory source 的 `max_items` 总和不得超过 plan budget。planner 对多个 view 做稳定、确定性的总预算分配。
3. `ContextPack` 将 evidence 类型、workspace、ordinal、selected/truncated/omission/content usage 精确绑定到 plan 和实际内容；构造后的对象也必须在 service boundary 重校验。
4. evidence canonicalization 会替换任意字符串或 key 内嵌 UUID，删除内部 identifier key，并对 token、permission、identity、source reference 等敏感 metadata fail closed；renderer 不输出 scope UUID、record/Memory ID 或内部路径。
5. `memory_lookup` 允许 customer/project business scope；Memory scope 与请求 scope 做双向精确匹配，缺失、错误、额外维度均拒绝。
6. C1 调用 `read_memory_projection(..., lifecycle_mode="read_only")`。TTL/source drift 只导致本次读取为空，不更新 item 状态、不写 lifecycle audit；默认 `lifecycle_aware` 行为保持不变。
7. canonicalization 补齐长字符串、长列表、深度、NaN/Infinity、稳定 path、单项与总字符预算测试；零额度 source 不会向底层 view service 传递 `limit=0`。

## Fix Round 2 与 Fix Round 3 收口

1. `ContextPack` 现将每个 `platform_record` evidence 精确绑定到计划中的 `view_id`、view source version、业务 scope 与该 source 的 `max_items`；`memory_item` 同样受已计划 source、精确 scope 和 source 上限约束；唯一 `general_advice` marker 只能使用固定的 scope/version/content 形状。
2. evidence content 在合同层拒绝内部 identifier carrier，包括 `id`、`record_id`、`memory_id` 及其规范化变体；嵌入式 UUID、token、permission、identity 与 source-reference 仍保持 fail-closed。正常构造及 `model_construct` 后的边界重验证均拒绝攻击对象。
3. 新增真实本地 PostgreSQL 的 `(customer=None, project=None)` 成功路径，并保留客户、项目、双维度和不匹配的范围回归。
4. Fix Round 3 独立复审实际复跑构造绕过、`read_only` 与默认 `lifecycle_aware` 路径、UUID/内部 ID 脱敏、scope/budget/normalization。结论为 `PASS`；唯一 Minor 是本报告与证据的旧计数，现已同步。

## Verification

- C1 unit：`74 passed in 1.20s`。
- Context + Memory focused unit：`158 passed`（C1 `74` + Memory `84`，分别复跑）。
- C1 real local PostgreSQL：`6 passed in 9.00s`，目标仅为已授权的 disposable local PostgreSQL。
- C1 + Package A/B focused regression：`196 passed in 9.37s`。
- `compileall`：exit `0`。
- forbidden production dependency scan：`NO_FORBIDDEN_C1_PRODUCTION_MATCHES`；API/router/migration registration scan：`NO_C1_ROUTE_OR_MIGRATION_REGISTRATION`。
- scoped `git diff --check`：exit `0`。

## Skipped tests and external boundaries

- 未运行 full backend suite、前端 suite 或 Stage08 package acceptance；本轮以 C1 修复和直接回归为范围。
- 未调用 Telegram、Provider/LLM/OpenRouter、HTTP/network、Redis、RAG/pgvector 或 LangGraph。
- 未部署，未写 staging/production，未发送消息。
- 未新增 API/router、migration、schema、permission action/role、ticket、draft、notification 或 AgentRun。

## Remaining risks

- C1 三轮独立审查已完成并通过；任务级风险已收口。
- Package C C2/C3 尚未完成，因此 C1 不提升 Package C 或 Stage08 状态；Package B B5 已在后续独立复审后关闭。
- C2 的 group recent window、Message/history、retention、edit/delete/version/order 仍是独立合同门禁；C1 没有预埋这些读取路径。
- 后续 Package E 仍需把 C1 纳入 read-only ticket/Coordinator lifecycle；C1 自身不是执行入口。

## Temporary cleanup

- 无临时脚本、fixture 文件、服务或外部资源保留。
- PostgreSQL fixture 仅使用授权的 disposable local schema，并在每项测试结束 rollback 业务事务。
- 未 stage、commit、reset、checkout 或 clean。
