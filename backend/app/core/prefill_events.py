import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class _Job:
    event: asyncio.Event = field(default_factory=asyncio.Event)
    result: dict = field(default_factory=dict)
    completed_at: datetime | None = None


_jobs: dict[tuple[uuid.UUID, str], _Job] = {}

_COMPLETED_JOB_TTL = 300  # seconds to retain a completed job for late-connecting clients


def register(project_id: uuid.UUID, language: str) -> None:
    _evict_stale()
    _jobs[(project_id, language)] = _Job()


def signal(project_id: uuid.UUID, language: str, filled: int, skipped: int) -> None:
    job = _jobs.get((project_id, language))
    if job:
        job.result = {"filled": filled, "skipped": skipped}
        job.completed_at = datetime.now(UTC)
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
        return json.dumps({"status": "timeout"})
    finally:
        _jobs.pop((project_id, language), None)


def _evict_stale() -> None:
    cutoff = datetime.now(UTC).timestamp() - _COMPLETED_JOB_TTL
    stale = [
        key for key, job in _jobs.items()
        if job.completed_at is not None and job.completed_at.timestamp() < cutoff
    ]
    for key in stale:
        _jobs.pop(key, None)
