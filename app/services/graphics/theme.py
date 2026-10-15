"""Visual theme definitions for programmatic graphic cards.

Provides curated color palettes and styling for 9:16 vertical cards.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class CardTheme:
    name: str
    bg_top: Tuple[int, int, int]
    bg_bottom: Tuple[int, int, int]
    card_bg: Tuple[int, int, int, int]
    card_border: Tuple[int, int, int, int]
    badge_bg: Tuple[int, int, int, int]
    badge_text: Tuple[int, int, int]
    text_primary: Tuple[int, int, int]
    text_accent: Tuple[int, int, int]
    text_secondary: Tuple[int, int, int]
    divider_color: Tuple[int, int, int, int]


THEMES: Dict[str, CardTheme] = {
    "chalkboard": CardTheme(
        name="chalkboard",
        bg_top=(14, 26, 22),
        bg_bottom=(20, 36, 30),
        card_bg=(18, 32, 27, 230),
        card_border=(52, 211, 153, 160),
        badge_bg=(52, 211, 153, 50),
        badge_text=(110, 231, 183),
        text_primary=(240, 253, 244),
        text_accent=(250, 204, 21),  # chalk gold
        text_secondary=(167, 243, 208),
        divider_color=(52, 211, 153, 80),
    ),
    "dark_modern": CardTheme(
        name="dark_modern",
        bg_top=(11, 15, 25),
        bg_bottom=(24, 30, 48),
        card_bg=(17, 24, 39, 235),
        card_border=(56, 189, 248, 160),
        badge_bg=(56, 189, 248, 50),
        badge_text=(125, 211, 252),
        text_primary=(248, 250, 252),
        text_accent=(56, 189, 248),  # electric cyan
        text_secondary=(148, 163, 184),
        divider_color=(56, 189, 248, 80),
    ),
    "editorial": CardTheme(
        name="editorial",
        bg_top=(18, 18, 20),
        bg_bottom=(32, 30, 32),
        card_bg=(26, 25, 28, 240),
        card_border=(245, 158, 11, 160),
        badge_bg=(245, 158, 11, 45),
        badge_text=(251, 191, 36),
        text_primary=(254, 243, 199),
        text_accent=(251, 191, 36),  # warm gold
        text_secondary=(214, 211, 209),
        divider_color=(245, 158, 11, 70),
    ),
    "neon_sports": CardTheme(
        name="neon_sports",
        bg_top=(10, 10, 18),
        bg_bottom=(26, 20, 45),
        card_bg=(19, 17, 33, 235),
        card_border=(163, 230, 53, 180),
        badge_bg=(163, 230, 53, 50),
        badge_text=(190, 242, 100),
        text_primary=(255, 255, 255),
        text_accent=(163, 230, 53),  # volt lime
        text_secondary=(203, 213, 225),
        divider_color=(163, 230, 53, 90),
    ),
    "sunset_burst": CardTheme(
        name="sunset_burst",
        bg_top=(26, 16, 37),
        bg_bottom=(60, 24, 48),
        card_bg=(34, 18, 44, 235),
        card_border=(244, 63, 94, 160),
        badge_bg=(244, 63, 94, 50),
        badge_text=(251, 113, 133),
        text_primary=(255, 241, 242),
        text_accent=(251, 146, 60),  # vibrant orange
        text_secondary=(226, 232, 240),
        divider_color=(244, 63, 94, 80),
    ),
}


def get_theme(name: str | None = None) -> CardTheme:
    """Gets a theme by name with default fallback to 'dark_modern'."""
    if not name:
        return THEMES["dark_modern"]
    clean_name = name.lower().strip()
    return THEMES.get(clean_name, THEMES["dark_modern"])
