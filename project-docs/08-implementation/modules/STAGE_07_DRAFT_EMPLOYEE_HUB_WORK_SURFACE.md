# Stage07 Draft and Digital Employee Hub Work Surface

## Status

- Status: proposed pending TD005 approval.
- Functional ownership: consume only S5 server-safe contacts/invocation/drafts; never evaluate employee scope, build a raw diff or directly write a record.

## Functional Modules

| Surface | Authorized user can do | Deliberately cannot do |
| --- | --- | --- |
| Contact directory | open an active server-visible contact | view employee scope/actions/configuration, publish/configure/disable a contact |
| Context rail | select/remove a permitted Base/view/record for one intent | infer context from chat history, retain it in browser storage or cross Base scope |
| Assistant result | read a safe summary or open a returned draft pointer | browse raw records, runtime evidence, prompts or provider metadata |
| Draft queue/detail | read server-filtered list/diff and terminal status | reconstruct hidden fields, edit proposed values or view trace/creator/policy |
| Confirm/reject | submit explicit versioned terminal command | self-confirm as agent, partially apply fields, invoke notification/send/external action |

## UI States

| State | Required UI behavior |
| --- | --- |
| contacts-loading / contacts-empty | labelled status; no fake default assistant |
| context-empty | state exactly that no Base/view/record is currently in context |
| contact-ready | intent choices are server-derived fixed labels only |
| invocation-pending | submitted control disabled; typed instruction retained; no streamed/raw execution claims |
| summary-ready | safe answer/citations only; no raw record export/download |
| draft-ready | immutable field rows; action buttons only from `actions` model |
| terminal-pending | just the chosen command locks; close/navigation cannot render success early |
| confirmed / rejected | authoritative reread plus opaque audit reference, not a locally inferred status |
| stale / conflict | typed local intent kept; explicit reread, never automatic resubmit |
| denied / expired | protected-state cleanup then generic boundary |
| invalid / network | fixed local text and explicit retry; raw response omitted |

## Accessible and Responsive Rules

- 1440/1280: contacts, context and content may be adjacent but focus order remains contact → context → result/draft.
- 430/390: each editing/review step is a full-height sheet with 44px controls and independent scrolling; context chips and terminal buttons remain reachable without hover.
- Draft diff names each field and semantic before/proposed value. Hidden values have no placeholder row.
- Open, close, retry and terminal completion retain predictable focus; every pending state uses text/status, not color alone.

## Data Boundary

No component may receive or persist `accessible_tables`, `accessible_views`, `allowed_actions`, `field_policy`, confirmation policy, generic draft values, trace, creator identity, expected record version, provider/model/runtime details, AgentRun skill evidence, raw errors or Telegram data. TanStack Query keys stay user/workspace scoped and have no localStorage persistence.

## Acceptance Ownership

This work surface owns DE-A08/DE-A09 and contributes no authority proof to DE-A01--DE-A07. Contact publication, memory, knowledge, Telegram and external notification are outside its ownership.

