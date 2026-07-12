# Stage07 S6 Telegram Mini App Identity and Deep-Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让已验证的 Telegram Mini App 启动证明安全映射到既有 WorkspaceMember，并把服务端签发的短期不透明链接解析为经过当前权限复核的 Base、View、Record 或 Draft 导航指针。

**Architecture:** React 仅在内存读取官方 `window.Telegram.WebApp.initData` 并将它附在受保护请求头；后端以纯标准库验证 Telegram HMAC/时效，再以既有绑定和成员模型解析唯一内部用户。深链接只持久化随机 token 的 SHA-256；每次解析同时重查 token、启动证明、绑定、成员、资源归属和现有授权服务，失败目标一律返回 `recovery`，App 再走既有安全读取。

**Tech Stack:** FastAPI、Pydantic v2、SQLAlchemy 2.x、Alembic、PostgreSQL、Python 标准库、React、TypeScript、TanStack Query、Vitest。

## Global Constraints

- 仅实现 TD007 Option A 和 S6.1；S6.2 Bot 投递、BotFather/Webhook 配置、真实 Telegram 烟测不在代码范围。
- `X-Stage06-User-Id` 仍只允许 local/test；staging/production 只允许验证成功的 Telegram 或既有 verified adapter 身份。
- `X-Telegram-Init-Data` 最大 8 KiB，`hash`、`auth_date`、`user` 各仅一份；认证时间最多 300 秒前、最多 60 秒后。
- 不记录、不返回、不持久化 raw `initData`、Bot token、raw token、profile JSON、消息体、chat title 或错误回显。
- `chat_instance` 不能用于查询 `telegram_chat_id`，不能形成权限。
- token 为至少 256-bit 随机值；仅保存 SHA-256；服务端固定 10 分钟；状态只有 `active`/`revoked`。
- 不新增 mint 浏览器 API、`sendMessage`、`sendData`、`answerWebAppQuery`、JWT/cookie/session、`localStorage`、`sessionStorage`、通用链接搜索/列表/导出接口。
- 未知、过期、撤销、转发、失去绑定、资源消失、未授权均为相同 `200 {"outcome":"recovery"}`；启动证明错误为 401，验证后无唯一有效绑定为 403。
- resolved 仅能输出闭合 ID 指针；客户端必须使用既有授权读取流程，不得以 pointer 直接渲染目标。
- 复用 `Stage06PlatformUnitOfWork`、`stage06_authorization`、Stage06 audit 和 Mini App 缓存清理模式；不引入新认证/权限框架。

---

## Execution Status (2026-07-13)

- Tasks 1–5 are implemented locally in commits `6826df8`, `a13e39d` and `ff7b89e`: launch validation, binding identity, migration/hash lookup, safe resolver and Mini App handoff are present.
- Task 6 local evidence is partly complete: focused backend `52 passed`, disposable PostgreSQL `3 passed`, synthetic 4,096-row unique-index plan (`0.045 ms`, `shared hit=3`), focused Mini App `6 files / 38 tests`, production build and a synthetic safe-DTO Browser recovery/Record matrix at 1440/1280/430/390. The fixture was deleted and its port closed. A second local PostgreSQL session cannot revoke an active pointer while the Resolver has acquired its `FOR UPDATE` lock; a third proves the persisted audit has only fixed outcome/kind/durable-ID metadata; zero-lookup/no-send inventory plus cross-workspace/field-policy projection regressions are also covered.
- The remaining plan items are acceptance gaps, not unimplemented scope: exhaustive App failure/supersession permutations and S6.2 external authority. Cross-workspace recovery and field-policy projection were reconciled against the current Stage07 API data-security contract: a field-policy change filters the later authoritative read; a workspace/resource action failure recovers. No delivery/configuration code is permitted until separately authorized.

## File Structure

