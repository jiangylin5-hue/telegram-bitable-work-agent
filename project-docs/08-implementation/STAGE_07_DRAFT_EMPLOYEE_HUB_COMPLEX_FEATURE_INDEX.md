# Stage07 Draft and Digital Employee Hub Complex Feature and Index Design

## Status

- Status: approved TD005 Option A index decision. I-A starts as the measured baseline; I-B remains conditional on the documented `EXPLAIN (ANALYZE, BUFFERS)` gate.
- Scope: S5 transition, scope, safe-diff and pending-queue complexity; not a general database tuning or agent-memory proposal.

## Logical Feature Index

| ID | Concern | Server invariant | Required proof |
| --- | --- | --- | --- |
| DE-I01 | contact visibility | active contact ∩ Base ∩ caller scope only | API/workspace/Base omission tests |
| DE-I02 | context confusion | all IDs belong to one authorized Base and employee scope | cross-Base/stale/hidden denial tests |
| DE-I03 | action escalation | browser sends only fixed intent; backend maps intent to allowed runtime action | strict schema and malicious payload tests |
| DE-I04 | raw runtime disclosure | safe invocation response drops records/config/runtime/skill/trace fields | parser/DOM/response-redaction tests |
| DE-I05 | hidden draft disclosure | draft fields filter on current field read authority | hidden-before/proposed/detail/DOM tests |
| DE-I06 | partial confirmation | every proposed field must be currently writable or whole command fails | permission-change/mixed-field tests |
| DE-I07 | lost terminal transition | lock + draft revision + idempotency permits one terminal outcome | PostgreSQL confirm/reject race/replay tests |
| DE-I08 | record concurrency | confirm checks current record version through existing record service | stale record/version tests |
| DE-I09 | audit linkage | terminal status and opaque audit ID are written together | rollback/audit-reference tests |
| DE-I10 | protected UI lifecycle | exact user/workspace/draft/query removal and no optimistic terminal state | delayed 401/403/404/409 App tests |
| DE-I11 | responsive confirmation | all target widths expose labelled review/terminal paths | synthetic built-client matrix and focus checks |
| DE-I12 | S6 leakage | no memory, Telegram, publication, send or external execution route | route/DTO inventory and negative UI tests |

## Physical PostgreSQL Index Decision

### Query being protected

S5 list reads only pending drafts for one Base in newest-first order. The expected predicate is:

```sql
WHERE base_id = :base_id AND status = 'pending_confirmation'
ORDER BY created_at DESC, id DESC
LIMIT :limit
```

### Alternatives

| Option | Physical design | Benefit | Cost / decision |
| --- | --- | --- | --- |
| I-A — no new index until measured | reuse current PK/FK paths and bounded page size | no migration/index write cost | recommended until real disposable `EXPLAIN` shows an unsuitable scan |
| I-B — partial pending queue index | `(base_id, created_at DESC, id DESC) WHERE status = 'pending_confirmation'` | narrow queue read acceleration, excludes terminal rows | requires migration, explain evidence and user-approved TD005 Option A |
| I-C — broad status/workspace/full-text index | multiple generic queue/search indexes | apparent flexibility | rejected: no approved query/filter/search contract and unnecessary write overhead |

No index is created merely because an S5 document names it. The implementation plan must first seed a disposable representative draft distribution, capture sanitized `EXPLAIN (ANALYZE, BUFFERS)` for I-A, then create I-B only if the measured result supports it. No raw draft values are used as index/evidence data.

## Scope Guard

This index document authorizes no full-text search, vector memory, knowledge retrieval, chat history, Telegram event table, action queue, general audit index, group policy or formula/index work.
