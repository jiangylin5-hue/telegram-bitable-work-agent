# Stage08 Package E final independent review brief

## Goal

Decide whether Package E (E1–E4) can close and hand off to Package F. This is
a bounded package-level review, not a restart of all Stage08 validation.

## Required reading

- Package E plan, BDD and E collaboration contract;
- E3 safe execution and E4 safe replay decisions;
- E1/E2 reports, E3 R1/R23/final reports, E4 implementation/review/remediation
  reports;
- E1–E4 source/tests and the local pgvector integration test.

## Acceptance questions

1. E1 private, non-checkpoint coordinator topology accepts only sealed
   server-derived commands and fails closed on state/provider shape drift.
2. E2 consumption-time C3/D4 reads preserve scope/budget/degradation and do
   not persist private material.
3. E3 draft behavior passes policy before ticket/Gateway, atomically rechecks
   current scope under locks, rolls back on failure, safely replays, and has
   no trace/audit UUID/private leakage.
4. E4 exposes only the approved POST, derives authority server-side, maps
   errors safely, and replays the exact versioned safe view only after current
   scope revalidation.
5. No E component added a schema/migration/global role/provider/Telegram/
   deployment behavior or weakened Stage06 defaults.
6. The selected E suite and disposable local pgvector test are substantive,
   and all reports truthfully separate local evidence from real Provider/
   production evidence.

## Method

Inspect source directly and run the compact E-focused unit/API suite and
existing PostgreSQL integration test. Do not expand into F, UI, Stage07 or
full-suite work. Do not edit code or call external systems.

## Output

Write `.superpowers/sdd/stage08-package-e-final-review-report.md` in Chinese:
findings by severity, exact commands/results, close/hold decision, remaining
risks. Only `0 Critical / 0 Important` may recommend Package E closure.
