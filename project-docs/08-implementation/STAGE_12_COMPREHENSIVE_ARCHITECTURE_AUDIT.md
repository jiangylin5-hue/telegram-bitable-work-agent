# Stage12 全量技术架构与开发审计

## Status

- Status: audit complete; corrections implemented locally; bounded Composer campaign release `FAIL`
- Date: 2026-07-30
- Scope: Stage12-A–F uncommitted local delivery package plus the newly started final-campaign reporting slice
- Production status: not deployed, not activated; Stage11/r76 remains production authority
- Audit rule: every conclusion requires direct source, command, database, Provider, browser or artifact evidence; aggregate test counts do not substitute for requirement-level evidence
- Correction approval: user explicitly confirmed all nine Section 8 packages on 2026-07-30; production activation/deployment remains unauthorized

## 0. Superseding acceptance update — 2026-07-31

The nine correction packages, Human Gold `48/48`, ISO-01, bounded deterministic-section Composer correction and its one new independent real `48 × 3` campaign are complete locally. This supersedes the implementation-open findings below without erasing their historical evidence.

- Local gate: focused `113 passed`; expanded Stage12 `446 passed, 1627 deselected`; full backend `2411 passed, 40 skipped`; disposable PostgreSQL/pgvector `7 passed`, current/head `0039`, temporary schemas `0`.
- User-visible answer outcome: all `144/144` Case and final-answer release dimensions passed; the two previously collapsed mixed Cases are complete; unsupported claims and effects remain zero.
- Current release result: `FAIL`. Composer unavailable is `36/48`, `47/48`, `37/48`, Provider-unavailable mean/worst `0.833333/0.979167`; total-latency P95 mean/worst `11636.716667/13775.8 ms`.
- Evidence: `evidence/stage12-final-provider-campaign-v2-2026-07-31/AUDIT.md`, bundle hash `6b15446524a5a084d744dfc82564a73354d1477260c8e2e705375e9c392f1aa8`.
- Production remains Stage11/r76. No Stage12 deployment, production migration, activation, confirmed Action, business write or Telegram send occurred.
- 2026-08-01 superseding Provider update: user-approved TDR-028 per-slot isolation passed bounded real P1 `12/12` and exact P2 `36/36` with zero fallback/effects/writes/sends and p95 `4385 ms` (hash `54de9da4eb0e7ae7eb65d62bbb85807d5382af05a2b795a29628dc10eecc86cc`). This closes the focused P1/P2 blocker described above, but integrated P3, native deployment and Telegram gates remain open; the overall production decision remains `FAIL` until those gates pass.
- 2026-08-01 local release-candidate update: the P3 reporter now enforces exact zero fallback and separate zero transport/schema/grounding/language failure rates, and applies the `8000 ms` SLO to the worst round P95. Fresh local evidence is backend `2519 passed, 40 classified skips`, explicit native PostgreSQL/pgvector `17 + 3 + 17 passed`, Alembic current/head `0039`, Mini App `413 passed`, production build PASS and eight repository-native asset suites PASS. Native Ubuntu Redis/live asset gates remain Task11 and are not counted as local passes. Evidence: `evidence/stage12-native-release-candidate-local-2026-08-01.md`.
- 2026-08-01 isolated-runtime wiring update: the existing public Agent Run POST/SSE path now has an exact-workspace Stage12 admission branch, encrypted typed Specialist dispatch, Grounded Provider fan-in and safe SSE source/status projection. A new deployed campaign harness is `implemented-local`: it calls only `/health`, the existing Agent Run POST and SSE/replay URLs; verifies `result` before `done`; checks the persisted Grounded artifact before and after replay for zero additional Provider calls; compares workspace record-state hashes and Telegram/notification/confirmed-Action deltas; evaluates the user-visible answer against Human Gold in process; and retains only Case IDs, verdicts, timings and hashes. Focused campaign/evaluation evidence is `94 passed`; Planner plus real local PostgreSQL mixed/action evidence is `77 passed`; the campaign SQL observer also passed a read-only local PostgreSQL smoke. This is implementation evidence only: no deployed P2/P3, native Redis, server activation or Telegram proof has run, so release remains `FAIL`.
- 2026-08-01 fresh local release audit: full backend `2595 passed, 40 classified skips`; explicit real local PostgreSQL/pgvector `30 passed`; Mini App `79 files / 415 passed`; production build PASS with `1853 modules transformed`; Alembic current/head both `20260730_0039`; all eight repository-native release asset fixture suites PASS; `git diff --check` and the campaign secret/in-memory-runner scans PASS. The 40 skips are exactly 3 Redis, 17 legacy Stage02 online PostgreSQL, 3 Stage08 PostgreSQL and 17 Stage08 pgvector. The Stage08 PostgreSQL/pgvector gaps were explicitly exercised in the 30-pass run; the three Redis tests and live `psql`/Redis/systemd/`nginx -t` asset branches remain server gates. Existing inaccessible empty pytest temp directories are unchanged and untracked. Release remains `FAIL` until those live gates and deployed P2/P3/Telegram evidence pass.

The historical requirement ledger remains useful for why the correction exists; its old `OPEN`/`FAIL` implementation statements must not be read as current. The remaining release blockers are the real native Redis/server topology, deployed public-path P2, the single gated P3, rollback proof and bounded Telegram evidence; component or in-memory campaign results cannot substitute for them.

## 1. Audit objective

本审计逐一回答：

