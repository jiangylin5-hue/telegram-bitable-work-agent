# Stage 07 Bitable Work Surface Module

## Scope

`BaseCanvas` and `RecordDetail` present the durable table system: Base, table, field schema, saved view and record. They share the same returned typed field metadata used by governance and digital-employee draft rendering.

## Interaction Contract

1. `AppShell` provides an authorized Base/view destination.
2. `BaseCanvas` loads permitted table/view metadata, then schema and paginated records for the active view.
3. User filters, sorting, grouping or view changes are submitted as server-recognized view operations; client-only manipulation cannot create a different authority scope.
4. Selecting a record opens `RecordDetail` with only permitted fields.
5. Direct edits use the record version returned by the server; success replaces that record window, conflict reloads it.
6. Bot draft links open the same `RecordDetail` field vocabulary and then `DraftConfirmation`; the draft renderer never invents field labels or before values.

## Responsive Behavior

Grid remains table-shaped. Mobile can hide low-priority columns, support horizontal movement and use full-screen record detail, but cannot silently change saved filter/sort/group semantics. Kanban, Calendar and Form likewise change density and gesture only.

## Builder Interaction

Desktop builders open field/view/schema editors from the active table. A mutation refreshes the schema before record rendering resumes, preventing stale column/permission interpretation. Mobile builders use sheets or full-screen editors with the same API contracts.

### Approved F1 Independent Field Creation

F1 is the first real field action after P3's fieldless table. The authorized browser opens a table-local drawer/sheet, sends only `name`, approved `field_type`, `required` and permitted select choices through an idempotent initialization endpoint, then rereads the safe schema and current saved-view data before displaying the column. The server owns generated field keys, order, default policy, field/value validation, active-view visibility update and sanitized audit. The Canvas schema and F1 receipt never expose a field policy or raw configuration.

F1 creates only independent `text`, `number`, `date`, `status`, `single_select`, `multi_select`, `user`, `checkbox`, `url`, `email` and `phone` fields. Relation/lookup target selection, advanced JSON fields, field editing/reorder/delete and additional view configuration remain separate F2/V1 work.
