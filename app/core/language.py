import re
from typing import Annotated

from pydantic import AfterValidator

# BCP 47 language tag: primary subtag (2-3 alpha) with optional further subtags
_LANGUAGE_RE = re.compile(r"^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8})*$")


def _validate_language_code(v: str) -> str:
    if not _LANGUAGE_RE.match(v):
        raise ValueError(f"'{v}' is not a valid BCP 47 language code (e.g. 'en', 'en-US', 'zh-Hans')")
    return v


LanguageCode = Annotated[str, AfterValidator(_validate_language_code)]
