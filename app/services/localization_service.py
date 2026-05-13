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
                combos.string_key_id,
                pl.language,
                combos.variation_type,
                combos.variation_key,
                'new',
                NULL
            FROM (
                -- Replicate every (variation_type, variation_key) combination that already
                -- exists for this project's strings in any language
                SELECT DISTINCT l.string_key_id, l.variation_type, l.variation_key
                FROM localizations l
                JOIN string_keys sk ON sk.id = l.string_key_id
                WHERE sk.project_id = :project_id

                UNION

                -- For string keys that have no localizations at all, seed a flat placeholder
                SELECT sk.id, 'none', ''
                FROM string_keys sk
                WHERE sk.project_id = :project_id
                AND NOT EXISTS (
                    SELECT 1 FROM localizations l WHERE l.string_key_id = sk.id
                )
            ) combos
            JOIN project_languages pl ON pl.project_id = :project_id
            WHERE NOT EXISTS (
                SELECT 1 FROM localizations l
                WHERE l.string_key_id = combos.string_key_id
                AND l.language = pl.language
                AND l.variation_type = combos.variation_type
                AND l.variation_key = combos.variation_key
            )
        """),
        {"project_id": project_id},
    )
