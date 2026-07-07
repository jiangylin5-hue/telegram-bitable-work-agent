# Stage 05 Risk Register

## Status

- Document status: active risk register draft
- Scope: Stage05 product, technical, security, staging and operational risks.
- Current Progress: 2026-07-07 Risk register drafted before implementation and updated after local Stage05 implementation through out-of-scope runtime guard, deployment config gate and redacted runtime summary command. Local mitigations have evidence from focused Stage05 tests 82 passed / 190 deselected, full backend suite 255 passed / 17 skipped, staging-contract preflight, scope guard, deployment compose/env tests, runtime summary tests, secret scan and traceability audit. Real OpenRouter, real allowlisted Telegram receipt, staging account exception evidence, staging business no-op evidence and safety close remain pending explicit approval and execution.

## 1. Risk Summary

Stage05 introduces real LLM calls and limited automatic account exception mutation. The main risks are hallucinated business facts, unsafe draft confirmation, accidental Telegram send, incorrect inventory abnormal marking and storing sensitive LLM context.

## 2. Risks

| ID | Risk | Impact | Likelihood | Mitigation | Owner |
| --- | --- | --- | --- | --- | --- |
| R05-01 | OpenRouter hallucinated intent or entities | Wrong draft or wrong manual action | medium | Schema validation, confidence threshold, manual review, no automatic provider execution | Agent workflow |
| R05-02 | Full prompt or raw response leaks sensitive data | Customer/privacy exposure | medium | Persist only structured output and redacted summary; view masking; secret scan | LLM evidence |
| R05-03 | Agent incorrectly marks usable account as blocked | Inventory disruption | medium | Only high-confidence abnormal statuses; audit and account status event; ambiguous signals manual review | Account Inventory Agent |
| R05-04 | Agent auto-replaces account despite scope | Unauthorized distribution | low | Tests reject reserve/allocate replacement actions; source of truth forbids it | Account Inventory Agent |
| R05-05 | Customer reply sent to real customer chat | Customer-facing incident | medium | Allowlist checks at request, confirm and worker; staging-only send mode | Confirmation/send |
| R05-06 | Business draft confirmation triggers provider | External business side effect | medium | Provider mode disabled; no-op execution evidence; tests assert no provider call | Confirmation |
| R05-07 | Duplicate worker delivery creates duplicate drafts | Operational clutter and confusion | medium | Idempotency keys per message/draft/intent index | Workflow |
| R05-08 | LangGraph state diverges from PostgreSQL | Hard-to-debug workflow | medium | PostgreSQL is source of truth; graph state persisted only through services | Architecture |
| R05-09 | OpenRouter key committed or logged | Secret leak | low | Env-only key; scan; no logs with headers | Operations |
| R05-10 | Stage05 breaks Stage04 Telegram send path | Regression | medium | Stage04 regression tests mandatory | Testing |
| R05-11 | Staging safety close forgotten | Later accidental sends | medium | Runbook explicit close; acceptance requires dry-run and allowlist cleared | Operations |
| R05-12 | Cost unexpectedly high | Budget surprise | low-medium | Record usage/cost; no complex limit in Stage05 by user choice | Operations |
| R05-13 | Bitable views expose sensitive fields | Data exposure | medium | Field masking and role-scoped tests | Views |
| R05-14 | Account production boundary remains confusing | Future scope creep | medium | Update Agent/scenario docs; Stage05 source says no production | Documentation |

## 3. Local Mitigation Evidence

| Risk ID | Local Evidence Status | Evidence |
| --- | --- | --- |
| R05-01 | mitigated locally; staging pending | Router schema validation, invalid-output failure mapping, confidence/manual-review tests |
| R05-02 | mitigated locally; staging pending | AgentRun evidence tests, raw prompt/response defaults, service draft API response-shape tests, redacted runtime summary test, secret scan |
| R05-03 | mitigated locally; staging pending | High-confidence account exception tests, allowed-status guard, ambiguous-risk manual review |
| R05-04 | guarded locally; staging pending | Account assignment remains draft-only; `replacement_action = none`; scope guard blocks Stage05 assignment confirmation/activation path |
| R05-05 | mitigated locally; staging pending | Request-time, confirm-time and worker allowlist tests; local fake Telegram send only |
| R05-06 | guarded locally; staging pending | Business confirmation creates `ExecutionLog(provider=noop, execution_status=skipped)`; no `ExecutionTicket`; scope guard blocks Stage05 provider execution paths |
| R05-07 | mitigated locally | Duplicate workflow trigger idempotency test |
| R05-08 | mitigated locally; staging pending | Workflow persists AgentRun, service drafts, account status events and message states through services |
| R05-09 | mitigated locally; repeat before staging | Secret scan finds config names, placeholders, documented commands and fake test values only; `python -m app.core.runtime_summary` reports presence flags without raw key/token/allowlist values |
| R05-10 | mitigated locally; staging smoke pending | Stage03/Stage04 regression command passed locally |
| R05-11 | preflighted locally; real close pending | Staging safety-close contract test passes; deployment config gate keeps safe defaults and redacted runtime summary can prove deployed settings after approval |
| R05-12 | not evaluated with real LLM | AgentRun usage/cost fields exist; real OpenRouter usage/cost evidence pending |
| R05-13 | mitigated locally; staging view evidence pending | Stage05 Bitable view masking and row-scope tests |
| R05-14 | mitigated locally | Account docs updated; scope guard blocks Stage05 account production paths |

## 4. Risk Handling Rules

- Any risk that could cause real external provider write blocks implementation until user confirms a new stage scope.
- Any discovered secret in git/docs must be treated as a security incident and removed before continuing.
- Any accidental customer chat send means Stage05 staging rehearsal stops and safety close is performed.
- Any ambiguous account status signal must not auto-mutate inventory.

## 5. Open Follow-ups For Later Stages

- Production monitoring and alerting.
- OpenRouter budget/rate limits and fallback model policy.
- RAG/pgvector retrieval.
- UI/Mini App review queue.
- Account replacement recommendation workflow.
- Provider sandbox and execution_ticket production hardening.
