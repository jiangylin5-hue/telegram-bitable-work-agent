# Stage07 Persisted Marker Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely bootstrap the isolated Stage07 restricted-test target from one fresh, exact private marker already persisted by the unchanged Stage03 webhook.

**Architecture:** A new dual-mode Python helper is sent over stdin to the existing Stage03 API container for a read-only SQLAlchemy ORM selection, then receives its selected JSON through stdin in the isolated Stage07 image to atomically update the existing ignored target env file. A small remote shell wrapper holds raw candidate JSON only in a non-echoed process variable and emits one sanitized receipt. No product route, migration, index, Stage03 write or Telegram API call is introduced.

**Tech Stack:** Python 3.12, SQLAlchemy 2.x existing `Message` model, existing Stage07 target env writer, POSIX shell, Docker Compose/Docker exec, pytest.

## Global Constraints

- The existing `telegram-bitable-stage03` containers, PostgreSQL, Redis, webhook, runtime file and source are read-only for this bridge.
- The source selector must use the existing SQLAlchemy model/session factory; raw SQL and `psql` are prohibited.
- A candidate is valid only when marker, text type, explicit freshness window, non-empty IDs and `telegram_chat_id == telegram_user_id` all match, and it is the sole eligible candidate.
- Only `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS`, `STAGE06_TELEGRAM_TEST_CHAT_ID` and `STAGE06_TELEGRAM_TEST_USER_ID` may change in the ignored isolated env file.
- No raw candidate/identifier/token/secret/webhook URL may reach stdout, stderr, logs, CLI arguments, source or evidence.
- A bridge success is not delivery acceptance; existing restricted-test preflight, TD008 confirmation/reservation and cleanup gates still apply.

---

### Task 1: Implement and test pure persisted-marker selection

**Files:**
- Create: `backend/scripts/stage07_import_persisted_private_target.py`
- Create: `backend/tests/unit/test_stage07_import_persisted_private_target.py`

**Interfaces:**
- Consumes: an iterable of `PersistedMarkerCandidate`, `marker: str`, `not_before: datetime`, `now: datetime`.
- Produces: `select_eligible_persisted_marker(...) -> PersistedMarkerCandidate | None` and `build_persisted_marker_receipt(status: str) -> dict[str, object]`.

- [x] **Step 1: Write failing tests**

```python
def test_selects_one_fresh_exact_private_marker() -> None:
    candidate = PersistedMarkerCandidate(
        chat_id="private-chat", user_id="private-chat", text="/stage07-bind",
        message_type="text", received_at=NOW,
    )
    assert select_eligible_persisted_marker(
        [candidate], marker="/stage07-bind", not_before=WINDOW_START, now=NOW
    ) == candidate

def test_rejects_stale_non_private_and_ambiguous_candidates() -> None:
    assert select_eligible_persisted_marker([...], marker="/stage07-bind", not_before=WINDOW_START, now=NOW) is None

def test_sanitized_receipt_omits_candidate_identifiers() -> None:
    receipt = build_persisted_marker_receipt(status="captured")
    assert receipt == {"ok": True, "status": "captured", "source": "stage03_persisted_marker"}
```

- [x] **Step 2: Run the new test file and verify RED**

Run: `python -m pytest -q tests/unit/test_stage07_import_persisted_private_target.py`

Expected: collection/import failure because the helper module does not yet exist.

- [x] **Step 3: Write minimal pure implementation**

```python
@dataclass(frozen=True)
class PersistedMarkerCandidate:
    chat_id: str
    user_id: str
    text: str
    message_type: str
    received_at: datetime

def select_eligible_persisted_marker(candidates, *, marker, not_before, now):
    eligible = [candidate for candidate in candidates if ...]
    return eligible[0] if len(eligible) == 1 else None
```

The filter must enforce every global candidate condition and normalize all input timestamps to UTC before comparison.

- [x] **Step 4: Run the new test file and verify GREEN**

Run: `python -m pytest -q tests/unit/test_stage07_import_persisted_private_target.py`

Expected: all selector/receipt tests pass.

### Task 2: Add dual-mode ORM selection and atomic isolated-env application

**Files:**
- Modify: `backend/scripts/stage07_import_persisted_private_target.py`
- Modify: `backend/tests/unit/test_stage07_import_persisted_private_target.py`

