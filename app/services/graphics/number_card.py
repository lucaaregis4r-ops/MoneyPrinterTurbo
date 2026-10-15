"""Number Card Renderer for statistics, metrics, records and numbers.
"""

from __future__ import annotations
import re
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .base_card import BaseCardRenderer
from .theme import CardTheme, get_theme

_NUMBER_REGEX = re.compile(
    r"(\b\d{1,3}(?:\.\d{3})*(?:,\d+)?%?|\b\d+(?:[\.,]\d+)?\s*(?:km\/h|km\/s|km|m\/s|mph|ms|anos|segundos|minutos|kg|t|milhões|bilhões|mil|vezes|x|%|s)\b|\b\d+%)",
    re.IGNORECASE,
)


def extract_hero_number(text: str) -> Tuple[str, str]:
    """Extracts hero number/metric and remaining context."""
    # Check directive [number: 9.58s]
    m_dir = re.search(r"\[number:\s*([^\]]+)\]", text, re.IGNORECASE)
    if m_dir:
        return m_dir.group(1).strip(), text

    matches = _NUMBER_REGEX.findall(text)
    if matches:
        hero = matches[0].strip()
        return hero, text

    # Fallback to first digits
    digits = re.search(r"\b\d+\b", text)
    if digits:
        return digits.group(0), text

    return "100%", text


class NumberCardRenderer(BaseCardRenderer):
    """Renders prominent metric and statistics cards."""

    def __init__(self, theme: Optional[CardTheme] = None):
        super().__init__(theme=theme or get_theme("neon_sports"))

    def render_card_image(
        self,
        text: str,
        hero_number: Optional[str] = None,
        context_label: Optional[str] = None,
        explanation: Optional[str] = None,
    ) -> Image.Image:
        """Renders the number card onto a 1080x1920 PIL image."""
        img = self.create_background()
        draw = ImageDraw.Draw(img)

        # 1. Badge
        curr_y = self.draw_badge(draw, "⚡ ESTATÍSTICA EM FOCO", center_y=400)

        # 2. Extract number if not provided
        if not hero_number:
            hero_number, _ = extract_hero_number(text)

        # 3. Context headline above number
        if context_label:
            lbl_font = self.load_font(32, bold=True)
            curr_y = self.draw_multiline_centered(
                draw,
                context_label.upper(),
                start_y=curr_y,
                font=lbl_font,
                fill=self.theme.text_secondary,
                max_width=820,
            ) + 20

        # 4. Hero Number (Giant typography)
        num_len = len(hero_number)
        font_size = 150 if num_len <= 6 else (110 if num_len <= 10 else 80)
        num_font = self.load_font(font_size, bold=True)

        bbox = draw.textbbox((0, 0), hero_number, font=num_font)
        nw = bbox[2] - bbox[0]
        nh = bbox[3] - bbox[1]

        # Draw number highlight pill
        box_pad_x = 50
        box_pad_y = 35
        box_x1 = max(100, (self.width - nw) // 2 - box_pad_x)
        box_y1 = curr_y + 20
        box_x2 = min(self.width - 100, (self.width + nw) // 2 + box_pad_x)
        box_y2 = box_y1 + nh + box_pad_y * 2

        draw.rounded_rectangle(
            [(box_x1, box_y1), (box_x2, box_y2)],
            radius=24,
            fill=(0, 0, 0, 75),
            outline=self.theme.card_border,
            width=3,
        )

        draw.text(
            ((self.width - nw) // 2, box_y1 + box_pad_y - bbox[1] // 2),
            hero_number,
            font=num_font,
            fill=self.theme.text_accent,
        )
        curr_y = box_y2 + 45

        # 5. Divider
        curr_y = self.draw_divider(draw, y=curr_y, width=620)

        # 6. Explanation / Narration text
        narration_to_draw = explanation or text
        if narration_to_draw:
            body_font = self.load_font(30, bold=False)
            curr_y = self.draw_multiline_centered(
                draw,
                narration_to_draw,
                start_y=curr_y + 15,
                font=body_font,
                fill=self.theme.text_primary,
                max_width=820,
                line_spacing=14,
            )

        return img
