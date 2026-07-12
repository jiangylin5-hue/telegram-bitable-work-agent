# Stage07 Technical Decision 007: Telegram Mini App Identity and Deep-Link Resolution

## Status

- Decision status: approved Option A on 2026-07-12 for S6.1 documentation and implementation planning. It authorizes no code until the complete document package and implementation plan are reviewed; it never authorizes external Telegram configuration, BotFather change, webhook registration, message delivery or production test by itself.
- Scope: S6's verified Telegram Mini App identity path and a safe, durable deep-link resolver over existing workspace resources.
- Authority: current user instruction, `AGENTS.md`, Stage07 source of truth, Stage06 identity/security contract, TD005/TD006 boundaries and the product constitution.

## Decision Required

S5 deliberately remains a local, header-identity Mini App slice. The project already has Telegram webhook parsing, source allowlists, message idempotency, `Stage06TelegramBinding` and a table-bound digital-employee mention service. It does **not** yet validate Telegram Mini App `initData`, resolve Mini App requests to a bound workspace member, or safely turn a Telegram `startapp` parameter into an authorized platform destination.

This cannot be solved by a frontend parameter parser:

```text
untrusted browser URL / initDataUnsafe
-> official server-side initData verification
-> active Telegram binding(s)
-> one unambiguous workspace member user_id
-> normal Stage06 authorization for every resource
-> bounded deep-link destination or safe recovery
```

Telegram's official Mini App documentation requires the backend to validate `initData`, not `initDataUnsafe`, with the Bot-token-derived HMAC and to check `auth_date`. It also states that a `startapp` parameter is made available to the Mini App for a direct-link launch. This proposal uses those documented primitives; it does not introduce a custom Telegram protocol.

## Non-Negotiable Constraints

- Telegram user/chat data is identity and context evidence, never a role, permission claim or bypass of `WorkspaceMember` authorization.
- The browser never supplies a role, workspace, resource permission, target display label, employee action, raw record value or approval result.
- `initData`, Bot token, raw `startapp` token, profile JSON and raw Telegram message body must never be returned in API models, stored in client persistence or written to audit/error text.
- Every deep-link resolution rechecks current active binding, membership, target ownership and the normal resource action. A link is a pointer, not a capability.
- Existing `X-Stage06-User-Id` stays local/test only. In staging/production it remains rejected unless a verified identity source is present.
- No automatic Bot reply, group send, external provider write, contact publication, memory, knowledge, generic chat, personal assistant or employee lifecycle is included.
- No real Telegram operation occurs without a separately authorized non-production Bot token, URL, webhook secret, target allowlist and user-controlled external setup.

## Options

| Option | Identity and link model | Advantages | Risks / decision |
| --- | --- | --- | --- |
| A — official `initData` verification plus bound opaque links **(recommended)** | Validate the raw `initData` on every protected Mini App request; resolve one unambiguous active member through existing Telegram bindings; persist a short-lived opaque deep-link pointer and resolve it only after current authorization. | Uses the official Telegram verification model, existing FastAPI/SQLAlchemy/Alembic/Stage06 authorization stack and supports expiry/revocation without exposing resource IDs in `startapp`. No session framework or browser storage is added. | Adds one narrowly scoped table/migration, one identity adapter extension, one safe resolver and an internal mint service. Requires explicit approval. |
| B — stateless signed `startapp` payload | Validate `initData`, then decode a server-signed payload containing destination metadata and expiry. | No link table or database lookup. | Rejected: target data is either exposed in the URL or requires custom encryption; individual revocation and issuer audit are weak; replay cannot be distinguished from a current authorized pointer. |
| C — existing binding default only | Validate `initData` and always open the binding's default Base/employee. | Smallest code change. | Rejected: it cannot safely resolve a mention/draft/record destination, cannot satisfy the Stage07 deep-link BDD and conflates a default context with a durable target. |

## Recommended Option A

### 1. Request Identity

The Mini App frontend reads the official runtime's raw `window.Telegram.WebApp.initData` only when present and sends it in `X-Telegram-Init-Data` on protected requests. It does not use `initDataUnsafe` as authority. Desktop/local development continues through the already-approved development or verified adapter paths.

The backend validator applies these fixed rules before it creates `Stage06RequestIdentity`:

| Rule | Required behavior |
| --- | --- |
| raw input | URL-query-string decoding with duplicate key rejection; maximum 8 KiB; required `hash`, `auth_date` and JSON `user.id` |
| integrity | Telegram's documented sorted data-check-string plus HMAC-SHA-256 calculation; `compare_digest` only |
| freshness | `auth_date` must be no more than 300 seconds old and no more than 60 seconds in the future according to server UTC clock |
| binding | find active `Stage06TelegramBinding` rows for the validated Telegram user; every selected binding must point to an active member |
| ambiguity | if the active bindings resolve to zero internal users or more than one distinct `WorkspaceMember.user_id`, deny rather than choosing one |
| output | `{ user_id, source: 'telegram_binding', telegram_user_id }`; no Telegram profile, chat, raw init data or role travels past the adapter |

The identity adapter does not infer a raw `telegram_chat_id` from `chat_instance`: Telegram documents `chat_instance` as an opaque global chat identifier, whereas existing bindings hold Telegram chat IDs. It may be retained only as a signed launch-context comparison value inside the resolver; it is not a binding lookup key or an authorization substitute.

