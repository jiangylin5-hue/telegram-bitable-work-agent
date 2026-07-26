# Stage09 Codex-style AI Conversation SSE — Task5 Transport Evidence

## Status

- **Status:** Task5 transport asset evidence only; not whole-stage acceptance.
- **Date:** 2026-07-26
- **Scope:** Exact-route Nginx rendering contract for `POST /api/stage08/assistant/query-stream`.
- **Worktree:** `D:\telegram多维表格和工作智能体的开发\.worktrees\stage09-ai-conversation-sse`
- **Branch:** `codex/stage09-ai-conversation-sse`
- **Approved base:** `b57b152 docs(stage09): add AI conversation handoff`
- **HEAD observed:** `46de92a`

## Change Boundary

Only the two Stage09 Nginx templates and their repository-only render-and-inspect
scripts were changed for this task. Both templates now contain one exact
`location = /api/stage08/assistant/query-stream` block before the generic
`location /` fallback. The block preserves the existing loopback upstream
`http://127.0.0.1:18080` and the existing `Host`, `X-Real-IP`,
`X-Forwarded-For` and `X-Forwarded-Proto` forwarding headers, then adds:

```text
proxy_http_version 1.1
proxy_buffering off
proxy_cache off
proxy_read_timeout 90s
add_header X-Accel-Buffering no always
```

The new script assertions render the templates first and extract only that
exact location block before checking each directive. They do not treat a
directive in the generic proxy location or the unrendered template source as
evidence. Task5 review extended both scripts to also assert that this exact
block retains `proxy_pass http://127.0.0.1:18080` plus the four source-template
identity headers: `Host $host`, `X-Real-IP $remote_addr`,
`X-Forwarded-For $proxy_add_x_forwarded_for` and
`X-Forwarded-Proto $scheme`.

## TDD Evidence

### RED

Before changing either template, the following Git Bash asset scripts were run
after adding the rendered-location assertions:

```powershell
& 'C:\Program Files\Git\bin\sh.exe' deploy/stage09-native/scripts/test-native-service-assets.sh
& 'C:\Program Files\Git\bin\sh.exe' deploy/stage09-native/scripts/test-public-ingress-assets.sh
```

Both exited `1` as expected. The internal script stopped at
`sse-proxy-http-version-location: FAIL`; the public script stopped at
`public-ingress-assets: FAIL https-sse-proxy-http-version-location`. This proves
the assertions were checking for the missing exact location rather than merely
matching a pre-existing generic proxy setting.

### GREEN

After the minimal exact-route configuration was added, the same two scripts
were run with Git Bash:

```powershell
& 'C:\Program Files\Git\bin\sh.exe' deploy/stage09-native/scripts/test-native-service-assets.sh
& 'C:\Program Files\Git\bin\sh.exe' deploy/stage09-native/scripts/test-public-ingress-assets.sh
```

Results:

| Command | Result | Relevant pass/skip evidence |
| --- | --- | --- |
| `test-native-service-assets.sh` | exit `0` | Ten exact-block checks reported `PASS`: five SSE transport checks plus `sse-proxy-pass-preserved`, `sse-forward-host-preserved`, `sse-forward-real-ip-preserved`, `sse-forward-for-preserved` and `sse-forward-proto-preserved`; the script also reported `native-service-assets: PASS`. `nginx-config-syntax: SKIPPED` because `nginx` is not installed in this local execution environment. |
| `test-public-ingress-assets.sh` | exit `0` | Ten exact-block checks reported `PASS`: five SSE transport checks plus `https-sse-proxy-pass-preserved`, `https-sse-forward-host-preserved`, `https-sse-forward-real-ip-preserved`, `https-sse-forward-for-preserved` and `https-sse-forward-proto-preserved`; the script reported `public-ingress-assets: PASS`. |

The first combined GREEN invocation exceeded the local command wrapper's
30-second limit after the native script had already printed its complete PASS
output; the public script was then rerun separately and exited `0`. This is a
tool-wrapper timeout, not a failed asset assertion, and no command result is
inferred from it.

### Task5 Review Follow-up

After review, the five retained upstream/identity assertions above were added
to both render-and-inspect scripts before rerunning them. The exact Git Bash
commands were the two commands shown in the GREEN block. The public script
exited `0` with all ten `https-sse-*` checks passing; the internal script exited
`0` with all ten `sse-*` checks passing and the same explicit `nginx-config-syntax:
SKIPPED` limitation. This follow-up is still repository-only verification.

## Final Acceptance

The complete automated acceptance was rerun after Tasks 1–5: selected
Stage06/Stage08/Stage09 backend pytest exited `0` with `209 passed in 28.35s`;
the final `npm.cmd run test:run` exited `0` with `77` files, `398 passed` and
`2 skipped` in `279.22s`; `npm.cmd run build` exited `0` (only the retained
`>500 kB` chunk advisory); both Git Bash rendered-Nginx scripts exited `0`; and
`git diff --check` exited `0` with CRLF conversion notices only. Whole-branch
review reported no new Critical or Important code safety finding.

After user-authorized isolated test-data provisioning, Browser/Product Design
QA captured a populated desktop read-only Ledgerline state and a compact
current-record state. It found and then verified fixes for: Vite missing the
`/api` proxy, a static portal backdrop rendered below compact record detail, and
the missing compact record-context entry. The retained screenshots live under
`evidence/stage09-visual-qa/`; `design-qa.md` now records `final result: passed`.
The worktree has no deployment or production-write evidence; cleanup/audit
completed and the user-required one local squash commit is recorded on this branch.

## Authorized Real OpenRouter Smoke

After explicit user authorization, one bounded real-provider smoke ran on the
existing Stage09 server using its configured runtime environment. The executed
fixture was in-memory only: it created one synthetic workspace, one visible
synthetic task record and one temporary digital employee, then requested a
read-only `summarize` action through `live_openrouter`. The command returned a
sanitized receipt only: provider `openrouter`, model `openrouter/auto`, a
non-empty answer and usage metadata. The synthetic record remained unchanged,
no draft was created, and raw prompt/response persistence were both `false`.
No server database row, Telegram action or deployed configuration was changed.
The remote invocation was hard-bounded to 60 seconds; it completed in roughly
ten seconds. No credential value, prompt or model response was retained in
this evidence.

## Not Executed in This Task

- Full backend suite: the final backend evidence remains the Stage09 selected
  suite; this frontend-only closeout did not change backend code after it ran.
- `nginx -t` local syntax validation: the internal asset script explicitly
  skipped it because the local `nginx` executable was unavailable.
- Deployment, push, merge and release activation.
- Any real draft, import, table, permission, provider or Telegram write.

## Dependency Warning

The approved Stage09 design continues to record one existing high-severity
`npm audit` dependency warning; this task made no dependency change. A local
`npm.cmd audit --omit=dev --json` probe was not usable as a new audit result
because the Mini App directory has no lockfile and npm returned `ENOLOCK`.
That probe did not write a lockfile or modify dependencies.

## No-write and Cleanup Boundary

This task rendered repository templates only. It did not modify any live Nginx
configuration, service, database, provider, Telegram conversation or deployed
asset. The shell scripts use `mktemp -d` and their traps remove their temporary
rendered fixtures. No generated files from this task are retained outside this
evidence document. Changes remain unstaged and uncommitted in the isolated
worktree, pending the required whole-stage acceptance and audit.