1. Stage12 是否严格实现了已批准的 Quality Architecture V2，而不是扩大范围或平行造轮子；
2. A–F 的 contracts、实现、测试和验收文档是否一一对应；
3. 大量新增代码是否存在未接线、默认回退、权限绕过、错误持久化、敏感信息暴露或错误状态投影；
4. PostgreSQL/pgvector、Redis、Provider、SSE、Action 和 Mini App 的 skip/timeout 是否合理，是否掩盖关键缺口；
5. 与 Stage11/r75 相比，是否有直接证据证明 Planner、结构化事实计算、检索、Specialist 和 Action 能力正向提升；
6. 是否具备进入人工 Gold 与 48 Case × 3 real-LLM 总验收的条件。

## 2. Frozen inventory

Audit baseline:

```text
branch = codex/stage09-ai-conversation-sse
HEAD = 09b9d5f70895d18efe307ba952c46775cd716dd2
tracked modified files = 33
tracked diff = +3228 / -368
untracked paths = 148
deleted paths = 0
commit/push/deploy = none
production activation = none
```

`git diff --check` 没有 whitespace error；Windows 工作树报告 LF→CRLF conversion warnings，必须在最终 diff/format 审计中复核，不能记为失败也不能忽略。

## 3. Authoritative requirements

| Area | Primary truth | Audit status |
| --- | --- | --- |
| Overall architecture and hard gates | `project-docs/02-architecture/stage12-quality-v2/README.md`, `07_SECURITY_OBSERVABILITY_AND_SLO.md`, `08_DELIVERY_TEST_AND_ACCEPTANCE.md` | FAIL — A–F runtime chain and permission/grounding hard gates are open |
| A Evaluation V2 | `STAGE_12_A_EVALUATION_V2_ACCEPTANCE.md`, A code plan | FAIL — fact-value and recovery applicability semantics are invalid |
| B TaskSpec/Planner | `STAGE_12_B_TASKSPEC_PLANNER_ACCEPTANCE.md`, B code plan | FAIL — evaluator/runtime entity parity and genericity fail |
| C Authorized Query Engine | `STAGE_12_C_AUTHORIZED_QUERY_ENGINE_ACCEPTANCE.md`, C code plan | PASS at component level; PARTIAL in integrated trace/runtime |
| D Retrieval/Embedding | `STAGE_12_D_RETRIEVAL_EMBEDDING_ACCEPTANCE.md`, D code plan, TDR-018/TDR-019 | PASS at adapter/component level; FAIL in application materialization/loading |
| E Typed Specialist/Provider | `STAGE_12_E_TYPED_SPECIALIST_PROVIDER_SOURCE_OF_TRUTH.md`, acceptance and E code plan | FAIL — real worker and semantic grounding gates fail |
| F Durable Action/UI | `STAGE_12_F_DURABLE_ACTION_UI_SOURCE_OF_TRUTH.md`, acceptance and F code plan | PARTIAL — durable/UI path works and two defects are repaired; blind admission, field policy and Redis remain open |
| Final campaign | `2026-07-30-stage12-final-quality-campaign.md` | Task 1 implemented and focused-tested; remaining tasks pending |

## 4. Requirement-by-requirement ledger

Allowed audit results: `PASS`, `FAIL`, `PARTIAL`, `BLOCKED`, `DEFERRED`, `NOT_APPLICABLE`.

### 4.1 Stage12-A — Evaluation V2

| Requirement | Result | Direct evidence | Gap / action |
| --- | --- | --- | --- |
| Strict V2 truth/trace model validation | PASS within current schema | Stage12-A focused suite `58 passed in 2.37s` after redirecting pytest temp to workspace | schema itself is insufficient for independent fact-value verification; see hard-gate failure below |
| 48 unique Gold cases and source hashes | PASS as agent-audited fixture integrity | focused truth/hash/generator tests included in the `58 passed` run | this is not human semantic approval |
| Human Gold sign-off | DEFERRED | all 48 audit entries remain `agent_audited_pending_human_signoff` | must remain open until explicit user review |
| No Gold leakage into execution | PARTIAL | request-key guard and scorer-after-execute tests pass | no A–F integrated execution callback exists, so independent runtime-context construction is not proven |
| Answer fact-value hard gate | FAIL | one-off controlled trace used valid `MT-004`/`RISK-004` evidence IDs but deliberately wrong values; `score_answer(...).gate_pass=True` and grounded precision `1.0` | current trace has no independently verifiable field/value fact set; requires contract/score correction before real campaign |
| Recovery/durability applicability | FAIL | terminal/idempotent normal trace with `recovered=False` yields durability gate failure and recovery accuracy `0.0` | recovery is treated as mandatory for every case instead of fault-case-only/applicable evidence |
| Other per-layer scorer behavior | PARTIAL | existing focused scorer tests pass | cannot call evaluator trustworthy until the two semantic failures above are corrected |
| Three-round aggregate mean/worst/variance | PARTIAL | new report slice RED `4 failed, 3 passed`; GREEN/refactor `8 passed`; Black formatter API says formatted | full A–F report, external round inputs and real campaign still missing |

### 4.2 Stage12-B — TaskSpec V2 / Planner

