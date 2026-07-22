# Stage08 Package B Task B1 独立代码审查

## 结论

**FAIL**

当前模型、迁移和 UoW 实现逐项对照 Task B1 后未发现 Critical 级实现错误：JSONB 类型、canonical status check、shape/version/confidence check、unique 组合、lifecycle index、`supersedes_id` 自外键、UoW 方法签名、SQL `created_at DESC, id DESC`、SQL `with_for_update()` 及 migration chain 都与 brief 一致。

但 Task B1 把“聚焦测试真实覆盖 lock query、精确排序和精确持久化合同”列为交付要求；现有测试不能防止这些行为被错误实现，而 report 已将其声明为已覆盖。因此不能 PASS。

## Critical

无。

## Important

### I-01、所谓 lifecycle-lock 测试没有验证 `SELECT ... FOR UPDATE`

- 位置：`backend/tests/integration/test_stage08_memory_postgres.py:130-133`
- 对应实现：`backend/app/services/stage06_platform.py:1286-1294` 和 `1320-1328`
- 问题：测试只调用两个 lock 方法并断言返回值非空。如果实现退化为 `session.get()` 或不带锁的 `select()`，测试仍会通过。它也没有使用第二个 transaction 证明行锁会阻塞竞争生命周期更新。
- 影响：Task B1 brief 明确要求“lock query”证据，并把 SQL `with_for_update()` 列为非可选语义。当前 production code 确实使用了 `with_for_update()`，但交付的回归测试无法保护它。
- 修复要求：至少断言实际发出的 SQL 包含 `FOR UPDATE`；更强证据是用两个独立 PostgreSQL session 做有界阻塞/解锁测试，且 item/candidate 两条路径都覆盖。

### I-02、列表测试没有覆盖 `id DESC` 的同时间戳 tie-break

- 位置：`backend/tests/unit/test_stage08_memory_contracts.py:82-112`；`backend/tests/integration/test_stage08_memory_postgres.py:135-149`
- 对应实现：`backend/app/services/stage06_platform.py:782-823` 和 `1296-1343`
- 问题：内存和 PostgreSQL 测试都把两条数据的 `created_at` 设为相差 1 秒。因此只证明了 `created_at DESC`，完全没有进入 `id DESC` tie-break。如果内存实现忽略 `id`、SQL 改为 `id ASC`，现有测试仍会通过。
- 影响：brief 明确要求内存/SQL parity 且顺序精确为 `created_at DESC, id DESC`。当前代码写法正确，但没有可防回归的证据。
- 修复要求：为 item 和 candidate 使用相同 `created_at` 与可预测 UUID，在 InMemory 和 PostgreSQL UoW 中都断言较大 `id` 先返回。

### I-03、迁移测试不能证明声称的“精确 constraints/unique/index/supersedes FK”

- 位置：`backend/tests/integration/test_stage08_memory_postgres.py:76-105` 和 `151-194`
- 问题：
  - 列只用 `issubset` 检查，未核对 item 的 `supersedes_id/revoked_at/deleted_at`、candidate 的 `reviewed_at/reviewed_by_user_id`、类型及 nullable 属性。
  - lifecycle index 只检查 index name 含 `workspace_status_valid_until`，未断言索引精确列为 `(workspace_id, status, valid_until)`。
  - 没有 introspect 两个 unique constraint 的精确列；只证明同 workspace/type/fingerprint 重复时会失败，没有证明“不同 workspace 或不同 type 但同 fingerprint”必须成功。因此过宽或过窄的 unique 也可能漏过。
  - 没有 introspect/行为测试 `supersedes_id -> stage08_memory_items.id`，也没有证明 candidate 没有这条外键。
  - confidence 只测了 `1.1`，没有测试负数被拒绝和 `0/1` 边界被接受。
- 影响：实际 model/migration 手工核对后是一致的，但当前测试与 report 中“JSONB/status/version/confidence, unique fingerprint, indexes, MemoryItem-only supersedes FK 已覆盖”的表述不对等。这是 B1 持久化契约的主要验收产物，不宜仅依赖审查者人工阅读。
- 修复要求：对 columns/types/nullability、check 名称与语义、unique 精确列、index 精确列、workspace/self FK 做 inspector 断言；增加 unique 正例和 confidence 边界行为测试。

## Minor

无。

## 已核对且通过的实现项

