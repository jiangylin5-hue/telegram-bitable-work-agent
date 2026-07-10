# Stage07 F1 Field Builder Design

## Status

- Status: approved design specification; implementation-plan and code work follow this document.
- Date: 2026-07-10
- Scope: Stage07 Package 2 F1 — safe creation and immediate use of independent, typed table fields on desktop and mobile.
- User decision: the user approved the F1 → F2 → V1 sequence and approved F1 to support the independent business field types listed in section 2. F2 retains relations and lookup; V1 retains additional saved views.
- Source alignment: `AGENTS.md`; `project-docs/08-implementation/STAGE_07_SOURCE_OF_TRUTH.md`; `STAGE_07_MINI_APP_UI_DESIGN.md`; `STAGE_07_VISUAL_REFERENCE_MANIFEST.md`; `STAGE_07_SDD.md`; `STAGE_07_API_DATA_SECURITY_CONTRACT.md`; `modules/STAGE_07_BITABLE_WORK_SURFACE.md`; `STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`; Stage06 platform models, authorization and audit services.
- Visual baseline: [Workspace Ledger reference](../../../project-docs/08-implementation/assets/stage07/workspace-ledger-reference.png) supplies the desktop table/toolbar grammar. It is a comparison reference, not copied product data or source code.

## 1. Purpose

P3 deliberately creates an empty table with a real default Grid and no fake field action. F1 turns that honest empty state into a usable, authorized schema action without exposing Stage06's backend/admin primitive field API to the browser.

```text
authorized table -> add field -> server validates and persists one field
-> server makes it visible in saved views -> client rereads safe schema
-> table and record forms use the authoritative field model
```

The F1 outcome is not a generic schema administration console. It is a controlled first-field and additional-independent-field workflow that makes an empty or existing table usable while preserving field policy, saved-view semantics, audit and database authority.

## 2. Product Scope

### 2.1 In scope

F1 supports creation of these independent business field types:

| Family | Field types | Builder input |
| --- | --- | --- |
| Basic value | `text`, `number`, `date`, `checkbox` | display name, type, optional required flag |
| Choice | `status`, `single_select`, `multi_select` | display name, type, optional required flag, ordered choices |
| People/contact | `user`, `url`, `email`, `phone` | display name, type, optional required flag |

All F1 field creation is available only to a current workspace member whose server role permits `field.manage`. The same condition controls the visible entry control, but the control is only a presentation hint; every server request independently authorizes the action.

F1 also includes the minimum follow-through required for a field to be useful:

1. an authorised desktop drawer and mobile full-screen sheet;
2. generated internal field keys and validated choice options on the server;
3. atomic visibility of the new field in the current table's saved views;
4. server-filtered record-create support for `multi_select`;
5. choice-aware direct record editing for `status`, `single_select` and `multi_select`;
6. schema/presentation/record/create-form rereads after a successful creation;
7. safe validation, denial, retry, conflict and rollback behaviour; and
8. sanitised audit events and automated/browser evidence.

### 2.2 Explicitly out of scope

F1 does **not** create a hidden partial implementation of later Builder packages:

- `linked_record`, `lookup` and their target-table/target-field pickers (F2);
- `json` as an end-user editable Builder type; it remains a backend/integration reservation until a separately designed advanced-field surface;
- field rename, type conversion, required-state edit, options edit, reorder, hide, archive, delete or restoration;
- choosing a table primary field or auto-promoting the first field;
- field/view permission-policy editing, field masking or role management;
- creating additional views, filters, sorts, groups, view policies or default-view switching (V1 and later decisions);
- importing/templates, Base/table rename or deletion, governance, Bots, draft confirmation, Telegram sends or external provider actions;
- client-provided `key`, `options`, raw view configuration, `permission_policy`, `status`, `order_index`, audit data or role claims; and
- a local-only field list, optimistic column or client-side filter/sort/group semantics.

F2 and V1 remain planned product scope, not discarded functionality. This sequencing isolates relationship disclosure and saved-view configuration from independent field creation.

## 3. Reuse And Technology Boundary

F1 reuses project-native mature patterns rather than adding a new client schema engine:

| Existing pattern | F1 reuse |
| --- | --- |
| P3 atomic Builder initialization | explicit safe browser endpoint, `Idempotency-Key`, one transaction, safe receipt, fresh authorised reread and `409` lock behaviour |
| Stage06 UoW, authorization and audit services | ownership resolution, `field.manage`, SQLAlchemy transaction, audit sanitation and PostgreSQL enforcement |
| `@tanstack/react-query` protected-query boundary | verified user/workspace/table keys, cancellation and invalidation of safe reads |
| Existing Builder drawer/sheet and native form controls | accessible controlled inputs, focus management, inline validation and mobile sheet behaviour |
| Existing Stage06 field/value validation | typed JSONB record values, with the choice-membership validation added by F1 |

No new form, drag-and-drop, grid or visual dependency is introduced in F1. `react-hook-form`, dnd-kit and a client-side data-table engine are unnecessary for one-field creation and would add state authority that the current server-owned contract does not need. Later reorder and large-grid work may evaluate those mature libraries separately.

## 4. Confirmed Domain Decisions

| Topic | F1 rule | Reason |
| --- | --- | --- |
| Field identity | Browser submits a display name; server generates a collision-safe opaque `fld_<server-uuid-suffix>` key. | Ordinary users do not manage technical keys and a duplicate-click cannot choose one. |
| Display names | Trimmed `1..160` character names; duplicate visible names in one table are rejected case-insensitively after whitespace normalization. | Field labels must be unambiguous in a compact table and record form. |
| Default policy | New fields receive the current project default policy `{}`. No policy travels from browser to server. | F1 does not silently add permission administration. |
| Select choices | `status`, `single_select` and `multi_select` require `1..100` nonblank, unique choices of at most 64 characters. Order is preserved. | A newly required choice field must be immediately creatable and editable. |
| Choice enforcement | Values are accepted only when the field has a valid persisted `options.choices` list. Legacy primitive fields without that list retain their existing type-only validation. | F1 gains real selection semantics without retroactively breaking historical data. |
| Required fields | Required status applies to new record creation; existing record updates remain partial and do not retroactively corrupt old rows. | A field add is schema evolution, not an unannounced data migration. |
| Field order | Server locks the table row, assigns the next `order_index`, then commits. Different concurrent field creations serialize rather than producing duplicate order. | List order is a durable presentation property, not a client race outcome. |
| Saved views | The server appends the field key once to every active same-table view whose persisted `config.fields` is an explicit list. A view without that list already resolves all current fields and needs no mutation. | A created field becomes visible immediately without the browser editing raw view JSON or changing filters/sorts/groups. |
| First/default field | F1 does not set `tables.primary_field_id` and does not impose a title field. | Primary-field semantics belong to later typed-field/relationship decisions. |
| Record state | Existing rows receive no synthetic value. The renderer shows an empty cell; new records use the server-returned create form. | The field is real without inventing user data. |

## 5. Safe API And Data Contract

### 5.1 Safe schema read correction

The current UI must never receive `permission_policy` or arbitrary field options from `/tables/{table_id}/schema`. F1 formalizes the project rule already stated in Stage07 API documentation: the ordinary Canvas schema read returns only a safe field projection.

```ts
type SafeTableField = {
  id: string
  table_id: string
  name: string
  key: string
  field_type: string
  required: boolean
  options: { choices?: string[] }
  order_index: number
}

type SafeTableSchema = {
  table: { id: string; base_id: string; name: string; key: string; status: string }
  fields: SafeTableField[]
}
```

Only `status`, `single_select` and `multi_select` can expose a validated `options.choices` array. All other field types expose `{}`. The response excludes `permission_policy`, `default_value`, `unique`, `status`, unrecognised option keys and any role/membership claim. It still removes fields not readable by the requesting actor.

This is a security alignment of an existing Stage07 read route, not a permission-model change. Backend/admin-only primitive endpoints may continue to use their own raw response models; the Mini App never calls them.

### 5.2 Field initialization endpoint

```http
POST /tables/{table_id}/field-initializations
Idempotency-Key: <non-empty UUID-like opaque token, max 160 chars>
Content-Type: application/json
```

```json
{
  "name": "客户阶段",
  "field_type": "status",
  "required": true,
  "choices": ["线索", "跟进中", "已成交"]
}
```

The request model has `extra="forbid"`. It accepts only `name`, `field_type`, `required` and (for choice fields) `choices`. `key`, `options`, `permission_policy`, `order_index`, `status`, view identifiers, policies and arbitrary JSON are rejected before any durable write.

The response is a navigation/cache receipt, not a raw field model:

```ts
type FieldInitializationReceipt = {
  field: SafeTableField
  affected_view_ids: string[]
}
```

`affected_view_ids` contains only active same-table views whose explicit field list changed. It contains no raw view configuration, policies, audit state, roles, idempotency record or record data.

### 5.3 Response and recovery rules

| Condition | HTTP result | Browser behaviour |
| --- | --- | --- |
| First valid submission | `201 Created` plus safe receipt | Invalidate safe table/view/create-form reads, reread authorised resources, verify exact field ID and then close the panel. |
| Same key and normalised payload | `200 OK` plus original receipt | Treat as the same successful operation; never add a second column. |
| Same key with a different payload | `409` | Lock the panel until it is closed; a deliberate new panel gets a new key. |
| Invalid name/type/choices | `422` safe code | Preserve values, identify the relevant input without echoing untrusted raw data, and make no durable write. |
| Missing table | `404` generic unavailable state | Do not infer the Base/workspace or retry against a guessed table. |
| Missing membership or `field.manage` | `403` generic denied state | Clear the affected protected workspace scope; no field preview survives. |
| Unauthenticated/expired identity | `401` | Remove protected client state and restart bootstrap. |
| Network/5xx before receipt | no assumed outcome | Preserve values and the same idempotency key for one explicit retry. |
| Database/view-update failure | safe server error | One rollback removes field, config changes, audit and idempotency reservation together. |

### 5.4 Server transaction

For a new key the service performs these operations in one SQLAlchemy transaction:

1. resolve table -> Base -> workspace and require current active membership plus `field.manage`;
2. normalise and validate the request, reject duplicate display names, and acquire a row lock for the target table;
3. reserve/replay the operation through the existing scoped Stage06 idempotency record pattern;
4. generate a `fld_<server-uuid-suffix>` key, persist one `PlatformField` with default policy and the next durable order;
5. append the generated key once to eligible active same-table view configurations entirely on the server;
6. write a sanitised `stage07.field_initialized` audit event containing resource identifiers, field type, required flag, order and affected-view IDs — never a policy, arbitrary options or record values;
7. store the safe receipt reference as completed; and
8. commit all writes once, or roll them all back.

An identical concurrent key replays the winner only after its completed normalised payload matches. Distinct concurrent field additions serialize on the table lock and receive consecutive orders. Database failures and losing unique-key races reread only the final matching completed idempotency result.

### 5.5 Record form and direct editing alignment

`GET /tables/{table_id}/create-form` adds `multi_select` only when the actor can write it and returns its validated choices. `can_create` remains false whenever any required field cannot be safely created.

`POST /tables/{table_id}/records` and `PATCH /records/{record_id}` validate a configured select value against `options.choices`:

- `status` and `single_select`: one allowed string;
- `multi_select`: an array of distinct allowed strings;
- fields without a valid choices list: retain existing historical type-only behavior.

The Mini App renders a native select for single-value choices and an accessible checkbox-list/popover pattern for multi-select in create and direct-edit flows. It submits only visible, server-writable keys; it never coerces unknown options or writes a policy.

## 6. Interaction Design

### 6.1 Entry and layout

The active table uses the retained `Workspace Ledger` grammar. On desktop, the capability-gated `添加字段` action is adjacent to the table/view controls and opens a compact right drawer. On mobile, the same action opens a labelled full-screen sheet with large touch targets and a persistent submit bar.

An empty authorised Grid replaces the P3 honest waiting message with a real `添加第一个字段` action. A caller without the existing `can_manage_schema` display hint sees only the explanatory empty state; the server remains the final authority.

The form contains:

1. field name with initial focus;
2. a compact type picker grouped as Basic, Choice and Contact;
3. a required toggle;
4. an ordered choice editor only for choice types, with add/remove and keyboard access; and
5. cancel and create actions.

The form never shows technical keys, raw JSON, policies or a fake colour/automation configuration. It starts with `text` selected, but no field exists until a server receipt is verified.

### 6.2 Success flow

```text
Builder opens safe panel
-> enter name/type/allowed choices
-> client validates obvious missing values
-> POST safe field initialization with new Idempotency-Key
-> server commits Field + safe view visibility + audit once
-> client invalidates protected table schema/current-view presentation and windows/create form
-> client rereads authorised resources and verifies receipt.field.id
-> drawer closes; new column appears at the final server order
```

No optimistic column, inferred field key or locally fabricated value is rendered. If a view is revoked or a reread no longer contains the exact field, the app enters its existing safe unavailable/denied state rather than displaying the receipt as authority.

### 6.3 Failure and accessibility

- Client validation gives input-level feedback for blank names and missing/duplicate local choices, while server validation remains authoritative.
- `422` retains the panel and entered content; `409` locks fields and submit but retains the Cancel/Close control; network/5xx supports an explicit same-key retry; `401`/`403` remove protected state.
- Escape/Close works when no pending creation is active; focus returns to the invoking control after a non-successful close; focus moves to the first field input when opened.
- The type picker, required toggle, choice ordering controls, errors and pending state have visible labels and keyboard-operable controls. Colour never supplies the only status meaning.

## 7. BDD Acceptance Scenarios

### Scenario F1-1: Builder creates an immediately visible first field

Given an active builder opens a fieldless Grid, when they create a required `status` field with valid choices, then the server persists exactly one field, the default Grid displays the generated column after reread, the create form offers the choices, and no raw policy/configuration appears in the browser.

### Scenario F1-2: Unauthorised member sees no usable field mutation

Given a member lacks `field.manage`, when they open the same table or attempt the endpoint, then the entry is absent, the server returns a generic denial before a durable write, and no field name/key/policy is leaked by the error or cache.

### Scenario F1-3: Select values retain schema meaning

Given a builder created a `multi_select` field with three choices, when an authorised member creates or directly edits a record, then only a distinct subset of those three choices is accepted and rendered; an unknown choice is rejected without altering the record.

### Scenario F1-4: Retry never duplicates a field

Given a network interruption happens after the request leaves the browser, when the member explicitly retries with the same idempotency key and payload, then the response replays the same receipt and only one field/one audit event exists.

### Scenario F1-5: Atomic view visibility cannot leave a half-created column

Given the server fails while updating eligible saved-view configurations, when the request ends, then no new field, changed view configuration, completed idempotency record or field-initialization audit event survives.

### Scenario F1-6: Concurrent builders preserve order

Given two authorised users add different fields to the same table concurrently, when both operations complete, then both fields exist once with consecutive server-owned orders and each is visible under the returned saved-view semantics.

### Scenario F1-7: Mobile preserves authority and usable layout

Given a builder uses a `390px` or `430px` viewport, when they add a field, then the full-screen labelled sheet exposes all relevant inputs and error/retry/close controls, and success returns to the same authorised Grid rather than a desktop-only route.

## 8. Test And Evidence Plan

### 8.1 Backend tests

- TDD red/green service tests for supported-type allowlist, generated key, default policy, name/choice validation, no duplicate visible names, safe receipt and append-once view updates.
- Route/security tests for missing membership, `field.manage` denial, cross-workspace table references, raw request fields rejected, raw response policy/options omitted and no field/audit on failure.
- Record validation tests for configured choices, multi-select subset/distinctness and legacy no-choice compatibility.
- PostgreSQL integration tests for transaction rollback, same-key replay/different-payload conflict, distinct-key concurrent ordering, one field per successful operation, exact view config updates and audit sanitation. They use only the existing disposable `STAGE06_LOCAL_DATABASE_URL` mechanism and are not production evidence.
- Regression test for `/tables/{table_id}/schema`: a visible field with a policy and non-choice internal option returns neither value to the browser.

