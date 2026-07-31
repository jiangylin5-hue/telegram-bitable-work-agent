# Stage12-A Evaluation V2 Focused Baseline Evidence

## Status

- Status: PASS for the Stage12-A evaluator foundation
- Scope: contracts, 48-case truth/audit files, typed layer scorers, leak-free runner, Stage11 trace adapter, executable service-layer fixture and focused deterministic verification
- Not included: 48 Case × 3 real-LLM campaign, production deployment, Telegram send, real business writes, PostgreSQL fixture replay
- Gold review state: `agent_audited_pending_human_signoff`; no human approval is claimed

## Frozen sources

| Artifact | SHA-256 |
| --- | --- |
| `stage12_complex_cases_v2.json` | `c1c2ccc0b1e2a73d40ed130d9b1ad80787426b14363a2720f54e3b7de71e2624` |
| `stage12_complex_cases_v2.audit.json` | `2679c802a6103482564b69b2d8e993ebe0b282d982a305f3d7265bb6df59a1d5` |
| canonical fixture snapshot | `b98dfd2d0e3713c8aacd89de33100373e849a0bc7aaeeca4663bb8542aa0098c` |
| immutable Stage11 r75 JSON | `726651914241906634b665ff484e88cf9074a61c325be0344ffea1b0661a6ded` |

Truth has 48 unique cases and 48 audit entries. The fixture materializer creates seven tables through existing Stage06 service APIs and verifies typed fields, linked targets, defaults, record values, versions, relation edges and read/write ACLs. A mutation test proves changed data no longer passes by returning the expected snapshot blindly.

## Verification

Focused Stage12-A and legacy compatibility suite:

```text
58 passed in 2.66s
```

Backend regression with unavailable PostgreSQL-only historical files explicitly excluded and optional database variables cleared:

```text
1714 passed, 132 skipped in 142.57s
```

`python -m compileall -q app scripts` passed. `git diff --check` passed. Alembic has one head, `20260728_0034`. Ruff is not installed, so no lint pass is claimed.

An attempted full run with the configured local PostgreSQL reached migration setup but the configured role cannot execute `CREATE EXTENSION vector`. With the database variable cleared, four historical PostgreSQL files that do not carry their own `skipif` produced 15 setup errors; all other tests produced `1714 passed, 132 skipped`. These are recorded as environment/historical-test constraints, not hidden as a green PostgreSQL result.

## Historical baseline interpretation

The Stage11 r75 score `83.8144` remains an immutable coarse baseline. It does not contain V2 Query trace, Retrieval candidate/evidence identities, typed claims or ActionSlot trace. Those layers are therefore `not_observed`; no answer regex was used to fabricate them.

## Safety and deferrals

- Real Provider calls: 0
- Telegram sends: 0
- Real business writes: 0
- Draft confirmations: 0
- Gold values in execution payloads: rejected by the leak guard tests
- 48 Case × 3 real-LLM evaluation: deferred until Stage12 final acceptance by the user's technical-architecture-first priority
- Gold recomputation through the deterministic Authorized Query Engine: deferred until Stage12-C provides that engine; current Gold is source-audited and hash-frozen, not claimed as human approved
- PostgreSQL replay: deferred until an authorized disposable database with pgvector extension support is available
