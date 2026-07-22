# Stage08 Package C3 — Task 1 Independent Review Brief

Review only C3 Task 1 against its implementation brief, the C3 design/plan, and actual diff. Do not modify code, tests, docs beyond creating the review report, database, API, schema, C1/C2, or external systems.

Verify: exact 12,000/24,000/36,000 and 24/120 caps; status/flag arithmetic; pending contains no rendered group content; C1 general marker is safely dropped when direct group evidence exists; safe view has no text/UUID/actor/plan/scope/handle/digest/source-reference carrier; deep validator rejects model_construct/subclass/nested carrier paths; Pydantic errors do not echo values in normal string representation. Ensure no C1/C2 public contract modification and no prohibited dependency/import.

Independently run the focused contract suite, compileall, static carrier scan, and scoped diff check. Classify findings Critical/Important/Minor. If none, return PASS with exact outputs. Do not claim C3/Package C complete.
