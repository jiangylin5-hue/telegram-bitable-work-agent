# Stage 07 F2 Relation / Lookup Complex Feature Index

## Status

- Document status: active F2 navigation, state, logical-index and evidence index
- Scope: cross-document traceability for the relationship/lookup slice; this is not a database migration or a new runtime feature
- Physical-index decision: no new PostgreSQL index is approved or implied in F2. Any later performance index requires query evidence, migration design and separate user confirmation.

## 1. Document Navigation Index

| Need | Authoritative document |
| --- | --- |
| approved product choices | `docs/superpowers/specs/2026-07-11-stage07-f2-relation-lookup-design.md` |
| task-by-task implementation sequencing | `docs/superpowers/plans/2026-07-11-stage07-f2-relation-lookup-implementation.md` |
| user behavior, failures and acceptance | [F2 BDD and Acceptance](STAGE_07_F2_RELATION_LOOKUP_BDD_AND_ACCEPTANCE.md) |
| services, API, data and state machines | [F2 SDD](STAGE_07_F2_RELATION_LOOKUP_SDD.md) |
| UI module ownership | [F2 Work Surface Module](modules/STAGE_07_F2_RELATION_LOOKUP_WORK_SURFACE.md) |
| global Stage07 security baseline | [Stage07 API Data Security Contract](STAGE_07_API_DATA_SECURITY_CONTRACT.md) |
| overall Stage status/risk/traceability | Stage07 Source, Progress, Risk Register and Requirement Traceability Audit |

## 2. Functional Requirement Index

| ID | Capability | Primary state owner | BDD | SDD section | Evidence target |
| --- | --- | --- | --- | --- | --- |
| F2-I01 | same-Base relation initializer | backend transaction | F2-01..03 | 2,3,5 | unit/API/PostgreSQL |
| F2-I02 | idempotency/replay/rollback | idempotency service + DB | F2-02 | 3,10 | unit/API/PostgreSQL |
| F2-I03 | safe candidate search/cursor/label | backend read model | F2-04 | 4,5,8 | service/API/frontend |
| F2-I04 | relation create/PATCH enforcement | record service | F2-05 | 7 | service/API |
| F2-I05 | safe relation render | server projection | F2-06 | 4,7 | service/API/frontend |
| F2-I06 | lookup initializer/type graph | schema service | F2-07..09 | 3,6 | unit/API/PostgreSQL |
| F2-I07 | fail-closed lookup render | server evaluator | F2-10 | 5,6,7 | unit/API |
| F2-I08 | deletion conflict guards | reusable service guards | F2-11 | 3 | service/PostgreSQL |
| F2-I09 | protected responsive UI | Mini App modules | F2-12 | 8,9 | frontend/browser |

## 3. Logical Data and Dependency Index

| Logical index | Key/path | Used for | Safety property |
| --- | --- | --- | --- |
| field identity index | `PlatformField.id` within owning table | F2 configuration reference | stable across display-name change; never browser config |
| relation-target index | `linked_record.options.target_table_id` | validates fixed target table | server-only, same-Base checked |
| lookup dependency edge | `lookup.source_field_id -> target_field_id` | cycle/depth/type resolution | server-only; legacy keys are read compatibility only |
| incoming-link index | `RecordLink.target_record_id` | future record delete conflict | no source identity returned to browser |
| field-dependency index | any relation target/source or lookup source/target stable ID | future field delete conflict | conflict has code only, no dependency path |
| label selection order | `tables.primary_field_id`, then readable independent text-like fields by `order_index` | candidate/relation label | no target raw fallback |
| protected query index | `stage07,userId,workspaceId,relation-candidates,fieldId,q,cursor` | client cache isolation | revoked/switch scope invalidates cache |

These are logical lookup/access indices, not permission to add a physical database index. Existing primary/foreign-key/unique constraints remain the database baseline.

## 4. State Index

| State family | Success terminal | Non-success terminals | Forbidden transition |
| --- | --- | --- | --- |
| relation initializer | committed + verified reread | replay, conflict, validation, denied, rollback, cancelled | error/late receipt -> rendered field |
| lookup initializer | committed + verified reread | replay, graph/type error, denied, rollback, cancelled | invalid graph -> partial field |
| candidate page | available/empty/exhausted | denied, expired, cancelled, stale-discarded | stale scope -> selected relation |
| record relation write | persisted versioned record + links + audit | invalid target/self/required/version/denied | client-only relation success |
| lookup evaluation | safe value or numeric-empty null | absent unreadable/invalid/cycle/depth | partial aggregation -> visible value |
| future delete guard | no references -> caller may continue | referenced/dependent conflict | guard -> automatic unlink/cascade |

## 5. Code and Test Index

| Layer | Planned/active area | Required proof |
| --- | --- | --- |
| schema | `backend/app/schemas/stage06_platform.py` | extra keys rejected; safe candidate/form contracts |
| service | `backend/app/services/stage06_platform.py` | atomic creation, graph, projections, writes, guards |
| route | `backend/app/api/routes/stage06_platform.py` | authorisation, idempotency, safe models |
| unit/API | `backend/tests/unit/test_stage07_relation_lookup.py` | F2-I01..I08 |
| PostgreSQL | `backend/tests/integration/test_stage07_relation_lookup_postgres.py` | rollback/lock/replay/guards |
| transport/cache | `mini-app/src/app/api.ts`, `protectedQuery.ts` | allowlist/redaction/scope cancellation |
| UI | Builder, Picker, Create, Detail, Canvas, App | F2-I09 and four widths |

## 6. Physical Database Index Decision Gate

No F2 implementation may add an Alembic revision merely to speculate about lookup speed. If evidence later shows a real query plan problem, a new decision document must state:

1. exact query and measured PostgreSQL plan/cardinality;
2. candidate index columns/type/order and write cost;
3. tenant/Base/permission filter interaction;
4. migration forward/backward/rollout and local-smoke proof;
5. whether a foreign key or constraint changes deletion behavior;
6. regression and privacy evidence;
7. explicit user approval before implementation.

Until then, F2 relies on the existing durable identity/foreign-key/unique baseline and bounded candidate pagination. This gate prevents a documentation index from silently becoming a schema/API/technical-selection change.

## 7. Evidence and Status Index

| Evidence class | Required artifact/status rule |
| --- | --- |
| code commits | identify commit and exact scope; never equate with accepted F2 |
| automated test | command, test count and output after final implementation |
| PostgreSQL | disposable local target only; no credentials; record rollback/concurrency result |
| browser | width, scenario, screenshot/console result, temporary fixture cleanup |
| skipped/blocker | condition, affected F2-I IDs and safe next action |

Current F2 status must be read from `STAGE_07_PROGRESS.md` and the requirement traceability audit; this index intentionally makes no completion claim.
