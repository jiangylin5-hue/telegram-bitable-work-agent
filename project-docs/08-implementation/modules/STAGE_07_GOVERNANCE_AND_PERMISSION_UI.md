# Stage 07 Governance And Permission UI Module

## Scope

`Governance` presents members, roles, field/view permissions, audit readback, imports/templates and team Bot administration to authorized users.

## Interaction Contract

1. `AppShell` renders the management entry only from server capability data.
2. Governance loads paginated management models independently from regular user queues.
3. Permission editors reference immutable Base/table/field IDs from `BaseCanvas` schema; changes are submitted to backend authorization services.
4. After a role/field/view permission mutation, affected workspace caches are invalidated and bootstrap/capabilities refresh before further rendering.
5. Audit readback displays only server-sanitized metadata and paginates; it never requests raw record values to enrich a row.
6. Team Bot administration follows the approved lifecycle gate and cannot publish/configure beyond creator and workspace authority.

## Safety Rules

Local hiding is not security. Every governance request is separately authorized. A failed mutation restores authoritative state and avoids optimistic role/permission UI that could mislead the operator.