| File | Responsibility |
| --- | --- |
| `backend/app/services/stage07_telegram_mini_app_identity.py` | 纯 initData 校验、稳定错误码、最小 launch DTO、绑定身份解析。 |
| `backend/app/api/deps.py` | 将 Telegram launch 接入既有 request identity，并复用单个 UoW/session。 |
| `backend/app/models/stage07_telegram.py` | 不透明链接的一张窄表和检查约束。 |
| `backend/app/services/stage07_telegram_deep_links.py` | server-only mint、解析、权限/归属复核、safe pointer。 |
| `backend/app/schemas/stage07_telegram.py` | 仅允许 `start_param` 与 closed response 的 DTO。 |
| `backend/app/api/routes/stage07_telegram.py` | 唯一公开 resolver endpoint，没有 mint endpoint。 |
| `backend/alembic/versions/20260712_0025_stage07_telegram_mini_app_deep_links.py` | 从 0024 到该窄表的迁移。 |
| `mini-app/src/app/telegram-mini-app.ts` | 隔离 Telegram runtime；只向内存暴露 raw launch。 |
| `mini-app/src/app/api.ts`、`protectedQuery.ts`、`App.tsx` | 内存 header、resolver、精确清理、权威重读和 recovery。 |
| `backend/tests/unit/test_stage07_telegram_mini_app_identity.py` | HMAC/时钟/重复参数/绑定矩阵。 |
| `backend/tests/unit/test_stage07_telegram_deep_link_api.py` | resolver 等价 recovery、safe DTO、无公开 mint。 |
| `backend/tests/integration/test_stage07_telegram_deep_link_postgres.py` | disposable PostgreSQL 迁移、unique hash、撤销、过期和权限复核。 |
| `mini-app/src/test/telegram-mini-app.test.ts`、`telegram-deep-link-app-flow.test.tsx` | 无持久化、header、handoff、recovery、401 与代际竞争。 |

## Task 1: Validate the official Telegram launch proof

**Files:**
- Create: `backend/app/services/stage07_telegram_mini_app_identity.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/unit/test_stage07_telegram_mini_app_identity.py`

**Interfaces:**
- Produces `ValidatedTelegramMiniAppLaunch(telegram_user_id: str, auth_date: datetime, start_param: str | None, chat_type: str | None, chat_instance: str | None)`.
- Produces `validate_telegram_mini_app_init_data(raw: str, *, bot_token: str | None, now: datetime, max_age_seconds: int) -> ValidatedTelegramMiniAppLaunch`.
- Produces `Stage07TelegramMiniAppIdentityError(code: str)` whose allowed codes are `telegram_init_data_required`, `telegram_init_data_too_large`, `telegram_init_data_duplicate_key`, `telegram_init_data_malformed`, `telegram_init_data_bot_token_unavailable`, `telegram_init_data_signature_invalid`, `telegram_init_data_auth_date_invalid`, `telegram_init_data_auth_date_stale`, `telegram_init_data_auth_date_future`, `telegram_init_data_user_invalid`.

- [ ] **Step 1: Write the failing valid-vector and rejection tests**

```python
def signed_init_data(fields: dict[str, str], bot_token: str) -> str:
    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    signed = {**fields, "hash": hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()}
    return urlencode(signed)

def test_validates_minimal_signed_launch_fields() -> None:
    raw = signed_init_data({"auth_date": "1720000000", "user": '{"id":123}', "start_param": "opaqueToken_123"}, "test-token")
    launch = validate_telegram_mini_app_init_data(raw, bot_token="test-token", now=datetime.fromtimestamp(1720000030, UTC), max_age_seconds=300)
    assert launch.telegram_user_id == "123"
    assert launch.start_param == "opaqueToken_123"

@pytest.mark.parametrize("raw,code", [("auth_date=1&auth_date=2", "telegram_init_data_duplicate_key"), ("auth_date=bad", "telegram_init_data_malformed")])
def test_rejects_ambiguous_or_malformed_pairs(raw: str, code: str) -> None:
    with pytest.raises(Stage07TelegramMiniAppIdentityError, match=code):
        validate_telegram_mini_app_init_data(raw, bot_token="test-token", now=NOW, max_age_seconds=300)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend; pytest tests/unit/test_stage07_telegram_mini_app_identity.py -q`

Expected: FAIL because the validator module does not exist.

- [ ] **Step 3: Implement strict standard-library parsing and HMAC**

