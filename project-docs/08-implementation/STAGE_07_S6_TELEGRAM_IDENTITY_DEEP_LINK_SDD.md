# Stage07 S6 Telegram Mini App Identity and Deep-Link SDD

## Status

- Status: TD007 Option A is `partial-local` implementation. Backend validation/identity/storage/resolver and Mini App memory/handoff code exist; external delivery and unaccepted evidence remain outside this SDD's implemented boundary.
- Scope: server identity adaptation and opaque destination resolution for Telegram Mini App launches.
- Current Progress: S6.1 route, schema/migration, frontend header and local synthetic validation exist. A disposable safe-DTO Browser fixture observed recovery and Record handoff at 1440/1280/430/390, including the 44px recovery action and raw-token absence. The local resolver matrix now proves cross-workspace recovery and the existing field-read rule: hiding a field after issuance retains only a closed record pointer and the authoritative reread omits the field. No Telegram configuration, external message or real Telegram identity test exists; exhaustive failure/supersession and external evidence remain unaccepted.

## Architecture

```text
React App runtime adapter
  -> optional raw Telegram initData in memory
  -> existing protected transport
  -> Stage06 request identity dependency
      -> initData validator
      -> active binding/member identity resolver
      -> normal Stage06 resource authorization
  -> optional safe deep-link resolver
      -> token hash lookup
      -> subject/expiry/status checks
      -> resource ownership/action authorization
      -> closed destination pointer or recovery
  -> App authoritative target reread
```

The validator is pure and dependency-free (`urllib.parse`, `hmac`, `hashlib`, `json`, `datetime`). The binding resolver, link resolver and mint service use the current SQLAlchemy Unit of Work and existing authorization service. No authentication framework, JWT library, session store, Telegram SDK or client persistence is introduced.

## Interfaces

### Validated Launch

```py
@dataclass(frozen=True)
class ValidatedTelegramMiniAppLaunch:
    telegram_user_id: str
    auth_date: datetime
    start_param: str | None
    chat_type: str | None
    chat_instance: str | None
```

The object intentionally omits profile name, username, photo URL, query ID, raw query string, hash and Bot token.

### Request Identity Precedence

| Environment / input | Result |
| --- | --- |
| `local` / `test`, verified Telegram header present and valid | Telegram binding identity wins; header is still never a role |
| `local` / `test`, no Telegram header, development header valid | existing `development_header` identity |
| any environment, configured non-Telegram verified adapter yields user | existing `verified_adapter` identity |
| `staging` / `production`, valid Telegram header + one binding user | `telegram_binding` identity |
| `staging` / `production`, missing/invalid Telegram proof and no verified adapter | `401` |
| any environment, valid Telegram proof but zero/inactive/ambiguous binding | `403` |

The concrete dependency must use one request-scoped database session; it must not open a second independent connection or use route-level `get_system_actor`. Existing tests may continue to override the public request-identity dependency.

### Resolver Request and Response

```py
class TelegramDeepLinkResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_param: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")

class SafeTelegramDeepLinkDestination(BaseModel):
    kind: Literal["base", "view", "record", "record_change_draft"]
    workspace_id: str
    base_id: str | None = None
    table_id: str | None = None
    view_id: str | None = None
    record_id: str | None = None
    draft_id: str | None = None

class TelegramDeepLinkResolveResponse(BaseModel):
    outcome: Literal["resolved", "recovery"]
    destination: SafeTelegramDeepLinkDestination | None = None
```

`destination` is required only for `resolved`; its field combination is server-created from one durable resource chain. The browser cannot select `kind`, resource IDs, a workspace or a fallback target.

### Internal Mint Interface

```py
def mint_telegram_deep_link(
    uow: Stage06PlatformUnitOfWork,
    *,
    actor: Actor,
    subject_telegram_user_id: str,
    source_telegram_chat_id: str,
    destination: TelegramDeepLinkDestinationInput,
    expires_at: datetime,
) -> MintedTelegramDeepLink:
    ...
```

This service performs ownership/action validation before persistence and returns the raw token only to the caller in memory. The route layer never serializes `MintedTelegramDeepLink` to a browser. It must have a caller-owned transaction so a future trusted webhook/delivery workflow can atomically write its own event/audit evidence.

