# Stage12-F Durable Action / UI Evidence

## Status

- Status: accepted locally
- Date: 2026-07-30
- Deployment: not authorized and not performed
- Production data write: not performed
- Telegram send: `0`

## Verified Chain

```text
TaskSpec ActionSlot
-> authorized candidate resolution
-> encrypted private payload
-> durable action command/outbox/worker
-> independent Action Specialist validation
-> existing Tool Gateway materialization
-> pending_confirmation
-> Mini App review/edit
-> explicit confirm
-> existing backend record service
-> audit
```

The browser acceptance used the real local Vite application, real FastAPI routes and a disposable PostgreSQL database. The final action remained a draft at `pending_confirmation`; the record count was `3` before confirmation and `4` after confirmation. The exact edited value `Browser edited value` and default status `planned` were persisted, the UI reread `executed`, notification requests stayed `0`, and Telegram send requests stayed `0`.

An earlier browser pass exposed a real defect: the UI displayed the edited title, but SQLAlchemy `populate_existing=True` reloaded the original draft because the session disables autoflush. A PostgreSQL regression first reproduced `Original != Edited by user`; the service now flushes the reviewed draft values inside the same transaction before the confirmation lock is reacquired. The regression and a second browser flow both passed after the fix.

## Verification

| Check | Result |
| --- | --- |
| Stage12-F focused unit/API/PostgreSQL | `49 passed` |
| Full backend from `backend/` with disposable PostgreSQL | `2209 passed, 38 skipped, 0 failed` |
| Mini App focused | `25 passed` |
| Mini App full | `79 files, 412 tests passed` |
| Mini App production build | PASS |
| Real Action Provider | `1/1`, one OpenRouter call, `google/gemini-2.5-flash` |
| Alembic | one head/current `20260730_0036` |
| Black | `132` changed/new Python files unchanged after formatting |
| Compileall | PASS |
| `git diff --check` | PASS |
| Credential/developer-path/JSON scan | PASS |

The real Provider report is retained separately as `stage12-f-real-action-provider-2026-07-30.json`. It contains only aggregate metadata and reports record mutations/sends as `0/0`.

## Browser Acceptance

- Objective timeline rendered `fact_query` and `task_creation` independently.
- Action card rendered only server-authorized editable fields.
- Before confirmation, the card showed `待确认 · 尚未写入` and no record was created by that proposal.
- User editing survived the confirmation boundary and was verified in PostgreSQL.
- After the server receipt, the card showed `状态 · executed` and controls became disabled.
- At `390 × 844`, the dialog stayed within the viewport (`374.67 px` wide), document scroll width was `375 px`, the action remained accessible, and no error overlay appeared.
- Browser console error count was `0`.

## PostgreSQL / pgvector

The local test database uses a non-superuser application account. To keep `vector` available when historical fixtures recreate `public`, pgvector is installed by `postgres` in a durable `extensions` schema; the test database search path is `public, extensions`. A real `DROP public -> Alembic head -> PostgreSQL security test` then passed. The project database `ads_agent` was not used by these destructive test fixtures.

## Skipped Tests And Environment Limits

- Real Redis integration was not executed: there was no listener on `6379` and no `STAGE10_REDIS_URL`. The Redis worker path, crash recovery and ack-once behavior passed through the in-memory Redis Streams contract.
- Full backend skips were exactly: one Redis integration, 17 online PostgreSQL smoke cases, three Stage08 collaboration database cases and 17 Stage08 RAG/pgvector cases.
- Ruff was unavailable; Black and compileall passed.
- The approved 48-case × 3 real-model campaign was intentionally not run. It remains the final Stage12 quality gate after the architecture stages.

## Temporary Cleanup

- Vite and FastAPI browser-acceptance processes were stopped.
- Provider credentials were loaded transiently from the ignored local environment and were not written to evidence.
- The disposable Stage12-F database is dropped in the final cleanup step after evidence generation.
- No deployment, production migration, production workspace activation or Telegram send occurred.
