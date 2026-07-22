# Stage08 Package B Task B4 独立审查

## Review Status

- Status: `APPROVED` (latest verdict after Fix Round 2; earlier findings are retained below as review history)
- Scope: Task B4 当前 source、tests 与 B1/B2/B3 集成面。
- Method: 逐行检查 brief/report/review package 列出的全部生产代码与 B4 tests，并核对 B1/B2 model/UoW/migration、B3 materializer 与现有 authorization。未重跑实现者已报告通过的相同 suite；仅用无持久化的纯内存 Python 脚本验证下述具体疑点。

## Critical Findings

### C1. Telegram group 原文载体可绕过 candidate contract 直接落入 Memory 并由安全列表返回

**Code refs:**

- `backend/app/runtime/stage08_memory_contracts.py:117-145`
- `backend/app/runtime/stage08_memory_contracts.py:168-180`
- `backend/app/services/stage08_memory.py:44-100`
- `backend/app/services/stage08_memory.py:660-691`
- `backend/app/services/stage08_memory.py:587-609`

`raw_caption`/`content` 等 group-only 禁止 key 只在 `GroupMemoryCandidateProjection` 中检查。`MemoryMaterializationProjection` 只调用较弱的 `_reject_forbidden_keys()`，而 B4 又在 `_validate_current_platform_sources()` 中对精确 Telegram group source 开放了通用 `materialize_memory_from_projection()` 路径。该路径不要求 candidate，也不再执行 group payload 检查，因此可直接保存原文载体；`list_memory_projections()` 随后把 payload 原样交给 HTTP response model。

**Independent verification:** 使用真实 B4 adapter 生成的精确 `telegram_message + group_candidate_projection + stage06-binding:<uuid>` source，构造 `MemoryMaterializationProjection(payload={"raw_caption": "RAW_CAPTION_SENTINEL"})`。结果为：

```text
stored_payload= {'raw_caption': 'RAW_CAPTION_SENTINEL'}
safe_list_projection= [{'memory_type': 'decision', 'status': 'active', 'version': 1, 'payload': {'raw_caption': 'RAW_CAPTION_SENTINEL'}, 'valid_until': None}]
```

这直接违反“原始消息不得进入 candidate/Memory/API”的绝对边界。修复需要在所有 group-source materialization/read 入口上执行同一严格 group payload 合同，或使 group source 只能通过已验证 candidate 的不可绕过入口进入 materializer。

### C2. Candidate payload 允许明确禁止的 chat/binding/source 载体，会持久化并由 API 返回

**Code refs:**

- `backend/app/runtime/stage08_memory_contracts.py:23-46`
- `backend/app/runtime/stage08_memory_contracts.py:168-180`
- `backend/app/services/stage08_memory.py:185-203`
- `backend/app/services/stage08_memory.py:602-609`
- `backend/app/schemas/stage08_memory.py:7-20`

group forbidden-key set 拒绝了部分文本 key，却允许 `chat_id`、`binding_id`、`group_chat_ref`、`source_refs`、`field_keys` 等明确禁止的 source/identity 载体。Candidate create 会原样保存 `normalized_payload`，promotion 会原样复制到 Memory，list/API 又允许 payload 中的任意 JSON key。这不是“无法数学证明任意字符串不是原文”的残余风险，而是已知、可结构化拦截的明确载体。

**Independent verification:** 当 payload 分别为以下结构时，`GroupMemoryCandidateProjection` 全部成功构造：

```text
chat_id accepted= {'chat_id': '-100123456'}
binding_id accepted= {'binding_id': '<binding-uuid>'}
group_chat_ref accepted= {'group_chat_ref': 'stage06-binding:<binding-uuid>'}
source_refs accepted= {'source_refs': [{'source_kind': 'telegram_message', ...}]}
```

因此当前合同无法保证 brief 规定的“不保存原始 chat ID/binding ID，API 不返回 source refs/group_chat_ref/field keys”。

