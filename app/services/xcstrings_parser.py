"""
Parse .xcstrings JSON into lists of StringKey and Localization instances ready for upsert.
This is a pure function — no DB calls.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.models.localization import Localization, LocalizationState, VariationType
from app.models.string_key import StringKey


@dataclass
class ParseResult:
    string_keys: list[StringKey] = field(default_factory=list)
    localizations: list[Localization] = field(default_factory=list)
    source_language: str = "en"


_STATE_MAP: dict[str, LocalizationState] = {
    "new": LocalizationState.new,
    "needs_review": LocalizationState.needs_review,
    "translated": LocalizationState.translated,
}


def parse_xcstrings(data: dict, project_id: uuid.UUID) -> ParseResult:
    result = ParseResult(source_language=data.get("sourceLanguage", "en"))

    for key_str, key_data in data.get("strings", {}).items():
        sk_id = uuid.uuid4()
        sk = StringKey(
            id=sk_id,
            project_id=project_id,
            key=key_str,
            comment=key_data.get("comment"),
            should_translate=key_data.get("shouldTranslate", True),
        )
        result.string_keys.append(sk)

        for lang_code, loc_data in key_data.get("localizations", {}).items():
            if "stringUnit" in loc_data:
                result.localizations.append(
                    _make_localization(sk, lang_code, VariationType.none, None, loc_data["stringUnit"])
                )
            elif "variations" in loc_data:
                for variation_kind, variations in loc_data["variations"].items():
                    vtype = VariationType.device if variation_kind == "device" else VariationType.plural
                    for vkey, vdata in variations.items():
                        if "stringUnit" in vdata:
                            result.localizations.append(
                                _make_localization(sk, lang_code, vtype, vkey, vdata["stringUnit"])
                            )

    return result


def _make_localization(
    sk: StringKey,
    language: str,
    variation_type: VariationType,
    variation_key: str | None,
    string_unit: dict,
) -> Localization:
    raw_state = string_unit.get("state", "new")
    state = _STATE_MAP.get(raw_state, LocalizationState.new)
    return Localization(
        id=uuid.uuid4(),
        string_key_id=sk.id,
        language=language,
        variation_type=variation_type,
        variation_key=variation_key,
        state=state,
        value=string_unit.get("value"),
    )
