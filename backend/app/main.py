from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.models import project_language  # noqa: F401 — ensure models are registered with Base
from app.routers import auth, projects, proposals, strings, users, xcstrings

app = FastAPI(title="Localez", version="0.1.0", openapi_prefix="/api")

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
