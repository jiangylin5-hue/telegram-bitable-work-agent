# Stage08 Package B — Task B3 Independent Review

## Verdict

- Current review round: **Fix Round 2 re-review**
- Spec compliance: **通过 / approved**。
- Task code quality: **通过 / approved**。
- Critical findings: 0
- Important findings: 0
- Minor findings: 0

确认无问题的主要边界：confirmation hook 的调用顺序位于现有确认 audit 之后；新事件 payload 是精确六个 reference 字段；pending materialization 会重读 record/policy/field/actor/scope 并在 B2 成功后才置 `processed`；HMAC 使用独立环境变量，安全读取投影排除了 `identity_token`；未发现 B3 直接修改 source record 或新增外部调用。

## Initial Review Findings (historical)

### I-1 [Resolved in Fix Round 1] Processed-event 重放绕过 actor/field/scope 重新授权，并可能返回错误的 Memory

- References: `backend/app/services/stage08_memory.py:212-213`, `backend/app/services/stage08_memory.py:786-808`
- `event.status == "processed"` 时直接进入 `_memory_item_for_processed_event`。该 helper 的 `actor`、`now` 参数完全未使用，也不执行 active membership、field visibility、scope/source validity、TTL/status 检查。
- 它仅按 payload 中的 `workspace_id + record_id + record_version` 扫描 `source_refs`，没有校验精确六键、`table_id`、`policy_version`、`rule_index`、memory type 或 event-to-item fingerprint。因此同一 source/version 存在多个 Memory 时可能返回另一规则/流程的 item；被撤权 actor 也能拿到 ORM item（包含 payload 和内部 scope）。
- 针对性复现：先以 owner materialize 并把 event 置为 `processed`，随后用非 workspace 成员重放，结果 `unauthorized_replay_returned_item=True`。
- Required change: processed replay 必须 fail closed。要么在完整重建并重新授权后精确定位该事件对应 item，要么安全地返回 `None`；不能以 record/version 模糊匹配并绕过 B2/read safety checks。

### I-2 [Resolved in Fix Round 1] Policy 接受多条有效规则，却静默只处理第一条

- References: `backend/app/services/stage08_memory.py:581-596`, `backend/app/services/stage08_memory.py:148`, `backend/app/services/stage08_memory.py:167-178`
- `_memory_policy` 验证并接受任意非空 rules 列表，但 enqueue 固定读取 `rules[0]`、固定 `rule_index=0`，其余有效规则不会生成事件或 Memory，也没有拒绝该 policy。
- 这违反 review package 要求的“multiple rules 不得静默丢失”语义；report 中的 follow-up 说明不能把运行时数据丢失变成安全行为。
- 针对性复现：policy 含两条有效规则时，输出为 `accepted_rule_count=2, event_count=1, rule_indices=[0]`。
- Required change: 在已批准的 singular interface 下，应明确拒绝 `len(rules) != 1` 并 fail closed；如需多规则，应先获得并实现明确的 multi-event contract。

### I-3 [Partially resolved in Fix Round 1] 强制 TDD 矩阵未落实，且恰好遗漏了上述安全/语义缺陷

- References: `.superpowers/sdd/stage08-package-b-task-b3-brief.md` TDD cases 1-6; `backend/tests/unit/test_stage08_memory_confirmed_record.py:90-204`
- Task test 仅覆盖直接 enqueue/materialize、pending draft、version=2 policy、identity differentiation、update confirmation hook 和 safe reader exclusion。
- 缺少 brief 明确要求的 create-draft integration、rejected/failed draft、unconfigured policy、unreadable/removed field、stale record version、invalid scope、inactive resource、actor permission revocation、missing HMAC key、multiple rules、processed replay authorization/precise correlation，以及并发/idempotency database behavior。
- 现有 replay assertion（`backend/tests/unit/test_stage08_memory_confirmed_record.py:121`）只用原 owner 重放，未验证 processed path 的授权；policy fixture 永远只有一条 rule（`:53-69`）。实施报告声称的广泛 fail-closed/idempotency coverage 因此超出实际证据。
- Required change: 修复 I-1/I-2 后补齐 brief 的负向和重放测试；并发/唯一约束至少需要 B3 PostgreSQL 证据或清晰地移交到已确认的 B5 acceptance gate，不能只依赖 in-memory 顺序执行。

## Verification

- 已审阅 task brief、implementer report、review package、Stage08 data/security contract section 7，以及 review package 指定的全部 source/test 文件。
- 运行了两项只针对具体 finding 的内存复现；未重复运行报告中已通过的 `71 passed` 套件。
- 未修改 production code、tests、既有 docs、Git state 或外部系统；仅新增本 review 文件。

## Fix Round 1 Re-review

### Resolution status

- Initial I-1: **resolved**. `processed` replay now returns `None` before any ambiguous item lookup (`backend/app/services/stage08_memory.py:212-216`).
- Initial I-2: **resolved in code and source-of-truth docs**. `_memory_policy` now requires exactly one rule (`backend/app/services/stage08_memory.py:584-599`), and brief/contract both record the singular-interface boundary.
- Initial I-3: **partially resolved**. Negative coverage increased materially and PostgreSQL concurrency evidence is explicitly handed to B5, but the required actor-drift and lifecycle/idempotency paths below remain absent.
- Scope: no B3 Fix Round 1 production scope creep identified.

### Important FR1-I-1: Pending-event actor revocation escapes as `PlatformValidationError` instead of failing closed through the B3 adapter

