# Repository Governance

## Status

- Status: active; activation partial because private-repository branch protection is unavailable on the current GitHub plan
- Scope: GitHub default branch, feature branches, historical stage branches, pull requests and repository-facing technical documentation
- Previous default branch: `stage-02-backend`
- Current default branch: `main`
- Protection: unavailable; GitHub returned HTTP `403` requiring GitHub Pro or a public repository, so `main.protected=false`
- Historical branches: retained
- Superseded pull request: #1 remains open because the protection gate did not pass
- Current integrated source: Stage12 present, default-off and not finally accepted
- Current Progress: 2026-08-25 root `README.md`, repository description and 12 technical topics were published; the default branch changed from `stage-02-backend` to `main` at activation source commit `b6cdc23628f40e5b37c9933a9a1c69568b4aeeff`. Classic branch protection was rejected by GitHub plan enforcement, so no protection success is claimed and PR #1 was deliberately retained. The evidence-record commit is verified on both `main` and `codex/stage09-ai-conversation-sse` after this document is committed.

## 1. Purpose

This document defines how the repository presents current source, preserves stage history and communicates release status. It prevents branch names, a default branch or a green local test from being mistaken for deployed production acceptance.

The governing distinction is:

```text
latest source != deployed source != active runtime authority != final acceptance
```

## 2. Branch Model

| Branch class | Purpose | Normal write policy |
| --- | --- | --- |
| `main` | Current integrated source and technical documentation | Fast-forward or reviewed pull request only; no force-push or deletion |
| `codex/*` | Bounded feature, stage or documentation development | Work according to the approved design/plan for that branch |
| Historical stage branches | Durable implementation and migration evidence | Retained; not normal development targets |

The initial retained historical branches are:

- `codex/stage09-ai-conversation-sse`
- `codex/stage07-mini-app-ui`
- `codex/stage-06-hardening`
- `codex/stage-05-development`
- `stage-03-backend`
- `stage-02-backend`

Creating `main` does not delete, rename, squash or rewrite any of them. A later branch-cleanup request must identify exact targets, retention evidence and recovery steps before implementation.

## 3. Pull Requests

New product or infrastructure work uses a focused `codex/*` head and `main` base. A pull request must state:

- Scope and explicit non-scope.
- Changed files and behavior.
- Verification commands and results.
- Skipped tests and their reasons.
- Remaining risks.
- Database, deployment, Telegram or other external writes.

A Draft pull request is review material, not an accepted release. A stale PR may be closed as superseded only after its replacement source and documentation are directly verifiable on the intended default branch. Closing a PR does not authorize deleting its source branch.

## 4. Protection And History

The target `main` policy is deliberately minimal until real GitHub Actions checks exist:

- force-push disabled;
- branch deletion disabled;
- no invented required-status checks;
- no history rewrite;
- no automatic deletion of historical branches.

Adding required checks, review counts, CODEOWNERS or release automation is a separate governance change and must reflect workflows that actually exist.

As of 2026-08-25 this target policy is not enforced by GitHub: the classic branch-protection endpoint returned HTTP `403` for the private repository under the current account plan. The repository was not made public and no paid-plan change was attempted. Until the owner upgrades the plan or separately approves another supported protection mechanism, collaborators must follow the no-force-push/no-deletion rule operationally and treat the missing server-side enforcement as an open governance risk.

## 5. Source And Runtime Status

The latest integrated source includes Stage12 Quality Architecture V2. This does not change its runtime acceptance boundary:

- `STAGE12_RUNTIME_MODE` defaults to `off`;
- Stage12 activation is restricted to an exact isolated workspace allowlist;
- Stage11 remains production answer authority;
- deployed public-path P2, the single P3, bounded Telegram proof and rollback/forward-recovery evidence remain pending;
- Stage12 is not finally accepted.

Repository documentation must use those statements until newer direct evidence updates the active Stage12 truth documents.

## 6. Repository Documentation

The root `README.md` is the technical entry point, not a replacement for project truth. Engineers should follow this order:

1. `AGENTS.md` for collaboration, safety and source-of-truth order.
2. `project-docs/README.md` for the active document index.
3. Current architecture, implementation and acceptance documents.
4. Sanitized evidence linked by those documents.

Historical Stage02–Stage05 documents remain useful evidence but cannot override the platform-first constitution or current Stage12 status.

## 7. GitHub Repository Metadata

The repository description and topics should identify the product and confirmed stack without claiming a public release. A homepage URL remains unset unless a reachable product URL is freshly verified and explicitly approved.

Badges for CI, coverage, release, uptime or production status may be added only when the corresponding public or repository-visible evidence exists.

## 8. External Change Safety

Default-branch changes, protection settings, PR closure and repository metadata are external GitHub writes. Execution must follow the approved plan, record pre-change state and verify post-change state. If a gate fails:

- do not close the superseded PR;
- do not delete any branch;
- do not force a branch pointer;
- report the exact partial state;
- roll the default branch back only to the previously recorded pointer when necessary.
