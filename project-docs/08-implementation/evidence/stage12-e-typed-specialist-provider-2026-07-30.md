# Stage12-E Typed Specialist / Provider V2 Evidence

## Status

- Status: passed local technical gate
- Date: 2026-07-30
- Runtime authority: Stage11 V1 unchanged
- Deployment: not performed
- Data boundary: synthetic authorized artifacts only

## Focused Diagnostic

`python -m scripts.stage12_specialist_provider_evaluation --output-json ../project-docs/08-implementation/evidence/stage12-e-typed-specialist-provider-2026-07-30.json`

- four distinct handlers executed;
- contract exact `4/4`;
- typed artifacts `6`;
- ClaimGraph claims `2` with one deduplicated evidence reference;
- optional failure retained grounded facts and produced a safe degraded result;
- action proposal `1`, record writes `0`, external sends `0`;
- deterministic diagnostic Provider attempts `0` by design.

The hash-validated machine report is `stage12-e-typed-specialist-provider-2026-07-30.json`. It contains counts, booleans, duration and a report hash only; no query, field value, candidate, evidence ID, prompt or answer text is retained.

## Real Provider Profile Evidence

`python -m scripts.stage12_provider_profile_benchmark --output-json ../project-docs/08-implementation/evidence/stage12-e-provider-profile-benchmark-2026-07-30.json`

- provider: `openrouter-compatible`;
- model: `google/gemini-2.5-flash`;
- roles: risk, daily, composer;
- pass `3/3` synthetic cases;
- attempts `3`, failures `0`;
- input tokens `207`, output tokens `125`;
- mean latency `3465 ms`, p95 `4957 ms`.

The ignored local env key was loaded only into the benchmark process. No key, prompt, response, synthetic field value or evidence ID was written to the report. The baseline was retained; no model-profile change or TDR was required.

## Verification

- final E focused suite: `78 passed in 7.54s`;
- real disposable PostgreSQL event/fan-in artifact integration: `1 passed in 2.69s`;
- Redis integration: `1 skipped` because `STAGE10_REDIS_URL` and the Python `redis` package were unavailable;
- unit/API: `1966 passed in 146.04s`;
- full backend under the accepted four-file historical PostgreSQL boundary: `2065 passed, 134 skipped in 151.07s`;
- `compileall`, Alembic one head `20260729_0035`, E-file Black check, `git diff --check`, JSON/hash validation, credential scan and developer-path scan: passed;
- Ruff: unavailable because the Python module is not installed.

The full-backend command excluded only:

- `tests/integration/test_stage07_draft_employee_hub_postgres.py`
- `tests/integration/test_stage07_governance_write_postgres.py`
- `tests/integration/test_stage07_telegram_deep_link_delivery_postgres.py`
- `tests/integration/test_stage07_telegram_deep_link_postgres.py`

## Cleanup

- No temporary script or fixture was retained.
- The disposable `ads_agent_stage12_test` database was rebuilt after the Stage10 integration fixture and restored to Alembic `20260729_0035`; `vector`, `fields` and `stage12_retrieval_chunks` were verified.
- The project database `ads_agent`, `stage06_smoke`, production, Telegram and external write systems were not touched.