| Requirement | Result | Direct evidence | Gap / action |
| --- | --- | --- | --- |
| Structured objectives/predicates/joins/actions/conflicts contracts | PASS at component level | B focused suite `123 passed in 5.18s`; current deterministic 48-case runner completes 48/48 | integrated runtime inputs remain materially weaker than evaluator inputs |
| Planner record-scan boundary | PARTIAL / misleading acceptance | Planner function itself does not call a record repository, but `stage12_planner_v2_evaluation._authorized_entities` scans fixture records and supplies 40 entity candidates | the actual API shadow passes `authorized_entities=()`; no authorized Entity Linker populates general runtime candidates |
| Entity-aware runtime parity | FAIL | controlled `join_01`: evaluator with 40 candidates gives Objective/Predicate exact `True/True`; runtime-shadow-equivalent empty candidates gives `False/False` and loses `PRJ-ATLAS` scope | evaluation overstates the Planner behavior available on the real shadow path |
| Multiple independent ActionSlots | PASS at component level | action-template metric remains `24/24`; focused ActionSlot tests pass | final blind A–F integration and public API multi-action admission remain unproven |
| Generic schema-driven entity typing | FAIL | `agent_task_planner_v2.py` production logic branches on `code.startswith("PRJ-")` and `code.startswith("MT-")` | business-fixture prefixes are embedded in a generic platform Planner; should use authorized table identity/relations |
| Authorized Schema Binder and ambiguity boundary | PARTIAL | binding visibility/ambiguity tests pass | Binder can bind only candidates supplied by caller; no runtime candidate discovery for general queries |
| Shadow allowlist/default-off and no authority expansion | PASS within shadow scope | source passes empty entity candidates, feature flag is off/shadow only, focused config/shadow tests pass | this safety pass also exposes the functionality gap; shadow is not representative of B evaluator quality |
| Objective exact gate | DEFERRED / denominator risk | raw exact remains `37/48`; acceptance reports `37/37` by excluding all 11 mismatches as `truth_review_required` | cannot claim final `>=0.90` until human Gold resolves these cases |
| Predicate exact gate | PASS threshold but evidence drifted | current rerun `44/48 = 0.9166667`; mismatches `join_04`, `daily_03`, `mixed_02`, `mixed_04` | acceptance/evidence still says `46/48`; regression source and intended truth need review |
| 48-case exact improvement over Stage11 markers | PARTIAL | deterministic current metrics exceed the `0.90` Predicate threshold and support multi-action templates | no runtime-parity comparison and no integrated real-Provider result; uplift claim is not yet proven |

### 4.3 Stage12-C — Authorized Query Engine

| Requirement | Result | Direct evidence | Gap / action |
| --- | --- | --- | --- |
| Deterministic Filter/Project/Sort/Limit | PASS at component level | current C diagnostic `46/46`; focused C suite `100 passed in 4.25s` | final A/C trace projection is inconsistent, so integrated score is unproven |
| Linked-record traversal and cycle/budget safety | PASS at service-test level | focused relation/compiler/executor tests pass; real PostgreSQL integration includes linked traversal | diagnostic relation metric uses prefix-containment, not literal set equality |
| Aggregate/Group By/Having exactness | PASS at component level | current diagnostic Aggregate `11/11`, Sort `2/2`; aggregate unit coverage included in focused `100 passed` | Provider/Claim value accuracy still blocked by A evaluator defect |
| Permission/view/field/version fail-closed | PASS at component/PostgreSQL level | local PostgreSQL `1 passed in 4.20s`; test covers hidden fields, view scope, deterministic replay, version change and cross-workspace refusal | one broad integration test is direct but not a production-runtime integration |
| No raw SQL/Provider/write/send | PASS within C execution boundary | diagnostic reports Provider/Action/write/send `0`; executor uses authorized UOW/services | fixture setup writes are explicitly excluded |
| C applicability | PASS with disclosed scope | 46 applicable; `permission_01` and `permission_03` are not applicable because they contain no query-result truth | permission denial itself is scored elsewhere |
| Diagnostic result/evidence semantics | PARTIAL | C unions `result.records` and `source_versions`, then accepts any subset of required+allowed evidence | this is not the same contract as A `RuntimeQueryTrace.result_record_ids`, which requires exact required IDs |
| Relation path metric semantics | PARTIAL | `_relation_paths_exact` accepts actual prefix paths in addition to expected maximal paths; `join_01` passes with one-hop plus two-hop actual paths | rename/canonicalize or change Gold/trace contract before claiming literal exactness |
| V2 runtime trace integration | FAIL | no A–F execution callback calls `run_v2_report`; `join_01` artifact records only risks while required work items live in source versions together with allowed project evidence | requires an explicit result/evidence trace contract; must not use Gold to separate them |
| Runtime parity from B into C | FAIL | actual Query shadow consumes the Planner artifact built with `authorized_entities=()` | B controlled parity test already shows the same join query loses entity/predicate exactness before C execution |

### 4.4 Stage12-D — Retrieval / Embedding / Chunk V2

| Requirement | Result | Direct evidence | Gap / action |
| --- | --- | --- | --- |
| Schema/Record/Relation projection contracts | PASS at component level | core D unit set `69 passed in 2.73s`; projection tests explicitly exclude sensitive/link UUID/long-field content | production indexing/consumption is not connected |
| Fixed 1024-dim pgvector profile and migration | PASS locally | PostgreSQL/pgvector integration `1 passed in 3.04s`; explicit `stage06_smoke` Alembic current/head both `20260730_0036` | migrations are not deployed |
| Authorization before candidate scoring | PASS in service tests | hybrid/evidence tests build candidates only after authorized projection and revalidate fields/scope/version | no real SQL candidate loader exists on the route path |
| Revoke-first invalidation / stale version handling | PASS at component/PostgreSQL level | tests cover permission contraction, stale event without Provider call, revoke-before-cleanup and atomic profile rollback | no application worker consumes the retrieval projection outbox |
| Real embedding semantic quality | PARTIAL | current approved-network OpenRouter BGE-M3 rerun: 12 cases, Recall@20 `1.0`, MRR `0.9583`, forbidden `0`, mean/P95 `2824.246 ms`, tokens `2370`, one completed round; retained report has the same quality metrics | synthetic-only; candidate pool is only 27 and all `12/12` cases are therefore effectively Top20-truncated; no real workspace or 48-case integration evidence |
| Local embedding alternative | DEFERRED | accepted TDR-018 exception; local BGE-M3 transfer/measurement did not finish | only remote profile has measured evidence |
| Projection outbox consumer | FAIL | `process_retrieval_projection_event` callers exist only in unit/PostgreSQL tests | emitted production outbox references are not materialized by an app worker |
| Runtime Retrieval candidate loader | FAIL by explicit closure | `_load_retrieval_v2_shadow_candidates` always raises `retrieval_v2_shadow_source_unavailable`; route catches all exceptions | shadow cannot produce a real candidate/evidence observation, even when enabled |
| Structured queries do not depend on Top-K retrieval | PASS by architecture/component separation | C structured engine is independent; D exposes truncation/completeness | E/final composer integration remains unproven |
| Generic linked-record coverage | FAIL / architecture concern | migration/model constraint `source_table_id <> target_table_id` forbids all same-table relation edges | generic multidimensional tables commonly support self/same-table links; changing this requires schema decision and user confirmation |
| Agent-visible retrieval uplift | NOT PROVEN | D acceptance itself states answer path remains Stage11; route loader is closed | real semantic benchmark proves adapter quality only, not current Agent quality |

