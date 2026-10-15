"""Voice Studio Service: Coordinates TTS engines, phrase previews, and persistent pronunciation dictionaries.
"""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.editorial.pronunciation import PronunciationEngine
from .voice_provider import EdgeVoiceProvider, VoiceProvider


class VoiceStudioService:
    def __init__(
        self,
        storage_dir: str | Path = "storage/voices",
        provider: Optional[VoiceProvider] = None,
    ):
        self.storage_dir = Path(storage_dir).resolve()
        self.previews_dir = self.storage_dir / "previews"
        self.dictionary_file = self.storage_dir / "dictionary.json"

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.previews_dir.mkdir(parents=True, exist_ok=True)

        self.provider = provider or EdgeVoiceProvider()
        self.pronunciation_engine = PronunciationEngine()

        # Load persistent dictionary if exists
        self._load_dictionary()

    def _load_dictionary(self) -> None:
        if self.dictionary_file.exists():
            try:
                with self.dictionary_file.open("r", encoding="utf-8") as f:
                    rules = json.load(f)
                    if isinstance(rules, dict):
                        for k, v in rules.items():
                            self.pronunciation_engine.add_rule(k, v)
            except Exception:
                pass
        else:
            # Seed default dictionary file
            self._save_dictionary()

    def _save_dictionary(self) -> None:
        rules = self.pronunciation_engine._dictionary
        with self.dictionary_file.open("w", encoding="utf-8") as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)

    def list_voices(self) -> List[Dict[str, Any]]:
        return self.provider.list_voices()

    def get_pronunciation_rules(self) -> Dict[str, str]:
        return dict(self.pronunciation_engine._dictionary)

    def add_pronunciation_rule(self, term: str, spoken: str) -> None:
        clean_term = term.strip()
        clean_spoken = spoken.strip()
        if not clean_term or not clean_spoken:
            raise ValueError("Termo e pronúncia não podem estar vazios.")
        self.pronunciation_engine.add_rule(clean_term, clean_spoken)
        self._save_dictionary()

    def remove_pronunciation_rule(self, term: str) -> bool:
        if term in self.pronunciation_engine._dictionary:
            del self.pronunciation_engine._dictionary[term]
            self._save_dictionary()
            return True
        return False

    def preview_phrase(
        self,
        text: str,
        voice_name: str = "pt-BR-AntonioNeural-Male",
        rate: float = 1.0,
        apply_pronunciation: bool = True,
    ) -> Dict[str, Any]:
        """Synthesizes a single test phrase into audio for instant playback."""
        clean_display = text.strip()
        if not clean_display:
            raise ValueError("Texto para teste de voz não pode estar vazio.")

        spoken = (
            self.pronunciation_engine.to_spoken(clean_display)
            if apply_pronunciation
            else clean_display
        )

        slug = hashlib.md5(f"{spoken}_{voice_name}_{rate}".encode("utf-8")).hexdigest()[:12]
        target_path = self.previews_dir / f"preview_{slug}.mp3"

        res = self.provider.synthesize(
            text=spoken,
            voice_name=voice_name,
            rate=rate,
            output_path=target_path,
        )

        return {
            "display_text": clean_display,
            "spoken_text": spoken,
            "audio_path": res["audio_path"],
            "duration": res["duration"],
            "subtitles": res.get("subtitles"),
            "voice_name": voice_name,
            "provider": res["provider"],
        }