### 8.2 Frontend tests

- Component tests for desktop drawer/mobile sheet labels, type-dependent controls, choice operations, focus, validation, pending/409/retry/denial behaviours and no technical policy/key controls.
- API tests for exact request body/header, safe receipt parsing and protected-query invalidation keys.
- Application tests for fieldless -> field-created canvas transition, exact field ID verification, stale workspace/view response rejection, 401/403 cleanup, refreshed create-form choices and direct multi-select record mutation.
- Existing record/view tests are extended so a schema reread cannot restore raw policies/options or allow a hidden field to become a column.

### 8.3 Browser visual QA

Use a disposable fixture only after automated checks pass. Compare fresh screenshots against the retained `Workspace Ledger` reference at `1440px`, `1280px`, `430px` and `390px` for:

- desktop table toolbar and field drawer hierarchy;
- fieldless empty state versus real first-field entry;
- select/multi-select configuration and record use;
- validation, `503` explicit retry, `409` lock and generic `403` boundary;
- mobile sheet and return to the same Grid; and
- zero relevant browser console warnings/errors.

Fixtures, generated test fields and artifacts are deleted or documented after the run. Browser evidence does not substitute for real PostgreSQL or real Telegram Mini App evidence.

## 9. File And Module Ownership

| Area | Expected owner | Responsibility |
| --- | --- | --- |
| Request/response schemas and route | `backend/app/schemas/stage06_platform.py`, `backend/app/api/routes/stage06_platform.py` | safe F1 request/receipt and schema projection |
| Domain transaction and UoW | `backend/app/services/stage06_platform.py` plus UoW implementation | field initialization, table locking, choice validation, view update and audit |
| Database model/migration | existing `fields`, `views` and idempotency tables | no new table/migration unless implementation proves a missing lock or constraint cannot be met with current schema |
| Mini App transport/state | `mini-app/src/app/api.ts`, `App.tsx`, `protectedQuery.ts` | typed request, scoped invalidation/re-read and receipt verification |
| Field UI | new focused field-builder panel plus `BaseCanvas`, `CreateRecordPanel`, `RecordDetail` | desktop/mobile creation and choice-aware record controls |
| Design/acceptance documentation | Stage07 contract, SDD, BDD, test plan, risk register, progress, traceability and F1 substage plan | maintain evidence and exact out-of-scope boundary |

## 10. Risks And Guards

| Risk | F1 guard |
| --- | --- |
| Browser receives policy or arbitrary config | safe schema/receipt projections and negative response tests |
| New field is invisible after success | server updates explicit view field lists and client rereads presentation |
| Duplicate click or recovery duplicates a column | endpoint-specific idempotency and same-key replay |
| Concurrent builders give the same order | table row lock and real PostgreSQL concurrency evidence |
| Choice field cannot create a record | required validated choices plus multi-select create/edit support |
| Field add alters old records | no synthetic values and partial update semantics |
| Later relation/permission work leaks through F1 | strict type allowlist and no policy/relation/configuration controls |
| Visual drift from selected references | retained image baseline plus four-width screenshot comparison |

## 11. Specification Self-Review

- Placeholder scan: no `TBD`, `TODO` or unresolved implementation marker is used as a requirement.
- Consistency: the field allowlist, request shape, record editor support, server validation and BDD scenarios all cover the same independent-field scope.
- Scope: F1 creates fields and makes them usable; relation, lookup, advanced JSON, view configuration and governance remain explicitly outside it.
- Ambiguity: server-generated keys, choice rules, view visibility update, order serialization, retry semantics and safe response fields are defined above rather than delegated to client interpretation.

## 12. Implementation Gate

This specification authorises writing the detailed F1 implementation plan and aligned Stage07 documents. Implementation starts only after those documents are internally consistent with this specification; every code change must stay inside the scope and verification gates above.
