# Stage09 r60 多表中文评测发布与运行证据

## Status

- Artifact: `stage09-p1-20260727-r60-multitable-chinese-evaluation`
- Scope: deploy the dedicated three-CSV import/link evaluation utility, then perform one service-account fixture import and one bounded real OpenRouter 20-case batch.
- Excluded: migration, runtime environment change, Telegram, draft/write workflow, notification, provider write and all non-fixture data.

## Local Gates

- `test_stage09_multitable_chinese_eval.py`, `test_stage06_template_import.py`, and `test_stage08_openrouter_analysis_provider.py`: `48 passed`.
- Mini App production build: passed; static entry remains `assets/index-CRyRxsFj.js`.
- Candidate activation must validate sealed layout/assets, release manifest, static parity, service-account import and bounded readiness before switching all three links.

## Expected Server Operation

1. Activate r60 atomically with r59 retained for rollback.
2. Run `stage09_multitable_chinese_eval.py --import-persisted` once as the restricted service account with runtime values loaded only in the privileged shell.
3. Run the same module without flags once to emit a fictional-query/answer JSON report. The process is bounded to 45 seconds per case and no retry expands data scope.
4. Copy only the report payload to this local evidence package, render Markdown, and record aggregate metrics verbatim.

## Execution Result

- Candidate source, venv and static artifacts passed sealed layout, release-asset, manifest and static-parity gates before activation. Bounded readiness passed after the three `current` links switched atomically; the previous r59 artifact remains the rollback target.
- The restricted service account imported the fictional fixture once: `table_count=3`, `record_count=32`, `relation_field_count=2`, `edge_count=26`, status `imported`.
- The bounded real OpenRouter batch finished 20/20 Chinese cases with zero timeout/error. Its full fixture-only results, skills and scoring receipt are retained in `stage09-multitable-chinese-real-llm-report-2026-07-27.md`.
- The r60 sealed source was built before a SQLAlchemy flush correction discovered during the first fixture attempt. The successful service-account import used the audited corrected runner from a temporary server path. r61 subsequently sealed and activated that exact correction; see `stage09-r61-multitable-import-flush-deployment-2026-07-27.md`.

## Safety Receipt

- The import created only the documented dedicated fictional evaluation Base. It neither reads nor modifies user-owned bases.
- No Telegram send, draft, notification, migration, provider write or raw database operation occurred.
- The real-provider request path received the bounded permission-filtered fixture context only; credentials, raw prompts and request identifiers are not retained in this evidence.
