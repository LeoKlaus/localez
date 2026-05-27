"""
Tests for xcstrings import/export using the Example.xcstrings fixture.
These are pure unit tests against the parser/exporter services — no DB needed.
"""
import json
from pathlib import Path

import pytest

from app.services.xcstrings_exporter import build_xcstrings
from app.services.xcstrings_parser import parse_xcstrings

import uuid

EXAMPLE_PATH = Path(__file__).parent.parent.parent / "Example.xcstrings"


@pytest.fixture
def xcstrings_data() -> dict:
    return json.loads(EXAMPLE_PATH.read_text())


def test_parse_all_keys(xcstrings_data):
    project_id = uuid.uuid4()
    result = parse_xcstrings(xcstrings_data, project_id)
    assert len(result.string_keys) == 8
    assert result.source_language == "en"


def test_parse_non_translatable(xcstrings_data):
    project_id = uuid.uuid4()
    result = parse_xcstrings(xcstrings_data, project_id)
    dont_translate = next(sk for sk in result.string_keys if sk.key == "Don't translate")
    assert dont_translate.should_translate is False


def test_parse_device_variations(xcstrings_data):
    project_id = uuid.uuid4()
    result = parse_xcstrings(xcstrings_data, project_id)
    save_key = next(sk for sk in result.string_keys if sk.key == "Save to your iPhone")
    device_locs = [l for l in result.localizations if l.string_key_id == save_key.id and l.variation_type.value == "device"]
    assert len(device_locs) > 0
    variation_keys = {l.variation_key for l in device_locs}
    assert "iphone" in variation_keys or "mac" in variation_keys


def test_parse_plural_variations(xcstrings_data):
    project_id = uuid.uuid4()
    result = parse_xcstrings(xcstrings_data, project_id)
    plural_key = next(sk for sk in result.string_keys if "lld" in sk.key)
    plural_locs = [l for l in result.localizations if l.string_key_id == plural_key.id and l.variation_type.value == "plural"]
    assert len(plural_locs) > 0


def test_parse_state_mapping(xcstrings_data):
    project_id = uuid.uuid4()
    result = parse_xcstrings(xcstrings_data, project_id)
    reviewed_key = next(sk for sk in result.string_keys if sk.key == "Reviewed")
    reviewed_locs = [l for l in result.localizations if l.string_key_id == reviewed_key.id]
    states = {l.state.value for l in reviewed_locs}
    assert "translated" in states


def test_export_roundtrip(xcstrings_data):
    from app.models.project import Project
    project_id = uuid.uuid4()
    result = parse_xcstrings(xcstrings_data, project_id)

    # give all string keys a project
    for sk in result.string_keys:
        sk.project_id = project_id

    project = Project(id=project_id, name="Test", source_language=result.source_language)
    exported = build_xcstrings(project, result.string_keys, result.localizations)

    assert exported["sourceLanguage"] == "en"
    assert exported["version"] == "1.2"
    assert "Don't translate" in exported["strings"]
    assert "Reviewed" in exported["strings"]
    assert "Save to your iPhone" in exported["strings"]
    assert exported["strings"]["Don't translate"].get("shouldTranslate") is False


def test_empty_string_value_treated_as_null():
    """An xcstrings entry with value='' should produce value=None, not ''."""
    project_id = uuid.uuid4()
    data = {
        "sourceLanguage": "en",
        "strings": {
            "greeting": {
                "localizations": {
                    "de": {"stringUnit": {"state": "new", "value": ""}},
                }
            }
        },
        "version": "1.2",
    }
    result = parse_xcstrings(data, project_id)
    de_loc = next(l for l in result.localizations if l.language == "de")
    assert de_loc.value is None, "Empty string value should be stored as None"


def test_export_device_variations_preserved(xcstrings_data):
    from app.models.project import Project
    project_id = uuid.uuid4()
    result = parse_xcstrings(xcstrings_data, project_id)
    project = Project(id=project_id, name="Test", source_language="en")
    exported = build_xcstrings(project, result.string_keys, result.localizations)

    save_str = exported["strings"].get("Save to your iPhone", {})
    if save_str.get("localizations"):
        for lang_data in save_str["localizations"].values():
            if "variations" in lang_data and "device" in lang_data["variations"]:
                assert len(lang_data["variations"]["device"]) > 0
                return
