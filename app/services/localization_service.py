import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def fill_missing_localizations(project_id: uuid.UUID, db: AsyncSession) -> None:
    """Insert state=new placeholder rows for every (string_key, project_language) pair
    that doesn't already have a flat (variation_type=none) localization."""
    await db.execute(
        text("""
            INSERT INTO localizations
                (id, string_key_id, language, variation_type, variation_key, state, value)
            SELECT
                gen_random_uuid(),
                sk.id,
                pl.language,
                'none',
                '',
                'new',
                NULL
            FROM string_keys sk
            JOIN project_languages pl ON pl.project_id = sk.project_id
            WHERE sk.project_id = :project_id
            ON CONFLICT (string_key_id, language, variation_type, variation_key) DO NOTHING
        """),
        {"project_id": project_id},
    )
