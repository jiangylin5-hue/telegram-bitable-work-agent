# GitHub Repository Governance And Technical README Design

## Status

- Status: approved direction; design pending user review
- Date: 2026-08-25
- Scope: GitHub landing page, root technical README, branch governance, repository metadata, default-branch promotion and obsolete PR handling
- Source branch: `codex/stage09-ai-conversation-sse`
- Target default branch: `main`
- Current source commit before documentation work: `86117cfc76c88aa83277466503e79153a2eb6262`

## 1. Objective

Make the GitHub repository understandable to an engineer opening it without prior project context. The repository landing page must show the latest Stage12 source, while clearly separating source freshness from production acceptance.

### 2026-08-25 visibility amendment

The owner explicitly approved changing repository visibility from `private` to `public` after the initial `main` promotion exposed that classic branch protection was unavailable on the current private-repository plan. Public transition is permitted only after a tracked-history credential audit finds no real Provider, Telegram, GitHub, cloud or private-key material. Public visibility does not change Stage12 runtime authority, deployment authorization or production acceptance.

The resulting repository must answer, from its root page:

1. What product is this?
2. What is implemented now?
3. What is still unaccepted or disabled?
4. How do the core components fit together?
5. How can an engineer install, test and inspect the system safely?
6. Which documents are authoritative?
7. Which branches are active development versus retained history?

## 2. Current Problems

The current GitHub presentation is misleading and difficult to navigate:

- the default branch is the historical `stage-02-backend` branch;
- the repository root has no `README.md`;
- the repository description and topics are empty;
- the latest code is on `codex/stage09-ai-conversation-sse`;
- pull request #1 is a long-lived Draft from `codex/stage09-ai-conversation-sse` into `codex/stage07-mini-app-ui`, not an integration path into the default branch;
- historical stage branches are displayed together without lifecycle guidance;
- no branch is protected;
- the latest source contains Stage12 code, but Stage12 is not finally accepted or the production answer authority.

## 3. Considered Approaches

### 3.1 Add a README only to `stage-02-backend`

This would improve the landing page without changing the default branch, but engineers would still browse historical Stage02 source by default. It preserves the central source-of-truth problem and is rejected.

### 3.2 Promote latest Stage12 source to `main` without rewriting history

Create `main` from the latest verified Stage12 branch after the repository-documentation commit, make it the default branch, protect it from force-push and deletion, and retain every historical branch. The README explicitly states that latest source does not mean production acceptance.

This is the approved approach because it makes current engineering work discoverable without deleting evidence or misrepresenting runtime status.

### 3.3 Rewrite or squash history and delete old branches

This could make the branch list visually smaller, but would destroy useful stage evidence, complicate rollback and make existing document hashes harder to trace. It is rejected for this delivery.

## 4. Target Repository Model

```text
main
  latest integrated source and technical documentation
  Stage12 present but default-off and not finally accepted

codex/stage09-ai-conversation-sse
  retained source branch for the Stage09/Stage12 development history

codex/stage07-mini-app-ui
codex/stage-06-hardening
codex/stage-05-development
stage-03-backend
stage-02-backend
  retained historical stage branches; not default development targets
```

No branch is deleted, renamed or history-rewritten. The two local-only resume/PDF documentation commits on `codex/stage07-mini-app-ui` remain outside this repository-governance delivery.

## 5. Root README Contract

Create `README.md` in Chinese with stable English technical names. It must be concise enough to scan but complete enough for an engineer to orient and run the project.

The README contains these sections in this order:

1. **Project title and one-sentence positioning**
   - Telegram-first multidimensional table, no-code workspace and table-bound digital employee platform.
2. **Current status**
   - latest source: Stage12 Quality Architecture V2;
   - runtime default: `STAGE12_RUNTIME_MODE=off`;
   - production answer authority: Stage11 until deployed P2/P3, Telegram and rollback gates pass;
   - no claim of final production acceptance.
3. **Product capabilities**
   - workspace/base/table/schema/record/view/import;
   - permissions and field visibility;
   - Digital Employee and controlled draft/action flow;
   - Telegram Bot, Mini App and browser surfaces.
4. **Architecture overview**
   - one GitHub-renderable Mermaid flow from request through authorization, planner, structured query/retrieval, typed Specialists, Grounded Provider, SSE and controlled Tool Gateway;
   - explicit rule that structured facts come from the query engine, embedding finds candidates and the LLM analyzes/expresses.
5. **Technology stack**
   - Python 3.12+, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, JSONB, pgvector, Redis, LangGraph, OpenRouter-compatible API, React/Vite/TypeScript/Tailwind/shadcn/ui and Telegram Bot API.
6. **Repository map**
   - explain `backend`, `mini-app`, `deploy/stage09-native`, `project-docs`, `docs/superpowers`, `postgresql`, `redis`, `systemd` and `scripts`.
7. **Local development**
   - prerequisites;
   - backend installation and test commands derived from `backend/pyproject.toml`;
   - PostgreSQL/pgvector and Alembic commands;
   - Mini App install, test and build commands derived from `mini-app/package.json`;
   - environment configuration references only `.env.example` or documented variable names and never includes credentials.
