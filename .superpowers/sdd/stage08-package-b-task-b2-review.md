# Stage08 Package B Task B2 独立严格代码审查

## 结论

**FAIL**

Task B2 的主体边界是克制的：实现只支持 `platform_record`，draft/Telegram/group scope 均在 dereference 前拒绝；未引入 API、outbox、provider、RAG、Redis、LangGraph、前端或外部调用；审计调用也没有传入 payload、scope、source refs、fingerprint、field key 或 source value。candidate 路径实际调用了 B1 的 lifecycle lock，并同时核验 actor role 与当前 membership role。

但当前实现存在一个直接的数据安全 fail-open：workspace/base/table/source record/field 的 inactive/deleted 状态没有进入有效性计算，导致已失效资源仍可 materialize/read。另有 forbidden field key、非标准 JSON 数值、并发 identity/version、TTL 和 candidate expected-version 的合同缺口。因此不能通过 B2。

## Critical

### C-01：资源 inactive/deleted 状态未参与 scope/source validity，失效后仍返回 Memory payload

- 位置：`backend/app/services/stage08_memory.py:209-238`、`:241-298`
- 依赖实现：`backend/app/services/stage06_platform.py:2603-2624`、`:4275-4280`
- 问题：
  - `_validate_scope` 只检查 workspace/base/table/relationship record 是否存在以及 ID 链是否同 workspace，不检查 `Workspace.status`、`BitableBase.status`、`PlatformTable.status` 或 relationship `PlatformRecord.record_status`。
  - `_validate_current_platform_sources` 只检查 source record 存在、version、table/base 归属和 `read_record_for_actor` 的返回字段，不检查 source `record_status`。
  - `read_record_for_actor` 本身会返回 inactive/deleted record，并且 `_can_actor_read_field` 不检查 `PlatformField.status`；因此不能把这些 valid-state 检查委托给它。
  - `revoke_memory_candidate` 同样未检查 candidate 所属 workspace 是否 active；只要 membership 仍 active，inactive workspace 中仍可变更 candidate。
- 独立复现：把已 materialize item 的 workspace/base/table 分别设为 `inactive`、source record 设为 `deleted`、source field 设为 `inactive` 后，五种情况的 `read_memory_projection` 都仍返回 payload，item 仍为 `active`；在 workspace inactive 或 source record deleted 后直接 materialize 也仍创建 `active` item。
- 影响：workspace 停用、表/字段停用或 source 删除/失效不能立即撤销 Memory 读取，违反 BDD B-04/B-05、数据安全合同的 `source validity/deletion/retention state` 交集和 B2 的同步 fail-closed 要求。这是权限/留存撤销后的数据泄露路径。
- 修复要求：在 materialize/read 的同一 server-owned valid-state helper 中严格要求 workspace/base/table/field/source record/relationship record 全链 active；materialize 使用固定验证码拒绝，read 在锁内把受影响 active item 转为 `deleted`、写脱敏 audit 并返回 `None`；candidate 变更也必须拒绝 inactive workspace。补齐上述每种状态的回归测试。

## Important

### I-01：forbidden field key 可通过 `source_refs.field_keys` 持久化并触发读取

- 位置：`backend/app/runtime/stage08_memory_contracts.py:50-60`、`:105-125`
- 问题：递归检查只把 dict 的实际 key 与 forbidden set 比较；`field_keys` 中的值只是 list/tuple element，所以 `prompt`、`response`、`raw_text`、`normalized_text`、`api_key`、`token`、`telegram_user_id` 全部会被 `MemorySourceRef` 接受。
- 影响：这些 forbidden 标识可写进持久化 `source_refs`，服务还会读取对应当前字段值。虽然当前 safe read/audit 不回传该值，但这与 brief 对 source refs/field keys 的递归禁止边界不一致，也给后续 adapter 暴露敏感 provenance 留下入口。
- 修复要求：field-key validator 额外做 case-insensitive forbidden-name 拒绝；补齐七个名称（含大小写变体）在 field keys 中的参数化测试。