```python
def validate_telegram_mini_app_init_data(raw: str, *, bot_token: str | None, now: datetime, max_age_seconds: int) -> ValidatedTelegramMiniAppLaunch:
    if not raw:
        raise Stage07TelegramMiniAppIdentityError("telegram_init_data_required")
    if len(raw.encode("utf-8")) > 8192:
        raise Stage07TelegramMiniAppIdentityError("telegram_init_data_too_large")
    pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
    values: dict[str, str] = {}
    for key, value in pairs:
        if key in values:
            raise Stage07TelegramMiniAppIdentityError("telegram_init_data_duplicate_key")
        values[key] = value
    supplied_hash = values.pop("hash", None)
    if not supplied_hash or not bot_token:
        raise Stage07TelegramMiniAppIdentityError("telegram_init_data_signature_invalid" if supplied_hash is None else "telegram_init_data_bot_token_unavailable")
    secret = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected = hmac.new(secret, "\n".join(f"{key}={values[key]}" for key in sorted(values)).encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied_hash):
        raise Stage07TelegramMiniAppIdentityError("telegram_init_data_signature_invalid")
    # Parse only signed auth_date/user and return only the five DTO fields.
```

Convert `parse_qsl` errors to `telegram_init_data_malformed`; require nonblank `auth_date` and `user`; parse signed user JSON and `user.id`; use UTC clock boundaries. Extend `Settings` with `telegram_mini_app_init_max_age_seconds: int = 300`, parse `TELEGRAM_MINI_APP_INIT_MAX_AGE_SECONDS`, and reject values outside `1..900` in `validate_runtime_settings`. Do not require a Bot token when no Telegram header is present.

- [ ] **Step 4: Prove boundary and secrecy cases**

Add tests for tampered signed values, missing hash/token, `now-300` accepted, `now-301` stale, `now+60` accepted, `now+61` future, raw >8 KiB, invalid JSON/missing `user.id`, and no raw input/token in `str(error)`.

Run: `cd backend; pytest tests/unit/test_stage07_telegram_mini_app_identity.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/config.py backend/app/services/stage07_telegram_mini_app_identity.py backend/tests/unit/test_stage07_telegram_mini_app_identity.py
git commit -m "feat(stage07): validate telegram mini app launch proof"
```

## Task 2: Resolve validated proof into the existing request identity

**Files:**
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/services/stage06_identity.py`
- Modify: `backend/app/api/routes/stage06_platform.py`
- Modify: `backend/app/services/stage06_platform.py`
- Test: `backend/tests/unit/test_stage07_telegram_mini_app_identity.py`

**Interfaces:**
- Consumes Task 1 and existing `Stage06TelegramBinding`/`WorkspaceMember`.
- Produces `resolve_telegram_request_identity(uow, launch) -> Stage06RequestIdentity` with source `telegram_binding`.
- Produces `get_stage06_identity_uow(session=Depends(get_session)) -> Stage06PlatformUnitOfWork`; the route and identity share this session.

- [ ] **Step 1: Write failing binding and dependency tests**

```python
def test_binding_resolver_allows_same_user_multi_binding(uow, launch) -> None:
    seed_active_bindings_for_same_user(uow, telegram_user_id="123", user_id="member-1")
    assert resolve_telegram_request_identity(uow, launch) == Stage06RequestIdentity("member-1", "telegram_binding", "123")

@pytest.mark.parametrize("seed,code", [(seed_no_binding, "telegram_binding_not_found"), (seed_inactive_member, "telegram_binding_member_inactive"), (seed_two_users, "telegram_binding_ambiguous")])
def test_binding_resolver_fails_closed(seed, code) -> None:
    with pytest.raises(Stage06IdentityError, match=code):
        resolve_telegram_request_identity(seed(), LAUNCH)

def test_valid_proof_without_binding_is_403(client) -> None:
    assert client.get("/mini-app/bootstrap", headers={"X-Telegram-Init-Data": VALID_INIT_DATA}).status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend; pytest tests/unit/test_stage07_telegram_mini_app_identity.py -q`

Expected: FAIL because this source precedence does not exist.

- [ ] **Step 3: Implement single-session, fail-closed source precedence**

```python
def resolve_telegram_request_identity(uow: Stage06PlatformUnitOfWork, launch: ValidatedTelegramMiniAppLaunch) -> Stage06RequestIdentity:
    user_ids = {
        member.user_id
        for binding in uow.list_telegram_bindings()
        if binding.status == "active" and binding.telegram_user_id == launch.telegram_user_id
        for member in [uow.get_workspace_member(binding.workspace_member_id)]
        if member is not None and member.status == "active"
    }
    if len(user_ids) != 1:
        raise Stage06IdentityError("telegram_binding_not_found" if not user_ids else "telegram_binding_ambiguous", status_code=403)
    return Stage06RequestIdentity(user_id=user_ids.pop(), source="telegram_binding", telegram_user_id=launch.telegram_user_id)
