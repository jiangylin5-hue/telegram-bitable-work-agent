# Stage07 Persisted Marker Bridge Design

## Status

- Status: `approved-direction; C runtime-layout correction selected`.
- Decision: the user first selected the read-only persisted-marker bridge on 2026-07-14 after direct Bot API polling repeatedly failed to observe a private marker that the existing Stage03 webhook demonstrably persisted. After the single-file mount boundary was demonstrated, the user selected runtime-layout option C on 2026-07-14.
- Scope: one non-production, one-time target bootstrap for the already approved isolated Stage07 acceptance environment.
- Non-goal: this is not a general Stage03-to-Stage07 data migration, a new product API, a webhook consumer, or a permanent integration.

## Evidence and Problem Statement

The configured Bot identity is publicly `@BitableAgentBot` with display name `BitableWorkAgentBot`; the user supplied evidence of the matching private chat. Five approved 120-second polling attempts resulted in four `blocked` receipts with webhook restoration and one early Bot API failure. The most recent marker was sent while polling was active but remained absent from `getUpdates`.

A read-only SQLAlchemy query inside the existing Stage03 API container then found three recent rows whose text was exactly `/stage07-bind` and whose stored chat/user values matched the private-chat invariant. No identifier, raw message, token, secret or webhook URL was emitted. Therefore the existing Stage03 webhook persistence is the proven durable, auditable source for this one-time bootstrap.

## Chosen Architecture

```text
user sends one fresh /stage07-bind in Bot private chat
  -> existing Stage03 webhook and existing Message persistence
  -> one-time bridge runs inside the existing Stage03 API image via SQLAlchemy ORM
  -> exact/fresh/private-invariant candidate is selected
  -> protected in-process pipe (never terminal output)
  -> existing Stage07 atomic env writer
  -> ignored runtime/.env.stage07-acceptance receives only 3 target keys
  -> Stage07 restricted-test validator may start API/Worker
```

The bridge queries the existing `Message` SQLAlchemy model. It does not use raw SQL, write Stage03 data, alter the Stage03 webhook, stop Stage03 containers, add a route, change an existing environment file, or introduce a Stage03 schema/index migration. It writes only to the ignored, mode-`0600` Stage07 isolated runtime file through the already tested atomic writer.

## Candidate Contract

An eligible marker must satisfy every condition:

| Check | Rule | Failure result |
| --- | --- | --- |
| Marker | `raw_text` is exactly `/stage07-bind` | `blocked` |
| Type | stored `message_type` is `text` | `blocked` |
| Freshness | `received_at >= bind_window_not_before_utc` and not later than bridge execution time | `blocked` |
| Private invariant | `telegram_chat_id` and `telegram_user_id` are both non-empty and equal | `blocked` |
| Ambiguity | exactly one eligible candidate exists for the newly opened window | `blocked` |
| Stage03 access | existing API container ORM query succeeds, read-only | `failed` |
| Stage07 write | atomic isolated-env writer succeeds after selection | `captured`; writer failure is `failed` |

The execution operator creates a fresh not-before timestamp immediately before instructing the user to send one marker. Earlier markers are intentionally ignored. This prevents a prior chat message or a different actor's old command from becoming an unreviewed target.

## Data Handling and Receipts

The selector's raw candidate exists only in the Stage03 container process, the protected command-substitution pipe and the short-lived Stage07 writer process. It must not be echoed, logged, written to a non-ignored file, placed in a Docker image layer, appear in a command line, evidence artifact or chat response.

The writer changes exactly these existing isolated runtime keys:

```text
TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS
STAGE06_TELEGRAM_TEST_CHAT_ID
STAGE06_TELEGRAM_TEST_USER_ID
```

It retains every other line and sets the target file mode to `0600`. The externally visible receipt is fixed and sanitized:

```json
{"ok": true, "status": "captured", "source": "stage03_persisted_marker"}
```

Blocked/failed receipts must contain no candidate count, message text, timestamp, chat/user identifier, token, secret, database URL, webhook URL or exception text.

## Failure and Rollback

