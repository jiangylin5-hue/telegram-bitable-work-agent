# F1 Field Builder Visual QA

## Result

passed (F1 visual scope)

## Scope and reference

- Scope: the F1 Base Canvas field-creation path only, not the complete Stage07 product.
- Reference: `../project-docs/08-implementation/assets/stage07/workspace-ledger-reference.png`.
- Comparison: the reference and rendered F1 desktop state were emitted together for review at 1440px. The test then exercised 1280px, 430px and 390px with a disposable local fixture.

## Passed F1 visual checks

- The Canvas keeps the selected reference grammar where F1 owns it: white surface, cool gray separators, restrained azure action color, compact 6-8px controls and a dense table toolbar.
- Desktop field creation uses a right-side drawer; 430px and 390px use a full-width sheet with a visible close control, labelled inputs and an anchored action row.
- The corrected 390px nonempty-table toolbar keeps both `添加字段` and `新建记录` reachable. This was verified by opening the drawer from the actual mobile trigger, rather than resizing an already-open drawer.
- Blank-name validation, retryable 503 feedback, locked 409 feedback and generic 403 denial were observed. The final fixture console check reported no warnings or errors.
- The corrected direct-edit fixture changed `客户阶段` from `新建` to `跟进中`, removed `续费关注` from the selected tags and rendered version `2` in both Grid and Record Detail. The retained sanitized evidence is `../project-docs/08-implementation/artifacts/stage07/f1-direct-edit-success-1440.png`; the final console check was empty.
- The duplicate-name fixture was exercised at 1440px, 1280px, 430px and 390px. At every width it preserved `客户阶段`, showed only `字段名称已存在，请使用其他名称。` and omitted `field_name`; the final console check was empty. The companion pending fixture kept the dialog visible and disabled create, close and cancel at each of the four widths.

## Blocking evidence gaps

- The source reference includes a populated Workspace Ledger plus assistant rail, which belongs to wider Package 2/4 work and is intentionally not claimed as F1 parity.
- The delayed workspace/view replacement remains an application-level scope-isolation test because the modal correctly blocks the impossible background interaction. It is covered by the delayed-receipt application test, rather than by a forced browser interaction that the UI correctly makes impossible.
- The three F1 real-PostgreSQL proof cases ran and passed on 2026-07-11 against an authorised disposable local database. This supports F1's implementation evidence; it does not extend this visual-QA result to wider Stage07 scope.
