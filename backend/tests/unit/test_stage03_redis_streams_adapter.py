from app.queues.redis_streams import RedisStreamJob, RedisStreamsClient


def test_real_redis_adapter_adds_each_idempotency_key_once() -> None:
    redis = FakeRedisClient()
    streams = RedisStreamsClient(redis)

    first = streams.xadd_once(
        "stage03:events",
        idempotency_key="telegram.message_received:message-1",
        fields={
            "event_id": "event-1",
            "event_type": "telegram.message_received",
        },
    )
    second = streams.xadd_once(
        "stage03:events",
        idempotency_key="telegram.message_received:message-1",
        fields={
            "event_id": "event-1",
            "event_type": "telegram.message_received",
        },
    )

    assert first is True
    assert second is False
    assert redis.xadded == [
        (
            "stage03:events",
            {
                "event_id": "event-1",
                "event_type": "telegram.message_received",
                "idempotency_key": "telegram.message_received:message-1",
            },
        )
    ]


def test_real_redis_adapter_decodes_read_group_jobs() -> None:
    redis = FakeRedisClient()
    redis.seed(
        "stage03:events",
        [
            (
                b"1740000000000-0",
                {
                    b"event_id": b"event-1",
                    b"event_type": b"telegram.message_received",
                    b"trace_id": b"tg:update-1",
                },
            )
        ],
    )
    streams = RedisStreamsClient(redis)

    jobs = streams.read_group(
        "stage03:events",
        group_name="telegram-message-workers",
        consumer_name="worker-1",
        count=5,
    )

    assert jobs == [
        RedisStreamJob(
            entry_id="1740000000000-0",
            fields={
                "event_id": "event-1",
                "event_type": "telegram.message_received",
                "trace_id": "tg:update-1",
            },
        )
    ]
    assert redis.read_group_calls == [
        (
            "telegram-message-workers",
            "worker-1",
            {"stage03:events": ">"},
            5,
        )
    ]
    assert redis.created_groups == [
        ("stage03:events", "telegram-message-workers", "0", True)
    ]


def test_real_redis_adapter_acknowledges_stream_entry() -> None:
    redis = FakeRedisClient(ack_result=1)
    streams = RedisStreamsClient(redis)

    assert (
        streams.ack(
            "stage03:events",
            group_name="telegram-message-workers",
            entry_id="1740000000000-0",
        )
        is True
    )
    assert redis.acked == [
        (
            "stage03:events",
            "telegram-message-workers",
            "1740000000000-0",
        )
    ]


class FakeRedisClient:
    def __init__(self, *, ack_result: int = 0) -> None:
        self._entries: dict[str, list[tuple[object, dict[object, object]]]] = {}
        self.ack_result = ack_result
        self.xadded: list[tuple[str, dict[str, str]]] = []
        self.acked: list[tuple[str, str, str]] = []
        self.created_groups: list[tuple[str, str, str, bool]] = []
        self.read_group_calls: list[tuple[str, str, dict[str, str], int]] = []

    def seed(
        self,
        stream_name: str,
        entries: list[tuple[object, dict[object, object]]],
    ) -> None:
        self._entries[stream_name] = entries

    def xrange(
        self,
        stream_name: str,
        min: str = "-",
        max: str = "+",
    ) -> list[tuple[object, dict[object, object]]]:
        del min, max
        return list(self._entries.get(stream_name, []))

    def xadd(self, stream_name: str, fields: dict[str, str]) -> str:
        entry_id = f"{len(self._entries.get(stream_name, [])) + 1}-0"
        entry = (entry_id, dict(fields))
        self._entries.setdefault(stream_name, []).append(entry)
        self.xadded.append((stream_name, dict(fields)))
        return entry_id

    def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: dict[str, str],
        count: int,
    ) -> list[tuple[str, list[tuple[object, dict[object, object]]]]]:
        self.read_group_calls.append((groupname, consumername, dict(streams), count))
        return [
            (stream_name, list(self._entries.get(stream_name, [])))
            for stream_name in streams
        ]

    def xgroup_create(
        self,
        stream_name: str,
        group_name: str,
        id: str = "0",
        mkstream: bool = True,
    ) -> None:
        self.created_groups.append((stream_name, group_name, id, mkstream))

    def xack(self, stream_name: str, group_name: str, entry_id: str) -> int:
        self.acked.append((stream_name, group_name, entry_id))
        return self.ack_result