## Database and Migration Rules

1. Add `stage07_telegram_deep_links` with the columns in TD007 and a unique `token_hash` constraint.
2. Make `workspace_id`, user/chat context, destination kind/ID, status and expiry non-null; use server UTC timestamps.
3. Add check constraints for the closed `status` and `destination_kind` values.
4. Do not add a raw-token column, link URL column, JSON target blob, message body, provider data, role or permission snapshot.
5. Do not add a list route or a generic status/chat/user index. `UNIQUE(token_hash)` is the physical path for the single approved lookup.
6. Migration downgrade drops only the S6.1 table/constraints/index; it does not alter existing `Stage06TelegramBinding`, digital employee, notification or audit data.

## Resolution Algorithm

```text
1. identity dependency validates raw initData and resolves active internal member user.
2. route accepts only a syntactically bounded opaque start_param.
3. service requires start_param == validated launch.start_param.
4. hash parameter; SELECT one active/unexpired row by unique token_hash.
5. require row.subject_telegram_user_id == validated launch.telegram_user_id and an active stored source-chat/user binding whose member resolves to the current identity user.
6. resolve destination kind/id to current workspace/Base/table/view/record/draft chain.
7. require row.workspace_id matches that chain and call existing action authorization.
8. resolved -> construct closed pointer; every other link/target condition -> recovery.
9. commit sanitized outcome audit only when current audit policy permits it.
```

The query must not prefetch resource labels or values before link/membership checks. It must not return a different HTTP status or error body for unknown versus expired/revoked/unauthorized pointers. Resolver audit state contains outcome category and durable IDs only after successful authorization; it never includes raw token, init data, profile JSON, chat title or message body.

## Authorization Mapping

| Destination kind | Ownership chain | Required existing authorization before result |
| --- | --- | --- |
| `base` | Base -> workspace | `base.read` |
| `view` | View -> table -> Base -> workspace | `record.read` plus current view visibility |
| `record` | Record -> table -> Base -> workspace | `record.read` |
| `record_change_draft` | Draft -> record/table -> Base -> workspace | `record_change_draft.read`; detail later rechecks field filtering |

The resolver does not bypass field filtering. A `record` pointer never returns record values; a `draft` pointer never returns before/proposed values. A changed field-read policy does not itself deny a still-readable record: the normal destination screen performs its own safe read after navigation and omits newly hidden field keys. A changed workspace/resource read action, resource ownership chain or binding/member state instead returns recovery.

## Client State and Failure Rules

| Event | Required client behavior | Prohibited behavior |
| --- | --- | --- |
| Telegram runtime absent | use existing desktop/local identity transport | fake Telegram user, missing-header error, URL fallback |
| runtime present / initData empty | do not call resolver; normal existing identity path decides | use `initDataUnsafe` or URL user data |
| verified start parameter | one resolver request scoped by current launch generation | store raw token/initData, retry after context change |
| resolved pointer | invoke current authorized open function then reread target | render a target from IDs alone |
| recovery | remove exact resolver/target keys, show fixed Home recovery | reveal existence/reason or retain old target |
| `401` | complete existing protected-state reset | cache header/error/previous workspace |
| `403` | remove S6/current workspace scope | choose another binding/default Base |
| `404`/`409`/`422` after target reread | exact target removal and fixed recovery/retry | automatic retry or optimistic success |
| request cancellation / workspace replacement | increment launch generation and discard response | reopen prior workspace/resource |

## Accessibility and Visual Contract

- Use the existing white/cool-gray/azure Mini App system; no new Telegram-branded dashboard, QR/scan surface or data-rich security screen.
- Loading/recovery is part of App shell, not a modal containing raw launch metadata.
- Recovery action has a visible label, 44px target minimum, accessible name and focus destination.
- Test 1440, 1280, 430 and 390 widths, including Telegram safe-area CSS variables when available and a no-runtime fallback when unavailable.

## Out-of-Scope Enforcement

Route inventory must contain only the safe resolver addition; `mint_telegram_deep_link` has no public route. Client inventory must contain no `sendData`, `answerWebAppQuery`, `openTelegramLink`, `localStorage`, `sessionStorage`, raw Telegram profile render or direct Bot API call. No change may add a general Telegram message command or expand external notification permissions.