```

`Stage06IdentityError` gets `status_code` default 401. A present Telegram header is verified first; a valid launch uses the resolver; absent header retains existing verified/development logic. The code must not read `chat_instance`, role, `default_base_id`, or a caller workspace. Keep `get_stage06_platform_uow` as the same request-session factory/delegation, not a second connection.

- [ ] **Step 4: Run source-precedence regressions**

Run: `cd backend; pytest tests/unit/test_stage06_identity.py tests/unit/test_stage07_telegram_mini_app_identity.py tests/unit/test_stage07_mini_app_api.py -q`

Expected: PASS; production without proof remains 401, one active binding is 200, and an invalid present Telegram header cannot fall back to a development header.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/deps.py backend/app/api/routes/stage06_platform.py backend/app/services/stage06_identity.py backend/app/services/stage06_platform.py backend/tests/unit/test_stage07_telegram_mini_app_identity.py
git commit -m "feat(stage07): map verified telegram launches to members"
```

## Task 3: Persist only opaque expiring pointers

**Files:**
- Create: `backend/app/models/stage07_telegram.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/services/stage06_platform.py`
- Create: `backend/alembic/versions/20260712_0025_stage07_telegram_mini_app_deep_links.py`
- Test: `backend/tests/unit/test_stage07_telegram_deep_link_api.py`
- Test: `backend/tests/integration/test_stage07_telegram_deep_link_postgres.py`

**Interfaces:**
- Produces `Stage07TelegramDeepLink` with token hash, workspace/subject/source context, closed kind/ID, status, expiry, issuer and timestamps.
- Adds `add_telegram_deep_link(link)` and `get_active_telegram_deep_link_by_token_hash(token_hash, now)` to every UoW implementation.

- [ ] **Step 1: Write failing model/migration/UoW tests**

```python
def test_deep_link_has_closed_constraints() -> None:
    names = {item.name for item in Stage07TelegramDeepLink.__table__.constraints}
    assert {"uq_stage07_telegram_deep_links_token_hash", "ck_stage07_telegram_deep_links_kind", "ck_stage07_telegram_deep_links_status"} <= names

def test_lookup_returns_only_active_unexpired_hash(uow, now) -> None:
    uow.add_telegram_deep_link(active_link(token_hash="a" * 64, expires_at=now + timedelta(minutes=1)))
    uow.add_telegram_deep_link(revoked_link(token_hash="b" * 64, expires_at=now + timedelta(minutes=1)))
    assert uow.get_active_telegram_deep_link_by_token_hash("a" * 64, now).token_hash == "a" * 64
    assert uow.get_active_telegram_deep_link_by_token_hash("b" * 64, now) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend; pytest tests/unit/test_stage07_telegram_deep_link_api.py -q`

Expected: FAIL because the model/UoW/migration are absent.

- [ ] **Step 3: Implement the one-table physical design**

```python
class Stage07TelegramDeepLink(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stage07_telegram_deep_links"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_stage07_telegram_deep_links_token_hash"),
        CheckConstraint("destination_kind IN ('base', 'view', 'record', 'record_change_draft')", name="ck_stage07_telegram_deep_links_kind"),
        CheckConstraint("status IN ('active', 'revoked')", name="ck_stage07_telegram_deep_links_status"),
    )
```

Use `String(64)` hash, `String(120)` user/chat/issuer IDs, `String(40)` kind/status/type and non-null `Uuid(as_uuid=True)` workspace FK/destination ID/expiry. Migration has `revision = "20260712_0025"`, `down_revision = "20260712_0024"`; its upgrade creates only this table, downgrade drops only this table. The SQLAlchemy query is `token_hash == value`, `status == "active"`, `expires_at > now`; add no raw token, JSON target, history or chat/user index.

- [ ] **Step 4: Run UoW and PostgreSQL proof**

Run: `cd backend; pytest tests/unit/test_stage07_telegram_deep_link_api.py tests/integration/test_stage07_telegram_deep_link_postgres.py -q`