### I-02：JSON-safe 合同接受 `NaN` 和正负无穷

- 位置：`backend/app/runtime/stage08_memory_contracts.py:18`、`:86-93`；`backend/app/services/stage08_memory.py:390-395`
- 问题：Pydantic `JsonValue` 在当前版本接受 `float('nan')`、`float('inf')` 和 `float('-inf')`；`json.dumps` 默认 `allow_nan=True`，fingerprint 会使用非标准 JSON 常量。
- 影响：这不是合法 JSON，可能让 PostgreSQL JSONB 持久化在晚期失败，并使 canonical fingerprint 脱离合同定义。当前“non-JSON values”测试只覆盖 `object()`，无法阻止该回归。
- 修复要求：递归拒绝所有 non-finite float，并使 canonical serializer 使用 `allow_nan=False` 作为纵深保护；增加三种数值的合同测试。

### I-03：materialization 的 idempotency / supersession / conflict 决策没有生命周期串行化

- 位置：`backend/app/services/stage08_memory.py:52-113`
- 问题：服务先无锁 `list_memory_items`，再决定 reuse、active version、supersede 或 conflict。相同 fingerprint 并发时两个事务都可能尝试 insert，最终由 unique constraint 抛错而不是幂等返回；不同 fingerprint、同 identity 并发时可同时创建 version 1，或同时基于同一 active 创建多个 version 2 active/conflicted item。数据库没有 identity/version 唯一约束可恢复该语义。
- 影响：BDD 的“同 fingerprint 幂等”和“同 identity 单一 active/version 链”在真实并发下不成立；现有测试全为单线程 InMemory，未覆盖。
- 修复要求：在读取 identity 集合和写 lifecycle 变更前使用可覆盖“尚无 item”的 workspace/identity 级串行锁，并在锁内重读；补真实 PostgreSQL 双 session 幂等、supersede 和 conflict 竞态测试。

### I-04：TTL 合同接受 naive datetime，read 不 fail closed 而是抛 `TypeError`

- 位置：`backend/app/runtime/stage08_memory_contracts.py:79-84`；`backend/app/services/stage08_memory.py:130`
- 问题：`valid_until` 未要求 timezone-aware。naive `valid_until` 可通过合同并 materialize；当 `now` 为 aware datetime 时，`valid_until <= now` 抛出 `TypeError: can't compare offset-naive and offset-aware datetimes`。
- 影响：TTL 不确定性没有返回 `None`/transition，而是服务错误，违反 read fail-closed 生命周期合同。
- 修复要求：合同层拒绝 naive datetime（或明确规范化为 UTC），并覆盖 aware/naive/到期边界测试。

### I-05：candidate `expected_version` 不是严格正整数，错误码不稳定

- 位置：`backend/app/services/stage08_memory.py:171-205`
- 问题：当前仅拒绝 bool 和 `< 1`。`1.0` 会被接受；`None`/字符串在比较时抛原生 `TypeError`，没有固定 `memory_candidate_expected_version_invalid`。锁本身与锁后 state/version 检查是正确的，owner/admin 也同时经过 actor 与 membership 双重角色核验。
- 影响：公共 service surface 对 malformed version 不能稳定 fail closed；后续 B4/API 只要有一个调用方绕过严格请求模型，就可能产生 500 或接受非整数版本。
- 修复要求：先做 `isinstance(expected_version, int) and not isinstance(..., bool)` 的严格检查，再获取/使用 lifecycle lock；补 `None`、字符串、float、bool、0、负数测试，并保留并发锁证据。

## Minor

### M-01：审计 permission snapshot 多写了合同 allowlist 外的 actor role

- 位置：`backend/app/services/stage08_memory.py:405-440`
- 问题：audit 没有泄漏 payload/scope/source/field key，符合本次主要安全红线；但 brief 说 audit state 只包含 IDs、type、status、versions 和固定 reason code，当前 `permission_snapshot` 还包含 `role`。
- 修复要求：若 role 不是正式批准的审计字段，从 B2 audit state 删除；若确需保留，应先把合同改为明确允许，而不是隐式扩张。

