# Stage09 r61 多表导入修正发布证据

## Status

- Artifact: `stage09-p1-20260727-r61-multitable-import-flush`
- Purpose: seal the SQLAlchemy flush correction used by the Stage09 fictional multi-table import, so the deployed source exactly contains the implementation exercised by the real server import.
- Rollback: `stage09-p1-20260727-r60-multitable-chinese-evaluation` remains retained.

## Candidate Construction

1. Copied the already sealed r60 source, venv and static artifacts into same-ID r61 candidate locations.
2. Replaced only `backend/scripts/stage09_multitable_chinese_eval.py` with the audited source containing flushes after workspace creation, import-job creation and import-job commit.
3. Regenerated the external static artifact ID and SHA-256 manifest. No UI code or build output changed.
4. Created an external release manifest. The sealed candidate passed release layout, release assets and static source/venv/static parity checks.
5. Ran a service-account import-module load check. This verified the released runner imports under its actual runtime account without performing another fixture import.

## Activation and Verification

- Source, venv and static `current` links switched atomically from r60 to r61.
- API, worker and outbox services restarted; Nginx and Redis were not reconfigured.
- The bounded activation readiness gate passed after the switch.
- The earlier r60 one-time fixture import is retained as the data-operation receipt: three tables, 32 fictional records, two relation fields and 26 normalized relation edges.
- No migration, Telegram send, draft, notification, non-fixture data access or provider write occurred during r61.

## Operational Note

The first r61 static-manifest attempt was rejected by the static-parity gate because the temporary manifest file was accidentally included in the file list. The candidate was not activated. The manifest was regenerated excluding its temporary file; parity then passed. This demonstrates the gate prevented an inconsistent static artifact from reaching `current`.

## Cleanup

- Removed the exact `/tmp/stage09-r60-*` and `/tmp/stage09-r61-*` upload, runner, diagnostic and report artifacts after their local evidence had been written and r61 parity was re-read.
- Retained r60 as the explicit rollback artifact and retained the fictional evaluation Base for reproducibility. Neither is a temporary file.
