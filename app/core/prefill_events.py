import asyncio
import json
import uuid


_futures: dict[tuple[uuid.UUID, str], asyncio.Future] = {}


def register(project_id: uuid.UUID, language: str) -> None:
    key = (project_id, language)
    _futures[key] = asyncio.get_running_loop().create_future()


def signal(project_id: uuid.UUID, language: str, filled: int, skipped: int) -> None:
    future = _futures.get((project_id, language))
    if future and not future.done():
        future.set_result({"filled": filled, "skipped": skipped})



async def wait_for_result(
    project_id: uuid.UUID, language: str, timeout: float = 120.0
) -> str:
    future = _futures.get((project_id, language))
    if future is None:
        return json.dumps({"status": "idle"})
    try:
        result = await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
        return json.dumps({"status": "ready", **result})
    except asyncio.TimeoutError:
        return json.dumps({"status": "timeout"})
    finally:
        _futures.pop((project_id, language), None)
