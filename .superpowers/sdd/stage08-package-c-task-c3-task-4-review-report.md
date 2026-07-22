# Stage08 Package C3 / Task 4 独立复审报告

## 补救后新鲜复审结论

`PASS — no Critical / Important / Minor findings`

原 I1 已解决。补救后的 Task 4 报告和持久 PostgreSQL 证据把时间线明确拆为：T0 原始 10 项 RED（`7 passed, 3 failed`）、T1 相同 10 项的合法 fixture GREEN（`10 passed`）、T2 将单一 Memory lifecycle case 有意扩展为 lifecycle/source/scope 三项（当前 12 项），以及 T3 对当前 12 项与关联回归的重新执行。它们不再把 T0 叙述为最终 12 项的 RED。

本复审独立重跑当前语料：`python -m pytest --collect-only -q tests/integration/test_stage08_context_composition_postgres.py` 得到 12 个与 T2 描述一致的 node ID（`2.10s`）；随后在同一 disposable local PostgreSQL 环境运行模块得到 `12 passed in 20.50s`。因此 I1 的计数缺口已关闭。

这只是 Task 4 的证据复审通过，不宣布 C3 或 Package C 完成；Task 5 仍是独立的包级交接复审。

## 复审范围

- 仅复审 C3 Task 4 的 disposable local PostgreSQL 集成证据、测试和任务报告。
- 未修改生产代码、测试、schema、API、迁移、数据库、Git 状态或外部系统。
- 本报告不宣布 C3 或 Package C 完成；Task 5 仍是单独的包级交接复审。

## 初次复审结论（已被上述补救后复审取代）

`FAIL — evidence correction required`

当前实现与新 PostgreSQL 集成用例的安全行为复现通过，未发现群正文泄露、外部副作用或当前状态重读缺陷。但 Task 4 报告和持久证据把“完整新增集成语料”的初始 RED 记为 `7 passed, 3 failed`，而当前该文件实际收集 12 项。这两个数字无法自洽，且未说明另外两项用例是在 RED 后新增还是未执行；因此无法按 brief 独立确认“原始 3 个失败”的完整、准确历史。该问题必须在证据叙述中更正或补充可核验的原始命令证据后，Task 4 才能通过。

## 初次复审发现（I1 已解决，保留以说明审计轨迹）

### Important

1. **I1 — RED 测试计数与当前完整集成语料不一致。**
   - `backend/tests/integration/test_stage08_context_composition_postgres.py` 现收集 12 项：1 个 direct、2 个 C1 business drift、3 个 Memory drift、5 个 C2 drift、1 个 pending drift。
   - `.superpowers/sdd/stage08-package-c-task-c3-task-4-report.md` 与 `project-docs/08-implementation/evidence/stage08-package-c3-composition.md` 均称“新集成语料”的首次 RED 为 `7 passed, 3 failed in 17.69s`，合计仅 10 项。
   - 如果最初只有 10 项，报告必须准确说明其范围、随后新增的两项和各自的 RED/GREEN 状态；如果当时已是当前 12 项，计数或结果记录错误。现有文本无法区分这两种情况，因而无法独立验证“3 个失败均在 C3 renderer 前被 fixture 合法性拒绝”的完整性。
   - 影响：证据/TDD 可追溯性，不是已复现的生产实现或隐私漏洞。修复应限于报告/证据的事实更正或补充可审计的原始输出；不需要修改 C3 生产代码。

### Critical / Minor

- 无。

## 已独立复现的行为与边界

1. 测试只使用 `stage06_postgres` fixture；该 fixture 从 `STAGE06_LOCAL_DATABASE_URL` 读取地址、先执行本地 disposable PostgreSQL 分类检查，并在每个 fixture 生命周期中重置后迁移到 head。Task 4 每个用例都通过 `try/finally` 调用 `session.rollback()` 与 `session.close()`；未见 production database、Telegram、Provider、HTTP 或网络调用。
2. 合法 direct 路径先渲染 C1，再以 D6 固定头渲染授权 group fragment，且测试验证 newest fragment 在 older fragment 之前。
3. C1 relation/record、field visibility、Memory lifecycle/source/scope 漂移均在渲染时重新读取；C2 mapping/relation/provenance/source-chat-type/retention/purge 漂移不会保留旧 group body。仍有资格的 C1 可保留，这是批准的 direct-path 语义。
4. pending 用例实际构造 `49 × 500 = 24,500` 字符窗口，初始 view 为 `group_compression_pending` 且 group rendered chars 为 0；随后 source-chat-type 漂移后 renderer 返回 `None`。用例还验证群正文不在 `repr` 和 safe view JSON 中。
5. 组合服务仅依赖既有 C1/C2 service 与权限对象；其源码不导入 Message、Telegram、Provider、HTTP、Redis、vector、LangGraph、Memory persistence、audit/outbox、`ContextCompressor` 或 digest。safe view contract 只暴露状态和计数；相关已存在的单元回归还覆盖 pending 下的 actor/record/binding/mapping/scope lineage 拒绝与不可物化断言。
6. PostgreSQL 测试仅构造 synthetic Message shell，`raw_text`、`raw_caption`、`normalized_text` 均为 `None`，没有填入或断言真实原始消息字段。所有 group fragments、标识与内容均为测试专用合成值，未进入 evidence、public DTO 或安全视图。

## 命令证据

| 命令 | 独立结果 | 说明 |
| --- | --- | --- |
| `python -m pytest -q tests/integration/test_stage08_context_composition_postgres.py`（临时把 `DATABASE_URL` 设为 `STAGE06_LOCAL_DATABASE_URL`，结束后恢复） | `12 passed in 19.48s` | disposable local PostgreSQL 集成模块通过。 |
| `python -m pytest --collect-only -q tests/integration/test_stage08_context_composition_postgres.py` | `12 tests collected in 1.81s` | 用于确认 I1 的当前用例数。 |
| `python -m pytest -q tests/unit/test_stage08_context_composition_contracts.py tests/unit/test_stage08_context_composition_service.py` | `63 passed in 1.35s` | 相关 C3 contract/service 回归通过。 |
| `python -W error -m pytest -q` 同上两份 unit 文件 | 未通过，pytest 收集期将既有 `pytest-asyncio` 的 `asyncio_default_fixture_loop_scope` 配置弃用警告提升为错误 | 此命令未计入通过；与 Task 4 代码无关，但需在未来全局测试配置中处理。 |
| `python -m compileall -q app/runtime/stage08_context_composition_contracts.py app/services/stage08_context_composition.py` | exit `0` | 编译检查通过。 |
| 禁止依赖静态扫描 + `git diff --check -- backend project-docs/08-implementation docs/superpowers` | 禁止依赖零命中；diff check exit `0` | 仅输出既有 dirty worktree 的 LF/CRLF 提示，没有 whitespace error。 |

## 后续步骤

1. I1 已由 T0/T1/T2/T3 的明确分段、原始 10 项 node 范围和当前 12 项 collect-only 结果解决。
2. 之后由 Task 5 进行 C3 包级安全/交接复审；本报告不替代该步骤。
