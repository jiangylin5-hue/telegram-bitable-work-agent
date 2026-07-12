# Stage07 S6 Telegram Identity and Deep-Link Complex Feature and Index Design

## Status

- Status: TD007 Option A `partial-local`; migration `20260712_0025` and only `UNIQUE(token_hash)` exist. A rollback-only synthetic PostgreSQL `EXPLAIN` confirmed the unique lookup path; no speculative index was added.
- Scope: launch proof parsing, binding ambiguity, opaque-link lifecycle, resolver non-enumeration and the one approved PostgreSQL lookup.

## Logical Feature Index

| ID | Concern | Required invariant | Required proof |
| --- | --- | --- | --- |
| TG-I01 | forged launch proof | only official HMAC-validated raw `initData` becomes a launch object | valid/forged/duplicate/malformed test-vector matrix |
| TG-I02 | stale/future replay | `auth_date` is max 300 seconds old and max 60 seconds future | boundary-clock unit/API tests |
| TG-I03 | raw data disclosure | raw init data, hash, Bot token, profile JSON and token never enter DTO/audit/error/cache/DOM | response/audit/parser/cache/DOM negative checks |
| TG-I04 | binding privilege escalation | active bindings resolve exactly one active internal user; no role/default selection | zero/inactive/ambiguous/same-user matrix |
| TG-I05 | chat identity confusion | `chat_instance` is not mapped to raw `telegram_chat_id` or permission | direct-link launch context tests |
| TG-I06 | token guessing/enumeration | opaque 256-bit random token; only SHA-256 stored; unknown/expired/revoked/denied all recover identically | endpoint equivalence/no-label tests |
| TG-I07 | subject forwarding | pointer subject must equal validated Telegram user | different-user PostgreSQL/API denial test |
| TG-I08 | stale authorization | every resolution reruns current binding, membership, ownership and action checks | membership/permission/resource deletion tests |
| TG-I09 | target leakage | resolver returns pointer only; target screen rereads normal safe projection | hidden-field/draft/404 client and API tests |
| TG-I10 | link lifecycle error | expiry/revocation never yields target or a distinct public response | time/revoke/race tests |
| TG-I11 | client stale state | launch/workspace switch cancels/resists late resolver result | App generation/cache-removal tests |
| TG-I12 | S6.1 external-action leak | no send/delivery/Bot config or provider call happens | route/transport inventory and mock-client negative tests |

## Physical PostgreSQL Index Decision

### Protected Query

```sql
SELECT id, workspace_id, subject_telegram_user_id, source_telegram_chat_id,
       destination_kind, destination_id, status, expires_at
FROM stage07_telegram_deep_links
WHERE token_hash = :sha256_token
  AND status = 'active'
  AND expires_at > now()
```

### Alternatives

| Option | Physical design | Decision |
| --- | --- | --- |
| I-A — unique token hash only **(recommended)** | `UNIQUE(token_hash)` from the model constraint | accepted for S6.1; a random opaque token is the sole lookup path, so unique equality lookup is sufficient |
| I-B — partial active/expiry compound index | `(token_hash, expires_at) WHERE status='active'` | rejected: a unique equality lookup already narrows to zero/one row; status/expiry filter is a single-row predicate and extra write/index cost has no approved measured query benefit |
| I-C — workspace/chat/user/status/history indexes | multiple collection/search indexes | rejected: S6.1 has no list/search/history/admin screen and must not enable Telegram identity enumeration |

### Measurement Gate

No speculative index is permitted. The implementation plan must first run migration and disposable PostgreSQL tests, then capture `EXPLAIN (ANALYZE, BUFFERS)` for the exact I-A resolver lookup at a representative synthetic token population only if planner behavior is unclear. A resolver must never use raw tokens or real Telegram data in fixture/evidence output. Any later collection/search feature needs a new decision rather than reusing this table's indexes.

## Lifecycle State Model

```text
server mint
-> active / expires_at
-> resolve repeatedly for matching current subject + authorization
-> revoked by future server-only control OR logically expired
-> recovery (all terminal/non-resolved cases)
```

Links are intentionally not consumed by normal resolution. They are not bearer authority: the authenticated subject and every current resource/membership permission is rechecked each time. This permits launch/reload retry during the short TTL without weakening revocation or authorization.

## Scope Guard

This index design authorizes no chat history, message table, broad Telegram send, token session list, generic identity search, group policy, per-user memory, knowledge source, notification UI, provider action or persistent browser token state.
