import json
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_admin
from app.dependencies.project_token import require_import_access
from app.models.localization import Localization
from app.models.user import User
from app.models.project import Project
from app.models.project_language import ProjectLanguage
from app.models.string_key import StringKey
from app.services.localization_service import fill_missing_localizations
from app.services.xcstrings_exporter import build_xcstrings
from app.services.xcstrings_parser import parse_xcstrings

router = APIRouter()


@router.post("/{project_id}/import", status_code=status.HTTP_200_OK)
async def import_xcstrings(
    project_id: uuid.UUID,
    file: UploadFile = File(..., description="xcstrings file to import"),
    conflict: str = Query(default="skip", pattern="^(skip|overwrite)$"),
    _: None = Depends(require_import_access),
    db: AsyncSession = Depends(get_db),
):
    try:
        contents = await file.read()
        data = json.loads(contents)
    except json.JSONDecodeError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "INVALID_XCSTRINGS", "message": f"File is not valid JSON: {e}"})

    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})

    try:
        parsed = parse_xcstrings(data, project_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "INVALID_XCSTRINGS", "message": str(e)})

    if project.source_language != parsed.source_language:
        project.source_language = parsed.source_language

    # Upsert string keys
    key_id_by_str: dict[str, uuid.UUID] = {}
    for sk in parsed.string_keys:
        stmt = pg_insert(StringKey).values(
            id=sk.id,
            project_id=project_id,
            key=sk.key,
            comment=sk.comment,
            should_translate=sk.should_translate,
        )
        if conflict == "overwrite":
            stmt = stmt.on_conflict_do_update(
                index_elements=["project_id", "key"],
                set_={"comment": sk.comment, "should_translate": sk.should_translate},
            )
        else:
            stmt = stmt.on_conflict_do_nothing()

        await db.execute(stmt)

        # fetch actual id (may differ if row already existed)
        existing = await db.execute(select(StringKey).where(StringKey.project_id == project_id, StringKey.key == sk.key))
        row = existing.scalar_one()
        key_id_by_str[sk.key] = row.id

    # Upsert localizations
    for loc in parsed.localizations:
        # find the string key the localization belongs to
        sk_key = next((sk.key for sk in parsed.string_keys if sk.id == loc.string_key_id), None)
        if sk_key is None:
            continue
        actual_key_id = key_id_by_str.get(sk_key)
        if actual_key_id is None:
            continue

        stmt = pg_insert(Localization).values(
            id=loc.id,
            string_key_id=actual_key_id,
            language=loc.language,
            variation_type=loc.variation_type,
            variation_key=loc.variation_key,
            state=loc.state,
            value=loc.value,
        )
        if conflict == "overwrite":
            stmt = stmt.on_conflict_do_update(
                index_elements=["string_key_id", "language", "variation_type", "variation_key"],
                set_={"state": loc.state, "value": loc.value},
            )
        else:
            stmt = stmt.on_conflict_do_nothing()

        await db.execute(stmt)

    # Register all language codes found in the file
    for lang in {loc.language for loc in parsed.localizations}:
        await db.execute(
            pg_insert(ProjectLanguage)
            .values(project_id=project_id, language=lang)
            .on_conflict_do_nothing()
        )

    # Fill placeholder rows for any (string_key, project_language) without a flat localization
    await fill_missing_localizations(project_id, db)
    await db.commit()

    keys_count = len(parsed.string_keys)
    locs_count = len(parsed.localizations)
    return {"imported_keys": keys_count, "imported_localizations": locs_count}


@router.get("/{project_id}/export")
async def export_xcstrings(
    project_id: uuid.UUID,
    languages: str | None = Query(default=None, description="Comma-separated language codes"),
    state: str | None = Query(default=None),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})

    keys_result = await db.execute(select(StringKey).where(StringKey.project_id == project_id))
    string_keys = list(keys_result.scalars().all())

    key_ids = [sk.id for sk in string_keys]
    loc_query = select(Localization).where(Localization.string_key_id.in_(key_ids))

    if languages:
        lang_list = [l.strip() for l in languages.split(",") if l.strip()]
        loc_query = loc_query.where(Localization.language.in_(lang_list))
    if state:
        from app.models.localization import LocalizationState
        try:
            state_enum = LocalizationState(state)
            loc_query = loc_query.where(Localization.state == state_enum)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "INVALID_STATE", "message": f"Invalid state: {state}"})

    locs_result = await db.execute(loc_query)
    localizations = list(locs_result.scalars().all())

    contributor_names: list[str] = []
    if key_ids:
        contributors_result = await db.execute(
            select(User)
            .join(Localization, Localization.value_set_by == User.id)
            .where(
                Localization.string_key_id.in_(key_ids),
                User.show_as_contributor.is_(True),
            )
            .distinct()
        )
        contributor_names = [
            u.attribution_name or u.username
            for u in contributors_result.scalars().all()
        ]

    xcstrings_data = build_xcstrings(project, string_keys, localizations, contributor_names)
    filename = f"{project.name.replace(' ', '_')}.xcstrings"

    return JSONResponse(
        content=xcstrings_data,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
