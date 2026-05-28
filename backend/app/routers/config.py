from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("")
async def get_config():
    return {"provider": settings.prefill_provider}  # "llm" | "deepl" | null
