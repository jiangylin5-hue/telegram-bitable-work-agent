from collections.abc import Callable
from dataclasses import dataclass
from time import sleep

from app.queues.redis_streams import RedisStreams, RedisStreamJob
from app.workers.stage03_handlers import (
    NonRetryableStage03WorkerError,
    RetryableStage03WorkerError,
    Stage03WorkerUnitOfWork,
    mark_message_processing_failure,
)

Stage03StreamHandler = Callable[[dict[str, str]], None]


@dataclass(frozen=True)
class WorkerRunResult:
    processed: int = 0
    retried: int = 0
    dead_lettered: int = 0
    missing_handler: int = 0

    def add(self, other: "WorkerRunResult") -> "WorkerRunResult":
        return WorkerRunResult(
            processed=self.processed + other.processed,
            retried=self.retried + other.retried,
            dead_lettered=self.dead_lettered + other.dead_lettered,
            missing_handler=self.missing_handler + other.missing_handler,
        )


class RedisStreamsWorker:
    def __init__(
        self,
        *,
        streams: RedisStreams,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        handlers: dict[str, Stage03StreamHandler],
        failure_uow: Stage03WorkerUnitOfWork | None = None,
    ) -> None:
        self.streams = streams
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name
        self.handlers = handlers
        self.failure_uow = failure_uow

    def run_once(self, limit: int = 10) -> WorkerRunResult:
        result = WorkerRunResult()
        jobs = self.streams.read_group(
            self.stream_name,
            group_name=self.group_name,
            consumer_name=self.consumer_name,
            count=limit,
        )
        for job in jobs:
            result = result.add(self._process_job(job))
        return result

    def run_continuously(
        self,
        *,
        limit: int = 10,
        poll_interval_seconds: float = 1.0,
        max_iterations: int | None = None,
    ) -> WorkerRunResult:
        result = WorkerRunResult()
        iterations = 0
        while max_iterations is None or iterations < max_iterations:
            iteration_result = self.run_once(limit=limit)
            result = result.add(iteration_result)
            iterations += 1
            if iteration_result == WorkerRunResult():
                sleep(poll_interval_seconds)
        return result

    def _process_job(self, job: RedisStreamJob) -> WorkerRunResult:
        handler = self.handlers.get(job.fields.get("event_type", ""))
        if handler is None:
            result = self._handle_failure(
                job,
                error_code="missing_handler",
                retryable=False,
            )
            return result.add(WorkerRunResult(missing_handler=1))

        try:
            handler(job.fields)
        except RetryableStage03WorkerError as exc:
            return self._handle_failure(
                job,
                error_code=str(exc),
                retryable=True,
            )
        except NonRetryableStage03WorkerError as exc:
            return self._handle_failure(
                job,
                error_code=str(exc),
                retryable=False,
            )

        self.streams.ack(
            self.stream_name,
            group_name=self.group_name,
            entry_id=job.entry_id,
        )
        return WorkerRunResult(processed=1)

    def _handle_failure(
        self,
        job: RedisStreamJob,
        *,
        error_code: str,
        retryable: bool,
    ) -> WorkerRunResult:
        if self.failure_uow is None:
            raise RuntimeError("failure_uow_required")

        disposition = mark_message_processing_failure(
            job.fields,
            self.failure_uow,
            error_code=error_code,
            retryable=retryable,
        )
        self.streams.ack(
            self.stream_name,
            group_name=self.group_name,
            entry_id=job.entry_id,
        )
        if disposition == "retry":
            return WorkerRunResult(retried=1)
        return WorkerRunResult(dead_lettered=1)
