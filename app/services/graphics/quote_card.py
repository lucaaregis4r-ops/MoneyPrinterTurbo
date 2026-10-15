"""Quote Card Renderer for memorable phrases and author citations.
"""

from __future__ import annotations
import re
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .base_card import BaseCardRenderer
from .theme import CardTheme, get_theme


def parse_quote_and_author(text: str) -> Tuple[str, str]:
    """Extracts quote body and author from text or directives."""
    # Directive [quote: "...", author: "..."]
    m_dir = re.search(r"\[quote:\s*([^\]]+)\]", text, re.IGNORECASE)
    if m_dir:
        content = m_dir.group(1).strip()
        if "author:" in content.lower():
            parts = re.split(r"author:\s*", content, flags=re.IGNORECASE)
            return parts[0].strip(" \"'“”),-"), parts[1].strip(" \"'“”)")
        return content.strip(" \"'“”)"), ""

    # Quoted text with author dash: "Quote" - Author
    m_dash = re.search(r'["“]([^"”]+)["”]\s*[-—]\s*([^,\.\n]+)', text)
    if m_dash:
        return m_dash.group(1).strip(), m_dash.group(2).strip()

    # Just quoted text: "Quote"
    m_quotes = re.search(r'["“]([^"”]{8,})["”]', text)
    if m_quotes:
        quote = m_quotes.group(1).strip()
        remaining = text.replace(m_quotes.group(0), "")
        # Search for author attribution words
        m_author = re.search(r'(?:como disse|disse|afirmou|escreveu|segundo)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', remaining)
        author = m_author.group(1).strip() if m_author else ""
        return quote, author

    # Fallback to whole text
    return text.strip(" \"'“”)"), ""


class QuoteCardRenderer(BaseCardRenderer):
    """Renders elegant quote cards with decorative quotation marks and author attribution."""

    def __init__(self, theme: Optional[CardTheme] = None):
        super().__init__(theme=theme or get_theme("editorial"))

    def render_card_image(
        self,
        text: str,
        quote: Optional[str] = None,
        author: Optional[str] = None,
    ) -> Image.Image:
        """Renders the quote card onto a 1080x1920 PIL image."""
        img = self.create_background()
        draw = ImageDraw.Draw(img)

        # 1. Badge
        curr_y = self.draw_badge(draw, "💬 CITAÇÃO NOTÁVEL", center_y=400)

        # 2. Extract quote & author if missing
        extracted_quote, extracted_author = parse_quote_and_author(text)
        final_quote = quote or extracted_quote
        final_author = author or extracted_author

        # 3. Decorative Quotation Mark
        quote_mark_font = self.load_font(120, bold=True)
        q_bbox = draw.textbbox((0, 0), "“", font=quote_mark_font)
        q_w = q_bbox[2] - q_bbox[0]
        draw.text(((self.width - q_w) // 2, curr_y - 20), "“", font=quote_mark_font, fill=self.theme.text_accent)
        curr_y += 90

        # 4. Quote Body Text
        q_len = len(final_quote)
        q_size = 40 if q_len <= 90 else (32 if q_len <= 180 else 26)
        body_font = self.load_font(q_size, bold=False)

        curr_y = self.draw_multiline_centered(
            draw,
            f'"{final_quote}"',
            start_y=curr_y,
            font=body_font,
            fill=self.theme.text_primary,
            max_width=820,
            line_spacing=18,
        ) + 40

        # 5. Divider
        curr_y = self.draw_divider(draw, y=curr_y, width=480)

        # 6. Author attribution
        if final_author:
            author_font = self.load_font(32, bold=True)
            author_label = f"— {final_author.upper()} —"
            a_bbox = draw.textbbox((0, 0), author_label, font=author_font)
            a_w = a_bbox[2] - a_bbox[0]
            draw.text(((self.width - a_w) // 2, curr_y + 10), author_label, font=author_font, fill=self.theme.text_accent)

        return img
