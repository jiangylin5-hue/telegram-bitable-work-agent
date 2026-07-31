# Stage12 Task 8 Real Redis Evidence

## Status

- Status: `implemented-local`
- Scope: disposable local Redis Streams delivery, crash recovery, pending claim, terminal sibling handling and ACK-once evidence
- Production boundary: no Stage09/staging/production Redis connection, no production worker activation, no business write and no external send

## Runtime Boundary

- Docker Desktop engine: `29.5.3`
- Image: `redis:7.4-alpine`
- Image digest: `sha256:e7723ff73d963f5cc6d9c4643ea3d989527a402a319239054e9472a7fb9219a2`
- Redis server: `7.4.10`
- Python client: `redis 8.1.0`; the project declaration remains unchanged at `redis>=5.0`
- Endpoint used only during the test: `redis://127.0.0.1:51498/15`
- Container: `stage12-task8-redis-30f11e7c73`, launched with `--rm`, disabled RDB/AOF and random loopback-only host port

## Verified Behaviors

- Sequential duplicate publish with the same idempotency key emits one stream entry.
- A worker exception leaves the entry pending and unacknowledged.
- A second consumer claims the pending entry through `XAUTOCLAIM` and processes it once.
- Successful recovery ACKs the entry; a later poll does not re-execute it.
- A required Specialist failure terminalizes its unfinished optional sibling through production orchestrator logic.
- The sibling's already-published Redis delivery is drained without re-executing business logic, ACKed, and does not create a second terminal event.
- Both terminal streams end with pending count `0`.

## Verification

- Existing real Redis adapter evidence:
  - `STAGE10_REDIS_URL=redis://127.0.0.1:51498/15 python -m pytest tests/integration/test_agent_event_streams_redis.py -q`
  - Before expansion: `1 passed in 1.02s`.
- Expanded real Redis integration:
  - Same command after adding crash/recovery and sibling-terminalization coverage.
  - Result: `3 passed in 3.49s`.
- Related runtime regression:
  - `python -m pytest tests/integration/test_agent_event_streams_redis.py tests/unit/test_agent_event_streams.py tests/unit/test_agent_event_workers.py tests/unit/test_agent_coordination_runtime.py tests/unit/test_agent_typed_specialist_runtime.py -q`
  - Result: `25 passed in 3.42s`.
- Cleanup checks:
  - Redis logical DB 15 `DBSIZE=0` before shutdown.
  - Disposable container remaining: `False`.
  - Docker Desktop was stopped after the container was removed, restoring the prior engine state.

## Skipped Tests

- No staging or production Redis was contacted.
- No long-running worker service was activated.
- No network partition, Redis failover/replica promotion or persistence restart test was required by Task 8.
- Human Gold and the three-round real-Provider campaign remain Task 9.

## Remaining Risks

- `RedisStreamsClient.xadd_once` proves sequential idempotency; concurrent multi-publisher atomicity is not claimed by this evidence.
- The disposable Redis server disabled AOF/RDB, so persistence across server restart is not accepted here.
- Production activation remains default-off and requires the later release decision.

## Temporary Cleanup

- Redis test keys: `0` remain in DB 15.
- Disposable Redis container: removed automatically.
- Docker Desktop: stopped.
- The pulled `redis:7.4-alpine` image and installed Python `redis` package are retained as approved local development dependencies.
