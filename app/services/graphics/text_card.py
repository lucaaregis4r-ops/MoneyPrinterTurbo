"""Text and Title Card Renderer for chapters, concepts and timeline steps.
"""

from __future__ import annotations
import re
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

from .base_card import BaseCardRenderer
from .theme import CardTheme, get_theme


class TextCardRenderer(BaseCardRenderer):
    """Renders structured textual cards for concepts, step breakdowns and titles."""

    def __init__(self, theme: Optional[CardTheme] = None):
        super().__init__(theme=theme or get_theme("dark_modern"))

    def render_card_image(
        self,
        title: str,
        subtitle: Optional[str] = None,
        bullet_points: Optional[List[str]] = None,
        badge_label: str = "📌 CONCEITO PRINCIPAL",
    ) -> Image.Image:
        """Renders the concept / title card onto a 1080x1920 PIL image."""
        img = self.create_background()
        draw = ImageDraw.Draw(img)

        # 1. Badge
        curr_y = self.draw_badge(draw, badge_label, center_y=400)

        # 2. Main Title (Bold & prominent)
        title_len = len(title)
        title_size = 54 if title_len <= 35 else (44 if title_len <= 70 else 36)
        title_font = self.load_font(title_size, bold=True)

        curr_y = self.draw_multiline_centered(
            draw,
            title.upper(),
            start_y=curr_y + 10,
            font=title_font,
            fill=self.theme.text_accent,
            max_width=820,
            line_spacing=14,
        ) + 30

        # 3. Divider
        curr_y = self.draw_divider(draw, y=curr_y, width=580)

        # 4. Optional Subtitle
        if subtitle:
            sub_font = self.load_font(30, bold=False)
            curr_y = self.draw_multiline_centered(
                draw,
                subtitle,
                start_y=curr_y + 10,
                font=sub_font,
                fill=self.theme.text_primary,
                max_width=820,
                line_spacing=14,
            ) + 25

        # 5. Bullet Points (if provided)
        if bullet_points:
            bp_font = self.load_font(28, bold=False)
            bullet_icon = "✦"
            curr_y += 10
            for bp in bullet_points:
                clean_bp = bp.strip()
                if not clean_bp:
                    continue
                # Draw bullet symbol with accent color
                bullet_text = f"{bullet_icon}  {clean_bp}"
                lines = self.wrap_text(bullet_text, bp_font, max_width=780)
                for i, line in enumerate(lines):
                    bbox = draw.textbbox((0, 0), line, font=bp_font)
                    line_w = bbox[2] - bbox[0]
                    line_h = bbox[3] - bbox[1]
                    x = 150  # Left aligned block inside card
                    draw.text((x, curr_y), line, font=bp_font, fill=self.theme.text_secondary)
                    curr_y += line_h + 12
                curr_y += 10

        return img