### 4.5 Stage12-E — Typed Specialist / Provider V2

| Requirement | Result | Direct evidence | Gap / action |
| --- | --- | --- | --- |
| Distinct tabular/risk/daily/action handlers | PASS only as isolated handler factories; FAIL in the real worker | E core unit rerun `53 passed in 2.04s`; `default_specialist_factories()` and `validate_specialist_readiness()` have test-only callers. `agent_specialist_runtime.main()` routes tabular to the Stage08/V1 handler, risk/daily to an `unavailable()` exception and action to the Stage12-F worker | the locked E architecture is not connected to the application worker; the source/acceptance statement that the old same-handler runtime was replaced is false |
| Typed artifacts and durable ownership | PARTIAL | focused persistence/hash/sealed-envelope tests pass | the claimed PostgreSQL test resets `public`, migrates only to `0034`, stores generic `SpecialistSafeResult` metadata and never executes a typed E handler, ClaimGraph or Composer; it is Stage10 control-plane evidence, not E typed fan-in evidence |
| Risk/Daily consume facts rather than repeat raw retrieval | PASS at isolated component level; FAIL at runtime | component tests prohibit query/retrieval ports and pass supplied typed artifacts | the application worker cannot execute either handler, and the API shadow source is deliberately unavailable |
| Action proposal does not expand/write/send | PASS at E component boundary | synthetic diagnostic reports one proposal and writes/sends `0/0`; focused handler tests pass | F owns actual durable action admission/execution and is audited separately |
| Provider schema/taxonomy/retry/repair validation | PASS at gateway/component level | E focused tests pass; current approved-network `google/gemini-2.5-flash` rerun completed risk/daily/composer `3/3`, attempts `3`, failures `0`, mean `2491.33 ms`, p95 `2574 ms`, tokens `207/125` | three synthetic role calls do not prove the application handler chain or 48-case answer quality |
| ClaimGraph grounding and partial failure | FAIL for fact grounding | `build_claim_graph()` validates only non-empty subject/predicate/evidence and version, then trusts arbitrary `value` and evidence IDs; no artifact fact/evidence membership validation occurs | an upstream/provider-produced unsupported value can become a valid ClaimGraph claim |
| Composer cannot introduce unsupported facts | FAIL | controlled provider draft referenced only allowed claim/evidence IDs but answered `该客户已经破产，项目预算为九亿元。`; Composer returned `status=completed`, no degradation and accepted the hallucination | current check is ID-subset plus a narrow completed-action regex; it does not validate answer semantics against claim values |
| Supervisor one-terminal-result behavior | PASS for generic orchestrator metadata; NOT PROVEN for E typed runtime | generic `execute_read_only_specialist()` unit/control-plane tests pass | no application caller runs typed handlers → ClaimGraph → Composer → terminal artifact |
| Default-off shadow preserves V1 authority | PASS for safety; FAIL as integration evidence | API loader `_load_typed_specialists_v2_shadow_metrics` always raises `typed_specialists_v2_shadow_source_unavailable` and the route catches it | E produces no real shadow observation, so unchanged V1 bytes do not prove E compatibility or uplift |
| Integrated final answer quality | FAIL / not measurable yet | no V2 handler-chain caller and no A–F execution callback to `run_v2_report` | must wire and independently validate typed claims before the 48-case campaign |

### 4.6 Stage12-F — Durable Action / API / SSE / UI