## Important Findings

### I1. Accepted-candidate revoke 信任存储的 fingerprint，未重算 canonical correlation，可撤销无关 Memory

**Code refs:**

- `backend/app/services/stage08_memory.py:238-249`
- `backend/app/services/stage08_memory.py:525-580`
- `backend/app/services/stage08_memory.py:1092-1104`

promotion 会重算 candidate 的 canonical fingerprint 并比较，但 revoke 只重建 group projection/验证 binding，然后直接用 `candidate.source_fingerprint` 查找 item。它没有重算 candidate fingerprint，也没有核验命中 item 的 scope/payload/source refs 是否与 candidate canonical 内容一致。

**Independent verification:** 将已 accepted candidate 的 `source_fingerprint` 改为另一 active item 的 fingerprint 后调用 revoke，结果：

```text
corrupt_fingerprint_revoke_result= CandidateRevocationResult(candidate_status='accepted', candidate_version=2, memory_status='revoked')
original_status= active
unrelated_status= revoked
```

这违反“只撤销精确 canonical fingerprint 关联 Memory；source/fingerprint 损坏 fail closed”。

### I2. Revoke 路径没有执行 candidate TTL，过期 candidate 仍会成功变更生命周期

**Code refs:**

- `backend/app/services/stage08_memory.py:235-237`
- `backend/app/services/stage08_memory.py:513-549`
- `backend/app/services/stage08_memory.py:550-580`

`resolve_group_candidate()` 在 promotion 前检查 `valid_until <= now`，但 `revoke_memory_candidate()` 在 version/source 检查后直接 reject candidate 或 revoke accepted item，完全未检查 TTL。

**Independent verification:** 创建 `valid_until=NOW+1s` 的 candidate，在 `NOW+2s` 以正确 version 撤销，得到：

```text
expired_candidate_revoke_result= CandidateRevocationResult(candidate_status='rejected', candidate_version=2, memory_status=None)
stored_status= rejected
```

预期应先持久化 `expired` + 脱敏 audit，然后固定 409。Accepted candidate 同样可在 TTL 后把尚未被读取路径转为 `expired` 的 item 直接改为 `revoked`。

### I3. Workspace 失效在 group binding validator 前被 scope validator 截获，Memory 被错误标记为 `deleted`

**Code refs:**

- `backend/app/services/stage08_group_memory_source.py:106-115`
- `backend/app/services/stage08_memory.py:445-480`
- `backend/app/services/stage08_memory.py:614-620`

group source validator 已将 inactive/missing workspace 分类为 `revoked`，但 read 先执行 `_validate_scope()`。Workspace 不 active 时先抛出普通 `memory_scope_invalid`，catch 分支因而将 item 记为 `deleted`，永远不会到达 group validator 的 revoked 分类。

**Independent verification:** 对已 promotion 的 group Memory 将 workspace 改为 `archived` 后读取：

```text
read= None item_status= deleted
```

fail-closed 本身生效，但生命周期终态和 audit 语义错误；这会把当前授权/范围失效记为 source deletion。

### I4. `autoflush=False` 下 promotion 新建的 Memory 未 flush，同一事务内的 list/revoke 看不到它

**Code refs:**

- `backend/app/core/database.py:20-26`
- `backend/app/services/stage06_platform.py:1313-1339`
- `backend/app/services/stage08_memory.py:90-100`
- `backend/app/services/stage08_memory.py:258-275`
- `backend/app/services/stage08_memory.py:550-565`
- `backend/tests/integration/test_stage08_memory_postgres.py:845-857`

production session 明确 `autoflush=False`。Candidate create 已为同事务 replay/resolve 显式 flush，但 promotion 中 `add_memory_item()` 后没有 flush。`list_memory_items()` 是 SQL query，所以在 commit/flush 前不包含 pending item；紧接着的 accepted-candidate revoke 会返回 `memory_candidate_related_item_missing`，同事务 list 也会漏掉新 item。当前 PostgreSQL revoke test 在 promotion 后先 `session.commit()`，因而未覆盖该服务组合。

