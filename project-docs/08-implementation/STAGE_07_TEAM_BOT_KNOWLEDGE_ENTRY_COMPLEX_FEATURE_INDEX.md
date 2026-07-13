# Stage07 Team Bot Knowledge Entry Complex Feature Index

## Status

- Status: TD011 index decision is implemented-local: no physical index was added, and the bounded existing access path is exercised by unit and disposable local PostgreSQL evidence.

## Complexity Map

| Feature | Complexity source | Required invariant | Required evidence |
| --- | --- | --- | --- |
| Team/Personal separation | same employee can be shown in two product surfaces | distinct server route/DTO/query subtree; no context bleed | API/parser/deferred replacement tests |
| active/member eligibility | status/grants may change after a contact read | catalog and command recheck TD010 state | pause/grant-revoke tests |
| scoped knowledge catalog | employee and caller scopes can drift | selected view is same Base, employee scope and current caller-readable | cross-Base/revocation/hidden-view matrix |
| knowledge window | a saved view can be large and sensitive | server owns filter/sort/field filtering and `limit=100` | runtime input capture/hidden-field/empty/truncation tests |
| provider replay | summary can cost or cause duplicate audit | idempotency fingerprint returns one safe durable result | same-key replay/changed-payload/no-second-call tests |
| citations | provider can cite inaccessible rows | opaque citation IDs are intersected with currently visible records | hidden/out-of-view citation tests |
| safe state replacement | result can outlive selected scope | scope generation and exact cleanup discard late response | workspace/contact/view replacement tests |
| no durable knowledge system | terminology can invite premature RAG/memory | no source table, vector query, file ingestion or thread store | model/migration/dependency/source inventory |

## Physical Index Decision

TD011 creates no physical index. It uses the existing Base-local employee listing, TD010 grant uniqueness, saved-view authorization/query path and existing idempotency/audit storage.

No JSONB GIN index, vector index, knowledge-source relation index or global employee directory index is justified by this package because it does not add broad source search: it reads one already-authorized employee and one selected saved view. Any future independent source catalog, file ingestion or semantic retrieval requires its own data model, measurement and index decision.

## Access Path Budget

| Operation | Bounded path | Server-owned bound |
| --- | --- | --- |
| contacts | existing paged workspace/Base employee contact path | `limit <= 100` |
| context catalog | existing employee Base and scoped saved views | `limit <= 100` |
| selected context | exact employee/view reread | one view |
| summary source | existing saved-view record query with one-row truncation probe | first `100` permitted rows reach runtime; `101`st row only sets truncation |

No optional index is proposed. A sanitized local query-plan/capacity measurement remains deferred until a measured scale requirement exists; it cannot be inferred from the one-command PostgreSQL acceptance test or converted into a production capacity claim.

## Future Decision Boundaries

The following each requires a new decision, not an append to TD011: durable knowledge sources; file/URL ingestion; semantic/vector retrieval; multi-Base sources; source revisioning; personal/shared memory; retention/deletion; Telegram group context; automated writes or external actions.
