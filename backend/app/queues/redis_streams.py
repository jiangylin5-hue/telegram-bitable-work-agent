from dataclasses import dataclass, field
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

    def read_group(
        self,
        stream_name: str,
        *,
        group_name: str,
        consumer_name: str,
        count: int = 10,
    ) -> list["RedisStreamJob"]:
        pass

    def ack(self, stream_name: str, *, group_name: str, entry_id: str) -> bool:
        pass


@dataclass(frozen=True)
class RedisStreamJob:
    entry_id: str
    fields: dict[str, str]


@dataclass
class RedisStreamEntry:
    entry_id: str
    idempotency_key: str
    fields: dict[str, str]
    delivered_groups: set[str] = field(default_factory=set)
    acknowledged_groups: set[str] = field(default_factory=set)


class InMemoryRedisStreams:
    def __init__(self) -> None:
        self._entries_by_stream: dict[str, list[RedisStreamEntry]] = {}
        self._next_id_by_stream: dict[str, int] = {}

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
                entry_id=self._next_entry_id(stream_name),
                idempotency_key=idempotency_key,
                fields=dict(fields),
            )
        )
        return True

    def read_group(
        self,
        stream_name: str,
        *,
        group_name: str,
        consumer_name: str,
        count: int = 10,
    ) -> list[RedisStreamJob]:
        del consumer_name
        jobs: list[RedisStreamJob] = []
        for entry in self._entries_by_stream.get(stream_name, []):
            if group_name in entry.acknowledged_groups:
                continue
            if group_name in entry.delivered_groups:
                continue
            entry.delivered_groups.add(group_name)
            jobs.append(
                RedisStreamJob(
                    entry_id=entry.entry_id,
                    fields=dict(entry.fields),
                )
            )
            if len(jobs) >= count:
                break
        return jobs

    def ack(self, stream_name: str, *, group_name: str, entry_id: str) -> bool:
        for entry in self._entries_by_stream.get(stream_name, []):
            if entry.entry_id != entry_id:
                continue
            entry.acknowledged_groups.add(group_name)
            return True
        return False

    def entries(self, stream_name: str) -> list[dict[str, object]]:
        return [
            {
                "idempotency_key": entry.idempotency_key,
                "fields": dict(entry.fields),
            }
            for entry in self._entries_by_stream.get(stream_name, [])
        ]

    def pending_count(self, stream_name: str, group_name: str) -> int:
        return sum(
            1
            for entry in self._entries_by_stream.get(stream_name, [])
            if group_name in entry.delivered_groups
            and group_name not in entry.acknowledged_groups
        )

    def _next_entry_id(self, stream_name: str) -> str:
        next_id = self._next_id_by_stream.get(stream_name, 0) + 1
        self._next_id_by_stream[stream_name] = next_id
        return f"{next_id}-0"
