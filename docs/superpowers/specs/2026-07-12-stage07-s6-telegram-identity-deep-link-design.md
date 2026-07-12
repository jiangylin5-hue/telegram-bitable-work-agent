# Stage07 S6 Telegram Mini App Identity and Deep-Link Design

## Status

- Status: TD007 Option A approved; companion design is ready for one document-package review. It is not code authority until the implementation plan is reviewed.
- Scope: verified Telegram Mini App request identity, an opaque expiring deep-link pointer and safe Mini App recovery/navigation.
- Product boundary: generic Telegram-first Bitable platform; all results remain workspace/Base/table/view/record/draft resources, not transient chat answers.

## Objective

Make a Telegram Mini App launch capable of becoming an authenticated, permission-filtered platform request and, when a server-issued pointer is present, arriving at one durable resource safely.

```text
Telegram Mini App launch
-> raw official initData in memory
-> backend integrity/freshness validation
-> active Telegram binding -> active workspace member
-> normal resource authorization
-> optional opaque deep-link resolver
-> authorized Base/view/record/draft reread or safe recovery
```

The design deliberately does not deliver a Bot message, publish a Bot, create memory, retrieve knowledge or execute an action. It closes the verified identity/deep-link contract gap before a future controlled delivery or Telegram smoke can be trusted.

## Existing Components Reused

| Existing component | S6 responsibility | Not reused for |
| --- | --- | --- |
| `app.api.deps.get_stage06_request_identity` / `Stage06RequestIdentity` | single request-identity dependency extended with a Telegram source | caller-supplied role or a second authorization engine |
| `Stage06TelegramBinding` / `WorkspaceMember` | maps validated Telegram user to active internal member identity | treating a Telegram profile/chat as a permission |
| `stage06_authorization` and resource ownership resolvers | normal Base/view/record/draft authorization after link lookup | authorizing on link token possession |
| FastAPI + Pydantic + SQLAlchemy 2.x + Alembic + PostgreSQL | closed DTOs, migration, transaction and row ownership | session/auth framework replacement |
| existing Mini App protected cache helpers | exact `401`/recovery removal and authoritative rereads | localStorage, URL or token persistence |
| existing notification/send policy | future controlled test delivery only | automatic send in S6.1 |

## Proposed Boundaries

### In Scope after Implementation-Plan Review

1. Verify Telegram `initData` server-side using the official HMAC data-check-string algorithm and fixed freshness checks.
2. Resolve exactly one internal `user_id` from active `Stage06TelegramBinding` and active `WorkspaceMember` rows, fail closed on none/ambiguous/revoked rows.
3. Add `stage07_telegram_deep_links`: opaque token hash, user-bound source context, one durable destination, status and expiry.
4. Add a server-only mint service and a browser-safe resolver route.
5. Attach raw `initData` only from memory to protected Mini App requests; use the resolver only for a current Telegram launch parameter.
6. Add local, disposable PostgreSQL and client state tests; perform a real non-production Telegram manual smoke only after external user authority/configuration is supplied.

### Explicitly Not in Scope

| Exclusion | Reason |
| --- | --- |
| BotFather/main-app/webhook registration | user-owned external system configuration and a later S6.2 evidence gate |
| sendMessage, inline keyboard, `answerWebAppQuery`, mass/group delivery | external writes are not authorized by this identity/resolver package |
| employee lifecycle/contact publishing, personal assistant/memory, knowledge source | separate Package 4 product contracts |
| generic auth provider, OIDC, JWT issuer, refresh token/cookie store | changes the technical baseline rather than using Telegram's verified launch proof |
| generic redirect/query/link history/search | creates a capability model and sensitive resource discovery outside S6.1 |

## Data Design

### `stage07_telegram_deep_links`

| Field | Type / constraint | Meaning | Exposure rule |
| --- | --- | --- | --- |
| `id` | UUID primary key | internal pointer identity | never in startapp/normal browser model |
| `token_hash` | fixed SHA-256 hex, unique | verifies opaque random token | raw token never persisted, audited or returned |
| `workspace_id` | FK workspace, required | ownership root | returned only after authorization as safe destination context |
| `subject_telegram_user_id` | bounded string, required | verified Telegram user eligible to resolve | never returned to browser |
| `source_telegram_chat_id` | bounded string, required | issuance context/audit evidence | never used as client permission claim or returned |
| `destination_kind` | closed enum | `base`, `view`, `record`, `record_change_draft` | safe destination kind only |
| `destination_id` | UUID, required | durable target pointer | emitted only after ownership/action check |
| `status` | `active` / `revoked` | explicit revocation | no raw status enumeration |
| `expires_at` | UTC timestamp, required | 10-minute resolver lifetime | no raw expiry in browser response |
| `created_by_type`, `created_by_id` | bounded strings | internal issuance audit attribution | no raw actor disclosure |
| timestamps | UTC server defaults | retention/audit chronology | no browser exposure |

`UNIQUE(token_hash)` provides the lookup index. No index is added for chat/user enumeration because S6.1 has no list/search screen. Expired links are treated as unresolved at read time; a cleanup worker is not needed for correctness and is not introduced.

### Identity Inputs

| Input | Trust level | Rule |
| --- | --- | --- |
| `X-Telegram-Init-Data` raw header | untrusted until verified | maximum 8 KiB; never logged; must contain exactly one `hash`, `auth_date`, `user` |
| `initDataUnsafe` / browser user object | untrusted | styling only; never sent as authority or copied to cache |
| `tgWebAppStartParam` URL hint | untrusted | may trigger one resolver call only when it exactly equals validated `initData.start_param` server-side |
| validated `user.id` | verified Telegram identity | maps through active bindings; does not itself become a role |
| `chat_instance` | verified launch metadata but not raw chat ID | cannot be used to locate `telegram_chat_id` bindings or grant scope |

