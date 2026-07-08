# Stage 05 Skills Extension Source Of Truth

## Status

- Document status: active post-Stage05 extension source of truth
- Scope: Stage05 Skills Extension for static project Agent skills, using the official `larksuite/cli` skills as the structural source while adapting scope to Telegram + Bitable-like advertising operations.
- Current Progress: 2026-07-09 Implemented static skill registry, sidecar candidate logging, AgentRun evidence persistence, fixtures, local real OpenRouter smoke and full backend regression. Existing Router/Supervisor business decisions remain unchanged; skill evidence is stored as sidecar evidence only.

## 1. Goal

Stage05 already proved the first real Agent workflow: Telegram ingress, OpenRouter router, child draft agents, account exception marking, confirmation/no-op evidence, allowlisted customer reply send and Bitable-like views.

The Stage05 Skills Extension turns those implicit capabilities into a static, inspectable and testable skill system:

```text
Telegram message
-> existing Stage05 Router/Supervisor business path
-> sidecar skill candidate matching
-> skill evidence stored in agent_runs.output_summary
-> local fixtures and real OpenRouter smoke verify hit behavior
```

The goal is not to make a plugin marketplace. The goal is to make current and near-next Agent capabilities:

- discoverable by trigger conditions,
- bounded by explicit non-goals,
- tied to owning Agent and Bitable endpoints,
- visible in AgentRun evidence,
- measurable for hit/miss baseline,
- ready for Stage06 without weakening safety boundaries.

## 2. Confirmed User Choices

| Topic | Decision |
| --- | --- |
| Delivery depth | Documentation + code implementation |
| Runtime behavior | Sidecar candidate logging first; do not change current Router/Supervisor business decisions |
| 27 official skills depth | P0/P1 detailed; P2/P3 concise |
| Naming style | Platform skills use `project-*`; business skills use short business names |
| Business skills | `recharge-draft`, `customer-reply-draft`, `bm-invite-draft`, `card-binding-draft`, `account-exception-marking`, `manual-review-handoff`, `spend-query`, `spend-table` |
| Reporting | Do not implement or register `report-draft`; reporting workflows may register as future/manual-review adapters only |
| Registry coverage | Register P0 + P1 adapters plus the listed business skills |
| Candidate logging | Reuse `agent_runs`; first try existing JSON fields before adding migration |
| API | Do not add a new API |
| Tests | Add formal fixtures; local automated tests; local real OpenRouter smoke with 5 cases; full backend regression |
| OpenRouter smoke | Must actually run successfully; missing key/network/model means incomplete, not done |
| Staging | Not in this extension |
| Commit strategy | Commit existing audit first, then commit extension docs/code/tests |

## 3. In Scope

- Static skill manifest definitions near the existing Stage05 Agent code.
- Skill matching/candidate logging that runs beside the existing Stage05 Router result.
- Storing skill evidence in `agent_runs.output_summary`.
- Small Router schema extension for future/manual-review intent evidence if needed.
- Formal local fixtures for Telegram-style skill cases.
- Tests for:
  - registry completeness,
  - skill layer and owner boundaries,
  - selected/rejected/future skill evidence,
  - spend/query and report/future behavior,
  - no behavior change in existing Stage05 workflow outputs.
- Local real OpenRouter smoke with five redacted cases:
  - recharge + customer reply,
  - BM invite,
  - spend/balance query,
  - card binding,
  - account exception.
- Documentation package and acceptance checklist.

## 4. Out Of Scope

- Dynamic skill marketplace.
- User-editable skills.
- Real Codex `.codex/skills` installation.
- New public API.
- Staging deployment.
- Telegram send.
- Provider calls.
- Funds movement.
- Account production, automatic replacement or automatic redistribution.
- Report generation or report sending.
- Real spend/balance readback from provider.
- Storing raw OpenRouter prompts/responses, secrets, chat ids, allowlist values or raw customer data in git.

## 5. Bitable Endpoint Rule

Skill evidence is not complete unless it lands in an inspectable project endpoint. For this extension, the endpoint is:

```text
agent_runs.output_summary.skill_evidence
```

Future stages may add a dedicated `agent_skill_matches` table only after this JSON evidence shape proves useful. This extension should not add a table unless existing AgentRun fields are demonstrably insufficient.

## 6. Safety Rules

- Existing Stage05 business decisions must remain unchanged.
- Skill evidence must be sidecar evidence, not the source of execution.
- Any unsupported or future skill must fall back to `manual_review` or `future_scope`.
- `report-draft` must not be registered this round.
- `spend-query` and `spend-table` may be matched, but must not execute real spend query or generate spend tables.
- Skill matching must not create drafts, send requests, service records, account mutations or provider calls by itself.

## 7. Exit Gate

This extension is complete only when:

- Documentation package exists and is linked.
- Static registry contains the confirmed P0/P1 adapters and business skills.
- Official LarkSuite skill summary is saved as a concise reference, not full copied source.
- AgentRun output includes skill evidence for Stage05 routed messages.
- Formal fixtures cover selected, rejected, spend, future reporting and safety cases.
- Local automated tests pass.
- Local real OpenRouter smoke succeeds on five cases.
- Full backend regression passes.
- Secret scan and temporary cleanup checks pass.
- Acceptance checklist is updated with actual evidence.

## 8. Acceptance Evidence

2026-07-09 local verification evidence:

- `pytest tests/unit/test_stage05_skill_registry.py tests/unit/test_stage05_skill_matching.py -q`: `10 passed in 0.06s`.
- `pytest tests -k stage05 -q`: `98 passed, 190 deselected in 3.11s`.
- `pytest tests -q`: `271 passed, 17 skipped in 4.84s`; skipped tests are existing online PostgreSQL smoke tests requiring `STAGE02_ONLINE_DATABASE_URL`.
- `python scripts/stage05_skill_openrouter_smoke.py`: passed against real OpenRouter with 5 redacted cases and `TELEGRAM_SEND_MODE=dry_run`, `PROVIDER_MODE=disabled`.
- `git diff --check`: passed with line-ending warnings only.

Remaining note: `.pytest_cache` was attempted for cleanup but Windows denied ACL access to the directory. It is ignored by git and is not a project source artifact.
