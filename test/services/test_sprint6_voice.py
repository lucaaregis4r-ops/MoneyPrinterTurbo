"""Sprint 6 Automated Tests: Voice Studio & Pronunciation Dictionary.

Validates:
1. VoiceProvider abstraction & EdgeVoiceProvider listing and synthesis.
2. VoiceStudioService phrase-by-phrase instant audition.
3. Persistent pronunciation dictionary CRUD and phonetic translation.
"""

import json
from pathlib import Path
import pytest

from app.services.voice_studio import (
    EdgeVoiceProvider,
    FallbackVoiceProvider,
    VoiceStudioService,
)


def test_edge_voice_provider_listing():
    provider = EdgeVoiceProvider()
    voices = provider.list_voices(locale_prefix="pt-BR")
    assert len(voices) >= 2
    ids = [v["id"] for v in voices]
    assert "pt-BR-AntonioNeural-Male" in ids
    assert "pt-BR-FranciscaNeural-Female" in ids


def test_voice_studio_phrase_preview(tmp_path: Path):
    storage_dir = tmp_path / "voices"
    service = VoiceStudioService(storage_dir=storage_dir)

    test_text = "Você sabia que F = m.a é a segunda lei de Newton?"
    result = service.preview_phrase(
        text=test_text,
        voice_name="pt-BR-AntonioNeural-Male",
        rate=1.0,
        apply_pronunciation=True,
    )

    assert result["display_text"] == test_text
    assert "Éfe é igual a ême vezes á" in result["spoken_text"]
    assert Path(result["audio_path"]).exists()
    assert result["duration"] > 0
    assert result["provider"] == "edge"


def test_pronunciation_dictionary_persistence(tmp_path: Path):
    storage_dir = tmp_path / "voices"
    service = VoiceStudioService(storage_dir=storage_dir)

    # 1. Add new custom rule
    service.add_pronunciation_rule("CBI", "cê-bê-i")
    rules = service.get_pronunciation_rules()
    assert rules.get("CBI") == "cê-bê-i"

    dict_file = storage_dir / "dictionary.json"
    assert dict_file.exists()

    with dict_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("CBI") == "cê-bê-i"

    # 2. Verify pronunciation in speech preview
    preview = service.preview_phrase("O torneio CBI de basquete começou.")
    assert "cê-bê-i" in preview["spoken_text"]

    # 3. Remove rule
    removed = service.remove_pronunciation_rule("CBI")
    assert removed is True
    reloaded_rules = service.get_pronunciation_rules()
    assert "CBI" not in reloaded_rules
