# Stage07 V1 Saved View Builder PostgreSQL Evidence

## Status

- Evidence status: local disposable PostgreSQL evidence; V1-7 through V1-10 safe field/list ACL projection `partial-local`
- Date: 2026-07-12
- Scope: migration/default invariant, initialization rollback, hidden-field non-disclosure, grant concurrency/uniqueness, V1 query ordering, safe Builder field projection, Base-list/direct-presentation ACL projection and optional-index decision
- Environment: authorized disposable local PostgreSQL only; PostgreSQL `18.4`; no remote staging or production target
- Migration head: `20260711_0022`

## 1. Commands And Results

| Command | Result | What it establishes |
| --- | --- | --- |
| `python -m alembic heads` | `20260711_0022 (head)` | one current V1 migration head |
| `python -m pytest -q tests/integration/test_stage07_view_builder_postgres.py tests/integration/test_stage07_view_builder_security_postgres.py -m postgres` | `11 passed` | real PostgreSQL V1 invariant/security/query/safe-field/list-ACL suite |
| `python -m pytest -q -s tests/integration/test_stage07_view_builder_security_postgres.py::test_v1_optional_access_indexes_remain_deferred_after_explain -m postgres` | `1 passed` | captured sanitized `EXPLAIN (ANALYZE, BUFFERS)` index decision evidence |

The test target is classified by the retained local-disposable guard before its public schema is reset and migrated. No connection string, database user, record value, request body or audit body is retained in this evidence.

## 2. Durable And Transactional Invariants

| Scenario | Proven result |
| --- | --- |
| migration shape | `views.owner_user_id`, `views.scope`, `views.version`, `view_member_grants` and `uq_view_member_grants_view_user` exist at the migration head |
| private initialization/replay | same idempotency key leaves one private view and one idempotency record |
| duplicate grant | PostgreSQL rejects two rows for one `(view_id, user_id)` |
| concurrent replacement | two concurrent expected-version writes produce exactly one update and one `view_version_conflict` |
| default invariant | an existing system default Grid remains default; a V1 private view is not default; a second default row is rejected by the partial unique index |
| route rollback | an injected safe-projection failure after V1 initialization rolls back the view, `stage07.view_initialized` audit and idempotency record together |

## 3. Security And Query Evidence

The hidden-field scenario creates a readable title and a viewer-hidden grouped status field, then configures the V1 view as owner with that field in visible/filter/sort/group state. An active viewer grant can read the V1 records but cannot learn the hidden field from:

- `GET /views/{view_id}/records`;
- legacy safe presentation read;
- V1 builder read, which returns denied for a viewer; or
- V1 builder context, which requires `view.manage`.

The V1 record-query scenario proves canonical filtering, group-first ordering, configured descending sort and cursor continuation against actual PostgreSQL. The first two one-row pages are the two rows in the first permitted group; group metadata contains only that page's returned IDs.

The V1 Builder-context route also reads from the real PostgreSQL fixture: a readable `status` field projects its existing safe `field_id` and validated `filter_values` choices, while an ordinary text field projects `filter_values: []`. The response contains none of raw `options`, field `permission_policy` or relation-target internals. This is a safe read-model proof only; it does not prove a Mini App lifecycle or Browser interaction.

The V1 list/direct-read ACL case creates an owner-private V1 view in the disposable database. An otherwise authorized table reader receives neither a Base-list summary nor a direct presentation projection before an explicit grant; the direct URL is `403`. After the owner grants `viewer`, the refreshed list has only `scope=restricted`, `caller_access_level=viewer` and `is_default=false` in addition to legacy summary fields; raw owner/config/policy fields remain absent, and the reader receives the safe presentation projection. This proves the list path cannot disclose a private/restricted V1 tab and the legacy presentation path cannot bypass V1 access. It does not prove a browser flow or remote environment.

## 4. Optional Non-Unique Index Decision

The measured ACL-list query used 128 V1 view rows and 32 active recipient grants for one table. This is a controlled local evidence sample, not a production workload forecast.

Sanitized plan summary:

```text
Nested Loop Left Join
  -> Index Scan using ix_stage06_views_table_id on views
  -> Index Scan using uq_view_member_grants_view_user on view_member_grants
Planning Time: 0.335 ms
Execution Time: 0.180 ms
```

`ix_views_table_scope_status` and `ix_view_member_grants_user_status` were absent. The existing table foreign-key index and correctness-critical unique grant index serviced the measured query; no slow sequential access path or workload evidence justified a new index. Therefore Task 7 explicitly **defers both optional non-unique indexes** and adds no migration.

This follows the project rule to add query indexes only after a measured query shape and plan, and retains the later re-evaluation trigger: materially larger view/grant cardinality or a new measured access/list query that cannot use the existing indexes.

## 5. Boundaries And Cleanup

- This proves only an authorized disposable local database. It does not prove staging, production, Telegram identity or Mini App behavior.
- No new index, schema migration, external service write, persistent test script or browser fixture was added.
- The fixture resets the disposable public schema before each PostgreSQL test and disposes its engine afterward. The designated local target may contain the last test's disposable rows until the next reset; it is not a deployment database and must be reset again before any later smoke/deployment operation.