- `Stage08MemoryItem` 和 `Stage08MemoryExtractionCandidate` 使用 UUID PK、timestamp mixin、workspace FK 和 PostgreSQL `JSONB`。
- 两组 status check 与 brief 的 canonical 值精确一致；`version > 0`、candidate `confidence >= 0 AND confidence <= 1` 以及三组 JSONB shape check 在 model/migration 中对称。
- unique constraint 和 lifecycle index 的实际 model/migration 定义精确一致。
- `supersedes_id` 可空且仅自引用 `stage08_memory_items.id`；candidate 无 `supersedes_id`。
- protocol、InMemory、SqlAlchemy 均有 brief 要求的 8 个方法；SQL 的两个 lifecycle lock 实际使用 `.with_for_update()`；列表实现实际为 `created_at DESC, id DESC`。
- 模型已进入 `app.models` registry。
- migration 为 `revision="20260718_0029"` / `down_revision="20260717_0028"`，upgrade/downgrade 对称，未引入第二个 head。
- B1 新增的 production 定义没有 raw-text、prompt/response、provider key、Telegram user ID 或 chain-of-thought 列，没有 API、provider、Telegram、Redis、materializer、outbox 或外部写入行为。JSONB 只做 shape check，符合 B1 明确的不在 DB trigger 中扫描内容的边界；敏感 key 的递归拒绝属于后续 B2 typed contract。

## Verification

- 聚焦测试：

  ```text
  python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/integration/test_stage08_memory_postgres.py -k memory
  4 passed in 5.09s
  ```

  `STAGE06_LOCAL_DATABASE_URL` 已配置，两个 integration test 通过现有 fixture 重建 public schema 并实际 upgrade 到 head；这只是 disposable local PostgreSQL 证据。

- Migration head：

  ```text
  python -m alembic heads
  20260718_0029 (head)
  ```

- Migration chain：

  ```text
  20260713_0027 -> 20260717_0028
  20260717_0028 -> 20260718_0029 (head)
  ```

- `python -m alembic check` 不能作为本任务的 clean-drift 证据：对 disposable Stage06 DB 运行时报告了一组既有 Stage05/06/07 index metadata drift，输出中没有 `stage08_memory_items` 或 `stage08_memory_extraction_candidates` 差异。这些全局历史 drift 不归因于 B1，未作为本次 FAIL 的 finding。
- `ruff` 未运行：当前 Python 环境未安装 `ruff` (`No module named ruff`)。
- 未运行 broad acceptance，符合 brief 对 B1 的范围限制。

## PASS 条件

1. 补齐 I-01 的真实 `FOR UPDATE` 证据。
2. 补齐 I-02 的同 `created_at` / `id DESC` 内存与 SQL parity 测试。
3. 补齐 I-03 的精确 schema/unique/index/FK 断言，并更正 report 中超出实际证据的表述，或以新测试使该表述成立。
4. 重跑聚焦测试与 Alembic single-head 检查并全部通过。

---

## Fix Round 1 独立复审

### 结论

**FAIL**

I-01 和 I-02 已被真实测试证据解决；I-03 已补齐大部分，但“所有 columns/types/nullability 的精确 introspection”仍未完成。因此 Fix Round 1 仍不满足原 review 的全部 PASS 条件。

### Critical

无。

### Important

#### FR1-I-01、I-03 仅部分修复：多个列的精确 type/nullability 仍无回归保护

- 位置：`backend/tests/integration/test_stage08_memory_postgres.py:105-170`
- 已修复部分：测试已断言两张表的完整列名集合、三个 JSONB 列、`id/workspace_id` UUID、candidate `Numeric(5,4)`、部分必填/可空列，并精确检查 unique/index/FK 列。
- 剩余问题：
  - 未检查 `memory_type` / `candidate_type` 为 `String(120)` 且 non-null。
  - 未检查 `status` 为 `String(40)`、`source_fingerprint` 为 `String(64)`、`version` 为 `Integer`。
  - 未检查 `supersedes_id` 和 `reviewed_by_user_id` 为 UUID；当前只检查了它们的 FK/可空性或可空性。
  - 未检查 `valid_until/revoked_at/deleted_at/reviewed_at/created_at/updated_at` 的 timezone-aware `DateTime` 类型。
  - 未精确检查 `id`、`memory_type/candidate_type` 和 candidate `confidence` 的 non-null（PK 会间接限制 `id`，但这不等于测试已完成明示的 exact nullability introspection）。
- 虚假阳性风险：例如将 `source_fingerprint` 改为无长度的 `Text`、将 `version` 改为 `Numeric`、将 `reviewed_by_user_id` 改为字符串，或将 `candidate_type/confidence` 改为 nullable，现有 inspector 断言与行为测试仍可能全部通过。
- 影响：Fix Round 1 report 的“JSONB/UUID/Numeric types”描述对其已测子集是真实的，但尚不足以满足复审任务明确要求的 columns/**types**/nullability 精确 introspection。
- 修复要求：对两张表的每个列建立 expected type/length/precision/scale/timezone/nullability 映射并逐列断言；保留现有 exact column-set、unique/index/FK 和行为测试。

### 原 Important 解决情况

