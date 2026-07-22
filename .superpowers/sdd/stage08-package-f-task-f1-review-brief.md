# Stage08 Package F — F1 independent review brief

## Scope

Review the opt-in `OpenRouterStage08AnalysisProvider` and its focused tests.
Read the Package F BDD, F plan, F1 brief/report, E5 decision and changed
source. No network call and no code edit.

## Blocking questions

1. Is the adapter unreachable from default API dependencies and only injectible
   by F evaluation code?
2. Does every real HTTP call use an explicit `httpx` transport timeout bounded
   by the smaller of E5 remaining deadline and provider budget, rather than a
   post-return/cooperative check?
3. Are no-key, timeout, HTTP error, invalid JSON/shape and citation/action
   violations all fail closed as existing safe outcomes without raw exception
   leakage?
4. Does the adapter accept only sealed/private material through the approved
   internal path and avoid persistence/logging of prompt, response, IDs,
   request IDs, usage values or secrets?
5. Can any model output create a sealed draft field/value or bypass E3 policy?
6. Is this limited to F1 (no public API/schema/permission/Telegram/deployment
   expansion or real external invocation)?

## Evidence

Inspect code directly and run focused tests necessary for concern validation.
Write `.superpowers/sdd/stage08-package-f-task-f1-review-report.md` with
Critical/Important/Minor, test evidence and PASS/HOLD. Critical/Important
blocks F2.