| Requirement | Result | Direct evidence | Gap / action |
| --- | --- | --- | --- |
| Objective/Action durable models and migration | PASS locally | migration/model/repository focused tests included in current F core `33 passed in 4.47s`; explicit local PostgreSQL Alembic current/head were both `20260730_0036` during D/F audit | migration is uncommitted, undeployed and not production-accepted |
| Blind ActionSlot parsing and candidate expansion | FAIL for public-runtime blindness; PASS for supplied-slot candidate safety | candidate resolver component tests cover empty/multiple/field/version cases | public request supplies `requested_action`; admission converts it to exactly one `allowed_action_kind` and filters Planner slots to that kind. Optional `target_record_id` is also directly converted into the only entity candidate. A natural-language action with default `read_only` never enters F, so the public path does not independently discover action kind/target as claimed |
| Encrypted private payload and minimized safe projection | PASS after TDD repair for current table/action/actor-field scope | AAD/scope/expiry/tamper and safe-shape tests pass; RED proved revoked scope still returned decrypted values; GREEN now rejects action read after employee table/action or actor field contraction | Digital Employee `field_policy` itself is not consumed by `build_authorized_schema_snapshot`; its read/write semantics require the permission-model correction listed below |
| Independent Action worker and idempotency | PASS at code/in-memory boundary; PARTIAL operationally | `platform.action.propose` has its own worker callback; focused worker/transition/idempotency tests pass | no real Redis listener/test. Unlike E risk/daily, the action callback is connected in `agent_specialist_runtime.main()` |
| Tool Gateway as only materialization boundary | PASS for drafts and blocked notification requests | worker calls `materialize_action_slot()` which calls `AgentControlledToolGateway.materialize()`; pre-confirmation Record/Telegram counts stay zero in tests/evidence | reminder materialization forcibly sets `dry_run=True`; confirmation leaves the notification `blocked` but marks the Action slot `executed`, so `executed` means “request accepted” rather than message delivered and must be documented precisely |
| Confirmation reauthorizes caller, employee, table/view/field/action scope | PARTIAL after TDD repair | RED: revoked employee table/action still returned `200 executed` and created a Record. GREEN: read/confirm now reject with `403 action_scope_changed`; current actor field contraction also rejects. Expanded F/config/API/worker regression `61 passed in 6.09s` | current view recheck is implemented but lacks a dedicated behavior test; Digital Employee `field_policy` is still absent from the authorized schema snapshot |
| Record/proposal version, edit, confirm/reject and idempotency | PASS within unchanged authority | focused F core `33/33`; retained real PostgreSQL/browser regression proves edited value persisted and record delta occurred only after explicit confirm | must be rerun after the reauthorization repair |
| SSE order/resume/terminal safety | PASS at backend/frontend component level | backend projection tests included above; current Mini App focused suite `4 files / 36 tests passed`; parser uses exact keys, run ID, sequence/event ID and terminal checks | real Redis reconnect remains unproven; no current audit browser rerun yet |
| Mini App proposal review/edit/confirm/reject | PASS locally at test/build level | current focused Mini App `36 passed`; current production build PASS; retained browser evidence covers desktop plus `390 × 844`, edited persistence and console `0` | browser evidence used a disposable local environment and must not be treated as production acceptance |
| Real Action Provider call | PARTIAL / disconnected benchmark | current approved-network one-call `google/gemini-2.5-flash` rerun passes strict synthetic schema, tokens `99/130`, writes/sends `0/0` | benchmark injects `action_kind`, authorized fields and evidence, and its output is not consumed by the real Action worker, which is deterministic; it does not prove blind public ActionSlot parsing |
| Telegram/external send safety | PASS as zero-send safety | worker/materializer force pending/blocked state; evidence and tests report Telegram/external sends `0` | no Telegram delivery acceptance was performed, and reminder `executed` status must not be presented as delivered |

### 4.7 Cross-stage architecture, activation and observability

| Requirement | Result | Direct evidence | Gap / action |
| --- | --- | --- | --- |
| A→B→C→D→E→F typed end-to-end chain | FAIL | A report has no application execution callback; D candidate loader and E metrics loader deliberately raise unavailable; E runtime handlers are not wired | component packages coexist but do not form the approved Quality Architecture V2 runtime |
| Independent feature flags and rollback | PASS for F after TDD repair; PARTIAL for B–E | `DURABLE_ACTION_V1_MODE=off|isolated|active` now defaults off, isolated requires UUID allowlist, admission/confirm/worker enforce it; B–E expose default-off/shadow configuration with naming/value drift from the architecture | B–E still have no active runtime path, and D/E loaders remain unavailable |
| Authorization order and scope-hash semantics | PARTIAL | F now revalidates current employee action/table, actor-visible writable fields and target view membership before read/confirm; B/C/D component services use authorized snapshots | `scope_hash` still hashes identifiers rather than an effective authority snapshot, and Stage12 schema binding ignores Digital Employee `field_policy`; Telegram chat scope is not represented on this HTTP path |
| Prompt/provider data minimization | PARTIAL | typed gateway/component tests and retained sanitized evidence show bounded payloads and no credential persistence | real runtime D/E providers are disconnected; therefore application-path minimization is not yet proven end to end |
| Required Stage12 trace dimensions | FAIL / mostly absent | source search finds isolated `task_spec_hash`/`provider_attempt_count` observations but no complete runtime set for planner/query/retrieval/specialist/action or the required segmented latency metrics | final runner and production SLO diagnosis cannot attribute failures/latency to the actual stage |
| Permission and external-send hard gates | PARTIAL / still release-blocking | the reproduced F employee/table/actor-field contraction bug is repaired and external sends remain zero | employee `field_policy` and Telegram chat-scope integration remain unproven, so permission safety cannot yet be declared `1.00` |
| Stage11 rollback authority | PASS operationally today | Stage12 code/migrations are uncommitted and undeployed; production remains Stage11/r76 | deploying the current package would remove the claimed independent F-off guarantee, so current local code is not activation-ready |

## 5. Skip and timeout ledger

