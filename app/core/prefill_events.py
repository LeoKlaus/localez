import asyncio
import json
import uuid
from dataclasses import dataclass, field


@dataclass
class _Job:
    event: asyncio.Event = field(default_factory=asyncio.Event)
    result: dict = field(default_factory=dict)


_jobs: dict[tuple[uuid.UUID, str], _Job] = {}


def register(project_id: uuid.UUID, language: str) -> None:
    _jobs[(project_id, language)] = _Job()


def signal(project_id: uuid.UUID, language: str, filled: int, skipped: int) -> None:
    # Pop here so completed jobs don't linger; waiters already hold a reference.
    job = _jobs.pop((project_id, language), None)
    if job:
        job.result = {"filled": filled, "skipped": skipped}
        job.event.set()


async def wait_for_result(
    project_id: uuid.UUID, language: str, timeout: float = 120.0
) -> str:
    job = _jobs.get((project_id, language))
    if job is None:
        return json.dumps({"status": "idle"})
    try:
        await asyncio.wait_for(job.event.wait(), timeout=timeout)
        return json.dumps({"status": "ready", **job.result})
    except asyncio.TimeoutError:
        _jobs.pop((project_id, language), None)
        return json.dumps({"status": "timeout"})
