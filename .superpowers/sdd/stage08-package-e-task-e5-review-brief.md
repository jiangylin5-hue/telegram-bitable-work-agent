# Stage08 Package E — E5 independent remediation review brief

## Review scope

Review only E5's repair for Package E final-review I-01. Read the E5 decision,
plan, brief/report, current service/agent/contracts/tests and prior E final
review. Do not edit code or broaden to Package F/UI/full-suite work.

## Blocking questions

1. Are the three production graph read nodes now actual branch work and is
   `fan_in` free of C3/D4 I/O?
2. Are concurrent SQLAlchemy read branches given distinct, isolated,
   read-only sessions/UoWs (not the request session), reliably closed, and
   demonstrated by a substantive local pgvector barrier test?
3. Do InMemory fallbacks remain safely serialized and never get presented as
   production concurrency proof?
4. Is runtime control sealed/internal and does it enforce cancellation and
   wall/provider deadline before/after read, compression, analysis, policy
   and draft such that no later ticket/Gateway/draft executes?
5. Are slow/exceptional branches fail-closed without leaking private material,
   session/runtime-control data, query or provider output to safe views,
   replay, audit, AgentRun, outbox or errors?
6. Did E5 preserve C3/D4 consumer-time revalidation, E3 transaction/locks,
   E4 exact safe replay, no new public/schema/permission/Provider/Telegram/
   deployment behavior and no Stage06 default changes?

## Method/output

Inspect direct source, run focused E5 service tests plus the PostgreSQL
collaboration integration as needed. Write
`.superpowers/sdd/stage08-package-e-task-e5-review-report.md` in Chinese with
findings and a PASS/HOLD recommendation. Critical or Important blocks the
subsequent Package E re-review.