| Item | Observed state | Classification | Required follow-up |
| --- | --- | --- | --- |
| Full backend `38 skipped` | post-repair rerun `2219 passed, 38 skipped in 333.17s`; exact skips are 1 Redis, 17 independent Stage02 online PostgreSQL, 3 Stage08 collaboration PostgreSQL and 17 Stage08 RAG/pgvector | verified environment gates | none of the 38 is a Stage12 unit/API/PostgreSQL test; Redis remains a Stage12 activation blocker, while the 37 independent historical/online cases do not block the local component audit |
| Real Redis integration | no listener, no `STAGE10_REDIS_URL`, no `redis-server` executable and Python `redis` package is not installed in the active interpreter despite being declared in `pyproject.toml` | critical operational gap for Redis-worker activation | install/use an approved Redis runtime and project dependency environment, then run the real duplicate/pending/recovery/ack-once test before activation |
| Ruff | not installed | tooling gap | install only with approval if dependency change is required; otherwise use existing format/static checks and record skip |
| Black CLI | repeated 60/120/180 s Windows timeout; formatter API completed | tooling-path issue, not code pass | retain exact evidence; use direct formatter API plus compile/tests; investigate before final static gate |
| Full backend runtime | current full run took `348.22s`; any 60/120/180-second wrapper would terminate a passing suite | command-timeout/tooling issue | final campaign commands need >=10-minute budgets and per-layer/JUnit progress artifacts |
| Mini App full runtime | current `79 files / 412 tests passed` in `297.99s`; focused `36/36` and production build also pass | verified slow but passing | retain >=10-minute budget; UI test environment itself consumed `193.17s` |
| Online PostgreSQL / Stage08 RAG URLs | 37 exact skips due missing independent URLs | environment gap outside the new Stage12 component set | do not point destructive fixtures at the project DB; use explicitly disposable databases if rerun is needed |
| Stage10 PostgreSQL control-plane test | executed because `STAGE06_LOCAL_DATABASE_URL` is configured; it drops the entire target `public` schema and migrates only to `0034` | dangerous fixture, not a skip | it must be isolated or rewritten; later tests restored the disposable DB to `0036`, verified by Alembic current/head |
| 48 Case × 3 real LLM | deliberately deferred, runner incomplete | required final gate | do not run until integrated trace and Gold sign-off exist |

## 6. Positive-improvement proof ledger

No final uplift claim is accepted yet.

| Capability | Stage11 baseline problem | Stage12 required proof | Status |
| --- | --- | --- | --- |
| Evaluation | answer regex/coarse scores | typed truth/trace, no leak, hard gates | **Mixed/regressed:** structural contracts and per-layer scorers are an improvement, but wrong fact values pass and normal no-crash runs fail durability; final truth is not yet more reliable than r75 |
| Planner | marker over/under-splitting; r75 Objective exact `18/48 = 0.375` | objective/predicate/action exact on same 48 cases | **Positive component signal, not runtime uplift:** V2 raw Objective exact is `37/48` and Predicate `44/48`, but evaluator injects 40 fixture entities while runtime supplies none; the runtime path cannot reproduce those gains |
| Query | flat Top-K used for facts; r75 record P/R `0.566/0.6521` are noisy | exact authorized join/aggregate results | **Positive component improvement:** deterministic C diagnostic is `46/46`, aggregate `11/11`, sort `2/2`, with real PostgreSQL permission/version tests; answer-path uplift remains unmeasured |
| Retrieval | keyword/hash approximation | real semantic profile plus authorization/completeness | **Positive adapter improvement:** real BGE-M3 synthetic Recall@20 `1.0`, MRR `0.9583`, forbidden `0`; **no Agent uplift** because indexing worker/candidate loader are disconnected |
| Specialist | same handler under labels | distinct handlers consuming typed upstream facts | **Component design improved, runtime failed:** four typed factories exist, but real risk/daily workers are unavailable and tabular remains Stage08 |
| Provider | raw query + flat chunks | validated typed inputs, grounded claims, stable error taxonomy | **Transport/schema improved, semantic safety failed:** real role calls pass and taxonomy/repair exist, but ClaimGraph trusts values and Composer accepts unsupported prose |
| Action | Gold-injected target/fields; r75 action/field/persistence `0.8229` | blind candidate resolution, pending-only durable proposal | **Durability/UI improved, still not accepted:** real pending/confirm/edit persistence exists, zero sends hold, and the reproduced employee/table/actor-field reauthorization bug plus missing kill switch are repaired; public admission still injects action kind/optional target and employee `field_policy` is not intersected |

## 7. Current preliminary findings

