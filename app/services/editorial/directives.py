"""Directives parser for human scripts.

Extracts optional inline direction tags without mutating the intended narration.
Example tags:
- [visual: formula F = m * a]
- [graphic], [formula], [quote], [number], [chart], [map], [stock], [photo], [archive]
- [keep-media]
- [pronounce: spoken text]
- [pause: 300ms]
- [emphasis: word]
"""

from __future__ import annotations
from dataclasses import dataclass, field
import re
from typing import Any

# Regex to match tags like [visual: ...], [graphic], [pause: 300ms], etc.
_DIRECTIVE_PATTERN = re.compile(r"\[([a-zA-Z_-]+)(?::\s*([^\]]+))?\]")


@dataclass
class ScriptDirective:
    tag: str
    value: str | None = None
    position: int = 0
    raw: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "value": self.value,
            "position": self.position,
            "raw": self.raw,
        }


@dataclass
class ParsedScriptSection:
    raw_text: str
    clean_narration: str
    directives: list[ScriptDirective] = field(default_factory=list)


def parse_directives(text: str) -> tuple[str, list[ScriptDirective]]:
    """Separates inline directives from the narration text.
    Returns:
        tuple[clean_narration, list[ScriptDirective]]
    """
    directives: list[ScriptDirective] = []

    def _replace(match: re.Match) -> str:
        tag = match.group(1).lower().strip()
        value = match.group(2).strip() if match.group(2) else None
        raw = match.group(0)
        pos = match.start()
        directives.append(
            ScriptDirective(tag=tag, value=value, position=pos, raw=raw)
        )
        return ""

    # Replace bracketed directives and normalize multiple spaces
    clean = _DIRECTIVE_PATTERN.sub(_replace, text)
    # Collapse double spaces without collapsing newlines
    clean = re.sub(r"[ \t]+", " ", clean)
    clean = re.sub(r"\n\s*\n\s*\n+", "\n\n", clean).strip()

    return clean, directives


def strip_directives(text: str) -> str:
    """Convenience helper to get only the spoken clean narration text."""
    clean, _ = parse_directives(text)
    return clean
