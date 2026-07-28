# Stage09 r59 Conversational Entry Deployment Evidence

## Status

- Artifact: `stage09-p1-20260727-r59-conversational-entry-routing`
- Scope: the normal Ledgerline conversational entry route and Chinese `general_advice` language-refusal fallback.
- External effects permitted: sealed source/venv/static candidate upload, bounded native-service activation and read-only readiness checks.
- Explicitly excluded: database migration or business writes, Telegram sends, provider writes, permission changes and draft confirmation.

## Local Verification Before Packaging

- `mini-app` focused app-flow/workbench suite: `27 passed, 2 skipped`.
- Full Mini App suite: `77 files passed, 403 passed, 2 skipped`.
- Provider plus real-evaluator fixture unit suites: `82 passed`.
- `npm.cmd run build`: passed; the Vite entry bundle is `assets/index-CRyRxsFj.js`.
- `git diff --check`: no whitespace error; repository line-ending conversion warnings are non-failing and pre-existing.

## Candidate/Activation Contract

1. Package current source while excluding inactive historical runtime example material that the sealed release-layout gate forbids.
2. Build a matching static artifact with a manifest and artifact-id marker.
3. On the server, create immutable candidate directories for source, venv and static; verify checksums, release layout/assets and static parity before changing any `current` symlink.
4. Use the existing bounded 40-second readiness gate during atomic activation. Any activation failure must restore all three previous links and restart only the affected Stage09 services.
5. Record only redacted results: link targets, unit states, HTTP status classes and verifier pass/fail. Do not record credentials, prompts, customer rows or Provider answers.

## Deployment Result

- Candidate upload checksums matched before extraction.
- Candidate gates passed: sealed release layout, release assets, deterministic release manifest, static artifact parity and an import of `app.main` as the service account.
- A first activation attempt failed closed because the orchestration command omitted the verifier's required `--verify` argument. Its rollback restored all three r58 links; read-only checks then confirmed r58 services and public/loopback health were `200`.
- The same r59 readiness verifier passed in read-only mode with the required argument. A corrected one-time activation then atomically switched all three links to r59 and passed the bounded readiness gate.

## Post-Activation Readback

| Check | Result |
| --- | --- |
| source link | `stage09-p1-20260727-r59-conversational-entry-routing` |
| venv link | `stage09-p1-20260727-r59-conversational-entry-routing` |
| static link | `stage09-p1-20260727-r59-conversational-entry-routing` |
| API / worker / outbox / Redis / Nginx | all `active` |
| API loopback health | HTTP `200` |
| public HTTPS health | HTTP `200` |
| public HTML entry | references `assets/index-CRyRxsFj.js` |

No database migration, business record write, Telegram send, provider write or permission mutation was made. The deployment verifies delivery and readiness, not an authenticated conversational answer. A redacted browser submission of `你好` remains the final live UI evidence.

## Temporary Cleanup

- Removed the exact r59 source/static transfer archives and candidate/activation scripts from server `/tmp`; a read-only exact-name check returned no remaining `stage09-r59-*` file.
- Retained the active r59 source/venv/static directories, its root-only release manifest and the prior r58 release as rollback material.