## 已核对且通过

- Contract 使用 `extra="forbid"`，memory type、UUID、正 source version、非空且唯一 lower-snake-case field keys、非空 source refs 的基本类型约束存在；普通 object/bytes/非字符串 dict key 等非 JSON 值被拒绝。
- Materialize 在任何 source dereference 前拒绝 `record_change_draft`、`telegram_message` 和 group scope；没有读取 draft/Telegram payload。
- 正常单线程路径的 source version、workspace/base/table ID 链、payload-key union、current readable value equality、same-fingerprint reuse、equal-payload supersede、different-payload conflict 均与 brief 一致。
- Active membership 和 field permission `hidden` 会 fail closed；candidate 使用 `SELECT ... FOR UPDATE` 对应的 UoW lock，锁后检查 state/version，且 actor role 与 membership role 都必须是 owner/admin。
- Safe read 只返回 `id/memory_type/version/scope/payload/valid_until`，不返回 source refs、fingerprints、field keys 或 audit。
- Audit 调用参数没有 payload、scope、source refs、fingerprint、field key、source value、prompt/response 或 Telegram/provider 标识。
- B2 production 文件没有 API/router、outbox、draft/Telegram adapter、provider、RAG/vector、LangGraph、Redis、HTTP/send 或外部 client import/call。
- 按 brief 后文件时间窗口做只读清单核对，B2 source/test 写入集中在指定四个文件（另有 task report 与 Python `__pycache__`）；遵守“不要 git”，未调用 git，因此不把该清单冒充 git diff 证据。

## Verification

目标测试本轮实际执行：

```text
python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py
14 passed in 0.84s
```

额外只读 Python probes 实际证明：

```text
workspace/base/table inactive, record deleted, field inactive -> READ True, item active
inactive workspace materialize -> ACCEPT active
deleted source record materialize -> ACCEPT active
NaN/+Inf/-Inf -> contract ACCEPT
all 7 forbidden names in source_refs.field_keys -> ACCEPT
naive valid_until vs aware now -> TypeError
expected_version None/"1" -> TypeError; 1.0 -> ACCEPT
```

未运行 broad suite、Package B PostgreSQL acceptance、API/Telegram/provider 或任何外部系统测试；这些不属于 B2 本次 focused review。未执行 git。无临时测试文件；本审查只新增本报告。

## PASS 条件

1. 修复 C-01 的全链 valid-state 校验与 read transition，并补 workspace/base/table/record/relationship record/field/candidate workspace 回归测试。
2. 修复 I-01、I-02 的 forbidden field key 与 finite JSON 契约。
3. 修复 I-03 并提供真实 PostgreSQL 并发幂等/version-chain 证据。
4. 修复 I-04、I-05 的 timezone 与 strict expected-version fail-closed 行为。
5. 处理 M-01 的 audit allowlist 偏差，重跑 focused tests，并更正 task report 中“已覆盖”的过度表述。

---

## Fix Round 1 独立复审

### 结论

**PASS**

Fix Round 1 已关闭初审的 C-01、I-01 至 I-05 和 M-01。复审未发现剩余 Critical 或 Important。修复保持在 B2 边界内：没有 schema/migration/API/outbox/draft/Telegram/provider/RAG/Redis/LangGraph/frontend 或外部调用扩张。

### Critical

无。

### Important

无。

### 初审 finding 关闭情况