这是与报告中已修 candidate visibility 同类的事务内可见性缺口。建议在 promotion 建 item 后、依赖 query-based correlation 前建立明确 flush 边界，并增加不经 commit 的 PostgreSQL 回归。

## Minor Findings

- None.

## Verified-Compliant Areas

- 部署阈值为唯一 `Decimal("0.85")`，DTO 与 service 双重 gate；`0.8499` 在写 candidate/Memory/outbox/audit 前被拒绝。
- `TrustedGroupMessageInput` 为 strict + `extra="forbid"`；adapter 只接受 group/supergroup，并重验 active workspace、`chat_user` binding、active same-workspace member 与 chat ID 精确匹配；输出不含 chat/user ID。
- Candidate 创建路径会比较 projection/source 的精确 scope/source 形状；promotion 会重算 canonical fingerprint，conflict 不覆盖 active item。
- GET/POST route 从 verified identity 派生 actor，仅复用 `workspace.read`/`member.manage`；request/path/query 校验错误使用固定脱敏 422，foreign workspace/非管理者/version conflict 的状态码映射符合 brief。
- API 顶层 response 未返回 item/candidate ID、scope 或 source refs；发现的 payload 载体问题已在 C1/C2 单独说明。
- Binding/member 失效、source shape 损坏与 item TTL 的基本读取 fail-closed 分支存在；candidate/item/workspace 关键路径使用 `FOR UPDATE`，未发现新 external call、migration、role/action、webhook/ingestion 或 frontend 扩张。

## Verification Evidence

- 执行 4 个无持久化、无外部调用的纯内存针对性脚本，分别复现 C1、C2、I1、I2 和 I3；全部 exit code 0，输出如各 finding 所列。
- 检查 production sessionmaker：`autoflush=False`；检查 SQLAlchemy UoW：`list_memory_items()` 是 DB query；检查 B4 PostgreSQL test：promotion 与 revoke 之间有 `session.commit()`，支持 I4 的静态结论。
- 未运行已报告的 `72 passed`/`110 passed` 相同 suite，避免无理由重复；未连接或改动本地 PostgreSQL，未修改 git 或外部状态。

## Verdicts

### Spec Compliance Verdict

`FAIL`。Threshold、adapter、基本 authorization/redaction/locking 部分符合 brief，但 C1/C2 直接突破 raw content、chat/binding/source 不持久化与 API 不暴露的绝对边界；I1/I2 未满足精确 fingerprint revoke 和 TTL 生命周期语义。Task B4 不应在修复并增加针对性回归前验收。

### Code Quality Verdict

`CHANGES_REQUIRED`。代码分层、固定错误码、审计脱敏和 UoW lock 习惯整体清晰，但 group-specific invariants 分散在 candidate DTO 而未收敛到所有 materialization/read 边界，revoke 与 resolve 的 fingerprint/TTL 验证不对称，且 SQLAlchemy flush 边界不完整。这些是可局部修复的 B4 范围内问题，不需要 schema/API/permission 扩展。

---

## Fix Round 1 Re-review

### Re-review Status

- Status: `CHANGES_REQUIRED`
- Scope: 仅复审 Fix Round 1 对 C1/C2/I1/I2/I3/I4 的修正、对应 tests、HTTP error-code/commit 语义与 B1/B2/B3 集成面。
- Method: 读取最新 report、brief、当前 contracts/service/route 及新增 unit/API/PostgreSQL tests；未重跑实现者已报告通过的相同 suite。执行 4 个无持久化的纯内存针对性脚本，验证原 finding 闭环并探测同义 carrier 和 stale-version + TTL 交叉语义。

### Closure Matrix

