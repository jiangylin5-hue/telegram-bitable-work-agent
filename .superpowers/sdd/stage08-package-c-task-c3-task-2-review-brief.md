# Stage08 Package C3 — Task 2 Independent Review Brief

Review Task 2 only. Read the C3 design/plan, Task 1 contract/review, Task 2 brief/report, actual C3 service/tests, and C1/C2 interfaces. Do not modify code/tests/phase docs, schema/API, database or external systems; create only an independent review report.

Verify actual behavior against the contract:

1. Only `compose_stage08_context` and `render_stage08_composite_context` are public service functions; returned composite is private/non-JSON and safe view has no content/identity carrier.
2. C1 plan revalidation and actor-plan identity equality happen before any C2 authority attempt; another valid member cannot supply a group binding for an old plan.
3. C2 authority/window/materialization use only existing private helpers and exact business scope; no Message/raw/history fallback/import/network.
4. Renderer recomposes current C1/C2 state, and original opaque C2 lineage blocks stale group body after projection/source/mapping/member/binding/relation drift or forged window state. Assess whether C1 stale content is likewise re-read and whether group drift handling remains safe.
5. C1 evidence first, D6 group blocks next, no general marker mixed with internal evidence, direct content budget stays 12k/24k/36k, and over-limit cannot emit a truncated or persisted group body.
6. Compression remains fail-closed/no raw rendering in Task 2; no provider/digest/persistence side effect has been added.
7. Tests are meaningful and C1/C2 public code untouched. Independently run Task2 focused (`-W error`), Task1+C1+C2+Task2 unit regression, compileall, static prohibited scan and scoped diff check.

Classify Critical/Important/Minor with exact lines. If no Critical/Important, PASS Task2 only; do not claim Task3/C3/Package C completion.
