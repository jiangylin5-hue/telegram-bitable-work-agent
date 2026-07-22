# Stage08 Package C2 Long Context — Task 3 Brief

## Task

Implement Task 3, **Trusted Ingress Projection and Best-Effort Lifecycle**, from `docs/superpowers/plans/2026-07-19-stage08-package-c2-long-context-implementation.md`.

Task 1 and Task 2 are independently approved. Follow TDD: write tests first, execute and preserve a genuine RED failure, then make the narrowest possible implementation Green. Do not begin Task 4 authority/window/purge service.

## Product Boundary

This task applies the user-approved D1 ingress exception only: a message already received through the existing secret-verified Telegram webhook may create a local C2 projection in the same local database transaction. It does not create a webhook, polling loop, outgoing Telegram API call, LLM/Provider call, public API route, raw history reader, RAG/Memory write, or context window.

The projection writer must use the new/edited payload supplied by the current verified ingress, never read `Message.raw_text`, `raw_caption`, or `normalized_text`. The real-time table relationship remains the authoritative business fact; the C2 mapping only gates whether a short-lived contextual fragment is eligible.

## Exact Scope

Create:

- `backend/tests/unit/test_stage08_group_context_ingestion.py`
- `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-3-report.md`

Modify only as needed to carry an existing verified update through the current internal route/service path and create the local projection:

- `backend/app/schemas/telegram_webhook.py`
- `backend/app/services/telegram_update_parser.py`
- `backend/app/services/telegram_ingestion.py`
- `backend/app/schemas/telegram.py` only if the existing internal `MockTelegramUpdate` carrier needs a backwards-compatible private field;
- `backend/app/api/routes/telegram_webhook.py` only if required to pass the already parsed `message`/`edited_message` discriminator and `chat.type` into the existing ingestion call. No new route, no changed response schema, no added request header/query field, and no change to secret/allowlist policy.
- `backend/tests/integration/test_stage08_group_context_postgres.py` only if one small real-PostgreSQL assertion is essential to prove the transaction/lifecycle behavior.

Do **not** change models, migration, Stage06 platform UoW, public route list, outbound client, Memory, RAG/vector, Redis, LangGraph, Provider, audit payload shape, or deployment/secrets. Do not stage/commit/reset/checkout/clean. Preserve unrelated dirty changes.

## Binding Behavior

1. The webhook model/parser accepts exactly one of normal `message` or `edited_message`. The parsed result carries a private/internal update kind (`new` or `edited`) and `chat_type`; safe response views must not add raw identifiers or body fields.
2. Only verified `group` or `supergroup` updates are eligible. `private`, `channel`, missing/invalid sender, empty normalised text/caption, duplicate update, or any failed gate produces no C2 projection.
3. The writer may use current update metadata to locate the Message source row by its stored identity, but it must never read that row's raw/normalised body fields and must not enumerate historical Message rows.
4. Before seeing/normalising a body, resolve one current active Stage06 `binding_type='chat_user'` that exactly matches the current chat/user and one active C2 mapping. Absence, more than one eligible binding/mapping, inactive status, workspace drift, invalid customer/project relation, or non-group input must fail closed without a projection.
5. For a new eligible message, normalise the **incoming** text or caption (`" ".join(value.strip().split())`), reject empty, truncate to no more than 500 Unicode code points, create version `1`, set `event_at` from current payload `message.date` in UTC and `retention_expires_at = event_at + 30 days`, lifecycle `active`.
6. For a known eligible edit of an existing source message, create the next version from the incoming edit body, mark the immediately previous active projection `superseded`, set `edited_at` from the current webhook delivery time only when this is the project-established edit timestamp; event ordering remains original `message.date` UTC. An edit must not create a second raw `Message` row or read historical body fields.
7. C2 additions must return no body, Telegram chat/message/update identifier, mapping ID or source handle to the existing webhook response, audit state, error, trace or outbox. Existing historical behavior may remain unchanged only where not touched; do not add new leak paths.
8. All C2 projection writes must use the same SQLAlchemy session/transaction as the already verified Message persistence, so an uncommitted/failed request cannot leave a projection. The in-memory test implementation may be a minimal equivalent, but do not invent a second durable store or raw-message cache.

## Required Tests and TDD Evidence

Write `test_stage08_group_context_ingestion.py` first. It must cover at least:

- parser differentiates normal `message` versus `edited_message` and rejects neither/both;
- a valid `group`/`supergroup` new inbound message makes exactly one 500-code-point-max projection with `event_at` UTC and exactly 30-day retention;
- private/channel/unmapped/inactive/wrong-type/ambiguous bindings and empty body create no projection;
- an `edited_message` makes version 2 and supersedes version 1 without reading/iterating historical raw body;
- a legacy `Message` raw-text row not received by this call cannot become a projection;
- C2 function/result and existing webhook response shapes have no new raw chat/message/update identifier or content fragment carrier;
- no outgoing networking/Provider/API route is introduced.

Run and record RED before adding production support:

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_group_context_ingestion.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Then run Green and scoped regression:

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_group_context_ingestion.py tests/unit/test_stage03_telegram_update_parser.py tests/unit/test_telegram_ingestion.py tests/integration/test_stage08_group_context_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
rg -n "getUpdates|sendMessage|httpx|requests|OpenRouter|APIRouter|add_api_route" backend/app/services/telegram_ingestion.py backend/app/services/telegram_update_parser.py backend/app/api/routes/telegram_webhook.py
```

Expected: focused tests pass; static scan has no newly introduced networking/Provider/route construction. If the local PostgreSQL fixture is needed, set `DATABASE_URL` only temporarily to the approved `STAGE06_LOCAL_DATABASE_URL`, restore it after the command and record that the default database has the previously known isolated revision risk. Do not conceal a failed migration command.

## Report

Write `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-3-report.md` with changed files, exact RED/GREEN evidence, relevant PostgreSQL evidence if any, static/privacy scans, scope exclusions, remaining risks and cleanup. Explicitly state whether any existing route file changed, and if so that the public endpoint/response/policy remained unchanged. Return only status, one-line verification, concerns and report path.