Expected: PASS; migration reaches head, duplicate hash fails, inactive/expired row is invisible.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/__init__.py backend/app/models/stage07_telegram.py backend/app/services/stage06_platform.py backend/alembic/versions/20260712_0025_stage07_telegram_mini_app_deep_links.py backend/tests/unit/test_stage07_telegram_deep_link_api.py backend/tests/integration/test_stage07_telegram_deep_link_postgres.py
git commit -m "feat(stage07): persist opaque telegram deep links"
```

## Task 4: Add server-only mint and non-enumerable resolver

**Files:**
- Create: `backend/app/services/stage07_telegram_deep_links.py`
- Create: `backend/app/schemas/stage07_telegram.py`
- Create: `backend/app/api/routes/stage07_telegram.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/unit/test_stage07_telegram_deep_link_api.py`
- Test: `backend/tests/integration/test_stage07_telegram_deep_link_postgres.py`

**Interfaces:**
- Produces `TelegramDeepLinkDestinationInput`, `MintedTelegramDeepLink`, `mint_telegram_deep_link(...)`, and `resolve_telegram_deep_link(...) -> SafeTelegramDeepLinkDestination | None`.
- Exposes only `POST /mini-app/telegram/deep-links/resolve` with `extra="forbid"`, `start_param` 16..128 characters and `^[A-Za-z0-9_-]+$`.

- [ ] **Step 1: Write failing equivalence and safe-output tests**

```python
@pytest.mark.parametrize("token", ["unknown_token_123456", "revoked_token_123456", "expired_token_123456", "other_subject_123456"])
def test_all_non_resolved_links_are_same_recovery(client, token) -> None:
    response = client.post(RESOLVE_URL, json={"start_param": token}, headers=valid_headers(token))
    assert response.status_code == 200
    assert response.json() == {"outcome": "recovery"}

def test_resolver_returns_pointer_without_labels_or_values(client, seeded_link) -> None:
    body = client.post(RESOLVE_URL, json={"start_param": seeded_link.raw_token}, headers=valid_headers(seeded_link.raw_token)).json()
    assert body["destination"] == {"kind": "record", "workspace_id": str(WORKSPACE_ID), "base_id": str(BASE_ID), "table_id": str(TABLE_ID), "record_id": str(RECORD_ID), "view_id": None, "draft_id": None}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend; pytest tests/unit/test_stage07_telegram_deep_link_api.py -q`

Expected: FAIL because no route/service exists.

- [ ] **Step 3: Implement mint, reread authorization, and closed recovery**

```python
def resolve_telegram_deep_link(uow, *, identity, launch, start_param, now):
    if start_param != launch.start_param:
        return None
    link = uow.get_active_telegram_deep_link_by_token_hash(_hash_token(start_param), now)
    if link is None or link.subject_telegram_user_id != launch.telegram_user_id:
        return None
    if not _has_current_source_binding(uow, link, identity.user_id):
        return None
    return _authorize_and_build_destination_or_none(uow, link, identity)
```

Mint uses `secrets.token_urlsafe(32)`, SHA-256 and `now + timedelta(minutes=10)`; validates the trusted actor's durable destination chain before inserting; returns raw token only to its in-process caller; records sanitized actor/kind/durable ID/expiry metadata, never raw token. Resolver rechecks Base (`base.read`), View (`record.read` plus `get_view_presentation`), Record (`record.read` plus `read_record_for_actor`), and Draft (`record_change_draft.read` plus Base/Table/Record chain). Catch expected missing/authorization/validation failures and return `None`; response model turns only `None` into recovery. No route serializes minted tokens.

- [ ] **Step 4: Prove boundary and stale authorization**

Add tests for body/signed-start mismatch, invalid proof 401, no binding 403, malformed body 422, Base/View/Record/Draft success, deleted target, removed member, revoked binding, changed role, and no OpenAPI route able to mint. Test response JSON equality across recovery causes and assert no token/profile/label/record value/draft value in output.

Run: `cd backend; pytest tests/unit/test_stage07_telegram_deep_link_api.py tests/integration/test_stage07_telegram_deep_link_postgres.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/stage07_telegram_deep_links.py backend/app/schemas/stage07_telegram.py backend/app/api/routes/stage07_telegram.py backend/app/main.py backend/tests/unit/test_stage07_telegram_deep_link_api.py backend/tests/integration/test_stage07_telegram_deep_link_postgres.py
git commit -m "feat(stage07): resolve authorized telegram deep links"
```

## Task 5: Implement in-memory Mini App transport and authoritative handoff

**Files:**
- Create: `mini-app/src/app/telegram-mini-app.ts`
- Modify: `mini-app/src/app/api.ts`
- Modify: `mini-app/src/app/protectedQuery.ts`
- Modify: `mini-app/src/app/App.tsx`
- Test: `mini-app/src/test/telegram-mini-app.test.ts`
- Test: `mini-app/src/test/telegram-deep-link-app-flow.test.tsx`

**Interfaces:**
- Produces `readTelegramMiniAppLaunch(): { initData: string; startParam: string | null } | null`, `api.setTelegramInitData`, `api.resolveTelegramDeepLink`, and `clearTelegramDeepLinkQueries`.

- [ ] **Step 1: Write failing client transport and handoff tests**

```tsx
it('does not persist or trust runtime profile data', () => {
  window.Telegram = { WebApp: { initData: 'raw-signed-data', initDataUnsafe: { start_param: 'opaqueToken_123', user: { id: 123 } } } } as never
  expect(readTelegramMiniAppLaunch()).toEqual({ initData: 'raw-signed-data', startParam: 'opaqueToken_123' })
  expect(localStorage.getItem('telegram-init-data')).toBeNull()
})

