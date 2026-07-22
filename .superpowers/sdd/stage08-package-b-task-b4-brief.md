# Stage08 Package B Task B4：受控 Telegram 群聊 Memory 候选与安全读取 API

## Status 与范围

- Task status：ready for implementation；本文件是实现前任务简报，不包含实现。
- Authority：`STAGE_08_SOURCE_OF_TRUTH.md`、`STAGE_08_PACKAGE_B_MEMORY_BDD_AND_ACCEPTANCE.md` 与 `STAGE_08_DATA_API_SECURITY_CONTRACT.md`。
- Goal：仅为已授权、仍有效的 Telegram 群聊来源创建版本化的安全候选，并提供 Memory 安全列表与管理撤销 API。
- 固定部署阈值：`GROUP_MEMORY_CANDIDATE_MIN_CONFIDENCE = Decimal("0.85")`。不得通过请求、环境变量、workspace/table 设置或浮点近似覆盖；`confidence < Decimal("0.85")` 时不创建 candidate、不创建 Memory、不写 outbox、不调用外部系统。

本任务只消费既有 B1/B2 的持久化模型、生命周期服务、`Stage06TelegramBinding` 与已验证 HTTP identity。它不实现群聊文本提取、Telegram webhook 改造、Bot API 读写、Provider/LLM、Redis、向量/RAG、新权限角色、迁移或前端。候选创建是**内部服务入口**；本任务没有 `POST candidate` HTTP 路由。

## 不可突破的安全边界

- `raw_text`、`raw_caption`、`normalized_text`、完整聊天窗口、prompt、response、Telegram user ID、provider key 和 CoT 不得进入 candidate、Memory、outbox、audit、异常 detail、HTTP request/response 或日志。
- source adapter 只能在当前进程持有 Telegram 入站消息的短暂投影；传给 B4 service 的 DTO 不含任何文本字段，`extra="forbid"`。不得由 B4 主动调用 Telegram API 或读取历史聊天。
- B4 只保存安全的 `message_id`（现有内部 UUID）、`binding_id` 派生的 opaque `group_chat_ref`、允许的候选类型、置信度、归一化 payload 和生命周期数据；不得保存原始 chat ID、原始 Telegram message/update ID 或 Telegram user ID。
- 读取、提升、撤销、TTL、绑定失效、来源不完整及权限不确定都 fail closed。API 不接受客户端提供的 actor、scope、field allowlist、candidate payload、source reference、confidence、状态、审计内容或版本终态。
- 使用现有 `workspace.read` 与 `member.manage`；不得增加 action/role。管理撤销等价于现有 `member.manage`，仅 owner/admin 可通过既有授权矩阵。
- 不得 stage、commit、reset、checkout 或 clean 当前 worktree。

## 已核对的现状与本任务的收敛

1. B2 当前 `MemorySourceRef` 已允许 `telegram_message`，但 `_validate_current_platform_sources()` 和 `read_memory_projection()` 对 `group_chat_ref` 一律拒绝；B4 只能为下述受控来源补齐这条路径，不能把它变成任意 Telegram/任意群聊读取能力。
2. 既有 `Stage06TelegramBinding` 有 `workspace_id`、`workspace_member_id`、`telegram_chat_id`、`telegram_user_id`、`binding_type`、`scope_policy` 和 `status`，但没有版本列，也没有群类型留存。source adapter 必须在入站处理的短命上下文中确认 `chat_type in {"group", "supergroup"}`；后续读取重新确认 binding、workspace 和绑定 member 仍 active。
3. 既有 `Message` 表历史上可包含原始文本字段；B4 不得查询、序列化或新增任何对此类字段的留存。它只接收由可信入站流程生成的安全 source reference。因此，B4 不能单独修复历史 Message 的原文留存；该跨阶段问题列为风险，而非在本任务静默扩大范围。
4. 现有 candidate 没有 `memory_item_id` 外键。B4 必须让 candidate 与提升出来的 Memory 使用**相同** `source_fingerprint`（同一 canonical `{type, scope, normalized_payload, source_refs}` SHA-256），这样 accepted candidate 的关联 Memory 可以无 schema 变更地精确定位、锁定和撤销。

## 精确接口与来源/版本语义

### 1. 内部短命 source adapter

在新文件 `backend/app/services/stage08_group_memory_source.py` 定义纯进程内的严格 DTO 与 adapter；它不注册路由、不发 Telegram 请求、不写数据库。