1. **Confirmed gap:** `run_v2_report` has no A–F execution caller; only its unit test calls it. The Stage11 adapter deliberately emits Planner/Query/Retrieval as `not_observed`. Therefore the final 48×3 campaign cannot yet prove Stage12 integration.
2. **Confirmed document drift:** the delivery document still described Stage12-F as next until corrected during the final-campaign preparation.
3. **Confirmed evidence limitation:** A–F acceptance is local/default-off; it is not evidence that production answers improved.
4. **Open concern:** component Query evaluation includes allowed/source-version evidence when reporting diagnostic record codes, while the generic V2 Query scorer requires exact required result IDs. The integrated trace projection must define result versus evidence precisely; no fix is made until source and tests are fully audited.
5. **Open concern:** repeated Black CLI timeouts and all skipped tests require node-level classification; no aggregate pass claim will be based only on historical counts.
6. **Confirmed evaluator defect:** Answer grounding validates only that non-empty `evidence_ids` are a subset of allowed record IDs. It does not validate claim `predicate/value` against a typed fact set. A deliberately wrong value therefore passes the Answer gate.
7. **Confirmed evaluator defect:** Durability scoring requires `recovered=True` for every case. A normal terminal/idempotent run that did not crash fails the gate, because recovery applicability is not represented.
8. **Environment note:** the first A focused run produced `57 passed, 1 error` because the sandbox denied the default Windows pytest temp directory. Re-running the identical suite with `TEMP/TMP` inside the worktree produced `58 passed`; the first error is infrastructure, not a skip or product failure.
9. **Confirmed Planner runtime-parity defect:** the B evaluator supplies 40 fixture-derived `AuthorizedEntitySpec` candidates, but the actual API shadow supplies an empty tuple. On the same `join_01` query, Objective/Predicate exact changes from `True/True` to `False/False` and the Atlas entity scope disappears.
10. **Confirmed genericity defect:** production Planner logic recognizes projects/work items through `PRJ-`/`MT-` record-code prefixes instead of authorized schema/table identity.
11. **Confirmed evidence drift:** current B rerun is Predicate exact `44/48`, while acceptance and retained evidence claim `46/48`. The gate still numerically exceeds `0.90`, but the evidence is stale and two additional mismatches are not disclosed there.
12. **Confirmed A/C trace mismatch:** C acceptance merges result records and source-version evidence and permits allowed evidence, whereas A Query scoring requires exact required result IDs. `join_01` cannot be projected correctly from the current artifact without either losing required work items or including an allowed project record.
13. **Confirmed metric naming mismatch:** C's relation-path helper implements maximal-path/prefix containment rather than exact set equality. The behavior may be defensible for provenance, but the contract and metric name must state it consistently.
14. **Confirmed Retrieval integration gap:** Stage06 can emit retrieval projection references, but no application worker calls `process_retrieval_projection_event`; the route candidate loader is intentionally hard-failed and swallowed. D cannot currently improve an Agent answer.
15. **Confirmed generic relation-schema conflict:** Stage12-D persistence rejects every same-table relation edge. This conflicts with the platform's generic linked-record model and needs an explicit migration/schema decision before correction.
16. **Database-command audit note:** one `alembic current` command accidentally used the default project DB and reported an unrelated legacy revision lookup failure. No migration/write was executed by that command. Re-running with explicit `DATABASE_URL=.../stage06_smoke` proved current/head `0036`.
17. **Confirmed Specialist runtime gap:** the E handler registry is isolated/test-only. The real specialist worker still executes the Stage08 tabular path, rejects risk/daily as not ready and executes only the later F action handler.
18. **Confirmed misleading PostgreSQL evidence:** `test_agent_event_runtime_postgres.py` drops the entire configured `public` schema, migrates only through Stage10 revision `0034`, persists generic `SpecialistSafeResult` metadata and never invokes an E typed handler, ClaimGraph or Composer. It must not be cited as typed E fan-in evidence and must only run on an explicitly disposable database.
19. **Confirmed ClaimGraph trust gap:** arbitrary claim values and evidence IDs are accepted without validation against the typed source artifacts. Hashing and deterministic merge preserve integrity of the submitted payload, not factual grounding.
20. **Confirmed Composer semantic bypass:** a Provider answer containing unrelated bankruptcy and nine-hundred-million-budget claims passed by attaching allowed claim/evidence IDs. The current ID-subset and completion-verb regex cannot enforce the documented “no unsupported facts” gate.
21. **Action reauthorization vulnerability — repaired locally by TDD:** RED proved that removing every Digital Employee `allowed_action` and `accessible_table` still exposed proposed values and allowed a Record write. The route now revalidates current employee action/table, actor-visible writable fields and record view membership before Action read/confirm/reject. Revoked employee/table and actor-field regression tests now return `403 action_scope_changed` with zero Records.
22. **Confirmed test-coverage mislabel:** the F API test named “scope drift” mutates `run.scope_hash` directly. It does not contract the actual user/employee/table/view/field permission sources and therefore did not cover the acceptance requirement it was cited for.
23. **Confirmed public Action hint injection:** Stage12-F admission selects its sole allowed Action kind from the client's `requested_action` and optionally creates its only entity candidate from `target_record_id`. A query submitted with the default `read_only` does not reach F at all. The retained real Provider benchmark also injects action kind, field allowlist and evidence and is disconnected from the worker. The current evidence does not prove blind natural-language ActionSlot parsing.
24. **Confirmed reminder-status semantic caveat:** Tool Gateway forces `dry_run=True`, producing a blocked notification. Stage12 confirmation records an audit entry but leaves that notification blocked, then marks the Action slot `executed`. This is safe with respect to external sends, but it must mean “request workflow executed”, never “reminder delivered”.
25. **Current F rerun evidence:** core unit/API/SSE set passed `33/33`; Mini App focused Action/SSE/API/workbench set passed `36/36`; Mini App production build passed. The first backend attempt had `32 passed, 1 error` only because the audit temp path was resolved relative to `backend`; the identical command with an absolute workspace temp path passed.
26. **Activation-control defect — repaired locally by TDD:** `DURABLE_ACTION_V1_MODE=off|isolated|active` and its isolated UUID allowlist now exist; default-off admission falls back to the unchanged V1 path, confirmation returns `409 durable_action_runtime_disabled`, reads remain available for rollback visibility, and the Action worker refuses disabled workspaces.
27. **Confirmed observability gap:** the required Stage12 trace dimensions and segmented latency set are not emitted by an integrated runtime. A few isolated shadow/benchmark fields exist, but they cannot support the documented SLO or explain an end-to-end Case failure.
28. **Cross-stage conclusion:** A–F are currently a collection of substantial component implementations, not a connected Quality Architecture V2. The strongest positive evidence is C's deterministic authorized query engine and F's controlled draft flow. Neither improves the current user answer path; F's reproduced table/action/actor-field bug is repaired, but the broader employee field-policy gate remains open.
29. **Current full regression evidence:** after the F repairs, backend completed `2219 passed, 38 skipped in 333.17s`; Mini App completed `79 files / 412 tests in 297.99s`; production build passed. These results prove broad regression compatibility of the current component package but do not override the semantic, runtime-wiring or permission hard-gate failures above.
30. **Exact skip classification:** the 38 backend skips are fully accounted for as 1 Redis, 17 Stage02 online PostgreSQL, 3 Stage08 collaboration PostgreSQL and 17 Stage08 RAG/pgvector. Earlier short command timeouts were insufficient for a suite that currently needs nearly six minutes.
31. **Current real Provider reproducibility:** after explicit network approval, E risk/daily/composer passed `3/3` in three attempts, F Action passed `1/1`, and OpenRouter BGE-M3 completed one 12-case retrieval round at Recall@20 `1.0` / MRR `0.9583` / forbidden `0`. The initial sandboxed E attempt produced six `provider_http_error` attempts; this was network isolation evidence, not a model-quality failure.
32. **Provider evidence boundary:** all current real calls use synthetic authorized payloads. The E/F outputs remain disconnected from the application runtime and the D corpus is small enough that Top20 includes most candidates. These results validate transport/profile/schema behavior only.
33. **Confirmed employee field-policy gap:** `build_authorized_schema_snapshot()` intersects employee tables and caller field permissions but never reads `DigitalEmployee.field_policy`. A controlled employee policy with only `writable_fields=['project_code']` still marked `customer_secret`, `project_code` and `status` all writable for the owner. Correcting default/allow/deny semantics changes the permission model and therefore requires explicit confirmation.
34. **Current post-repair F evidence:** targeted RED/GREEN permission and kill-switch tests pass; the expanded F/config/API/worker regression is `61/61`; targeted compile and Black API check pass; the post-repair full backend suite is `2219/2219` with the same 38 classified skips. Alembic current/head remain `0036`.

