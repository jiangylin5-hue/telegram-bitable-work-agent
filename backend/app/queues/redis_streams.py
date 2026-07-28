from dataclasses import dataclass, field
from typing import Any, Protocol


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

    def claim_pending(
        self,
        stream_name: str,
        *,
        group_name: str,
        consumer_name: str,
        min_idle_ms: int,
        count: int = 10,
    ) -> list["RedisStreamJob"]:
        pass


@dataclass(frozen=True)
class RedisStreamJob:
    entry_id: str
    fields: dict[str, str]


class RedisStreamsClient:
    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client
        self._known_groups: set[tuple[str, str]] = set()

    @classmethod
    def from_url(cls, redis_url: str, **kwargs: Any) -> "RedisStreamsClient":
        from redis import Redis

        redis_client = Redis.from_url(
            redis_url,
            decode_responses=False,
            **kwargs,
        )
        return cls(redis_client)

    def xadd_once(
        self,
        stream_name: str,
        *,
        idempotency_key: str,
        fields: dict[str, str],
    ) -> bool:
        for _entry_id, existing_fields in self._redis.xrange(stream_name):
            existing_idempotency_key = _decode_fields(existing_fields).get(
                "idempotency_key"
            )
            if existing_idempotency_key == idempotency_key:
                return False

        payload = dict(fields)
        payload["idempotency_key"] = idempotency_key
        self._redis.xadd(stream_name, payload)
        return True

    def read_group(
        self,
        stream_name: str,
        *,
        group_name: str,
        consumer_name: str,
        count: int = 10,
    ) -> list[RedisStreamJob]:
        self._ensure_group(stream_name, group_name)
        response = self._redis.xreadgroup(
            groupname=group_name,
            consumername=consumer_name,
            streams={stream_name: ">"},
            count=count,
        )
        jobs: list[RedisStreamJob] = []
        for _response_stream_name, entries in response:
            for entry_id, fields in entries:
                jobs.append(
                    RedisStreamJob(
                        entry_id=_decode_value(entry_id),
                        fields=_decode_fields(fields),
                    )
                )
        return jobs

    def ack(self, stream_name: str, *, group_name: str, entry_id: str) -> bool:
        acknowledged = self._redis.xack(stream_name, group_name, entry_id)
        return bool(acknowledged)

    def claim_pending(
        self,
        stream_name: str,
        *,
        group_name: str,
        consumer_name: str,
        min_idle_ms: int,
        count: int = 10,
    ) -> list[RedisStreamJob]:
        self._ensure_group(stream_name, group_name)
        response = self._redis.xautoclaim(
            stream_name,
            group_name,
            consumer_name,
            min_idle_ms,
            start_id="0-0",
            count=count,
        )
        entries = response[1] if len(response) >= 2 else []
        return [
            RedisStreamJob(
                entry_id=_decode_value(entry_id),
                fields=_decode_fields(fields),
            )
            for entry_id, fields in entries
        ]

    def _ensure_group(self, stream_name: str, group_name: str) -> None:
        group_key = (stream_name, group_name)
        if group_key in self._known_groups:
            return
        try:
            self._redis.xgroup_create(
                stream_name,
                group_name,
                id="0",
                mkstream=True,
            )
        except Exception as exc:
            if "BUSYGROUP" not in str(exc).upper():
                raise
        self._known_groups.add(group_key)


@dataclass
class RedisStreamEntry:
    entry_id: str
    idempotency_key: str
    fields: dict[str, str]
    delivered_groups: set[str] = field(default_factory=set)
    acknowledged_groups: set[str] = field(default_factory=set)
    delivered_consumer_by_group: dict[str, str] = field(default_factory=dict)


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
        jobs: list[RedisStreamJob] = []
        for entry in self._entries_by_stream.get(stream_name, []):
            if group_name in entry.acknowledged_groups:
                continue
            if group_name in entry.delivered_groups:
                continue
            entry.delivered_groups.add(group_name)
            entry.delivered_consumer_by_group[group_name] = consumer_name
            jobs.append(
                RedisStreamJob(
                    entry_id=entry.entry_id,
                    fields=dict(entry.fields),
                )
            )
            if len(jobs) >= count:
                break
        return jobs

    def claim_pending(
        self,
        stream_name: str,
        *,
        group_name: str,
        consumer_name: str,
        min_idle_ms: int,
        count: int = 10,
    ) -> list[RedisStreamJob]:
        if min_idle_ms < 0:
            raise ValueError("redis_stream_min_idle_invalid")
        jobs: list[RedisStreamJob] = []
        for entry in self._entries_by_stream.get(stream_name, []):
            if group_name not in entry.delivered_groups:
                continue
            if group_name in entry.acknowledged_groups:
                continue
            entry.delivered_consumer_by_group[group_name] = consumer_name
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


def _decode_fields(fields: dict[object, object]) -> dict[str, str]:
    return {
        _decode_value(key): _decode_value(value)
        for key, value in fields.items()
    }


def _decode_value(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)