it('re-reads a resolved record rather than rendering pointer content', async () => {
  mockResolve({ outcome: 'resolved', destination: recordPointer })
  render(<App />)
  await waitFor(() => expect(mockApi.readRecord).toHaveBeenCalledWith(recordPointer.record_id, expect.anything()))
  expect(screen.queryByText('secret record label')).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mini-app; npm test -- --run src/test/telegram-mini-app.test.ts src/test/telegram-deep-link-app-flow.test.tsx`

Expected: FAIL because adapter/resolver/handoff do not exist.

- [ ] **Step 3: Implement memory-only runtime/header behavior**

```ts
let telegramInitData: string | null = null
export function setTelegramInitData(value: string | null): void { telegramInitData = value?.trim() || null }
function protectedHeaders(headers?: HeadersInit): Headers {
  const merged = new Headers(headers)
  if (telegramInitData) merged.set('X-Telegram-Init-Data', telegramInitData)
  return merged
}
export function readTelegramMiniAppLaunch(): TelegramMiniAppLaunch | null {
  const webApp = window.Telegram?.WebApp
  const initData = webApp?.initData?.trim()
  return initData ? { initData, startParam: typeof webApp.initDataUnsafe?.start_param === 'string' ? webApp.initDataUnsafe.start_param : null } : null
}
```

Declare only the minimal runtime shape. Attach headers to every protected request, including bootstrap. Resolver posts `{ start_param }` and parses only the two documented outcomes. Query keys and errors never contain raw launch/token.

- [ ] **Step 4: Wire one launch generation into App**

After bootstrap and before default Home navigation, read current launch once, set its in-memory header, increment `telegramLaunchRequestVersion`, and resolve at most once. Base/View invoke `openBase`; Record invokes `openBase` then existing `openRecord`; Draft invokes existing safe draft read/hub without a fabricated focus trigger. Recovery, target 404/409/422 or stale generation removes only S6/current workspace keys and shows a fixed Chinese Home recovery action (44px target, accessible name and focus). 401 uses `denyInvalidSession`; 403 clears current workspace and shows existing denied state. Workspace replacement/unmount increments generation before late result writes state.

- [ ] **Step 5: Verify client cases and build**

Add no-runtime desktop fallback, blank-initData no-resolver, 401 reset, 403 clear, recovery focus, late workspace-switch result ignored, and source inventory tests for absent `sendData`/`answerWebAppQuery`/storage.

Run: `cd mini-app; npm test -- --run src/test/telegram-mini-app.test.ts src/test/telegram-deep-link-app-flow.test.tsx src/test/protected-query-state.test.ts`

Expected: PASS.

Run: `cd mini-app; npm run build`

Expected: PASS without TypeScript errors.

- [ ] **Step 6: Commit**

```bash
git add mini-app/src/app/telegram-mini-app.ts mini-app/src/app/api.ts mini-app/src/app/protectedQuery.ts mini-app/src/app/App.tsx mini-app/src/test/telegram-mini-app.test.ts mini-app/src/test/telegram-deep-link-app-flow.test.tsx
git commit -m "feat(stage07): hand off verified telegram deep links"
```

## Task 6: Integrate, measure only the approved lookup, and record evidence

**Files:**
- Modify: `project-docs/08-implementation/STAGE_07_S6_TELEGRAM_IDENTITY_DEEP_LINK_BDD_AND_ACCEPTANCE.md`
- Modify: `project-docs/08-implementation/STAGE_07_PROGRESS.md`
- Modify: `project-docs/08-implementation/STAGE_07_TRACEABILITY_AUDIT.md`
- Modify: `project-docs/08-implementation/STAGE_07_SOURCE_OF_TRUTH.md`

**Interfaces:**
- Produces sanitized local/disposable PostgreSQL/client evidence only; it does not produce Telegram delivery evidence.

- [ ] **Step 1: Run focused S6 backend matrix**

Run: `cd backend; pytest tests/unit/test_stage06_identity.py tests/unit/test_stage07_mini_app_api.py tests/unit/test_stage07_telegram_mini_app_identity.py tests/unit/test_stage07_telegram_deep_link_api.py tests/integration/test_stage07_telegram_deep_link_postgres.py -q`

Expected: PASS; record exact output/test count without credentials/raw inputs.

- [ ] **Step 2: Run migration and measure only if planner behavior is unclear**

Run: `cd backend; alembic upgrade head`

Expected: head `20260712_0025`.

With disposable PostgreSQL and synthetic hash values, run `EXPLAIN (ANALYZE, BUFFERS)` on `token_hash = :hash AND status = 'active' AND expires_at > now()`. Record use of the unique hash path. Do not add a partial/compound index unless evidence shows an issue and a new user-approved decision exists.

- [ ] **Step 3: Run frontend regression and build**

Run: `cd mini-app; npm test -- --run src/test/telegram-mini-app.test.ts src/test/telegram-deep-link-app-flow.test.tsx src/test/draft-employee-app-flow.test.tsx src/test/app-shell.test.tsx`

Expected: PASS.

Run: `cd mini-app; npm run build`

Expected: PASS.

- [ ] **Step 4: Bounded UI self-check**

Run a local synthetic fixture only if the app browser reaches loopback; inspect 1440, 1280, 430 and 390 widths plus safe-area/no-runtime fallback. Check loading/recovery copy, Home focus, no raw token/profile, Base/View/Record/Draft reread, and workspace-switch cancellation. If loopback is unreachable, record this limitation and do not claim Browser acceptance; stop fixture/remove generated data.

- [ ] **Step 5: Update evidence and commit**

Mark S6-A01 through S6-A09 only with observed evidence. Keep S6-A10 `external-authority-required` until the user separately authorizes a non-production bot/test chat configuration. Record Current Progress, changed files, skipped tests, risks and temporary cleanup.

```bash
git add project-docs/08-implementation/STAGE_07_S6_TELEGRAM_IDENTITY_DEEP_LINK_BDD_AND_ACCEPTANCE.md project-docs/08-implementation/STAGE_07_PROGRESS.md project-docs/08-implementation/STAGE_07_TRACEABILITY_AUDIT.md project-docs/08-implementation/STAGE_07_SOURCE_OF_TRUTH.md
git commit -m "docs(stage07): record s6 identity resolver evidence"
```

## Coverage and Acceptance Map

| Requirement | Tasks | Evidence |
| --- | --- | --- |
| TG-I01–TG-I03: HMAC, clock, redaction | 1–2 | signed fixtures, 401 contract, source/response negative checks |
| TG-I04–TG-I05: unique active binding, no chat confusion | 2, 4 | binding matrix and direct-link tests |
| TG-I06–TG-I10: opaque lifecycle/non-enumeration | 3, 4, 6 | migration/UoW/API/PostgreSQL recovery equivalence |
| TG-I11: stale client state | 5, 6 | launch-generation/workspace-switch tests |
| TG-I12: external-action leak | 4–6 | route/client inventory and no-send tests |
| S6-A01–S6-A09 | 1–6 | commands/build/optional browser evidence |
| S6-A10 | outside implementation | stays `external-authority-required`; no Telegram configuration/send |

## Out of Scope Enforcement

本计划不增加 BotFather 设置、Mini App URL、webhook 注册、Telegram 消息、inline keyboard、通知 UI、通用聊天、memory、knowledge、employee lifecycle、provider execution、OIDC、JWT、cookie、持久浏览器会话、raw token 列表/搜索/历史或 staging/production 发布。任何此类工作必须新建经用户批准的 Stage07 包。