| Finding | Status | Re-review evidence |
| --- | --- | --- |
| C1 generic group bypass | `CLOSED` | `materialize_memory_from_projection()` 现在对任何 group scope 或 `telegram_message` source 固定抛 `memory_group_source_not_supported`；原 `raw_caption` reproduction 得到该 code，`memory_items == []`。Private group materializer 当前只被 `resolve_group_candidate()` 调用。 |
| C2 known carriers | `PARTIAL` | 原报告的 `chat_id`/`binding_id`/`group_chat_ref`/`source_refs`/`field_keys` 均会递归拒绝；但明文禁止的 Telegram-prefixed transport carriers 仍可持久化和返回，见 R1-C1。 |
| I1 exact fingerprint revoke | `CLOSED` | revoke 重建 strict candidate、重算 canonical fingerprint，并对锁定 item 做全 projection canonical 匹配。原 redirect reproduction 返回 `memory_candidate_source_invalid`，原 item 和 unrelated item 均仍 `active`。 |
| I2 revoke TTL | `PARTIAL` | 正确 version 时 candidate/accepted candidate 会转 `expired`、不撤销 item，API 返回固定 `memory_candidate_expired` 409；但 TTL 位于 version check 前，stale request 仍会持久化变更，见 R1-I1。 |
| I3 workspace loss lifecycle | `CLOSED` | group read 先执行 strict group contract/current binding validator，再执行 generic scope validator。原 archived-workspace reproduction 返回 `None` 且 item 为 `revoked`，不再为 `deleted`。 |
| I4 uncommitted promotion visibility | `CLOSED` | active/superseding/conflicted 新 item 全部通过 `_add_memory_item_and_flush()` 显式 flush。新 PostgreSQL test 在 promotion 与 list/revoke 之间无 commit，同事务 list 和 exact revoke 均成功。本次未重置/连接共享本地 PostgreSQL，对该项依据 source + 现有真 PostgreSQL test 证据复核。 |

### Remaining Critical Findings

#### R1-C1. C2 只拦截了首轮举例的五个 key，仍允许 brief 明文禁止的原始 Telegram transport ID

**Code refs:**

- `backend/app/runtime/stage08_memory_contracts.py:23-50`
- `backend/app/runtime/stage08_memory_contracts.py:251-266`
- `backend/app/services/stage08_memory.py:151-224`
- `backend/app/services/stage08_memory.py:680-704`
- `backend/tests/unit/test_stage08_memory_contracts.py:370-382`

Fix Round 1 将原 C2 明示的 `chat_id`、`binding_id`、`group_chat_ref`、`source_refs`、`field_keys` 加入 forbidden set，但没有拒绝更明确的 `telegram_chat_id`、`telegram_message_id`、`telegram_update_id`。Brief 绝对边界明文禁止保存 raw chat ID 和原始 Telegram message/update ID；这三个是已知、可结构化拦截的 transport carrier，不属于“任意允许字符串无法自证不是原文”的残余风险。

`GroupMemoryCandidateProjection` 与 `create_group_memory_candidate()` 的二次重建都使用同一不完整 forbidden set，因此 service-boundary revalidation 也不会拦截。Promotion 原样复制 payload，list/API 原样返回它。

**Independent verification:** 构造 strict candidate，经实际 create 和 resolve 后列表：

```text
persisted_candidate_payload= {'decision': {'telegram_chat_id': '-100123456', 'telegram_message_id': '12345', 'telegram_update_id': '67890'}}
persisted_item_payload= {'decision': {'telegram_chat_id': '-100123456', 'telegram_message_id': '12345', 'telegram_update_id': '67890'}}
safe_list= [{'memory_type': 'decision', 'status': 'active', 'version': 1, 'payload': {'decision': {'telegram_chat_id': '-100123456', 'telegram_message_id': '12345', 'telegram_update_id': '67890'}}, 'valid_until': None}]
```