## Server Components and Responsibilities

### Telegram Init Data Validator

`validate_telegram_mini_app_init_data(raw, *, bot_token, now)` is a pure service with no database access. It:

1. parses query pairs without accepting duplicate keys;
2. removes `hash`, alphabetically orders the remaining `key=value` elements and joins them with `\n`;
3. derives Telegram's documented secret key and validates the HMAC using constant-time comparison;
4. validates integer `auth_date` against `now` (+60s future tolerance, 300s maximum age);
5. JSON-parses only the signed `user` value and extracts a string Telegram user ID;
6. exposes a small immutable validated launch object containing only `telegram_user_id`, optional signed `start_param`, optional signed `chat_type`/`chat_instance`, and `auth_date`.

Malformed input, unknown user JSON, duplicate security keys, signature mismatch, future/stale clock and missing Bot token all have stable internal codes. They do not echo raw input.

### Telegram Binding Identity Resolver

`resolve_telegram_request_identity(uow, launch)` loads active `Stage06TelegramBinding` records matching `launch.telegram_user_id`, then requires their linked active members to resolve to exactly one unique internal `user_id`. Multiple bindings are acceptable only if all point to the same active internal user; multiple distinct users are an ambiguity denial. The result is the existing `Stage06RequestIdentity(source='telegram_binding')` and all later routes continue using the existing workspace authorization service.

No S6 route queries by browser-provided workspace/Base/table/view/record IDs before identity is resolved.

### Deep-Link Mint Service

`mint_telegram_deep_link(...)` accepts a server actor and an already-authorized source binding/destination chain. It generates 32 cryptographically random bytes, base64url encodes them for `startapp`, stores only SHA-256, sets 10-minute UTC expiry and records sanitized issuance audit state. It is callable only by backend workflow code; no router or Mini App DTO exposes it.

### Deep-Link Resolver Service

`resolve_telegram_deep_link(...)` receives validated launch, the raw start parameter and current UOW. It first demands exact server-validated `start_param` equality, then finds an active/unexpired hash, validates the subject user and requires an active server binding matching the stored source chat/user and current internal member, resolves the target's workspace ownership and calls existing authorization. Only after all checks succeeds does it return a safe route pointer. Invalid token, revoked token, expiry, subject/source-binding mismatch, deleted target and authorization denial collapse to `recovery`; a valid but expired identity produces `401` before any link lookup.

## Resolver State Model

| State | Trigger | Server result | Client result | Durable mutation |
| --- | --- | --- | --- | --- |
| no-launch | desktop/local/non-Telegram runtime | existing identity path | normal Home; no resolver call | none |
| valid-identity/no-start-param | Telegram app opened normally | normal bootstrap identity | authorized Home | none |
| resolving | validated identity plus nonempty launch parameter | hash lookup and ownership/action checks | labelled loading state, no target preview | none |
| resolved | valid subject, active link, live authorized resource | closed route pointer | reread existing authorized target flow | sanitized resolution audit only if approved by audit policy |
| recovery | invalid/revoked/expired/missing/denied/deleted link | `{outcome:'recovery'}` | fixed safe recovery to Home; exact key removal | sanitized outcome audit only |
| invalid-identity | invalid, stale or missing `initData` in production-like env | `401` stable code | clear all protected state, local recovery message | no raw input persisted |
| binding-denied | validated Telegram user lacks one unambiguous active member | `403` stable code | clear scoped state; no resource UI | sanitized denial audit |

## Client Flow

```text
runtime capability check
-> obtain raw initData in memory only
-> protected bootstrap request with header
-> if start-param hint exists, POST resolver with hint
-> resolved pointer: existing route open + server reread
-> recovery: remove exact link state -> authorized Home
-> 401/403: existing protected-state fail-closed cleanup
```

The fetch wrapper never serializes raw init data into query keys, errors, DOM, telemetry, localStorage, sessionStorage or URLs. It attaches no header in desktop/local mode unless the official Telegram runtime supplies raw `initData`.

## Error Contract

| Condition | HTTP / safe result | Client storage rule |
| --- | --- | --- |
| malformed, forged, stale or missing production `initData` | `401` with stable `telegram_mini_app_identity_invalid` | remove all protected state; do not render detail |
| no/ambiguous/inactive member binding | `403` with stable `telegram_mini_app_binding_denied` | remove current workspace/S6 state; no target fallback |
| missing or invalid start parameter after valid identity | `200 { outcome:'recovery' }` | remove exact deep-link key only |
| expired/revoked/subject-mismatched/deleted/unauthorized pointer | `200 { outcome:'recovery' }` | same recovery path; no target leak |
| resolver network/5xx | fixed local failure plus explicit retry after new bootstrap | do not cache a target or infer success |

## Accessibility and Responsive Requirements

- The resolver emits a text status and fixed Home action; colour/status icons are not the sole indication.
- At 390px and 430px, loading/recovery controls remain one-tap reachable above Telegram safe-area insets.
- The resolved resource is never briefly rendered before its normal authorized re-read succeeds.
- Recovery focus lands on the Workspace Home heading/action; a rejected deep link cannot trap focus in a dead sheet.
- Desktop without Telegram runtime remains a supported existing verified/local identity path and does not render an identity error merely because `window.Telegram` is absent.

## Acceptance Boundary

This design requires: pure validator tests using Telegram-documented signed fixtures; API binding/ambiguity/denial tests; disposable PostgreSQL uniqueness/expiry/revocation/race tests; client parser/cache/route tests; production build; synthetic Browser width review; and a later user-approved real test-bot manual smoke. Passing local tests never proves BotFather configuration, real Telegram identity, staging, production or external delivery.
