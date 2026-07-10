# F1 Field Builder Visual QA

## Result

blocked

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

## Blocking evidence gaps

- The source reference includes a populated Workspace Ledger plus assistant rail, which belongs to wider Package 2/4 work and is intentionally not claimed as F1 parity.
- The direct-edit screenshot is now captured, but the full browser matrix still lacks explicit duplicate-name server feedback and an in-flight field request interrupted by a workspace/view transition. Existing component/application tests cover the corresponding behaviour; they are not substituted for those browser cases.
- The three F1 real-PostgreSQL proof cases remain skipped until an authorised disposable `STAGE06_LOCAL_DATABASE_URL` is available.