额外针对性 contract 检查还确认 `message_id`、`update_id`、`source_id` 与字符串型 `source_ref` 同样被接受。其中前三个 Telegram-prefixed key 已足以构成直接违反并阻断验收。

### Remaining Important Findings

#### R1-I1. TTL 检查位于 `expected_version` 之前，stale revoke 会修改 candidate 并返回错误 code

**Code refs:**

- `backend/app/services/stage08_memory.py:551-578`
- `backend/app/api/routes/stage08_memory.py:116-127`
- `backend/tests/unit/test_stage08_memory_service.py:791-847`
- `backend/tests/unit/test_stage08_memory_api.py:229-245`

Brief 要求“先锁 candidate，再执行 manager 授权，然后检查 `expected_version`”，并规定 version mismatch 固定 409、不改任何数据。当前实现在 manager check 后先执行 TTL：过期 candidate 会先转 `expired`、version +1、写 audit，然后抛 `memory_candidate_expired`；route 会对该 code 执行 commit。因此持有过期/stale version 的请求仍能改变服务端状态，optimistic concurrency 与固定错误码语义均被破坏。

**Independent service verification:** 对 `version=1`、已过 TTL 的 candidate 提交 `expected_version=999`：

```text
stale_expired_error= memory_candidate_expired candidate_status= expired candidate_version= 2
```

**Independent API verification:** 对 `version=2`、已过 TTL 的 accepted candidate 提交 `expected_version=999`：

```text
status_code= 409
body= {'detail': {'code': 'memory_candidate_expired', 'message': 'memory_candidate_expired'}}
candidate_status= expired candidate_version= 3
```

预期应为 `memory_candidate_version_conflict` 409，candidate/item/audit 均不改；只有正确 expected version 才可触发 TTL 迁移和受控 commit-on-409。现有新测试只覆盖正确 version，未覆盖 TTL + stale version 交叉。

### Fix Round 1 Verified-Compliant Areas

- C1 通用 group bypass 已关闭；任意 `telegram_message` source 即使没有 group scope 也被 public materializer 拒绝，不会将任意 Telegram source 变成通用 materialization 能力。
- Group read 重建 strict candidate-equivalent contract，已覆盖的 raw/source carrier 损坏会 fail closed 为 `deleted`，不进入 list/API。
- Accepted revoke 对 candidate fingerprint 和命中 item canonical projection 都重算/精确比较；原 fingerprint redirect 已无法撤销无关 item。
- 正确 version 下的 candidate/accepted-candidate TTL 会使 candidate 转 `expired`，并使用 `memory_candidate_ttl_expired` 脱敏 audit reason；API 对 `memory_candidate_expired` 固定返回并持久化 409。
- Group binding/member/workspace 授权失效在 generic scope 前判定，读取立即拒绝并转 `revoked`；source/contract 损坏仍转 `deleted`，item TTL 仍转 `expired`。
- `_add_memory_item_and_flush()` 覆盖 active、superseding 与 conflicted 三个新 item 分支；同事务 PostgreSQL test 没有用 commit 隐藏 visibility 问题。
- Route 仍仅接收 candidate path UUID 和 positive `expected_version`，从 verified identity 派生 actor，仅使用 `workspace.read`/`member.manage`；request validation 仍为脱敏 422。
- 未发现 migration、Message/Telegram persistence、webhook/parser/ingestion、role/action、frontend、Provider/LLM、Redis、vector/RAG 或 external-call 扩展。Fix Round 1 改动保持在 B4 contracts/service/routes/tests/report 边界内。

### Fix Round 1 Verification Evidence

- 独立纯内存回放原 finding：`C1 memory_group_source_not_supported 0`；原 C2 五个 key 全部拒绝；I1 返回 `memory_candidate_source_invalid` 且两个 item 均 active；I2 正确 version 时转 expired；I3 读取返回 `None` 且 item revoked。
- 独立 carrier 扩展检查及实际 candidate→Memory→list 回放复现 R1-C1。
- 独立 service 与 TestClient 回放均复现 R1-I1；TestClient 只使用 in-memory UoW，未连接外部系统。
- 未重跑最新 report 已列的 `87 passed`/`122 passed` suite；未连接或重置本地 PostgreSQL，未改动 git 或外部状态。