### 2. Opaque Deep-Link Pointer

One new persistent resource is proposed for implementation only after the approved document package receives its implementation-plan review:

```text
stage07_telegram_deep_links
  id UUID PK
  token_hash CHAR(64) UNIQUE              # SHA-256 of random 256-bit token; raw token is never stored
  workspace_id UUID FK workspaces
  subject_telegram_user_id VARCHAR(120)   # the only Telegram user allowed to resolve it
  source_telegram_chat_id VARCHAR(120)    # audited issuance context, not a browser role claim
  destination_kind VARCHAR(40)            # base | view | record | record_change_draft
  destination_id UUID
  status VARCHAR(40)                      # active | revoked
  expires_at TIMESTAMPTZ
  created_by_type VARCHAR(40)             # system | user
  created_by_id VARCHAR(120)
  created_at / updated_at
```

`startapp` contains an opaque random token, not IDs, JSON, a JWT, a role, a permission or a signature invented by the client. Links expire after 10 minutes and are reusable only by their subject Telegram user during that window. Reuse is deliberate: the resolver reauthorizes on every open, so marking the pointer consumed would turn ordinary reload/retry into a false denial without adding privilege protection. Revocation immediately returns the same safe recovery result.

The only S6.1 lookup predicate is:

```sql
WHERE token_hash = :sha256_token
  AND status = 'active'
  AND expires_at > now()
```

The `UNIQUE(token_hash)` constraint is sufficient for the approved resolver. No broad chat/user/status index, search, history list or token enumeration endpoint is proposed.

### 3. Safe Resolver Contract

The proposed browser endpoint is intentionally one-way:

```http
POST /mini-app/telegram/deep-links/resolve
X-Telegram-Init-Data: <raw Telegram initData>
Content-Type: application/json

{ "start_param": "<opaque token>" }
```

The server compares the request's token with the validated `initData.start_param`; a URL query parameter alone is never enough. It looks up the hashed token, verifies the subject user and a still-active server binding matching the stored source chat/user, resolves the linked member and target ownership chain, and applies normal existing read/review actions. It returns only either:

```ts
type SafeTelegramDeepLinkResolution =
  | {
      outcome: 'resolved'
      destination: {
        kind: 'base' | 'view' | 'record' | 'record_change_draft'
        workspaceId: string
        baseId?: string
        tableId?: string
        viewId?: string
        recordId?: string
        draftId?: string
      }
    }
  | { outcome: 'recovery' }
```

`recovery` deliberately represents malformed, missing, expired, revoked, subject-mismatched, unauthorized and no-longer-existing pointers alike. The client returns to authorized Home/Bootstrap recovery without displaying a target name, raw error or reason. An invalid/missing/expired `initData` is a typed `401` identity failure and triggers complete protected-state cleanup.

### 4. Issuance and Delivery Boundary

`mint_telegram_deep_link(...)` is a server-only service. It accepts a trusted server actor, a source Telegram chat/user context and one durable destination already checked against the existing resource chain. It returns a raw token **only to the immediate trusted delivery boundary** and records sanitized issuance audit metadata (`destination_kind`, durable IDs, expiry and outcome), never the raw token or message body.

S6.1 does not expose a browser mint endpoint and does not automatically call `sendMessage`. It may be exercised with synthetic stored pointers in local/PostgreSQL tests. Actual group-mention link delivery is a later S6 work group that must reuse the existing controlled notification/send policy in `restricted_test` mode and requires user authority for BotFather/webhook/test-chat configuration. This distinction prevents a resolver implementation from silently becoming an external messaging feature.

### 5. Frontend Boundary

The existing Mini App fetch client may attach raw `initData` in memory. It may parse `tgWebAppStartParam` only as an untrusted transport hint and immediately send it to the resolver; it may not persist, render or independently decode it. After `{ outcome: 'resolved' }`, App root uses the existing authorized open flows and re-reads their server data. It never constructs a target view from response IDs alone. After recovery/denial, it removes exact deep-link and workspace keys, shows a fixed recovery message and exposes no retry that reuses stale raw init data.

## Explicit Non-Goals

- OIDC/vendor authentication, JWT session infrastructure, cookie persistence or a general login page;
- automatic group reply, message sending, web-app query sending, link broadcast or a notification UI;
- chat history, user memory, knowledge ingestion/retrieval, employee publishing/configuration or personal assistant capability;
- API compatibility with Telegram/Feishu, generic link search/list/export or arbitrary URL redirects;
- trusting `initDataUnsafe`, `chat_instance`, user profile fields, query strings or a Telegram sender as a role/capability;
- staging/production deployment, BotFather setup, webhook registration or any production claim.

## Approval Boundary

The approved Option A defines the only permitted S6.1 implementation boundary after its implementation plan is reviewed: official `initData` verification, the narrow binding-backed identity adapter, one opaque-expiring link table, server-only mint service, safe resolver route, in-memory frontend header/handoff and proportional local/disposable PostgreSQL/client verification. It does not authorize S6.2 test-bot delivery, any external send, a new provider, Telegram configuration change or a Stage07 completion claim.