**Interfaces:**
- Consumes: `--select --not-before-utc <RFC3339>` inside the existing Stage03 API image; `--apply-stdin --env-file <path>` inside the Stage07 acceptance API image.
- Produces: selector JSON only to the protected caller pipe; a fixed sanitized apply receipt to stdout.

- [x] **Step 1: Write failing tests for the runtime boundary**

```python
def test_apply_stdin_writes_only_existing_target_keys(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.stage07-acceptance"
    env_file.write_text("UNCHANGED=kept\nTELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS=\n", encoding="utf-8")
    apply_persisted_target(env_file, {"chat_id": "private", "user_id": "private"})
    assert "UNCHANGED=kept" in env_file.read_text(encoding="utf-8")

def test_selection_payload_is_rejected_when_candidate_is_invalid() -> None:
    assert parse_selected_candidate({"status": "candidate", "candidate": {}}) is None
```

- [x] **Step 2: Run the affected tests and verify RED**

Run: `python -m pytest -q tests/unit/test_stage07_import_persisted_private_target.py`

Expected: fail because the runtime apply/parser functions are missing.

- [x] **Step 3: Write minimal runtime implementation**

`--select` lazily imports `get_session_factory` and `Message`, reads only `Message` rows, maps them into the tested dataclass and prints a candidate JSON only for the parent shell's captured pipe. `--apply-stdin` accepts that JSON from stdin, validates its exact shape, calls the existing `write_private_target_to_env` function and prints only `build_persisted_marker_receipt(status="captured")`. All parse/ORM/write exceptions are converted to fixed sanitized `blocked`/`failed` output; no exception string is emitted.

- [x] **Step 4: Run focused helper and existing capture-writer regressions**

Run: `python -m pytest -q tests/unit/test_stage07_import_persisted_private_target.py tests/unit/test_stage07_capture_restricted_test_target.py tests/unit/test_stage06_backend_smoke_scripts.py`

Expected: all tests pass without printing identifiers.

### Task 3: Add the remote non-echoing deployment wrapper

**Files:**
- Create: `deploy/stage07-acceptance/scripts/import-persisted-private-target.sh`
- Modify: `deploy/stage07-acceptance/scripts/validate-runtime-presence.sh`
- Modify: `deploy/stage07-acceptance/.env.stage07-acceptance.example`

**Interfaces:**
- Consumes: source helper path, existing Stage03 API container name, isolated env file and an operator-supplied RFC3339 bind-window start.
- Produces: fixed `captured`/`blocked`/`failed` receipt; no raw value output.

- [x] **Step 1: Write shell-contract tests**

```python
def test_bridge_wrapper_never_echoes_the_target_payload() -> None:
    script = Path("../deploy/stage07-acceptance/scripts/import-persisted-private-target.sh").read_text(encoding="utf-8")
    assert "set -x" not in script
    assert "printf '%s\\n' \"$candidate_json\"" not in script
    assert "docker exec -i" in script
    assert "docker run -i" in script
```

Add an assertion that the runtime preflight accepts a non-empty exact-one allowlist and rejects an empty/multi-value one without exposing its value.

- [x] **Step 2: Run the test and verify RED**

Run: `python -m pytest -q tests/unit/test_stage07_import_persisted_private_target.py`

Expected: fail because the wrapper/example contract does not yet exist.

- [x] **Step 3: Implement the wrapper**

The wrapper must use `set -eu`, never `set -x`, execute selector source through `docker exec -i "$STAGE03_API_CONTAINER" python - --select`, retain its success payload in a shell variable without echoing, pipe it through `docker run -i` to `--apply-stdin`, and remove/avoid all temporary plaintext files. It must require an explicit `--not-before-utc` argument, reject an unset container/path or malformed timestamp before contacting Stage03, and emit only the isolated helper's sanitized receipt. The example env adds only non-secret names/defaults for `STAGE03_API_CONTAINER` and does not contain the timestamp or target identifiers.

- [x] **Step 4: Run focused tests and shell syntax checks**

Run: `python -m pytest -q tests/unit/test_stage07_import_persisted_private_target.py tests/unit/test_stage07_capture_restricted_test_target.py tests/unit/test_stage06_backend_smoke_scripts.py`

Run: `sh -n deploy/stage07-acceptance/scripts/import-persisted-private-target.sh`

Expected: all focused tests pass and shell syntax check is silent.