### Fix Round 1 Spec Compliance Verdict

`FAIL`。C1、I1、I3、I4 已关闭，I2 的正常 expired 路径已实现，但 C2 未完整拒绝 brief 明文禁止的 raw Telegram chat/message/update ID carrier；TTL 与 expected-version 的先后顺序也违反 stale version 不得修改数据的撤销合同。

### Fix Round 1 Code Quality Verdict

`CHANGES_REQUIRED`。首轮的架构性问题已大幅收敛：public/private group materialization 边界、strict stored revalidation、canonical revoke correlation、lifecycle ordering 与 flush helper 都更清晰。剩余修复仍是最小 B4 范围：补齐明确 Telegram/source transport carrier key，并将 expected-version check 移到任何 TTL/source 状态变更之前，加入交叉回归。

---

## Fix Round 2 Re-review

### Re-review Status

- Status: `APPROVED`
- Scope: 复审 Fix Round 2 对剩余 Critical C2 和 Important I2 的修正，并回放 C1/I1/I3/I4 的关键不变量。
- Method: 读取最新 report、当前 contract/service/route 与新增 unit/API tests；未重跑实现者已报告通过的 `101 passed`/`134 passed` 相同 suite。执行无持久化的独立组合脚本，覆盖列表嵌套 carrier、合法相近业务 key、损坏 candidate/item、candidate/accepted 的 stale/current version + TTL 交叉及 API 无变更语义。

### Findings

#### Critical

- None.

#### Important

- None.

#### Minor

- None.

### Final Closure Matrix

| Finding | Final status | Evidence |
| --- | --- | --- |
| C1 generic group bypass | `CLOSED` | Public `materialize_memory_from_projection()` 仍对 group scope/任意 `telegram_message` source 抛 `memory_group_source_not_supported`；独立回放得到同一 code。Private group materializer 仍只由 strict candidate promotion 路径调用。 |
| C2 recursive source/transport carriers | `CLOSED` | Forbidden set 已覆盖原 5 个 key、`telegram_chat_id`/`telegram_message_id`/`telegram_update_id` 及 `message_id`/`update_id`/`source_id`/`source_ref` 别名；递归 validator 在 dict/list 任意层级使用该集合。Strict DTO、service 二次重建和 stored-item read 使用同一合同。 |
| I1 exact fingerprint revoke | `CLOSED` | Candidate canonical fingerprint 和锁定 item full canonical projection 匹配仍存在；原 redirect 回放仍为 `memory_candidate_source_invalid`，两个 item 均 active。 |
| I2 expected-version/TTL semantics | `CLOSED` | Revoke 顺序现为 lock → manager authorization → expected-version → TTL/source/lifecycle。Candidate 和 accepted candidate 的 stale request 均返回 `memory_candidate_version_conflict`，不改 candidate/review metadata/item/audit；随后 current version 仍返回 `memory_candidate_expired` 并正确持久化 expiry。 |
| I3 workspace loss lifecycle | `CLOSED` | Group current-source authorization 仍先于 generic scope；archived-workspace 独立回放仍使 item 转 `revoked`。 |
| I4 uncommitted SQLAlchemy visibility | `CLOSED` | active/superseding/conflicted 新 item 仍统一走 `_add_memory_item_and_flush()`；无 commit PostgreSQL regression 仍在当前 test source 中。Fix Round 2 未改动这些路径。 |

### C2 Independent Verification

#### Recursive rejection

对以下 12 个 key，将每个 key 放在 `{"decision": [{"nested_fact": {key: "S"}}]}` 的 dict/list 嵌套中构造 strict candidate，全部被拒绝：

