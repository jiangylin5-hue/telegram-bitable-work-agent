# Stage 07 Digital Employee Hub Module

## Scope

`BotHub` covers team Bot contacts, personal assistant, explicit context selection, Telegram `@` handoff and `DraftConfirmation`. It is a UI consumer of authorized employee/read/draft models and never a direct record-write client.

## Team Bot Interaction

1. A member opens an authorized published contact or receives a Telegram deep link.
2. Server resolves employee configuration, caller membership, chat scope and resource scope.
3. UI shows only resolved permitted context and the conversation/draft results.
4. A Bot proposal enters `DraftConfirmation`; confirm/reject uses one server command and returns terminal status plus audit reference.

## Personal Assistant Interaction

Personal assistant begins without work context. The user selects a Base/view/record in the UI; selection is visible, removable and submitted to the server for permission evaluation. Private conversation/memory labels never imply shared team memory.

## Contract Dependency

Workspace contacts, multiple resource scopes, published lifecycle, curated knowledge and per-user memory partitions exceed Stage06. Until a server feature gate exists, this module may show only an explicit unavailable-state explanation; it may not simulate these capabilities with client-only state.