- **I-01 已解决**：`test_memory_postgres_lifecycle_locks_block_competing_sessions` 为 item/candidate 分别捕获实际 SQL，断言目标表的 statement 含 `FOR UPDATE`；第二 session 在发起 lock 前暴露自身 backend PID，observer 用 `pg_blocking_pids` 确认它被 session A 的精确 PID 阻塞，A rollback 后 B 才在有界 timeout 内返回。这不是“只调方法断言非空”的虚假阳性。
- **I-02 已解决**：InMemory 和 PostgreSQL 测试均使用相同 `created_at` 与 `UUID(int=1/2)`，且 item/candidate 都断言较大 UUID 先返，真实进入 `id DESC` tie-break。
- **I-03 部分解决**：完整列名集合、JSONB 形状行为、canonical statuses、version/confidence 边界、unique namespace 正反例、unique 精确列、lifecycle index 精确列、workspace FK、MemoryItem self FK 及 candidate 无 self FK 已有真实证据；只剩 FR1-I-01 列出的 type/nullability 精确性。

### 范围与外部行为

- Fix Round 1 所见变更集中在两份聚焦测试与 report；未发现 B1 production model/migration/UoW 的功能扩张。
- 新增测试只调用 disposable local PostgreSQL、SQLAlchemy event capture、线程和 PostgreSQL lock-observer 查询；没有 provider、Telegram、Redis、HTTP/network API 或外部写入行为。

### Fresh Verification

```text
python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/integration/test_stage08_memory_postgres.py -k memory
8 passed in 7.90s

python -m alembic heads
20260718_0029 (head)
```

`STAGE06_LOCAL_DATABASE_URL` 已配置，PostgreSQL migration、inspector、双 session 行锁、排序、unique 与约束测试本轮实际执行，无 skip。

### Fix Round 1 PASS 条件

1. 补齐 FR1-I-01 的逐列 exact type/length/timezone/nullability introspection。
2. 重跑相同聚焦测试与 Alembic single-head 检查并通过。

---

## Fix Round 2 最终独立复审

### 最终结论

**PASS**

Fix Round 2 已完整解决剩余 FR1-I-01 / 原 I-03。结合 Fix Round 1 已验证的真实 `FOR UPDATE` 行锁和同 `created_at` 的 `id DESC` parity，Task B1 的三项 Important 现已全部关闭。

### Critical

无。

### Important

无。

### I-03 最终核验

- `stage08_memory_items` 的全部规范列均被精确 introspect：
  - `id/workspace_id/supersedes_id` 的 UUID 类型与各自 nullability；
  - `memory_type String(120)`、`status String(40)`、`source_fingerprint String(64)`；
  - `scope/payload/source_refs` 的 PostgreSQL JSONB；
  - `version Integer`；
  - `valid_until/revoked_at/deleted_at/created_at/updated_at` 的 timezone-aware `DateTime` 与精确 nullability。
- `stage08_memory_extraction_candidates` 的全部规范列均被精确 introspect：
  - `id/workspace_id/reviewed_by_user_id` 的 UUID 类型与各自 nullability；
  - `candidate_type String(120)`、`status String(40)`、`source_fingerprint String(64)`；
  - `confidence Numeric(5,4)` 且 non-null；
  - `scope/normalized_payload/source_refs` 的 PostgreSQL JSONB；
  - `version Integer`；
  - `valid_until/reviewed_at/created_at/updated_at` 的 timezone-aware `DateTime` 与精确 nullability。
- helper 断言使用 SQLAlchemy 类型族加明确 `length/precision/scale/timezone/nullability`，不依赖 PostgreSQL 可变的格式化字符串；UUID 则使用 reflection 的精确 `uuid` 表示。上述任一字段类型、长度、时区或可空性回归都会使测试失败，未发现宽泛断言造成的虚假阳性。
- 两表完整 column-name set、canonical status/shape/version/confidence 行为、unique constraint 名称与精确列、lifecycle index 名称与精确列、workspace FK、MemoryItem self FK 及 candidate 无 self FK 的断言均仍保留。

### 范围核验

- Fix Round 2 仅扩展 `backend/tests/integration/test_stage08_memory_postgres.py` 的持久化契约断言并更新 report；B1 production model、migration、UoW 定义与前两轮审查时一致，未发现生产范围扩张。
- 新增代码仅是 PostgreSQL inspector assertion helper，没有 provider、Telegram、Redis、HTTP/network API、外部写入或 B2-B5 行为。
- 本次复审按要求仅执行 B1 聚焦验收，未扩大为无关 broad acceptance。

### Fresh Verification

```text
python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/integration/test_stage08_memory_postgres.py -k memory
8 passed in 7.61s

python -m alembic heads
20260718_0029 (head)
```

`STAGE06_LOCAL_DATABASE_URL` 已配置，8 个聚焦测试全部实际执行，无 skip。证据属于 disposable local PostgreSQL，不表示 staging/production 验收。
