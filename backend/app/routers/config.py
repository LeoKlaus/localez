from fastapi import APIRouter

from app.config import settings
from app.version import __version__, channel

router = APIRouter()


@router.get("")
async def get_config():
    return {
        "provider": settings.prefill_provider,  # "llm" | "deepl" | null
        "version": __version__,
        "channel": channel
    }
