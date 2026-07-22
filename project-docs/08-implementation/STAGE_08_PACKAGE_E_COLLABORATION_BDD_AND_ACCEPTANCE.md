# Stage08 Package E：LangGraph 协作 BDD / 验收合同

## Status

- Current Progress Update (2026-07-22)：Package E 已 `accepted`。E1–E5 final re-review `0 Critical / 0 Important / 0 Minor`；compact E `218 passed`、real loopback pgvector PostgreSQL `3 passed`、compileall/diff check 通过。最终 E5 实证生产 C3/D4/general branch fan-out、worker zero request-session touch、isolated read session、runtime cancel/deadline；E3 safe execution 与 E4 strict query/safe replay 均保持。真实 Provider、Telegram、生产部署仍属于 F/上线阶段。
- Current Progress Update (2026-07-22)：E3 已 `implemented`。安全执行适配层覆盖 sealed intent、事务/savepoint、共同 current-state locks、replay 和最小 trace/audit 投影；合法分析 Provider unavailable 返回无 answer/citation/draft 的 `degraded`，无效/伪造/异常保持 `failed`。最终独立审查 `0 Critical / 0 Important / 0 Minor`，113 selected unit、40 Stage06 default-regression、2 local pgvector PostgreSQL integration、compileall 通过。E4 API 和 Package E 级证据仍 pending。
- Current Progress Update (2026-07-22)：E3 首轮实现独立复审发现 audit UUID、TOCTOU/rollback、idempotency 和空 mutation 缺口，故 E3 未关闭。用户已确认安全执行适配层；E3 的新增验收以 `decisions/STAGE_08_E3_SAFE_EXECUTION_ADAPTER_DECISION.md` 为准。E4、真实 Provider、Telegram 和部署仍未实现。
- Document status：`approved development boundary`
- Scope：E1-E4 的 Coordinator graph、private context/RAG collaboration、provider-unavailable degradation、draft policy routing、assistant query API 和 local PostgreSQL evidence。
- Current Progress Update (2026-07-22)：E2 已完成并通过最终 fresh review（`0 Critical / 0 Important / 0 Minor`）。它证明 C3/D4 读取、pending compression、current-state binding/mapping/source 检查、retrieval/compressor degradation 和 no-persistence safe view；137 unit + 17 local pgvector integration。E3/E4、Policy Gate/ticket/draft、API、AgentRun/audit 与真实 Provider 尚未实现。
- Current Progress Update (2026-07-21)：E1 已完成：private contracts、strict safe view、unavailable ports、sealed state reducer 与十节点 no-checkpoint topology 已由 39 个 focused tests 和最终独立复审（`0 Critical / 0 Important / 0 Minor`）验证。前两轮 review 发现的 reducer conflict 与 sequential marker forge 均以 fail-closed RED/GREEN 修复。E2-E4、C3/D4 real read adapter、API、PostgreSQL evidence、Provider 与外部系统仍未实现。
- Current Progress：Package D 已关闭。Package E 尚未实现；本文件、E 合同和逐任务实施计划是代码前真源。

## 1. BDD

### E-B01：服务端命令而不是客户端 graph state

**Given** 已验证 identity、active member、active employee 和严格 assistant query body

**When** API 创建协作请求

**Then** server 只构造私有 `AssistantQueryCommand` 和固定预算

**And** 客户端传入的 scope、field、view、group、retrieval filter、authority、provider、budget、tool/draft values、terminal state 或 graph state 均被 422/redacted 拒绝

### E-B02：并行读取只消费既有受控能力

**Given** 一个 current employee scope 与一个 `mixed` 请求

**When** Coordinator 进入 `reading`

**Then** C3 composite、D4 retrieval 与 general-advice marker 最多三个子图 fan-out

**And** C3/D4 分别重新验证当前权限、business relation、group retention、Memory/source/chunk lifecycle

**And** 任一 read failure 只产生标签化 omission/degradation，不伪造业务事实，也不提升 action tier

### E-B03：群压缩只能短暂存在

**Given** C3 返回 `group_compression_pending`

**When** 压缩端口可用

**Then** Coordinator 是唯一调用端，digest 和 source-version set 只在本次 state 内存在

**And** 默认/超时/无效 compressor 会丢弃群材料并降级，不写 Memory、RAG、AgentRun、audit、log、Redis 或 checkpoint

### E-B04：分析节点不能绕过读取与权限

**Given** 私有合法材料或没有材料的 general-advice 情况

**When** `AnalysisProvider` 返回结构化 decision

**Then** citation ordinal 必须属于本次 safe evidence，answer 不得声明未读取事实

**And** provider unavailable/shape invalid/timeout 只返回固定 degraded/failed safe view

### E-B05：草稿前必须经过 Policy Gate 和既有 Tool Gateway

**Given** 请求 `draft_update`，employee 当前允许该动作，且 provider 给出受限 draft intent

**When** policy gate 重新验证 member/employee/record/view/field/source 和预算

**Then** 只可通过既有 execution ticket/idempotency/Tool Gateway 创建 `pending_confirmation` draft

**And** 撤权、目标 record drift、cancel、budget exceed、policy deny 或 provider shape failure 均没有 draft、record 修改、外部写入或 orphan ticket

### E-B06：public response 和持久化都不带私有材料

**Given** completed、draft pending、denied、failed、cancelled 或 timed out run

**When** API、AgentRun 或 audit 输出结果

**Then** 只含安全 answer/label/count/code/ref

**And** query、answer persistence、群正文/digest、RAG chunk、Memory payload、UUID、field/score/vector、authority/provider exception/CoT 不可见

### E-B05a：E3 安全执行适配层

**Given** `draft_update` 的分析结果包含一个 sealed、process-local 的 `field_key + JSON-safe value` intent

**When** E3 进入草稿物化

**Then** 适配层在同一 savepoint 内锁定 workspace、member、employee、target record、group binding/mapping 与被消费 source，重验当前 scope/field/value 后才创建 ticket 与调用 Gateway

**And** provider shape error、cancel、timeout、budget exceed、Gateway exception、member/employee/record/mapping/source revoke 任一发生时，savepoint 回滚，ticket、idempotency、draft 及内部 audit 均没有残留

**And** 相同 idempotency key 在当前 scope 重验成功后重放同一 `pending_confirmation` draft；不同 key 不能通过 record-wide pending 数量推断、覆盖或误报失败

**And** E3 复用的 ticket/Gateway/Stage06 draft-service 仅输出白名单安全审计；query、answer、private material、field/value、record/draft/ticket UUID 不出现在该 trace 的 AgentRun、audit、tool summary、outbox、log 或 API-safe DTO

## 2. 最低验收矩阵

| ID | 验收行为 | 最低证据 |
| --- | --- | --- |
| E-01 | node isolation、opaque state、无 checkpoint、client state deny | unit topology/private-state corpus |
| E-02 | bounded fan-out、cancel、timeout、partial read degrade、current reread | graph service tests + disposable PostgreSQL drift |
| E-03 | policy-before-draft、ticket/idempotency/audit、zero direct write | service/API + PostgreSQL transaction/concurrency |
| E-04 | strict API/DTO/errors/AgentRun audit redaction | API security corpus + static scan |
| E-05 | provider unavailable 不网络调用，compressor private retention | fake-provider tests + external dependency scan |

## 3. 必须记录的证据

每轮任务报告须写明 RED/GREEN 命令、graph topology、provider 是否 fake/unavailable、PostgreSQL migration head、数据是否合成、API/DB side effect、取消/cleanup、跳过项和剩余风险。没有真实 provider/Telegram/部署时必须明确写出。
