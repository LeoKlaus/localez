import os

from slowapi import Limiter


def _client_ip(request) -> str:
    return request.headers.get("X-Real-IP") or request.client.host


limiter = Limiter(key_func=_client_ip, enabled=not os.getenv("TESTING"))
