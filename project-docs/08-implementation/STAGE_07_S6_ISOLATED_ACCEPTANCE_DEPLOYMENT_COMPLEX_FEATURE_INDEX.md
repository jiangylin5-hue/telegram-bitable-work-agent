# Stage07 S6.3 Isolated Acceptance Deployment Complex Feature Index

## Index Decision

S6.3 adds no product query, table, schema migration or physical database index. It reuses the existing Alembic head and provisions a separate empty PostgreSQL cluster so the existing primary/unique/foreign-key/index decisions are replayed unchanged.

| Concern | Existing/reused mechanism | New index decision | Evidence required |
| --- | --- | --- | --- |
| migration lookup | existing Alembic version table | none | isolated migration reaches the already tested head |
| TD007 pointer resolution | existing unique token-hash index | none | S6.1 real smoke uses existing resolver only |
| TD008 delivery reservation | existing unique delivery/request and Outbox locking constraints | none | S6D-A03 one-attempt receipt |
| persisted private-marker bootstrap | one bounded, one-time SQLAlchemy ORM read of historical `messages`; exact marker/freshness/private invariant is evaluated in application code | no Stage03 index or migration; a one-off acceptance read does not justify mutating the preserved historical database | selector tests, sanitized receipt and unchanged Stage03 state |
| runtime-file layout | dedicated ignored `runtime/` directory, Compose `STAGE07_ENV_FILE` path and atomic writer mount boundary | not a database index; no Stage03 file/data mount or migration | compose path test, remote mode check and sanitized preflight |
| Caddy upstream routing | stable Docker network aliases | not a database index | Caddy candidate validation and HTTPS health |
| cleanup | named Compose volumes | no retention/search index | volume removal record |

Adding an index for an empty disposable acceptance database would not answer a measured product query need and is prohibited by the Stage07 index rule.
