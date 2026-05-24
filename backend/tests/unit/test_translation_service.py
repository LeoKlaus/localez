"""Unit tests for app.services.translation_service."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _deepl_lang
# ---------------------------------------------------------------------------

def test_deepl_lang_uppercases_simple_code():
    from app.services.translation_service import _deepl_lang
    assert _deepl_lang("en") == "EN"
    assert _deepl_lang("de") == "DE"


def test_deepl_lang_replaces_underscore_with_hyphen():
    from app.services.translation_service import _deepl_lang
    assert _deepl_lang("zh_hans") == "ZH-HANS"
    assert _deepl_lang("pt_br") == "PT-BR"


def test_deepl_lang_leaves_hyphens_intact():
    from app.services.translation_service import _deepl_lang
    assert _deepl_lang("zh-HANS") == "ZH-HANS"


# ---------------------------------------------------------------------------
# translate_with_deepl
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_with_deepl_no_api_key_raises():
    from app.services.translation_service import translate_with_deepl
    with patch("app.services.translation_service.settings") as mock_settings:
        mock_settings.deepl_api_key = None
        with pytest.raises(RuntimeError, match="DEEPL_NOT_CONFIGURED"):
            await translate_with_deepl("en", "de", ["Hello"])


@pytest.mark.asyncio
async def test_translate_with_deepl_happy_path():
    from app.services.translation_service import translate_with_deepl

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"translations": [{"text": "Hallo"}, {"text": "Welt"}]}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=fake_response)

    mock_key = MagicMock()
    mock_key.get_secret_value.return_value = "test-key"

    with patch("app.services.translation_service.settings") as mock_settings, \
         patch("app.services.translation_service.httpx.AsyncClient", return_value=mock_client):
        mock_settings.deepl_api_key = mock_key
        mock_settings.deepl_api_base = "https://api.deepl.com/v2"
        result = await translate_with_deepl("en", "de", ["Hello", "World"])

    assert result == ["Hallo", "Welt"]


@pytest.mark.asyncio
async def test_translate_with_deepl_non_200_raises():
    from app.services.translation_service import translate_with_deepl

    fake_response = MagicMock()
    fake_response.status_code = 403

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=fake_response)

    mock_key = MagicMock()
    mock_key.get_secret_value.return_value = "test-key"

    with patch("app.services.translation_service.settings") as mock_settings, \
         patch("app.services.translation_service.httpx.AsyncClient", return_value=mock_client):
        mock_settings.deepl_api_key = mock_key
        mock_settings.deepl_api_base = "https://api.deepl.com/v2"
        with pytest.raises(RuntimeError, match="DEEPL_ERROR"):
            await translate_with_deepl("en", "de", ["Hello"])


# ---------------------------------------------------------------------------
# translate_with_llm
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_with_llm_no_api_key_raises():
    from app.services.translation_service import translate_with_llm
    with patch("app.services.translation_service.settings") as mock_settings:
        mock_settings.llm_api_key = None
        with pytest.raises(RuntimeError, match="LLM_NOT_CONFIGURED"):
            await translate_with_llm("en", "de", ["Hello"])


@pytest.mark.asyncio
async def test_translate_with_llm_happy_path():
    from app.services.translation_service import translate_with_llm

    translated = ["Hallo", "Welt"]
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "choices": [{"message": {"content": json.dumps(translated)}}]
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=fake_response)

    mock_key = MagicMock()
    mock_key.get_secret_value.return_value = "test-key"

    with patch("app.services.translation_service.settings") as mock_settings, \
         patch("app.services.translation_service.httpx.AsyncClient", return_value=mock_client):
        mock_settings.llm_api_key = mock_key
        mock_settings.llm_api_base = "https://api.openai.com/v1"
        mock_settings.llm_model = "gpt-4o-mini"
        result = await translate_with_llm("en", "de", ["Hello", "World"])

    assert result == ["Hallo", "Welt"]


@pytest.mark.asyncio
async def test_translate_with_llm_with_comments_builds_notes():
    from app.services.translation_service import translate_with_llm

    translated = ["Hallo"]
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "choices": [{"message": {"content": json.dumps(translated)}}]
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=fake_response)

    mock_key = MagicMock()
    mock_key.get_secret_value.return_value = "test-key"

    with patch("app.services.translation_service.settings") as mock_settings, \
         patch("app.services.translation_service.httpx.AsyncClient", return_value=mock_client):
        mock_settings.llm_api_key = mock_key
        mock_settings.llm_api_base = "https://api.openai.com/v1"
        mock_settings.llm_model = "gpt-4o-mini"
        result = await translate_with_llm("en", "de", ["Hello"], comments=["A greeting"])

    assert result == ["Hallo"]
    # The POST call should have been made with a system prompt containing the note
    call_kwargs = mock_client.post.call_args[1]
    system_content = call_kwargs["json"]["messages"][0]["content"]
    assert "greeting" in system_content.lower() or "[0]" in system_content


@pytest.mark.asyncio
async def test_translate_with_llm_strips_markdown_code_fences():
    from app.services.translation_service import translate_with_llm

    translated = ["Hallo"]
    content_with_fence = f"```json\n{json.dumps(translated)}\n```"
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "choices": [{"message": {"content": content_with_fence}}]
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=fake_response)

    mock_key = MagicMock()
    mock_key.get_secret_value.return_value = "test-key"

    with patch("app.services.translation_service.settings") as mock_settings, \
         patch("app.services.translation_service.httpx.AsyncClient", return_value=mock_client):
        mock_settings.llm_api_key = mock_key
        mock_settings.llm_api_base = "https://api.openai.com/v1"
        mock_settings.llm_model = "gpt-4o-mini"
        result = await translate_with_llm("en", "de", ["Hello"])

    assert result == ["Hallo"]


@pytest.mark.asyncio
async def test_translate_with_llm_non_200_raises():
    from app.services.translation_service import translate_with_llm

    fake_response = MagicMock()
    fake_response.status_code = 500

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=fake_response)

    mock_key = MagicMock()
    mock_key.get_secret_value.return_value = "test-key"

    with patch("app.services.translation_service.settings") as mock_settings, \
         patch("app.services.translation_service.httpx.AsyncClient", return_value=mock_client):
        mock_settings.llm_api_key = mock_key
        mock_settings.llm_api_base = "https://api.openai.com/v1"
        mock_settings.llm_model = "gpt-4o-mini"
        with pytest.raises(RuntimeError, match="LLM_ERROR"):
            await translate_with_llm("en", "de", ["Hello"])


@pytest.mark.asyncio
async def test_translate_with_llm_malformed_json_raises():
    from app.services.translation_service import translate_with_llm

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "choices": [{"message": {"content": "not valid json {"}}]
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=fake_response)

    mock_key = MagicMock()
    mock_key.get_secret_value.return_value = "test-key"

    with patch("app.services.translation_service.settings") as mock_settings, \
         patch("app.services.translation_service.httpx.AsyncClient", return_value=mock_client):
        mock_settings.llm_api_key = mock_key
        mock_settings.llm_api_base = "https://api.openai.com/v1"
        mock_settings.llm_model = "gpt-4o-mini"
        with pytest.raises(RuntimeError, match="malformed JSON"):
            await translate_with_llm("en", "de", ["Hello"])


@pytest.mark.asyncio
async def test_translate_with_llm_wrong_list_length_raises():
    from app.services.translation_service import translate_with_llm

    # Returns 3 items but only 1 was requested
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "choices": [{"message": {"content": '["a", "b", "c"]'}}]
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=fake_response)

    mock_key = MagicMock()
    mock_key.get_secret_value.return_value = "test-key"

    with patch("app.services.translation_service.settings") as mock_settings, \
         patch("app.services.translation_service.httpx.AsyncClient", return_value=mock_client):
        mock_settings.llm_api_key = mock_key
        mock_settings.llm_api_base = "https://api.openai.com/v1"
        mock_settings.llm_model = "gpt-4o-mini"
        with pytest.raises(RuntimeError, match="expected list of 1 items"):
            await translate_with_llm("en", "de", ["Hello"])


# ---------------------------------------------------------------------------
# prefill (routing)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prefill_routes_to_deepl():
    from app.services.translation_service import prefill

    with patch("app.services.translation_service.translate_with_deepl", new=AsyncMock(return_value=["Hallo"])) as mock_deepl:
        result = await prefill("en", "de", ["Hello"], "deepl")

    mock_deepl.assert_called_once_with("en", "de", ["Hello"])
    assert result == ["Hallo"]


@pytest.mark.asyncio
async def test_prefill_routes_to_llm():
    from app.services.translation_service import prefill

    with patch("app.services.translation_service.translate_with_llm", new=AsyncMock(return_value=["Hallo"])) as mock_llm:
        result = await prefill("en", "de", ["Hello"], "llm", comments=["note"])

    mock_llm.assert_called_once_with("en", "de", ["Hello"], ["note"])
    assert result == ["Hallo"]


@pytest.mark.asyncio
async def test_prefill_unknown_provider_raises():
    from app.services.translation_service import prefill

    with pytest.raises(ValueError, match="Unknown provider"):
        await prefill("en", "de", ["Hello"], "unknown_provider")