```python
GroupChatKind = Literal["group", "supergroup"]

class TrustedGroupMessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message_id: UUID
    chat_id: StrictStr = Field(min_length=1, max_length=120)
    chat_type: GroupChatKind
    binding_id: UUID

class GroupMemorySourceProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_ref: MemorySourceRef
    scope: MemoryScopeProjection
    binding_id: UUID

def resolve_authorized_group_message_source(
    uow: Stage06PlatformUnitOfWork,
    source: TrustedGroupMessageInput,
) -> GroupMemorySourceProjection | None: ...
```

输入只能由既有入站 webhook/parser 的当前处理链调用；不能从 HTTP body、query、outbox 或持久化 raw Message 重建。它只在内存中比较 `source.chat_id` 与 binding 的 chat ID，然后立即丢弃 `chat_id`，返回：

```python
MemorySourceRef(
    source_kind="telegram_message",
    source_id=message_id,
    source_version=None,
    field_keys=("group_candidate_projection",),
)
MemoryScopeProjection(
    workspace_id=binding.workspace_id,
    group_chat_ref=f"stage06-binding:{binding.id}",
)
```

`source_version=None` 的确切语义是“Telegram 单条入站消息在 B4 中为 immutable reference，既有 `Message` 无可用内容版本列”；它不是未知版本的放行。候选/Memroy 的 fingerprint 始终包含内部 `message_id` 与 opaque binding ref。source adapter 必须同时验证：binding 存在、`status == "active"`、`binding_type == "chat_user"`、`workspace_member_id` 非空且该 member 属于同 workspace 且 active、`source.chat_type` 为 group/supergroup、以及 binding chat ID 与短命 input chat ID 完全相等。任何一项不成立返回 `None`，不留存诊断原文。

### 2. 候选 contract 与服务

在 `backend/app/runtime/stage08_memory_contracts.py` 增加内部专用 DTO（或等价的同文件严格类型），但不要放入公开 request schema：

```python
class GroupMemoryCandidateProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    candidate_type: MemoryType
    confidence: Decimal
    scope: MemoryScopeProjection
    normalized_payload: dict[str, JsonSafeValue]
    source_refs: tuple[MemorySourceRef, ...]
    valid_until: datetime | None = None
```

要求：仅一个 `telegram_message` source ref；`scope.group_chat_ref` 必须严格为 `stage06-binding:<uuid>`；payload key 只能是 lower snake case、安全 JSON、非空且最多 16 个顶层 key；递归复用 B2 forbidden-key 检查，并额外拒绝 `text`、`message_text`、`chat_text`、`caption`、`transcript`、`excerpt`、`content`、`raw_content`。字符串值最大 500 Unicode code points，嵌套深度最多 4、列表最多 20 项；超限或不安全值一律拒绝。该结构防止“原文载体字段”进入持久化；不得声称它可自动证明任意自由文本绝非逐字摘要。

在 `backend/app/services/stage08_memory.py` 增加：

```python
GROUP_MEMORY_CANDIDATE_MIN_CONFIDENCE = Decimal("0.85")

def create_group_memory_candidate(
    uow: Stage06PlatformUnitOfWork,
    projection: GroupMemoryCandidateProjection,
    *,
    source: GroupMemorySourceProjection,
    actor: Actor,
    now: datetime,
) -> Stage08MemoryExtractionCandidate: ...

def resolve_group_candidate(
    uow: Stage06PlatformUnitOfWork,
    candidate_id: UUID,
    *,
    actor: Actor,
    now: datetime,
) -> Stage08MemoryItem | None: ...

def list_memory_projections(
    uow: Stage06PlatformUnitOfWork,
    workspace_id: UUID,
    *,
    actor: Actor,
    now: datetime,
) -> list[dict[str, object]]: ...
```

`create_group_memory_candidate` 必须先锁 workspace，并逐项重验 active member、scope、来源 projection、binding 与 `projection.scope/source_refs == source.scope/source_ref`。随后才校验 `confidence >= 0.85`。candidate 的 `source_fingerprint` 使用与 Memory 相同的 canonical SHA-256 输入：`candidate_type/memory_type`、脱敏 scope、normalized payload、source refs；禁止将 confidence、raw chat ID、binding chat ID 或任何文本原件计入 fingerprint。相同 fingerprint 直接返回既有 candidate（不重建、不升版本），不同候选正常新建为 `candidate, version=1` 并写仅含 status/version/action 的脱敏 audit。