## 8. Required architecture correction package

The audit recommends one bounded correction package. Items 1–5 change a contract, schema or permission semantic and require explicit user confirmation before implementation. Items 6–9 complete already-approved internal wiring and acceptance infrastructure after those semantics are frozen.

1. **Evaluation/trace contract V2.1**
   - split `result_record_ids` from `evidence_record_ids`;
   - add independently produced typed facts `(subject, predicate/field_ref, canonical value, evidence IDs, source versions)`;
   - Answer claims must reference and equal those facts;
   - add explicit recovery applicability/fault-injection expectation instead of requiring recovery on every Case.
2. **Generic authorized Entity Linker**
   - build runtime candidates from authorized schema identity fields, exact codes and aliases;
   - evaluator and runtime must use the same linker contract;
   - remove `PRJ-`/`MT-` production prefix branches and all fixture-derived candidate injection.
3. **Relation schema correction**
   - remove the Stage12-D constraint that rejects every same-table relation edge;
   - rely on relation definition, permission proof and traversal cycle/budget controls rather than table/record inequality as a generic validity rule.
4. **Digital Employee field-policy V2**
   - use a versioned explicit allowlist policy for Stage12 (`readable_field_ids`, `writable_field_ids`, masking rules);
   - Stage12 must fail closed when this explicit policy is absent; existing V1 agents remain unchanged until migrated;
   - bind the effective policy/version into scope proof and revalidate it before reads, Provider input, proposals and confirmation.
5. **Blind Action admission compatibility**
   - add a backward-compatible `requested_action=auto` controlled-action mode that permits multiple Action kinds from raw Query;
   - retain explicit action/target only as declared user context, never as evaluation Gold;
   - final blind Cases omit action/target hints and score independently resolved kind/target/field/value.
6. **Retrieval materialization and runtime loader**
   - add the outbox consumer for record/schema/relation projections;
   - implement the authorized candidate loader and version/revoke revalidation;
   - keep C structured facts independent from Top-K retrieval.
7. **Typed Specialist and safe Composer runtime**
   - wire Tabular/Risk/Daily factories into the real worker and fan-in chain;
   - build ClaimGraph only from validated typed artifact facts;
   - render structured fact text deterministically; Provider may select/order prevalidated claim text and bounded connectors, but may not invent free-form factual sentences.
8. **Integrated isolated runner and observability**
   - execute raw Query through A–F without Gold/context injection;
   - emit the documented per-stage hashes, counts, error classes and latency segments;
   - isolate the destructive Stage10 PostgreSQL fixture and add progress/JUnit artifacts for long suites.
9. **Final infrastructure and quality gates**
   - install/use a real Redis runtime plus the project dependency environment and run recovery/ack-once evidence;
   - complete 48/48 human Gold sign-off;
   - execute 48 Case × 3 real Provider rounds and report mean, worst round, variance, safety failures and P95.

## 9. Audit decision

- Local component readiness: **mixed**; C is strongest, D transport/profile is positive, F durable/UI is partial.
- Integrated Stage12 acceptance: **FAIL / reopened**.
- Production readiness: **FAIL**; no deployment is authorized and the current package has open hard gates.
- Measured Agent-quality uplift: **not proven**. Planner, Query and embedding components show positive signals, but the current user-answer runtime remains Stage11 and does not consume them.
- Real Case campaign: **must continue after the correction package and human Gold**; current real synthetic Provider/embedding calls are retained as prerequisite evidence only.

## 10. Completion conditions for this audit

- [x] Every row above has a non-pending result and direct evidence.
- [x] Every skipped/timeout item has a reason, risk classification and disposition.
- [x] Critical security and permission paths have source plus behavioral evidence.
- [x] Confirmed ordinary F bugs have RED/GREEN regressions; architecture/permission-contract gaps are explicitly left open with reason.
- [x] No unconfirmed architecture/schema/API/permission/model correction was implemented; the required confirmation package is frozen in Section 8.
- [x] The final conclusion distinguishes local component readiness, integrated acceptance, production readiness and measured Agent-quality uplift.
