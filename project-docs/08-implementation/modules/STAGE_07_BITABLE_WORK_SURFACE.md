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
