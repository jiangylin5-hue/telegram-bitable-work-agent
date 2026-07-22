# Stage08 Package F — F2 independent review brief

## Scope

Review the F2 synthetic 12-case isolated evaluation runner, its test suite and
task report. F1 is clean. This review is offline only: do not set an eval env
or invoke any external Provider/Telegram/deployment.

## Blocking questions

1. Are there exactly 12 static IDs covering all approved F matrix categories,
   with no caller-controlled case identity or prompt crossing process lines?
2. Does every case use a fresh spawned process and synthetic-only fixture;
   do hard timeout and <=2 concurrency behave per case without sibling harm?
3. Are child and parent DTOs strict enough to reject forged/subclass/extra/raw
   fields, exception text, IDs/tokens/request IDs and prompt/answer content?
4. Is all safety environment forced inside the child and does absent explicit
   `STAGE08_F_ENV_FILE` prevent provider construction/network access?
5. Is offline fake mode only a test seam that follows F1/E injection, while
   real provider timeout derives from the same E5 runtime control?
6. Did F2 avoid public API/schema/permission/migration and output artifacts?

## Output

Inspect source and run focused tests appropriate to concerns. Write
`.superpowers/sdd/stage08-package-f-task-f2-review-report.md` with C/I/M,
PASS/HOLD and evidence. Critical/Important blocks F3 real Provider execution.