- No candidate, stale candidate, non-text record, private-invariant failure or ambiguity: no target write, return `blocked`, retain Stage03 and isolated runtime state.
- ORM/database/pipe/atomic-write failure: return `failed`, do not start delivery-capable Stage07 services.
- A successful target write is not a send authorization. The existing `restricted_test` validator, synthetic fixture, TD008 confirmation and one-send reservation still apply.
- No Stage03 rollback is required because no Stage03 state is mutated. If post-bootstrap acceptance stops, remove the isolated runtime environment/volumes according to S6.3 cleanup policy.

## Runtime Mount Correction (Decision Resolved)

The first two live bridge invocations proved that the selector, candidate validation and writer logic are correct, but no target was written. The cause is Linux bind-mount semantics: the existing writer intentionally creates a sibling temporary file and atomically replaces the target; a container cannot atomically replace a single file that is itself a bind-mount target. This is a runtime boundary issue, not a Telegram, Stage03 ORM or identifier issue.

| Option | Change | Benefit | Cost / rejection rule |
| --- | --- | --- | --- |
| A — mount isolated deployment directory (recommended) | Mount the existing isolated `deploy/stage07-acceptance` directory at `/run/stage07`; call the same writer on `/run/stage07/.env.stage07-acceptance` | preserves the tested atomic writer and needs no Stage03 change, host helper or config migration | the short-lived trusted Stage07 image receives write visibility to the isolated deployment directory; wrapper must still mount no Stage03 path and write only the target env file |
| B — host-side atomic writer | Keep a file-only container mount, but invoke an explicitly reviewed host helper to perform the final atomic replacement | smallest container mount surface | duplicates/rehosts the existing writer behavior and adds a host-Python trust/runtime dependency |
| C — dedicated isolated runtime directory | Move the ignored env into a dedicated mounted directory and retarget Compose's env-file path | narrowest long-term mount and clean ownership | changes the Compose runtime-file layout and requires a separate migration/revalidation of all deployment commands |

No option may reuse the current single-file mount. A new live bridge attempt must not run until the user selects one option; it must use a fresh marker window and retain the no-automatic-retry rule.

## C-Selected Runtime Layout

Option C is selected. The ignored runtime env moves to `deploy/stage07-acceptance/runtime/.env.stage07-acceptance`; the dedicated `runtime/` directory is mode `0700` and the file is mode `0600`. Both are owned by the isolated deployment operator that executes the wrapper, so the directory remains private without making the wrapper fail closed solely because a root-owned directory is not traversable. Compose defaults and all documented commands resolve the same file through `STAGE07_ENV_FILE=runtime/.env.stage07-acceptance`.

The short-lived writer mounts only `runtime/` at `/run/stage07:rw` and invokes the existing atomic writer on `/run/stage07/.env.stage07-acceptance`. This permits sibling-temp-file atomic replacement but does not mount the deployment source tree or any Stage03 path. Because the short-lived container performs the atomic replace as `root`, the wrapper restores the target file to the invoking deployment user's UID/GID and mode `0600` before it emits a `captured` receipt. A failed ownership restoration is `failed`, not a successful bootstrap. Options A and B are not selected. The runtime migration, Compose validation, isolated API rebuild and temporary directory-mounted atomic-write probe have passed. One fresh user marker window is still required, with no automatic retry.

## Verification Plan

Before any live bridge execution, tests must first fail for: fresh exact private candidate selection, stale/group-equivalent rejection, multiple-candidate rejection, sanitized receipt and no-write-on-blocked behavior. The focused helper suite and existing capture-writer regression must pass before deployment. Live evidence is limited to a sanitized receipt, a safe restricted-test preflight result and later health/controlled-delivery evidence; it must never display the captured identifiers.

## Explicit Exclusions

- no Stage03 `Message` table migration, index, trigger, retention change or index backfill;
- no Stage03 API route, Mini App route, product permission or digital-employee authority change;
- no broad chat discovery, historical user import, group/channel support or repeated polling;
- no raw PostgreSQL shell, `psql`, raw SQL string or secret/identifier display;
- no outbound Telegram call as part of target bootstrap.
