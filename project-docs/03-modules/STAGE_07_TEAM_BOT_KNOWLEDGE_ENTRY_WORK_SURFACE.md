# Stage07 Team Bot Knowledge Entry Work Surface

## Status

- Status: TD011 approved S5.3 module boundary; implementation is in progress and no durable knowledge model exists.
- Scope: one Home Team Bot workbench over active employees and caller-permitted saved-view knowledge windows.

## Functional Modules

| Module | Reused foundation | Responsibility | Explicit boundary |
| --- | --- | --- | --- |
| Team entry | Home/AppShell capability grammar | opens one labelled Team Bot workbench | no Telegram/chat sidebar or inferred employee |
| Contact directory | TD005 safe contacts + TD010 eligibility | shows active, member-eligible employees only | no policies, member identities or publication state |
| Knowledge catalog | TD009 server-composed view intersection | shows safe permitted saved views for selected employee | no generic Base/view/record reads or search |
| Knowledge selection | exact protected reread pattern | verifies selected view immediately before invocation/handoff | no client ACL claim or stale selection use |
| Summary command | TD005 runtime/audit/idempotency | sends one bounded instruction over server-owned view window | no tool/model/provider control, direct write or draft creation |
| Result and handoff | safe citations + `openBase` | renders answer/opaque citations and opens same authorized Base on explicit action | no record preselection, transcript or implicit Canvas change |

## State Ownership

| State | Owner | Lifetime | Clear trigger |
| --- | --- | --- | --- |
| employee lifecycle/scope/grant | existing server models/services | durable | TD010 versioned command only |
| selected view and summary result | protected QueryClient + local workbench state | current user/workspace/open panel | close, replacement, denial, missing resource or retry |
| 100-row knowledge window | server command memory | one request | command completion/failure |
| idempotent summary receipt/audit | existing server idempotency/audit storage | durable by existing policy | existing retention policy |

## Supported User Actions

| Action | Preconditions | Server effect | Durable result |
| --- | --- | --- | --- |
| open Team Bot | active workspace session | reads safe contacts | no new durable resource |
| select contact/view | caller eligible and view visible | reads safe server projections | no client permission grant |
| summarize | selected revalidated view, bounded instruction, idempotency key | builds safe window and invokes existing summary runtime | redacted audit/reference and replay receipt |
| open Base | explicit action and current Base access | reuses existing authorized Base navigation | no draft/record mutation |

## Explicitly Excluded Work

- employee publication, workspace-wide/multi-Base scope, new permissions, member management or a knowledge-source manager;
- files, URLs, embeddings, vector search, query DSL, record picker, primary-field labels or unrestricted source export;
- durable personal/team memory, chat/messages, retention/delete controls, browser persistence and provider configuration;
- direct draft/update from Home, automatic confirmation, Telegram routing/send, notifications, deployment and production operations.

## Acceptance Dependencies

1. TD011 technical boundary and this document package were user-reviewed before the implementation plan and execution authorization.
2. Existing TD010 member-eligibility and TD005 citation/invocation boundaries remain authoritative.
3. Automated route/service/parser/protected-state coverage proves every BDD row before local promotion.
4. User-controlled visual review and any real OpenRouter/Telegram evidence remain separate later gates.