`resolve_group_candidate` 必须在同一 workspace lock 内锁 candidate，重验 candidate 状态、TTL、binding 与 source ref，再将候选转换为 `MemoryMaterializationProjection` 并使用 B2 的 same-identity/conflict 规则：

- 无 active same-identity item：创建 `active` Memory；candidate 变为 `accepted`、`version += 1`、写 `reviewed_at/reviewed_by_user_id` 与脱敏 audit。
- 等价 payload：复用/按 B2 supersede 规则处理；candidate 仍为 `accepted`，不重复写 Memory。
- 不同 payload：只创建 `conflicted` Memory；旧 active item 不得覆盖；candidate 仍为 `accepted`，审计不含 payload/source ID。
- candidate 已处理、过期、binding 不 active、member 不 active、scope/fingerprint/source 形状无效时返回 `None` 或抛固定 `PlatformValidationError`，且不得创建/暴露 Memory。

为支持上述路径，`_validate_current_platform_sources()` 与 `read_memory_projection()` 仅对精确的 B4 `telegram_message + group_candidate_projection + stage06-binding:<uuid>` 组合调用新的无文本 binding validator；其它 Telegram source 仍拒绝。读取时 source 消失/格式损坏应将 Memory 标为 `deleted`；binding 或 binding member 被停用应标为 `revoked`；TTL 标为 `expired`。三个状态均立即不返回 projection，并写脱敏 lifecycle audit。

### 3. 撤销语义

保留 `revoke_memory_candidate(...)` 名称但扩展返回安全生命周期回执，而不是 raw candidate：

```python
class CandidateRevocationResult(NamedTuple):
    candidate_status: Literal["rejected", "accepted", "expired"]
    candidate_version: int
    memory_status: Literal["revoked"] | None
```

流程必须先锁 candidate、再以 candidate workspace 执行现有 `member.manage` 管理者检查、然后检查 `expected_version`：

- `candidate`：转 `rejected`，`version += 1`，填 review actor/time，审计 `stage08.memory_candidate_rejected`。
- `accepted`：以相同 `source_fingerprint` 查找并 `FOR UPDATE` 锁定关联 Memory。若其仍是 `active` 或 `conflicted`，转 `revoked`、设 `revoked_at`、写审计；candidate 保持 `accepted` 作为历史事实，返回 `memory_status="revoked"`。若无精确关联 item 或 item 已不是可撤销状态，固定 409，绝不猜测/撤销其它 Memory。
- 已 `rejected`、`expired` 或 candidate version 不匹配：固定 409，不改任何数据。
- binding/source 已失效：candidate 先转 `expired` 并写脱敏 audit，再返回固定 409；不把不完整来源提升或暴露为成功。

## HTTP 契约

创建 `backend/app/schemas/stage08_memory.py` 和 `backend/app/api/routes/stage08_memory.py`。路由采用与 Stage08 Runtime 相同的 request-validation redaction：任何 Pydantic/query 校验失败只返回 `stage08_memory_request_invalid`，绝不回显输入。

```text
GET  /api/stage08/memory?workspace_id=<uuid>&status=active
POST /api/stage08/memory/extractions/{candidate_id}/revoke
     body: {"expected_version": <positive integer>}
```

`GET` 先 `UUID(workspace_id)`，随后 `authorize_workspace_action(..., "workspace.read")`，再调用 `list_memory_projections`。当前 B4 只接受 `status=active`（缺省也是 active）；其它 status 422。每一条输出仅为：

```json
{"memory_type":"decision","status":"active","version":1,"payload":{"decision":"..."},"valid_until":"..."}
```

不得输出 item ID、candidate ID、scope、`group_chat_ref`、source refs、field keys、binding ID、chat ID 或 Telegram 身份。服务逐项调用安全读取；任一 item 不确定时跳过并可做生命周期失效，整个列表仍是安全的空/部分投影。

`POST revoke` 只从 path 取 candidate UUID、从 body 取 expected version、从 `get_stage06_request_identity` 派生 identity/actor；它不接受 workspace ID。成功回执只含 `candidate_status`、`candidate_version`、可选 `memory_status`，不含 candidate/Memory payload 或 source reference。SQLAlchemy UoW 成功才 commit；任何错误 rollback。

