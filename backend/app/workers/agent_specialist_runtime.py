from __future__ import annotations

from dataclasses import dataclass
import os
from time import sleep

from app.core.config import validate_runtime_settings
from app.core.database import get_session_factory
from app.queues.redis_streams import RedisStreams, RedisStreamsClient
from app.schemas.agent_event_runtime import AgentCommandEnvelope
from app.workers.agent_tabular_runtime import (
    AgentTabularStreamWorker,
    AgentTabularWorkerResult,
    process_agent_tabular_command,
)


SPECIALIST_CAPABILITIES = (
    "platform.tabular.analyse",
    "platform.risk.analyse",
    "platform.daily.summarise",
)


@dataclass(frozen=True, slots=True)
class AgentSpecialistPoolResult:
    processed: int = 0
    recovered: int = 0
    dead_lettered: int = 0


class AgentSpecialistWorkerPool:
    def __init__(
        self,
        *,
        streams: RedisStreams,
        consumer_name: str,
        process,
        pending_min_idle_ms: int = 30_000,
    ) -> None:
        self.workers = tuple(
            AgentTabularStreamWorker(
                streams=streams,
                consumer_name=f"{consumer_name}-{capability.split('.')[1]}",
                process=process,
                stream_name=f"agent.commands.{capability}",
                group_name=f"stage11-{capability.replace('.', '-')}-workers",
                pending_min_idle_ms=pending_min_idle_ms,
            )
            for capability in SPECIALIST_CAPABILITIES
        )

    def run_once(self, limit_per_capability: int = 4) -> AgentSpecialistPoolResult:
        results: list[AgentTabularWorkerResult] = [
            worker.run_once(limit=limit_per_capability) for worker in self.workers
        ]
        return AgentSpecialistPoolResult(
            processed=sum(item.processed for item in results),
            recovered=sum(item.recovered for item in results),
            dead_lettered=sum(item.dead_lettered for item in results),
        )

    def run_continuously(self) -> None:
        while True:
            if self.run_once() == AgentSpecialistPoolResult():
                sleep(0.25)


def main() -> None:
    settings = validate_runtime_settings()
    if settings.agent_event_runtime_mode != "redis_worker":
        raise RuntimeError("Stage11 specialist worker requires redis_worker mode")
    streams = RedisStreamsClient.from_url(settings.redis_url)
    session_factory = get_session_factory()
    consumer_name = os.getenv("AGENT_SPECIALIST_CONSUMER_NAME", "stage11-specialist-1")

    def process(envelope: AgentCommandEnvelope) -> None:
        with session_factory() as session:
            process_agent_tabular_command(
                session,
                envelope,
                settings=settings,
                worker_id=f"{consumer_name}-{envelope.target_capability}",
            )

    AgentSpecialistWorkerPool(
        streams=streams,
        consumer_name=consumer_name,
        process=process,
    ).run_continuously()


__all__ = [
    "AgentSpecialistPoolResult",
    "AgentSpecialistWorkerPool",
    "SPECIALIST_CAPABILITIES",
]


if __name__ == "__main__":
    main()
