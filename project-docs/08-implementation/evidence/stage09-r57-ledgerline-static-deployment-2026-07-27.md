# Stage09 r57 Ledgerline Static Deployment — 2026-07-27

## Status

- Status: `activated; authorized-browser-visual-acceptance-pending`
- Candidate: `stage09-p1-20260727-r57-ai-workbench-static`
- Scope: deliver the tested Stage09 source, copied runtime environment and complete Vite static artifact as one matching candidate, replacing the public r39 static artifact that still exposed the legacy AI form.
- Non-goals: database migration, schema change, record/Base/import write, draft confirmation, Telegram send, provider/LLM invocation, permissions change or ingress configuration change.

## Trigger And Root Cause

The public workbench was observed in an authenticated user browser to open the old `AUTHORIZED AI COLLABORATION` three-column form when the user selected `AI 对话`. A read-only server probe resolved the public static `current` link to `stage09-p1-20260725-r39`; its root page referenced `index-ClvZQGCh.js` and `index-CBGJFEX0.css`.

The current source already routes all visible `AI 对话` entries to `CollaborationWorkbench`; the old `AssistantContextWorkbench` is retained only for explicitly named `智能汇总` and authorized context inspection. The defect was therefore split-artifact drift: the active source was newer while the browser static artifact remained r39.

## Candidate Construction

The candidate was assembled from the tested Stage09 worktree:

1. Build the production Mini App with `npm.cmd run build`.
2. Seal a source directory without `.git`, `node_modules`, runtime env files, secrets or full static assets; retain only `mini-app/dist/browser-handoff.html` required by the source-release contract.
3. Package the complete `mini-app/dist` separately as the static directory, add `.stage09-static-artifact-id`, and generate `static-manifest.sha256` over every regular static file except the manifest itself.
4. Copy the existing candidate-compatible Python environment into a new non-symlinked venv directory so the sealed static-parity verifier can reject traversal. Verify the copied interpreter imports the required runtime modules before activation.
5. On the server, validate the sealed release layout, create the deterministic source manifest, validate release assets, and run the source/venv/static parity verifier before any `current` link changes.

The local package staging directory is temporary and excluded from the repository. It contains no runtime env file, credential, customer record, Telegram init-data or provider payload.

## Local Verification Before Upload

| Command | Result |
| --- | --- |
| `npm.cmd test -- --run src/test/collaboration-app-flow.test.tsx src/test/assistant-context-app-flow.test.tsx src/test/collaboration-workbench.test.tsx --maxWorkers=1` | `26 passed`, `2` historical skips |
| `deploy/stage09-native/scripts/test-static-artifact-parity.sh` | PASS |
| `npm.cmd run test:run` | `77` files, `402 passed`, `2` historical skips |
| `npm.cmd run build` | PASS; emitted `index-CmyAhrfN.js`, `index-DEC6HgNm.css`, and separated React/Query/icon chunks |
| `python -m pytest -q tests/unit` | `1370 passed`, `1` POSIX-only server-shell skip |
| `git diff --check` | PASS; only existing line-ending advisories |
| `deploy/stage09-native/scripts/test-release-assets.sh` | PASS |

## Server Candidate Gate

The server-side candidate gates passed before activation:

```text
release-layout: pass
release-manifest: pass
release-assets: pass
static-parity: pass
```

The first static-parity attempt intentionally failed before any link change because a straight venv copy retained Python symlinks, which the sealed verifier rejects. The candidate venv was recreated by dereferencing that copied environment; it then passed the no-link invariant and Python import check. This is retained as a real fail-closed gate result, not suppressed.

## Activation And Post-Activation Checks

Activation changed only the three Stage09 candidate links and restarted only `stage09-p1-api`, `stage09-p1-worker` and `stage09-p1-outbox-bridge`. The activation script stored the previous targets and would restore all three and restart those same services if restart or readiness failed.

```text
static-parity: pass
readiness-gate: pass
stage09-activation: pass
artifact-id: stage09-p1-20260727-r57-ai-workbench-static
```

Post-activation read-only checks confirm:

| Check | Result |
| --- | --- |
| Public `GET /` | HTTP `200`; references `index-CmyAhrfN.js`, `index-DEC6HgNm.css`, `rolldown-runtime-Bh1tDfsg.js`, `vendor-react-CabwUXhB.js`, `vendor-query-BKbANQrJ.js`, `vendor-icons-CUJOQM0z.js` |
| Public `GET /health` | HTTP `200` |
| Active venv/static candidate | both resolve to r57 |
| API, worker, outbox, Redis and Nginx | all `active` |

## Remaining Acceptance Boundary

This deployment proves the public host now serves the new tested r57 static artifact, rather than the r39 bundle shown in the user screenshot. It does **not** by itself prove an authenticated visual flow: an authorized browser must refresh the workbench, click `AI 对话`, and retain a screenshot showing the Ledgerline dialog with its context header, timeline, safe-scope rail, skill controls and bottom composer. The legacy three-column modal is a rejection condition.

## Cleanup

- No database, business record, import, draft, Telegram or provider write occurred.
- The uploaded temporary tarballs remain only until post-activation visual acceptance is captured; they are not release inputs after candidate extraction and should be removed during final Stage09 cleanup.
- No Git staging, commit, push or history rewrite occurred in this deployment step.