固定 HTTP 映射：workspace 不存在 404；foreign workspace/非 active membership/非 owner-admin 403；candidate 不存在 404；expected-version conflict、非 candidate/accepted 的不可撤销状态、source invalid/expired、关联 Memory 缺失或已终态 409；UUID/DTO/status 参数错误 422。所有 body/error 使用 `error_detail(code, code)` 的固定 code，禁止回显路径/body 值。

在 `backend/app/main.py` 注册新 router。不得添加 candidate creation、Telegram、Provider 或 webhook route。

## 预期文件范围

| 操作 | 文件 | 责任 |
| --- | --- | --- |
| Create | `backend/app/services/stage08_group_memory_source.py` | 无文本、短命群聊 source input/projection 与 binding validator。 |
| Modify | `backend/app/runtime/stage08_memory_contracts.py` | 严格群聊 candidate DTO、payload 与 opaque binding-ref 校验。 |
| Modify | `backend/app/services/stage08_memory.py` | 0.85 gate、candidate 持久化/解析、精确关联撤销、群聊来源安全读取与生命周期。 |
| Create | `backend/app/schemas/stage08_memory.py` | 严格 list/revoke DTO；无 raw/source/scope 字段。 |
| Create | `backend/app/api/routes/stage08_memory.py` | verified identity、现有授权、红脱敏 422 与 commit/rollback。 |
| Modify | `backend/app/main.py` | 仅注册 memory router。 |
| Modify | `backend/tests/unit/test_stage08_memory_contracts.py` | Group DTO/forbidden-key/threshold contract tests。 |
| Modify | `backend/tests/unit/test_stage08_memory_service.py` | candidate lifecycle、binding/source revalidation、conflict、revoke、无 raw tests。 |
| Create | `backend/tests/unit/test_stage08_memory_api.py` | route identity/authorization/redaction and API contract tests。 |
| Modify | `backend/tests/integration/test_stage08_memory_postgres.py` | local PostgreSQL candidate idempotency、locking、revocation/read-fail-closed evidence。 |
| Create/Modify | `project-docs/08-implementation/evidence/stage08-package-b-memory.md` | RED/GREEN、PostgreSQL、audit-redaction 和 no-external-call evidence。 |
| Create | `.superpowers/sdd/stage08-package-b-task-b4-report.md` | 实施报告。 |

不得修改 migration、`Message`/Telegram persistence model、Telegram ingestion/webhook/parser、权限 action 表、Stage08 真源/BDD/计划/合同或生产配置。若实现发现必须改动这些文件，停止并请求独立 schema/API/permission 或 ingestion-retention 确认。

## TDD：先 RED，后最小 GREEN

### RED-1：contract 与 adapter

在 `test_stage08_memory_contracts.py` 先写以下失败测试：

```python
def test_group_candidate_requires_exact_deployed_confidence_floor():
    assert GROUP_MEMORY_CANDIDATE_MIN_CONFIDENCE == Decimal("0.85")
    with pytest.raises(ValueError, match="memory_candidate_confidence_below_threshold"):
        GroupMemoryCandidateProjection(..., confidence=Decimal("0.8499"))

def test_group_candidate_rejects_raw_message_carriers_recursively():
    with pytest.raises(ValueError, match="memory_forbidden_content_key"):
        GroupMemoryCandidateProjection(..., normalized_payload={"decision": {"raw_text": SECRET}})
    with pytest.raises(ValidationError):
        TrustedGroupMessageInput(..., raw_text=SECRET)

def test_adapter_requires_active_chat_user_binding_and_real_group_type():
    assert resolve_authorized_group_message_source(uow, private_or_inactive_input) is None
```

运行：

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py -k "group_candidate or adapter"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

预期：在 DTO/constant/adapter 尚不存在时 collection/import 或 assertion FAIL。

### RED-2：service lifecycle

在 `test_stage08_memory_service.py` 先写：

