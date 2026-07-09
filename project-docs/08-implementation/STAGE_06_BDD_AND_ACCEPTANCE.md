# Stage 06 BDD And Acceptance

## Status

- Document status: active Stage06 behavior and acceptance document
- Scope: BDD scenarios, acceptance criteria and evidence expectations for Stage06 backend readiness
- Current Progress: 2026-07-10 Backend acceptance is restored after Package 6 passed S6-11 and S6-22 through S6-27. Identity/membership, tenant isolation, lookup/audit redaction, notification fail-closed, import limits, pagination, idempotency, constraints and real PostgreSQL concurrency evidence are retained. Mini App remains deferred.

## 1. Acceptance Philosophy

Stage06 current pass must be proven by backend platform behavior, not by isolated vertical business demos and not by UI screenshots.

The backend-readiness evidence must show:

```text
Telegram backend entry or direct backend invoke
-> generic base/table
-> template or import
-> digital employee
-> permission check
-> real LLM summarize/draft when configured
-> draft confirmation
-> audit
-> safety close
```

Advertising-agency workflows must not be the pilot cut. Use Telegram productivity scenarios such as chat-derived tasks, team follow-ups, notifications, digital employee summaries and table audit.

## 2. BDD Scenarios

### Scenario 1: Create Generic Base From Scratch

Given a workspace owner is signed in  
When they create a base, create a table, add fields and create a grid view  
Then the base, table, fields and view are persisted  
And the user can create a record  
And an audit event records the create actions.

### Scenario 2: Import CSV Or Excel

Given a builder has a CSV or Excel file  
When they upload it to an import job  
Then the system infers fields and shows preview rows  
When the builder confirms or corrects the mapping  
Then the system creates fields and records  
And the import job becomes `committed`  
And audit records the import commit.

### Scenario 3: Install Official Template

Given a workspace has no bases  
When the user installs the CRM or project/task template  
Then a base is created with tables, fields, views and sample records  
And the resources are ordinary platform resources  
And advertising-agency sample templates are not the default product path.

### Scenario 4: Create Digital Employee

Given a base has a table and view  
When a builder creates a digital employee with read/summarize/draft permissions  
Then the digital employee config is persisted  
And its configured scope cannot exceed the builder's allowed resources.

### Scenario 5: Telegram Mention Resolves Context

Given a Telegram chat is bound to a workspace and default base  
And a user is bound to a workspace member  
When the user mentions `@employee_alias`  
Then the system resolves workspace, base, chat scope and caller user scope  
And invokes the matching digital employee only if all scopes permit it.

### Scenario 6: Deterministic Digital Employee Summarizes Records

Given a digital employee can read a view  
When it is asked to summarize records in deterministic mode  
Then it reads only permission-filtered records and fields  
And its response does not include hidden or masked values  
And an AgentRun/audit event is written.

### Scenario 7: Live Digital Employee Calls OpenRouter

Given OpenRouter credentials are configured  
And a digital employee can read a view  
When it is invoked in live mode  
Then the system runs a LangGraph workflow  
And calls OpenRouter with permission-filtered context  
And records AgentRun evidence with `model_provider = openrouter`  
And returns a structured answer or draft proposal  
And does not directly commit record writes.

### Scenario 8: Digital Employee Drafts A Record Update

Given a digital employee can draft updates on a table  
When it proposes a status change  
Then the system creates a `record_change_draft`  
And the original record is not changed yet  
And the draft appears through the backend draft list.

### Scenario 9: User Confirms Draft

Given a pending record-change draft exists  
When an authorized user confirms it  
Then permissions and record version are re-checked  
And the record is updated  
And the draft status becomes `confirmed`  
And audit records the confirmation and write.

### Scenario 10: Permission Denial Is Safe

Given a user asks a digital employee about a field they cannot read  
When the digital employee builds context  
Then the hidden field is omitted or masked  
And the response explains the permission boundary safely  
And audit records the denial without leaking the value.

### Scenario 11: Safety Close Blocks Sends

Given notification sending is disabled or dry-run only  
When a digital employee creates a notification request  
Then the request is blocked or dry-run according to policy  
And no uncontrolled Telegram send occurs  
And audit records the block.

### Scenario 12: Local PostgreSQL Migration Smoke

Given a local PostgreSQL database URL is configured  
When Alembic upgrades to head  
Then all Stage06 migrations apply against real PostgreSQL  
And the smoke evidence records the database target without exposing credentials.

### Scenario 13: API Identity Is Required

Given a Stage06 API request has no verified identity  
When it calls a workspace-owned read or write route  
Then the request returns `401`  
And no fixed privileged actor is substituted.

### Scenario 14: Workspace Membership Limits Authority

Given a user is an active member of workspace A but not workspace B  
When the user references a base, table, view, record, import, draft or employee in workspace B  
Then the request is denied without disclosing protected values  
And a sanitized denial audit is written where a safe workspace audit target exists.

### Scenario 15: Telegram Caller Uses Bound Member Permission

Given a Telegram binding references an active viewer member  
When that Telegram user invokes a digital employee  
Then viewer permissions are used  
And Telegram identity does not become admin permission.

### Scenario 16: Lookup Cannot Bypass Hidden Field Permission

Given a readable lookup points to a target field hidden from the caller  
When the caller reads the view  
Then the lookup value is omitted or masked  
And the hidden target value is absent from API, Agent and audit output.

### Scenario 17: Notification Policy Fails Closed

