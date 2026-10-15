"""Visual intent analysis and heuristics for Scene Director.
"""

from __future__ import annotations
import re
from typing import Optional

from .schemas import MotionType, VisualType

# Regex patterns for detecting specific content categories
_FORMULA_PATTERN = re.compile(r"(\b[FEmaMCvgt]\s*=\s*[\w\d\.\+\-\*\/²\^]+|[A-Z]\s*=\s*[A-Z\d\.\+\-\*\/]+)")
_NUMBER_PATTERN = re.compile(r"(\b\d{1,3}(?:\.\d{3})*(?:,\d+)?%?|\b\d+%\b|\b\d+\s*(?:milhões|bilhões|mil|anos|km|kg)\b)", re.IGNORECASE)
_QUOTE_PATTERN = re.compile(r'("[^"]{10,}"|“[^”]{10,}”|como disse|afirmou\s+[\w\s]+:)', re.IGNORECASE)
_MAP_PATTERN = re.compile(r"\b(país|cidade|mapa|fronteira|continente|oceano|áfrica|europa|ásia|brasil|estados unidos|china|terra|planeta)\b", re.IGNORECASE)


def infer_visual_type(narration: str, requested_directive: Optional[str] = None) -> VisualType:
    """Infers the most appropriate visual type based on directives or text semantics."""
    if requested_directive:
        req = requested_directive.lower().strip()
        for vt in VisualType:
            if vt.value == req:
                return vt

    text = narration.strip()
    if _FORMULA_PATTERN.search(text):
        return VisualType.FORMULA
    if _QUOTE_PATTERN.search(text):
        return VisualType.QUOTE
    if _MAP_PATTERN.search(text):
        return VisualType.MAP
    if _NUMBER_PATTERN.search(text) and len(text.split()) < 10:
        return VisualType.NUMBER

    return VisualType.STOCK_VIDEO


def estimate_duration_seconds(narration: str, words_per_minute: float = 140.0) -> float:
    """Estimates spoken duration in seconds for Portuguese speech."""
    words = len(re.findall(r"\w+", narration))
    if words == 0:
        return 2.0
    duration = (words / words_per_minute) * 60.0
    # Minimum duration 1.5s, rounded to 1 decimal place
    return max(1.5, round(duration, 1))