```python
def test_group_candidate_persists_only_safe_projection_then_accepts_once():
    candidate = create_group_memory_candidate(uow, high_confidence_projection, source=source, actor=owner, now=NOW)
    assert candidate.status == "candidate"
    assert SECRET not in json.dumps(candidate.normalized_payload)
    item = resolve_group_candidate(uow, candidate.id, actor=owner, now=NOW)
    assert item is not None and candidate.status == "accepted" and item.status == "active"

def test_same_message_projection_is_idempotent_and_conflict_never_overwrites_active_fact():
    assert create_group_memory_candidate(uow, projection, source=source, actor=owner, now=NOW).id == create_group_memory_candidate(uow, projection, source=source, actor=owner, now=NOW).id
    assert resolve_group_candidate(uow, conflicting_candidate.id, actor=owner, now=NOW).status == "conflicted"
    assert original_active.payload == original_payload

def test_binding_revocation_or_ttl_makes_group_memory_unreadable_and_marks_lifecycle():
    deactivate_binding_or_expire_item()
    assert read_memory_projection(uow, item.id, actor=owner, now=NOW) is None
    assert item.status in {"revoked", "expired"}

def test_accepted_candidate_revoke_revokes_only_exact_fingerprint_memory():
    result = revoke_memory_candidate(uow, candidate.id, actor=admin, expected_version=2, now=NOW)
    assert result.memory_status == "revoked"
    assert unrelated_item.status == "active"
```

运行：

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_service.py -k "group_candidate or group_memory or accepted_candidate"; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

预期：服务函数/群来源重验未实现前 FAIL。

### RED-3：API

在新 `test_stage08_memory_api.py` 先写：

```python
def test_list_requires_workspace_read_and_never_returns_source_or_raw_fields(client):
    response = client.get(f"/api/stage08/memory?workspace_id={workspace.id}&status=active")
    assert response.status_code == 200
    assert {"scope", "source_refs", "group_chat_ref", "id"}.isdisjoint(response.json()["items"][0])
    assert SECRET not in response.text

def test_foreign_workspace_is_403_and_revoke_requires_member_manage_and_version(client):
    assert client.get(f"/api/stage08/memory?workspace_id={foreign_workspace.id}").status_code == 403
    assert client.post(url, json={"expected_version": 99}).status_code == 409
    assert member_client.post(url, json={"expected_version": 1}).status_code == 403

def test_invalid_input_is_redacted_422(client):
    response = client.post(url, json={"expected_version": "secret-input"})
    assert response.status_code == 422
    assert "secret-input" not in response.text
```

运行：

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_api.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

预期：schema/route 未注册前 FAIL。

### GREEN 与 PostgreSQL 证据

按 RED-1、RED-2、RED-3 顺序实现最小代码，每一组转绿后才继续。最后增加 PostgreSQL 测试：相同 candidate fingerprint 只保留一行；candidate/item lifecycle lock 使用两个独立 session 验证 `FOR UPDATE` 阻塞；accepted candidate revoke 只撤销精确 fingerprint item；binding 失效后 `GET` 返回空项目且 item 不再 active；audit JSON dump 不含 sentinel raw/chat/user fields。

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_memory_api.py tests/integration/test_stage08_memory_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

预期：PASS（PostgreSQL fixture 已配置时）。只在本地真实 PostgreSQL 运行；不把它表述为 staging/production 证据。

额外执行：

```powershell
Push-Location backend; python -m alembic heads; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

预期：仍只有既有 `20260718_0029 (head)`；B4 不得创建 migration。

## 文档冲突处理与验收

- 旧 Package-B plan 的 B4 文件表把 BDD 列为可修改项；当前任务明确“只创建两份 `.superpowers/sdd` 文档，其他文档不改”。不修改 BDD：它已经明确 B-03/B-04/B-05 与 `0.85`，本 brief 只消除 B2 尚未支持群来源的实现细节歧义。
- BDD 的“source deleted/revoked”高于旧服务的笼统 `deleted`。B4 采用 `source missing/corrupt -> deleted`、`binding/member revoked -> revoked`、`TTL -> expired`，读取立即拒绝。
- 旧计划称“candidate first then promote”；本 brief 保留该顺序，并规定 accepted candidate 和关联 Memory 使用同 fingerprint，解决无 FK 情况下撤销对象不明确的问题。

实施验收必须证明：阈值精确为 `0.85`；`0.8499` 不落库；原文 sentinel 不出现在 candidate/Memory/audit/API；私聊、无 binding、inactive binding/member、foreign workspace、非管理者和版本冲突均 fail closed；冲突不覆盖 active item；accepted candidate 撤销只影响精确关联 Memory；没有 Telegram Bot API、Provider/LLM、Redis、外部写入、新 migration 或新权限角色调用。