Given the server notification mode is disabled or dry-run  
When a request omits safety fields or asks to queue an unallowlisted target  
Then the effective status is blocked/dry-run  
And confirmation cannot promote it to queued.

### Scenario 18: Import Limits Are Enforced

Given an import exceeds payload, row, column or cell limits  
When the import is submitted  
Then it fails with a stable redacted limit error  
And no base/table/record resources are committed.

### Scenario 19: Pagination Is Stable

Given more than one page of records, drafts, notifications or audit events  
When the caller follows `next_cursor`  
Then no item is skipped or duplicated  
And the page size never exceeds 200.

### Scenario 20: Mutations Are Idempotent

Given the same workspace, operation and `Idempotency-Key` are submitted twice  
When request fingerprints match  
Then the original result is returned without duplicate resources  
When fingerprints differ  
Then the second request returns `409`.

### Scenario 21: PostgreSQL Concurrency Has One Winner

Given concurrent confirmations or import commits target the same pending resource  
When PostgreSQL transactions race  
Then only one state transition commits  
And the other returns an idempotent result or conflict without duplicate writes.

## 3. Required Evidence

Final backend-readiness acceptance must include:

- migration status;
- focused backend tests;
- full backend regression where feasible;
- local PostgreSQL Alembic smoke evidence;
- Telegram mention/backend entry evidence;
- import/template evidence;
- deterministic digital employee evidence;
- real LangGraph/OpenRouter LLM evidence when credentials are configured;
- digital employee draft/confirmation evidence;
- permission denial evidence;
- audit readback;
- safety close readback;
- skipped tests and reasons.

Mini App frontend smoke is explicitly excluded from the current pass and must wait for separate user confirmation.

## 4. Acceptance Checklist

| ID | Requirement | Status |
| --- | --- | --- |
| S6-01 | Active top-level docs are platform-first and Telegram-ecosystem-first | Docs updated |
| S6-02 | UI implementation is deferred until separate confirmation | Docs updated |
| S6-03 | Generic workspace/base/table/field/record/view model works | Local backend passed |
| S6-04 | JSONB record values validate through field metadata | Local backend passed |
| S6-05 | CSV import preview and commit works | Local backend passed |
| S6-06 | Excel import preview and commit works | Local backend passed |
| S6-07 | Official generic templates install ordinary resources | Local backend passed |
| S6-08 | Advertising sample is not the default product path | Local docs/backend passed |
| S6-09 | Digital employee creation works | Local backend passed |
| S6-10 | Telegram `@` invocation resolves context | Local backend passed |
| S6-11 | Effective permission intersection is enforced | Passed: request identity, active membership, resource-to-workspace resolution, field/view policy and Telegram-member scope tests |
| S6-12 | Deterministic digital employee summaries are permission-filtered | Local backend passed |
| S6-13 | Live LangGraph/OpenRouter digital employee runtime works | Passed: unit-tested with injected client; real summarize and draft-update smokes passed via `.local/stage05-real-workflow.env` |
| S6-14 | Digital employee writes create drafts | Passed: local backend and real OpenRouter draft-update smoke created a pending draft without direct record mutation |
| S6-15 | Draft confirmation commits records and audit | Local backend passed |
| S6-16 | Controlled notifications obey safety switches | Passed: server mode and allowlist are authoritative; request policy can only narrow; disabled/dry-run fail closed |
| S6-17 | Local PostgreSQL migration smoke passes | Passed with disposable local `stage06_smoke` database at Alembic head `20260710_0020` |
| S6-18 | Telegram backend entry smoke passes when configured | Passed: real `@ops` message resolved to `summarize`; temporary polling restored webhook and post-smoke readback showed `pending_update_count = 0` |
| S6-19 | Safety close is verified | Local backend dry-run/allowlist safety close passed; external sends remain disabled |
| S6-20 | LarkSuite-style skill evidence is produced | Passed: 27 official skills represented in Stage06 manifest, active core subset matched deterministically, digital employee responses and AgentRun output include `skill_evidence`; real post-skill OpenRouter multi-case smoke passed with 5 cases |
| S6-21 | Active-core skill routing meets deterministic hit-rate and safety gates | Passed: 118 cases; top-1 89.23%, top-3 100%, high-risk false commit routes 0, unauthorized-data false positives 0, missing-context clarification 100%, evidence presence 100% |
| S6-22 | Stage06 API identity and active workspace membership are enforced | Passed: local/test development adapter plus production-like verified-adapter fail-closed tests |
| S6-23 | Cross-workspace/base resource combinations are rejected | Passed: service/API tests and real PostgreSQL outsider denial evidence |
| S6-24 | Lookup and audit readback cannot leak hidden/raw values | Passed: hidden lookup omission, stored/read audit sanitization and real PostgreSQL artifact scan |
| S6-25 | Import limits and cursor pagination pass | Passed: decoded byte, row, column and cell limits plus bounded cursor pages |
| S6-26 | Idempotency and PostgreSQL concurrency gates pass | Passed: replay/conflict API tests, additive constraints and real concurrent import one-winner evidence |
| S6-27 | Sanitized machine-readable hardening evidence is retained | Passed: `evidence/STAGE_06_SECURITY_HARDENING_EVIDENCE.json` contains only safe status/head/case/count fields |

## 5. Stage06 Backend Exit Report Must Include

- Changed files.
- What changed.
- Verification commands and results.
- Manual/pilot evidence.
- Skipped tests.
- Remaining risks.
- Temporary cleanup.
- Recommendation for the separate UI phase.
