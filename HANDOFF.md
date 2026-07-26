# Current Project Handoff

This root file is a stable entry point. The authoritative handoff for the
current Stage08/Stage09 work is:

`project-docs/00-governance/HANDOFF_2026-07-26_CODEX_STYLE_AI_CONVERSATION.md`

Read it together with:

1. `AGENTS.md`
2. `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`
3. `project-docs/00-governance/PROJECT_STRUCTURE_AND_DOCUMENT_LIFECYCLE.md`
4. `project-docs/08-implementation/STAGE_09_CODEX_STYLE_AI_CONVERSATION_DESIGN.md`
5. `project-docs/08-implementation/STAGE_09_CODEX_STYLE_AI_CONVERSATION_IMPLEMENTATION_PLAN.md`
6. `docs/superpowers/plans/2026-07-26-stage09-codex-ai-conversation-sse.md`
7. `project-docs/08-implementation/evidence/stage09-r40-regression-and-live-readiness-2026-07-26.md`

The historical Stage07 R0-R3 handoff remains available through Git history and
the Stage07 implementation/evidence documents. It is not the current execution
entry.

## Current Progress

2026-07-26 final update: an isolated local PostgreSQL workspace supplied a real
record-context Browser state. Browser/Product Design QA passed after fixing the
Vite `/api` proxy, the fixed modal-layer contract and the compact record-detail
entry. It captured the server-projected five-choice skill strip and a safe
read-only terminal timeline. Cleanup/audit completed and the one local squash
commit is recorded on this branch; deployment and external writes remain out of scope.

The active implementation is the Codex-style AI conversation workbench, the
controlled `POST /api/stage08/assistant/query-stream` SSE path and the
Stage06-registry skill launcher. The existing synchronous query endpoint
remains the compatibility path. Task5 rendered Nginx SSE transport checks pass
locally for the internal and public HTTPS templates; this is not deployment or
product-level acceptance. No new schema, permission model, external send
authority or persistent chat-history store is authorized by this handoff.
