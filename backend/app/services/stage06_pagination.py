import base64
from dataclasses import dataclass
import json
from typing import Generic, Protocol, TypeVar


class _HasId(Protocol):
    id: object


T = TypeVar("T", bound=_HasId)


class Stage06PaginationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Stage06Page(Generic[T]):
    items: list[T]
    next_cursor: str | None
    has_more: bool


def bounded_page_size(limit: int | None) -> int:
    value = 50 if limit is None else limit
    if value < 1 or value > 200:
        raise Stage06PaginationError("page_limit_exceeded")
    return value


def paginate_items(
    items: list[T],
    *,
    limit: int | None,
    cursor: str | None,
    preserve_order: bool = False,
) -> Stage06Page[T]:
    page_size = bounded_page_size(limit)
    ordered = list(items) if preserve_order else sorted(items, key=lambda item: str(item.id))
    cursor_id = _decode_cursor(cursor) if cursor else None
    if cursor_id is not None:
        if preserve_order:
            cursor_index = next(
                (index for index, item in enumerate(ordered) if str(item.id) == cursor_id),
                None,
            )
            if cursor_index is None:
                raise Stage06PaginationError("invalid_page_cursor")
            ordered = ordered[cursor_index + 1 :]
        else:
            ordered = [item for item in ordered if str(item.id) > cursor_id]
    window = ordered[: page_size + 1]
    has_more = len(window) > page_size
    selected = window[:page_size]
    next_cursor = (
        _encode_cursor(str(selected[-1].id))
        if has_more and selected
        else None
    )
    return Stage06Page(
        items=selected,
        next_cursor=next_cursor,
        has_more=has_more,
    )


def _encode_cursor(item_id: str) -> str:
    payload = json.dumps({"id": item_id}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(value: str) -> str:
    try:
        padding = "=" * (-len(value) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(value + padding).decode("utf-8")
        )
        item_id = payload["id"]
        if not isinstance(item_id, str) or not item_id:
            raise ValueError("invalid cursor id")
        return item_id
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise Stage06PaginationError("invalid_page_cursor") from exc
