from __future__ import annotations

from collections.abc import Iterable


_PREFIX_LIMITS = {
    "o": 16,
    "c": 128,
    "e": 256,
    "a": 32,
    "f": 64,
    "v": 384,
    "s": 7,
}


def compact_reference(prefix: str, index: int) -> str:
    limit = _PREFIX_LIMITS.get(prefix)
    if limit is None or index < 1 or index > limit:
        raise ValueError("grounded_request_reference_limit")
    return f"{prefix}{index:03d}"


def compact_reference_map(prefix: str, identities: Iterable[str]) -> dict[str, str]:
    ordered = tuple(sorted(set(identities)))
    return {
        identity: compact_reference(prefix, index)
        for index, identity in enumerate(ordered, start=1)
    }


__all__ = ["compact_reference", "compact_reference_map"]