### Task 3b: Apply the C-selected dedicated runtime-directory correction

**Files:**
- Move: `deploy/stage07-acceptance/.env.stage07-acceptance.example` -> `deploy/stage07-acceptance/runtime/.env.stage07-acceptance.example`
- Modify: `deploy/stage07-acceptance/compose.yml`
- Modify: `deploy/stage07-acceptance/scripts/import-persisted-private-target.sh`
- Modify: `backend/tests/unit/test_stage07_import_persisted_private_target.py`

- [x] **Step 1: Write failing runtime-layout contract tests**

Require all four Compose service `env_file` defaults to use `runtime/.env.stage07-acceptance`. Require the wrapper to mount `runtime/` rather than a single env file and to keep the no-source/no-Stage03-mount boundary.

- [x] **Step 2: Implement the C runtime layout**

Move the versioned example into `runtime/`; retarget Compose and the wrapper. The wrapper mounts only the `runtime/` directory and invokes the existing atomic writer at `/run/stage07/.env.stage07-acceptance`.

- [x] **Step 3: Run focused tests and remote migration/revalidation**

Run the existing focused helper/capture regressions, Compose expansion and shell syntax check. On the isolated server, create `runtime/` at mode `0700`, move the ignored env to the documented location, set mode `0600`, rebuild only the isolated API image, and rerun safe argument/preflight checks. Do not call the selector or write a target in this step.

### Task 4: Safely stage and execute the one-time bridge

**Files:**
- Modify: `project-docs/08-implementation/STAGE_07_PROGRESS.md`
- Modify: `project-docs/08-implementation/evidence/stage07-final-acceptance-closure.md`
- Modify: `project-docs/08-implementation/STAGE_07_S6_ISOLATED_ACCEPTANCE_DEPLOYMENT_BDD_AND_ACCEPTANCE.md`

**Interfaces:**
- Consumes: approved bridge assets, one new user-sent marker after the not-before timestamp, existing Stage03 API container and ignored isolated env file.
- Produces: sanitized target-bootstrap receipt, exact-one preflight status and unchanged Stage03 verification.

- [x] **Step 1: Sync only the reviewed helper/wrapper assets to the existing isolated remote source**

Use `scp` plus `sudo install -m 755` for shell assets and `-m 644` for Python assets. Do not copy `.env`, `.local`, keys, source archives or Stage03 files.

- [x] **Step 2: Rebuild the isolated API image and run the focused remote helper in a dry safe mode**

Run remote Compose build for the API image. Verify `--help` and wrapper argument rejection only; do not call the selector until a fresh marker window is opened.

- [x] **Step 3: Open one explicit bind window and invoke the wrapper after the user sends one marker**

Record the UTC not-before instant before asking the user to send exactly one marker. Run the wrapper once. If its fixed receipt is not `captured`, do not retry automatically and do not start Stage07 API/Worker.

- [x] **Step 4: Verify the isolated restricted-test preflight and unchanged Stage03 boundary**

Run `validate-runtime-presence.sh` against the ignored isolated env and verify only configured/shape statuses. Verify Stage03 HTTPS health remains `200`; inspect Stage03 container names/status without printing its configuration. Start Stage07 API/worker only after the preflight passes.

- [x] **Step 5: Update evidence with receipt/status only**

Record the bridge source, fixed result, preflight result, Stage03-before/after health and explicitly retain the no-send/no-Caddy claim until later S6.3 steps prove otherwise.

### Task 4b: Run one fresh C-layout bridge window

**Files:**
- Modify: `project-docs/08-implementation/STAGE_07_PROGRESS.md`
- Modify: `project-docs/08-implementation/evidence/stage07-final-acceptance-closure.md`
- Modify: `project-docs/08-implementation/STAGE_07_S6_ISOLATED_ACCEPTANCE_DEPLOYMENT_BDD_AND_ACCEPTANCE.md`

- [x] Record a new UTC not-before instant, ask the user to send exactly one `/stage07-bind` in the existing private Bot chat, and invoke the wrapper exactly once after confirmation.
- [x] Accept only a fixed `captured` receipt; otherwise retain fail-closed state without retry.
- [x] If captured, rerun the restricted-test preflight and Stage03 health boundary before starting any delivery-capable service; otherwise retain the empty allowlist and report the terminal receipt.