```text
recursive_carriers_rejected= ['chat_id', 'telegram_chat_id', 'message_id', 'telegram_message_id', 'update_id', 'telegram_update_id', 'binding_id', 'group_chat_ref', 'source_id', 'source_ref', 'source_refs', 'field_keys']
```

#### Valid payload compatibility

使用相近但非保留的业务 key，如 `customer_message_id`、`origin_source_id`、`summary`、`participants[].display_name`，strict DTO 构造、candidate create、promotion 与 list round-trip 均成功：

```text
safe_round_trip= True
```

这说明检查是 exact-key + casefold 的保留载体检查，没有以 substring 方式误拒绝合法业务 key。

#### Service and stored-data defense in depth

- 将已持久 candidate 的 payload 损坏为 nested `telegram_update_id` 后，promotion 抛 `memory_group_source_invalid`，不创建 Memory，且 sentinel 不进 audit。
- 将已持久 item 损坏为 nested `telegram_chat_id` 后，list 返回 `[]`，item 转 `deleted`，不返回 sentinel。
- `create_group_memory_candidate()` 仍在任何持久化之前用 strict constructor 重建 projection，因此 `model_copy`/unsafe internal DTO 无法绕过新 carrier 集合。

### I2 Independent Verification

#### Service semantics

对 `candidate` 与 `accepted` 两种状态分别执行 stale request，再执行 current request：

```text
accepted= False stale_code= memory_candidate_version_conflict stale_unchanged= True current_code= memory_candidate_expired final= expired 2 item= None
accepted= True stale_code= memory_candidate_version_conflict stale_unchanged= True current_code= memory_candidate_expired final= expired 3 item= active
```

`stale_unchanged=True` 同时比较 candidate status/version/review fields、audit count 和 item status。Correct-version expiry 仍不撤销 accepted item，符合现有受控 409 生命周期例外。

#### API semantics

TestClient 使用 in-memory UoW 对 expired accepted candidate 发送 stale version：

```text
api_stale_code= 409 memory_candidate_version_conflict state_unchanged= True
```

随后 current version 返回 `memory_candidate_expired` 409，candidate 转 `expired`、version +1，Memory 仍 `active`。Route 对 version conflict 仍 rollback，仅对 source-invalid/expired 受控生命周期 409 执行 commit。

### Regression and Scope Review

- C1: generic group bypass 仍固定拒绝。
- I1: candidate/item fingerprint corruption 仍 fail closed，不撤销 unrelated Memory。
- I3: inactive workspace 仍使 group Memory 转 `revoked`，不转 `deleted`。
- I4: 三个 new-item branch 仍显式 flush，当前 PostgreSQL test 仍覆盖无 commit list + exact revoke。
- Threshold、adapter exact source shape、verified identity、`workspace.read`/`member.manage`、固定脱敏 HTTP errors 与 safe response 结构未发现回归。
- 未发现 migration、schema/API/permission 扩展、Message/Telegram persistence、webhook/parser/ingestion、frontend、Provider/LLM、Redis、RAG/vector、LangGraph 或 external-call 扩大。
- 本次未连接/重置本地 PostgreSQL，未修改 git 或外部状态。

### Fix Round 2 Spec Compliance Verdict

`PASS`。六个原 finding 均已关闭。Recursive raw/source/transport carrier 拒绝、service/stored-data 二次防线、exact fingerprint revoke、version-before-TTL、正确 expiry 例外、workspace revocation 分类和 `autoflush=False` 事务内可见性均与 brief 一致。

### Fix Round 2 Code Quality Verdict

`PASS`。当前实现将 group-specific invariants 收敛到 strict candidate contract，并在 create、promotion、read 和 revoke 边界重新验证；public/private materializer、canonical correlation、lifecycle ordering、fixed error-code/transaction 语义与 flush 边界清晰。未留下 Critical、Important 或 Minor 审查 finding。