- References: `backend/app/services/stage08_memory.py:247-260`, `backend/app/services/stage08_memory.py:39-46`, `backend/tests/unit/test_stage08_memory_confirmed_record.py:207-217`
- The new revocation test only revokes membership **after** the event is already `processed`; line 215 returns `None` before actor validation, so it does not test materialization-time actor revalidation.
- Targeted reproduction created a pending event, disabled the confirming member, then called the B3 materializer. `_projection_from_confirmed_record` still produced a projection, after which B2 raised `PlatformValidationError("actor_not_workspace_member")`; the B3 function did not return `None`. The event remained pending and no Memory was created, but the raw exception contradicts the task report's stated invalid/unreadable error behavior and leaves an untested adapter error path.
- Required change: add a pending-event membership/actor revocation test and normalize the expected B3 fail-closed outcome around the B2 delegation (or explicitly revise the approved interface/error contract and worker handling). Also cover field visibility drift after enqueue; targeted reproduction currently returns `None` and leaves the event pending as intended.

### Important FR1-I-2: Required TDD semantics are still only partially asserted

- References: `.superpowers/sdd/stage08-package-b-task-b3-brief.md` TDD cases 1, 4 and 6; `backend/tests/unit/test_stage08_memory_confirmed_record.py:143-172`, `backend/tests/unit/test_stage08_memory_confirmed_record.py:233-250`
- The create-draft test stops after checking one event and never materializes it or verifies its policy-limited Memory payload, although case 1 requires create and update paths through materialization.
- The identity test covers only the “different subject stays separate” half. It never proves that unchanged `customer + subject` produces the intended same-identity lifecycle comparison when payload/source version changes.
- No task-local assertion calls the enqueue adapter twice for the same six references and proves the same event/no duplicate; processed replay is covered, but adapter replay from case 6 is not.
- Targeted diagnostics show create materialization currently succeeds and field drift fails closed, so these are evidence gaps rather than additional demonstrated production failures. They remain required task-level regression tests before I-3 can close.

### Important FR1-I-3: The updated task report contradicts the implemented and approved cardinality rule

- References: `.superpowers/sdd/stage08-package-b-task-b3-report.md:65`, `.superpowers/sdd/stage08-package-b-task-b3-report.md:73-80`, `backend/app/services/stage08_memory.py:148`
- The unchanged `Risks / Follow-up` section says the implementation “materializes the configured first rule,” while Fix Round 1 and the source-of-truth docs correctly state that any multi-rule policy fails closed. Both cannot describe the current implementation.
- The enqueue docstring still says “for the first rule,” which is now misleading because cardinality validation guarantees exactly one rule.
- Required change: replace the stale report risk statement and update the docstring to the singular exactly-one-rule contract. This is documentation consistency only; the cardinality implementation itself is correct.

### Fix Round 1 verification

- Re-read the updated report, prior review, B3 brief, Stage08 data/security contract, current B3 implementation/integration/UoW/contracts, and complete task-local test file.
- Did not rerun the implementer's identical passing 11/77-test suites.
- Ran targeted in-memory diagnostics only for previously untested cases: pending actor revocation raised `PlatformValidationError` with event still pending; field visibility drift returned `None` with event pending; confirmed create event materialized the expected policy payload and became processed.
- No production code, tests, source-of-truth docs, Git state, or external systems were modified; only this review file was updated.

## Fix Round 2 Re-review

### Final resolution

- FR1-I-1: **resolved**. The B3 adapter catches only the expected `PlatformValidationError` from B2 operational authorization/source/scope validation (`backend/app/services/stage08_memory.py:260-266`). Pending membership revocation and post-enqueue field-visibility drift both return `None`, leave the event pending, and create no Memory (`backend/tests/unit/test_stage08_memory_confirmed_record.py:310-331`).
- FR1-I-2: **resolved**. Create confirmation now continues through materialization and asserts the policy-limited payload (`backend/tests/unit/test_stage08_memory_confirmed_record.py:233-256`); same identity/same payload advances one supersession chain to version two (`:334-359`); repeated enqueue of the same exact six references returns the same event with no duplicate (`:362-370`). The earlier different-subject test still proves identity separation.
- FR1-I-3: **resolved**. The report now states zero/multi-rule fail-closed behavior consistently, and the enqueue docstring describes the exactly-one-rule contract. No stale “materialize the first rule” wording remains in the reviewed task artifacts.
- Initial I-1/I-2/I-3 and all Fix Round 1 findings are now closed.

### Exception-scope and safety verification

- The new catch is not broad: `RuntimeError`, database/programmer exceptions, and other non-`PlatformValidationError` failures are not swallowed. A targeted sentinel diagnostic confirmed `RuntimeError` propagates while the event remains pending and no Memory is created.
- B2 performs all `PlatformValidationError` authorization/source/scope checks before Memory mutation; the adapter only converts those expected drift denials to the documented fail-closed `None` result.
- Processed replay remains fail closed, payload remains exact-six-reference-only, HMAC behavior and safe-reader exclusion are unchanged, and terminal status is still assigned only after successful B2 materialization.

### Evidence and scope

- Inspected all 15 B3 task tests and the current implementation; the added assertions directly cover the previously missing paths rather than relying on indirect success.
- Accepted the reported `15 passed` task-local and `81 passed` focused regression evidence without rerunning identical passing suites. The targeted non-broad-exception diagnostic was the only execution performed in this round.
- PostgreSQL concurrency/lifecycle remains explicitly assigned to B5 and is not overstated as B3 evidence.
- No production scope creep identified: Fix Round 2 changes are limited to the B3 adapter, its task-local tests, and correction of the task report. No route, migration, permission, external call, Telegram/Provider, Redis, vector/RAG, or direct source-record write was added.
- No code, tests, source-of-truth docs, Git state, or external systems were modified during review; only this review report was updated.
