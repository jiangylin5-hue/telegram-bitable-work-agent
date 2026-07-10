# Stage 07 Technical Decision 002: Form/Create Writable Model

## Status

- Decision status: proposal; implementation is prohibited until explicit user approval
- Scope: Mini App/desktop record creation and saved Form submission for existing Stage06 tables
- Non-scope: field schema editing, new field types, client-side permission inference, Bot writes, imports, drafts or Telegram actions

## 1. Evidence And Problem

Stage06 already has `POST /tables/{table_id}/records` and server-side `record.create` authorization. It validates field values, normalizes them, writes audit history and creates version `1` records. However, its request is only `{ values }`. The current Mini App cannot safely decide which visible fields the current actor may write:

- Table schema is a read model and contains raw `permission_policy`; it must not become a create-form authority source.
- Field readability does not prove field writability.
- Required/options/type semantics must be filtered server-side before a form can validate or render controls.
- The existing Form renderer is deliberately a read-only record preview, not a creation form.

## 2. Proposed Minimal Contract

Add one server-composed, read-only model before using the existing create mutation:

```text
GET /tables/{table_id}/create-form
```

Response (proposal):

```json
{
  "table_id": "uuid",
  "can_create": true,
  "fields": [
    {
      "key": "title",
      "name": "Title",
      "field_type": "text",
      "required": true,
      "options": { "select_options": [] },
      "order_index": 0
    }
  ]
}
```

Rules:

- Resolve table -> Base -> workspace and require existing `record.create` authorization.
- Return only fields passing a server-side create/write decision. Do not return `permission_policy`, hidden-field metadata, raw view config, inaccessible linked values or an actor role claim.
- If creation is denied, use the existing generic `403` boundary; do not return a partially informative field list.
- Reuse existing Stage06 value validation on `POST /tables/{table_id}/records`. The client sends only edited/create-field keys and displays safe validation errors.
- `POST` success returns the existing authoritative `RecordResponse`; the Mini App invalidates/reloads the exact target view window and optionally opens the new permitted record detail.

## 3. Alternatives Considered

| Alternative | Decision |
| --- | --- |
| Client derives writable fields from full schema/policy | Rejected: leaks policy and makes browser permission logic authoritative. |
| Extend existing schema response with a writable boolean | Rejected for this phase: changes a shared primitive schema contract and risks broader metadata exposure. |
| Dedicated, server-filtered `create-form` view model | **Recommended**: narrow, explicit and reusable by Form/create without changing mutation semantics. |
| Build a generic form-layout/schema-builder first | Deferred: it depends on separately approved builder and layout contracts. |

## 4. UI Behavior After Approval

1. A permitted user enters a saved Form or table create entry.
2. The client loads the filtered `create-form` model under its verified user/workspace/table query key.
3. The form renders only the returned fields; field controls use known Stage06-compatible scalar semantics first.
4. Submit is disabled during one in-flight request; the UI never claims success before the server response.
5. Success invalidates the active authorized view window, reloads it, and shows the returned version-1 record only if its fields remain permitted.
6. `401` clears all protected queries; `403` clears the affected workspace scope; validation errors remain field-local only when the server returns a safe mapped field key.

## 5. Deliberate First-Slice Limits

- Support `text`, `number`, `date`, `checkbox`, `select/status`, `url`, `email`, `phone` and `user` only after confirming their normalized options model.
- Keep `multi_select`, `linked_record`, `json`, `lookup`, computed/rollup and attachment values out of the first create UI.
- Do not infer defaults, auto-create links, submit drafts, bulk-create records or make Agent/Bot writes.
- Do not turn the current read-only saved Form renderer into a schema/layout editor.

## 6. Acceptance Criteria

- A non-member or non-creator cannot load the model or submit a record.
- Hidden/readable-but-not-writable fields never appear in the model or client payload.
- The model never contains raw policy/config payloads.
- Required/type validation remains server authoritative; the UI preserves safe field-local errors.
- Success creates one audited version-1 record and re-renders an authorized server view window.
- Browser QA covers desktop and `390x844` create success, validation failure and denied state using a disposable safe fixture; full backend/frontend regression passes.

## 7. Approval Request

Approve this dedicated server-filtered `GET /tables/{table_id}/create-form` contract as the prerequisite for the first Form/create slice, or provide a different product boundary. This approval would authorize the contract, tests and first scalar create UI only; it would not authorize builder, imports, governance or Bot/Telegram work.