- **C-01 已关闭**：`materialize_memory_from_projection` 在任何 item-state 读取前取得现有 workspace row lock，并立即拒绝 missing/inactive workspace。`_validate_scope` 现在要求 workspace、显式/隐式 base、table、customer/project relation record 全链为 `active`；`_validate_current_platform_sources` 还要求 source record、source table/base 和每个 source field 为 `active`。read 遇到上述失效状态会取得 item lifecycle lock，把仍为 `active` 的 item 转为 `deleted`、设置 `deleted_at`、写固定 reason audit 并返回 `None`。candidate revocation 也拒绝 inactive workspace。
- **I-01 已关闭**：`MemorySourceRef.field_keys` 对七个 forbidden name 做 case-insensitive 拒绝，参数化测试覆盖大小写变体。
- **I-02 已关闭**：递归校验拒绝 `NaN/+Inf/-Inf`，canonical JSON 同时设置 `allow_nan=False`。
- **I-03 已关闭**：workspace row lock 位于 membership、scope/source validation、fingerprint/identity 计算和 `list_memory_items` 之前，因此 lock-before-read 成立，且事务持锁覆盖 reuse/supersede/conflict 写入。真实 PostgreSQL 双 session 测试通过 `pg_blocking_pids(blocked_pid)` 精确确认 session B 被 session A 的 PID 阻塞；A commit 后，同 fingerprint 返回 A 创建的同一 item，不同 fingerprint/同 identity 基于提交后状态创建 `conflicted` version 2，而不是竞争的 version 1 active。
- **I-04 已关闭**：合同边界拒绝无 timezone 的 `valid_until`；PostgreSQL 列仍为 timezone-aware，未改 schema。
- **I-05 已关闭**：`expected_version` 仅接受非 bool 的正 `int`；`None`、字符串、float、bool、0、负数均以固定 `memory_candidate_expected_version_invalid` 拒绝。candidate lifecycle lock 仍先于 state/version mutation，actor role 与当前 membership role 仍双重要求 owner/admin。
- **M-01 已关闭**：memory/candidate audit 的 `permission_snapshot` 只保留固定 `action` reason code；`after_state` 只含 status/version。未发现 payload、scope、source refs、fingerprint、field key、source value、Telegram/provider 标识进入 audit。

### Valid-state 与 transition 复核

- Unit regressions覆盖 materialize 时 inactive workspace/base/table/field/source record 拒绝，以及 read 时上述五类失效均转 `deleted`。
- customer/project relation 两个 scope 维度均覆盖 read 后失效转 `deleted`。复审另以只读 probe 验证：relation 在 materialize 前已 inactive 时，两种 scope 均以 `memory_scope_invalid` 拒绝。
- Membership disabled、foreign workspace/base/table/relation、stale source version、field hidden、payload/current value mismatch、TTL expiry、unsupported draft/Telegram/group source 的既有 fail-closed 行为继续通过。
- Safe read 仍只输出 `id/memory_type/version/scope/payload/valid_until`；source provenance、fingerprint、field keys 和 audit 未进入响应。

### Concurrency evidence 复核

生产代码使用既有 `lock_workspace_for_stage08_execution`，SQL UoW 实际为 workspace `SELECT ... FOR UPDATE`。新增 integration test 不是只断言返回值：

1. session A 进入 materialization 并保留未提交 workspace row lock；
2. session B 暴露自己的 PostgreSQL backend PID 后进入同 workspace materialization；
3. observer 使用 `pg_blocking_pids` 断言 B 的 blocker 正是 A 的 PID；
4. A commit 后 B 才完成，并断言同 fingerprint reuse 或不同 fingerprint/同 identity 的 version 2 conflict chain。

这同时证明了 lock-before-item-read、同 fingerprint 幂等和同 identity 不同 fingerprint 的提交后版本决策。证据属于 disposable local PostgreSQL，不代表 staging/production。

### Fresh Verification

```text
python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/integration/test_stage08_memory_postgres.py -k memory
51 passed in 10.89s
```

额外只读 probe：

```text
inactive customer_record_id at materialization -> memory_scope_invalid
inactive project_record_id at materialization -> memory_scope_invalid
```

未运行 broad suite、Package B 后续 B3-B5、API/Telegram/provider 或外部系统测试；这些不属于 B2 Fix Round 1。未执行 git，未修改业务代码，无临时文件。本轮只追加本复审记录。
