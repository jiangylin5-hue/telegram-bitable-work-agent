from dataclasses import dataclass
from typing import Protocol


class RedisStreams(Protocol):
    def xadd_once(
        self,
        stream_name: str,
        *,
        idempotency_key: str,
        fields: dict[str, str],
    ) -> bool:
        pass


@dataclass(frozen=True)
class RedisStreamEntry:
    idempotency_key: str
    fields: dict[str, str]


class InMemoryRedisStreams:
    def __init__(self) -> None:
        self._entries_by_stream: dict[str, list[RedisStreamEntry]] = {}

    def xadd_once(
        self,
        stream_name: str,
        *,
        idempotency_key: str,
        fields: dict[str, str],
    ) -> bool:
        entries = self._entries_by_stream.setdefault(stream_name, [])
        if any(entry.idempotency_key == idempotency_key for entry in entries):
            return False
        entries.append(
            RedisStreamEntry(
                idempotency_key=idempotency_key,
                fields=dict(fields),
            )
        )
        return True

    def entries(self, stream_name: str) -> list[dict[str, object]]:
        return [
            {
                "idempotency_key": entry.idempotency_key,
                "fields": dict(entry.fields),
            }
            for entry in self._entries_by_stream.get(stream_name, [])
        ]
