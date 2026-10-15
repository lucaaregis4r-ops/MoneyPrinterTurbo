"""Pronunciation Engine for Fábrica de Shorts.

Translates written / display text to phonetically readable text for TTS engines,
without ever altering the locked display / subtitle text approved by the user.

Example:
    'F = m.a' -> display: 'F = m × a', spoken: 'Éfe é igual a ême vezes á'
    'NBA'     -> display: 'NBA', spoken: 'ene-bi-ei'
"""

from __future__ import annotations
import json
from pathlib import Path
import re
from typing import Dict, Optional


class PronunciationEngine:
    def __init__(self, custom_dict: Optional[Dict[str, str]] = None):
        self._dictionary: Dict[str, str] = {
            # Default PT-BR scientific and common abbreviation phonetic mappings
            "F = m.a": "Éfe é igual a ême vezes á",
            "F=m.a": "Éfe é igual a ême vezes á",
            "F = m*a": "Éfe é igual a ême vezes á",
            "F = ma": "Éfe é igual a ême vezes á",
            "E = mc²": "É é igual a ême cê ao quadrado",
            "E=mc²": "É é igual a ême cê ao quadrado",
            "E = mc2": "É é igual a ême cê ao quadrado",
            "km/h": "quilômetros por hora",
            "m/s": "metros por segundo",
            "m/s²": "metros por segundo ao quadrado",
            "NBA": "ene-bi-ei",
            "FIFA": "fífa",
            "NASA": "nása",
            "IA": "i-á",
            "AI": "ei-ai",
            "vs.": "versus",
            "vs": "versus",
            "ex.": "por exemplo",
            "etc.": "etecétera",
            "etc": "etecétera",
        }
        if custom_dict:
            self._dictionary.update(custom_dict)

    def add_rule(self, term: str, spoken: str) -> None:
        self._dictionary[term] = spoken

    def load_dictionary_file(self, path: str | Path) -> None:
        file_path = Path(path)
        if file_path.exists():
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self._dictionary.update(data)

    def save_dictionary_file(self, path: str | Path) -> None:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(self._dictionary, f, ensure_ascii=False, indent=2)

    def to_spoken(self, text: str) -> str:
        """Translates text to TTS-friendly phonetic representation."""
        if not text:
            return ""

        spoken = text
        # Sort terms by length descending to match compound expressions first
        sorted_terms = sorted(self._dictionary.keys(), key=len, reverse=True)
        for term in sorted_terms:
            replacement = self._dictionary[term]
            # If term is an alphanumeric word, match on word boundaries; otherwise literal escape
            if re.match(r"^\w+$", term):
                pattern = rf"\b{re.escape(term)}\b"
            else:
                pattern = re.escape(term)
            spoken = re.sub(pattern, replacement, spoken, flags=re.IGNORECASE)

        return spoken

    def prepare_pair(self, text: str) -> dict[str, str]:
        """Returns both visual display text and spoken phonetic text."""
        return {
            "display": text,
            "spoken": self.to_spoken(text),
        }
