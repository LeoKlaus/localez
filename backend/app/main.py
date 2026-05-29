from app.logging_config import configure_logging
configure_logging()

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.core.limiter import limiter
from app.version import __version__
from app.models import project_language, project_member, project_token  # noqa: F401 — ensure models are registered with Base
from app.routers import auth, config, projects, proposals, strings, users, xcstrings

app = FastAPI(title="Localez", version=__version__, root_path="/api")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

_allowed_hosts = list({*settings.allowed_hosts.split(), "localhost"})
if _allowed_hosts != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts)

app.include_router(config.router, prefix="/config", tags=["config"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(strings.router, prefix="/projects", tags=["strings"])
app.include_router(xcstrings.router, prefix="/projects", tags=["xcstrings"])
app.include_router(proposals.router, prefix="/projects", tags=["proposals"])


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )
