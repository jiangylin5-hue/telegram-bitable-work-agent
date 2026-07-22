# Stage08 Package D / D2 Independent Review Brief

Review D2 source/chunking/UoW/outbox implementation and write findings only to
`.superpowers/sdd/stage08-package-d-task-d2-review-report.md`. Do not edit
implementation/tests/models/migrations/database/Docker/Git/external state.

Read the D2 brief/report, Package D data contract/BDD/plan, D1 contracts, and
all D2 allowed files before reviewing.

Required checks:

1. Confirm scope: no embedding/chunk persistence/search/API/external call and
no D1/C1/C2/B contract or migration edit. UoW's six new methods must have
Protocol/InMemory/SQLAlchemy parity, deterministic exact lists and source-row
`FOR UPDATE` lifecycle lock.
2. Attack canonicalization/chunking: controls/NFC/newline, 1200/200 bounds,
unicode code points, CJK/Latin terms, 256 term cap, hash/order determinism,
1M/1000 reject-with-no-partial output, no provider/transport import.
3. Validate Memory adapter really calls read-only projection before forming
text, never directly reads `item.payload`, rejects group scope and Telegram
source metadata, emits projection text only from memory type + current safe
payload, and exposes no IDs/scope/source refs in text/result/repr/errors/outbox.
4. Verify exact outbox type/aggregate/idempotency/payload reference fields,
same source version replay, changed-version source replacement, revoke text
scrub/one cleanup event, and no worker/audit/write side effects outside source/
outbox state.
5. **Lifecycle-design audit:** determine whether the brief-mandated logical
fingerprint `sha256("memory_item:" + item_id)` remains compatible with actual
Stage08 Memory supersession, which normally creates a new item ID. Compare it
to D's required replacement/delete/revoke lifecycle. State explicitly whether
this creates a functional stale-index/cleanup gap, whether present reread
paths fail closed, and whether it must block D2. Do not dismiss it merely
because the brief specified the formula; a contract conflict is a real finding.
6. Independently run focused D2, D1+D2 and Memory+D2 suites with `-W error`,
compile/static raw/import scans and diff check. Record commands/results and
C/I/M PASS/FAIL. D2 cannot be declared complete until any Important issue is
resolved; no Package D completion claim.