8. **Native deployment**
   - state that the approved server deployment is native PostgreSQL/Redis/systemd/Nginx and not container-based;
   - link to the authoritative Stage09 native deployment documents and scripts;
   - prohibit treating a local green build as production acceptance.
9. **Testing and latest evidence**
   - dated Stage12 local evidence: backend `2595 passed, 40 classified skips`, explicit PostgreSQL/pgvector `30 passed`, Mini App `415 passed`, production build `1853 modules transformed`, Alembic `20260730_0039`;
   - explain that these are 2026-08-01 local-candidate results and not a fresh 2026-08-25 rerun;
   - list the open deployed P2/P3, Telegram and rollback gates.
10. **Security boundaries**
    - no raw database access or provider keys for Agents;
    - permission intersection and field visibility;
    - write-like behavior defaults to draft/confirmation;
    - no secrets or real Telegram content in retained evidence.
11. **Documentation source of truth**
    - link to `AGENTS.md`, `project-docs/README.md`, Stage12 architecture README, Stage12 comprehensive audit and the current Stage12 execution plan;
    - warn that historical Stage02–Stage05 documents are evidence, not current product truth.
12. **Branch and contribution policy**
    - `main` is the current integrated source;
    - changes use `codex/*` branches and pull requests;
    - historical stage branches are read-only evidence unless separately authorized.

The README must not include decorative badges that imply unavailable CI, coverage, release or deployment guarantees.

## 6. Supporting Governance Document

Create `project-docs/00-governance/REPOSITORY_GOVERNANCE.md` as the durable detailed policy behind the README. It defines:

- `main` ownership and lifecycle;
- feature branch naming;
- pull request expectations;
- historical branch retention;
- default-branch protection;
- release evidence versus source status;
- rules for closing or superseding stale pull requests;
- prohibited force-push, branch deletion and history rewrite without explicit approval.

The root README links to this document instead of carrying every governance detail.

## 7. GitHub Metadata And Branch Actions

After documentation verification and push to `codex/stage09-ai-conversation-sse`:

1. Create remote `main` at the exact documentation commit.
2. Change the GitHub default branch from `stage-02-backend` to `main`.
3. Set the repository description to a concise Chinese product description with stable English product terms.
4. Add repository topics covering Telegram, multidimensional tables, FastAPI, PostgreSQL, pgvector, Redis, LangGraph, React and AI agents.
5. Protect `main` from force-push and deletion.
6. Do not require status checks until a real GitHub Actions workflow exists.
7. Add a factual comment to pull request #1 explaining that its head was promoted through the approved non-destructive `main` transition, then close it as superseded.
8. Keep every existing remote branch.

No homepage URL is set unless a currently reachable, explicitly approved public product URL is verified during implementation.

## 8. Status Language

Repository documentation must consistently distinguish:

```text
latest source != deployed source != active runtime authority != final acceptance
```

The exact Stage12 summary is:

- source: implemented and pushed on the latest development branch;
- runtime activation contract: default `off`, exact-workspace isolated allowlist only;
- local acceptance: passed documented local candidate gates;
- production authority: Stage11;
- remaining acceptance: native live-state revalidation, deployed public-path P2, single P3, bounded Telegram proof and rollback/forward-recovery evidence;
- release decision: not finally accepted.

## 9. Verification

Before any GitHub governance write:

- inspect all README commands against actual repository files;
- validate every relative Markdown link exists;
- scan README and governance files for credentials, absolute developer paths, raw IDs and unsupported production claims;
- run `git diff --check`;
- confirm only approved documentation files are staged;
- commit and push the documentation to the current Stage12 branch.

After GitHub governance writes:

- verify `main` resolves to the exact documentation commit;
- verify GitHub reports `main` as default;
- verify force-push and deletion are disabled for `main`;
- verify the repository description and topics;
- verify PR #1 is closed with a supersession comment;
- verify all historical branches still exist;
- open the GitHub root page and confirm `README.md` renders from `main`.

## 10. Failure And Rollback

- If documentation validation fails, do not push or change GitHub settings.
- If remote `main` creation fails, retain the current default branch and stop.
- If changing the default branch fails, do not close PR #1.
- If protection configuration fails after the default change, report the exact unprotected state and retry only the non-destructive protection write.
- If the rendered README is materially broken, fix it through a new commit; do not rewrite published history.
- Rolling back the default branch is allowed only to the previously recorded `stage-02-backend` pointer and does not delete `main`.

## 11. Acceptance Criteria

This repository-governance delivery is complete only when:

- root `README.md` accurately orients a technical reader;
- the detailed governance document exists and is linked;
- `main` contains the latest approved documentation commit and is the GitHub default branch;
- Stage12 status is accurate and does not claim production completion;
- `main` cannot be force-pushed or deleted;
- repository description and topics are populated;
- PR #1 is closed as superseded with an explanatory comment;
- no historical branch is deleted or rewritten;
- no temporary release directory, secret, credential or unrelated local commit is included;
- all verification results are reported with skipped checks and remaining risks.
