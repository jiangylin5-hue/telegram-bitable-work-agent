# Stage07 Digital Employee Management Complex Feature Index

## Status

- Status: approved TD010 complexity/index decision; no physical change has been made.

## Complexity Map

| Feature | Complexity source | Required invariant | Required evidence |
| --- | --- | --- | --- |
| lifecycle | active status controls contact/context/invocation availability | only server-owned `draft|active|paused` transitions; no optimistic client state | unit + PostgreSQL transition/replay/conflict matrix |
| immutable Base scope | employee runtime is currently Base-bound | no command changes `base_id`; every selected resource remains in Base | negative API and migration tests |
| table/view scope | scope arrays and caller access may drift independently | selected views belong to selected tables and Base; activation rereads all | service/API/post-revoke tests |
| member grants | assignment must not become authorization | grant only gates discovery/use after existing action/permission checks | caller A/B contact/context/invoke tests |
| legacy compatibility | existing active employees currently have workspace-wide eligible callers | migration defaults old rows to `workspace`; no silent contact loss | PostgreSQL upgrade/replay and S5 regression |
| concurrency | config, grants and lifecycle can race | employee lock + version + idempotency yields one result | two-session PostgreSQL race/rollback tests |
| alias uniqueness | existing partial unique active alias index interacts with pause/activate | activation collision is deterministic and audit-safe | database unique-index/transition tests |
| safe management DTO | generic runtime response carries forbidden data | parser/API/DOM never receives policies, runtime/provider/trace or values | negative response/parser/DOM inventory |
| cache replacement | panel and mutations can outlive Base/workspace state | late result cannot display/mutate replacement scope | deferred App-flow/query cleanup tests |

## Proposed Physical Indexes

| Object | Proposed index/constraint | Query served | Rationale |
| --- | --- | --- | --- |
| `digital_employees` | retain `uq_stage06_digital_employee_alias` active partial unique index | active alias uniqueness | existing safety behavior remains authoritative |
| `digital_employees` | `ix_stage07_digital_employee_management_base_updated (base_id, updated_at DESC, id DESC)` | cursor-paged Base directory | ordered, stable manager list; avoids JSONB scope scans |
| `digital_employee_member_grants` | unique `(employee_id, workspace_member_id)` | exact grant existence/replacement | prevents duplicates and supports assigned eligibility check |
| `digital_employee_member_grants` | index `(workspace_member_id, employee_id)` only if profile-wide assigned-employee list is introduced later | no TD010 query | deliberately not created now |

## Explicitly Rejected Indexes

- No GIN index on `accessible_tables`, `accessible_views` or `allowed_actions`: TD010 selects one employee by ID and validates JSONB in memory/row lock; it does not add broad JSONB filtering.
- No workspace-wide alias index: existing active alias uniqueness is Base-local by product constitution.
- No member-grant status/history table: grants have no independent lifecycle/audit surface in this package; employee versioned replacement/audit is the source of truth.

## Migration Safety

1. Migration is additive and reversible: add employee columns/defaults, create grant table/index/constraints, preserve existing foreign keys and alias index.
2. Upgrade gives every existing employee `version=1` and `access_mode=workspace`; it does not create grants, alter status or change Base scope.
3. Downgrade drops only TD010 additions after tests prove no unrelated Stage07 migration dependency.
4. Migration must not inspect or rewrite `field_policy`, `confirmation_policy`, `response_style`, runtime outputs, records or drafts.

## Future Decision Boundaries

Multi-Base scope requires a separate relational scope table, Base reassignment semantics, cross-Base member eligibility, context selection and new index analysis. Memory/knowledge requires retention/deletion/audit design. Neither may be appended to TD010 without a new decision document and approval.
