# Stage 07 Mini App UI Design

## Status

- Document status: approved design, awaiting written-spec review
- Scope: React/Vite Telegram Mini App and desktop-browser UI design for the generic workspace, Bitable and digital-employee platform
- Current Progress: 2026-07-10 user-approved discovery and visual direction are recorded. No frontend code, schema change, API-contract change or permission-model change has started.

## Purpose

Stage07 is the separate UI phase authorized after Stage06 backend-readiness acceptance. It turns the generic platform into a usable Telegram Mini App and desktop browser product while preserving the table-first constitution, authorization boundary and record-change-draft safety model.

## Approved Direction

- Workspace Home uses the queue-first `Work Queue Atlas` direction: `Today`, draft confirmations, `@` mentions and assigned records are primary; recent Bases and personal assistant are supporting contexts.
- Base/table workflows use the dense `Workspace Ledger` direction.
- Bot and draft-confirmation workflows use the contextual `Conversation Desk` direction.
- The design is true-white, cool-gray and restrained azure-blue. Dark AI dashboards, gradients, glows and generic card walls are rejected.
- Desktop favors building and governance; mobile favors processing, confirmation and conversation without changing authority or view semantics.

## Stage Packages

1. UI foundation and responsive App Shell.
2. Bitable work surface, builder, import/template and record interaction.
3. Governance and permission-aware management surface.
4. Digital employee surfaces, controlled drafts and separately approved backend contract extension.

## Contract Gate

The Stage06 backend currently supports base-bound employees. Team-shared workspace Bot contacts, personal assistants, multiple resource scopes, curated knowledge sources, user-isolated memory and Telegram contact/group publication are proposed extensions. They require a dedicated technical decision plus user approval before schema/API/permission implementation.

## Primary Specification

Read [Stage07 Mini App UI Design Specification](../../docs/superpowers/specs/2026-07-10-stage07-mini-app-ui-design.md) before planning or implementing Stage07.

## Acceptance Criteria

- Every Mini App action resolves to an authorized persistent workspace/Base/table/view/record/draft/audit destination.
- Desktop and mobile experiences preserve the same authority model and saved-view semantics.
- All AI writes remain explicit field-level drafts until user confirmation.
- Unauthorized data does not appear in UI state, error state or client-side cache.
- No Stage07 implementation begins until the specification is reviewed and the required contract changes are explicitly approved.
