# Stage09 P1 Task 1 Independent Review

## Scope

- Reviewed artifact: `project-docs/08-implementation/STAGE_09_PRODUCTION_READINESS_AND_DEPLOYMENT_PLAN.md`
- Review focus: P1 detailed deployment plan only.
- Constraints checked: preserve Stage03; new isolated Compose/runtime/PostgreSQL and Redis volumes; new HTTPS hostname; fixed migration `20260720_0032`; `dry_run` / LLM-off / fake workflow / disabled provider / empty Telegram allowlists; Stage07 Browser/UI acceptance remains a separate P3 gate.
- Method: documentation-only review. No remote command, deployment, migration, or service action was performed.

## Spec compliance verdict: PASS

The P1 plan satisfies all stated constraints:

1. It expressly prohibits replacing, reading from, migrating, rolling back, restarting, or otherwise altering the historical Stage03 deployment. It establishes the separate `stage09-p1` project, directory, service names, data volumes, runtime directory, and Caddy aliases.
2. It requires fresh, empty `stage09_p1_postgres_data` and `stage09_p1_redis_data` volumes and disallows every Stage03 database, Redis, queue, service, network, and volume as a P1 data source.
3. It requires one newly authorized, DNS-validated, independently routed HTTPS hostname; use of the Stage03 hostname, a temporary IP, or an unapproved hostname is blocked.
4. It fixes both offline and deployed migration execution to the unique Alembic revision `20260720_0032`, requires a single-head check, and prohibits silently using `head` or `latest`.
5. It makes `TELEGRAM_SEND_MODE=dry_run`, `LLM_ENABLED=false`, `AGENT_WORKFLOW_MODE=fake`, and `PROVIDER_MODE=disabled` mandatory across migrate/API/worker/outbox. It requires every Telegram allowlist to be empty or absent and blocks `restricted_test` until separately authorized P2.
6. It states repeatedly that P1 health/HTTPS evidence neither substitutes for nor implies Stage07 Browser/UI acceptance; that acceptance remains a P3 prerequisite.

## Task quality verdict: PASS

The plan is execution-ready at the documentation level. It separates P1-A local preparation from explicitly authorized P1-B remote writes, specifies pre-write gates, immutable artifacts, secret-presence-only validation, ordered database and ingress steps, observation criteria, sanitized evidence, and an isolated rollback sequence. Its declared external blocks appropriately prevent accidental deployment before server, hostname, ingress-network, and authorization prerequisites are available.

## Findings

### Critical

PASS — no critical issues found.

### Important

PASS — no important issues found.

### Minor

PASS — no minor issues found.

## Conclusion

Task 1's P1 detailed deployment plan passes independent review. It is a plan only; P1-B remains blocked pending the documented explicit external authorization and infrastructure prerequisites.
