from collections.abc import Mapping
from typing import Any


_VALUE_KEYS = {
    "values",
    "before_values",
    "proposed_values",
    "record_values",
}
_DROP_KEYS = {
    "content",
    "message_payload",
    "preview_rows",
    "prompt",
    "raw_response",
    "raw_text",
    "rows",
    "text",
}
_SAFE_KEYS = {
    "action",
    "actor_type",
    "base_id",
    "channel",
    "count",
    "draft_count",
    "employee_id",
    "field_type",
    "field_key",
    "field_keys",
    "import_job_id",
    "name",
    "order_index",
    "record_count",
    "record_id",
    "request_id",
    "role",
    "required",
    "status",
    "table_id",
    "template_id",
    "trace_id",
    "version",
    "view_id",
    "view_type",
    "workspace_id",
}
_SAFE_CONTAINERS = {
    "after",
    "before",
    "output",
    "resource_map",
}


def sanitize_stage06_audit_state(value: Any) -> Any:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        return None

    sanitized: dict[str, Any] = {}
    collected_field_keys: set[str] = set()
    for raw_key, item in value.items():
        key = str(raw_key)
        if key in _VALUE_KEYS:
            if isinstance(item, Mapping):
                collected_field_keys.update(str(field_key) for field_key in item)
            continue
        if key in _DROP_KEYS:
            continue
        if key in _SAFE_CONTAINERS and isinstance(item, Mapping):
            nested = sanitize_stage06_audit_state(item)
            if nested:
                sanitized[key] = nested
            continue
        if key in _SAFE_KEYS or key.endswith("_id") or key.endswith("_ids"):
            safe_value = _safe_audit_value(item)
            if safe_value is not None:
                sanitized[key] = safe_value
    if collected_field_keys:
        existing = sanitized.get("field_keys", [])
        sanitized["field_keys"] = sorted(
            set(str(item) for item in existing) | collected_field_keys
        )
    return sanitized


def _safe_audit_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [
            item
            for item in value
            if item is None or isinstance(item, (str, int, float, bool))
        ]
    if isinstance(value, Mapping):
        return sanitize_stage06_audit_state(value)
    return None
