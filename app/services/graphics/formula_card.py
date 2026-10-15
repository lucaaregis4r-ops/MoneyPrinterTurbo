"""Formula Card Renderer for scientific and mathematical equations.
"""

from __future__ import annotations
import re
from typing import Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .base_card import BaseCardRenderer
from .theme import CardTheme, get_theme

_KNOWN_FORMULAS: Dict[str, Dict[str, str]] = {
    "f = m · a": {"F": "Força (N)", "m": "Massa (kg)", "a": "Aceleração (m/s²)"},
    "f = m.a": {"F": "Força (N)", "m": "Massa (kg)", "a": "Aceleração (m/s²)"},
    "e = m · c²": {"E": "Energia (J)", "m": "Massa (kg)", "c": "Velocidade da Luz (m/s)"},
    "e = mc²": {"E": "Energia (J)", "m": "Massa (kg)", "c": "Velocidade da Luz (m/s)"},
    "v = d / t": {"v": "Velocidade (m/s)", "d": "Distância (m)", "t": "Tempo (s)"},
    "v = δs / δt": {"v": "Velocidade Média", "Δs": "Variação de Espaço", "Δt": "Intervalo de Tempo"},
    "ec = (m · v²) / 2": {"Ec": "Energia Cinética", "m": "Massa", "v": "Velocidade"},
}


def clean_formula_text(raw_text: str) -> str:
    """Extracts and normalizes math formula expression."""
    # Look for [formula: ...] directive first
    m_dir = re.search(r"\[formula:\s*([^\]]+)\]", raw_text, re.IGNORECASE)
    if m_dir:
        candidate = m_dir.group(1).strip()
    else:
        # Regex for equations like F = m.a or E = mc²
        m_eq = re.search(r"([A-Za-z0-9_Δ]+\s*=\s*[\w\d\.\+\-\*\/²\^]+)", raw_text)
        candidate = m_eq.group(1).strip() if m_eq else raw_text.strip()

    # Normalize multiplication signs
    normalized = candidate.replace("*", " · ").replace(".", " · ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


class FormulaCardRenderer(BaseCardRenderer):
    """Renders high-impact formula cards for physics and mathematics."""

    def __init__(self, theme: Optional[CardTheme] = None):
        super().__init__(theme=theme or get_theme("chalkboard"))

    def render_card_image(
        self,
        formula: str,
        title: Optional[str] = None,
        explanation: Optional[str] = None,
        variables: Optional[Dict[str, str]] = None,
    ) -> Image.Image:
        """Renders the formula card onto a 1080x1920 PIL image."""
        img = self.create_background()
        draw = ImageDraw.Draw(img)

        # 1. Badge
        curr_y = self.draw_badge(draw, "📐 FÓRMULA FÍSICA", center_y=400)

        # 2. Title (Optional)
        if title:
            title_font = self.load_font(34, bold=True)
            curr_y = self.draw_multiline_centered(
                draw,
                title.upper(),
                start_y=curr_y,
                font=title_font,
                fill=self.theme.text_secondary,
                max_width=800,
            ) + 20

        # 3. Main Hero Formula Display
        cleaned_formula = clean_formula_text(formula)
        formula_size = 80 if len(cleaned_formula) <= 14 else 60
        formula_font = self.load_font(formula_size, bold=True)

        bbox = draw.textbbox((0, 0), cleaned_formula, font=formula_font)
        f_w = bbox[2] - bbox[0]
        f_h = bbox[3] - bbox[1]

        # Draw highlight box for formula
        box_pad_x = 40
        box_pad_y = 30
        box_x1 = max(110, (self.width - f_w) // 2 - box_pad_x)
        box_y1 = curr_y + 30
        box_x2 = min(self.width - 110, (self.width + f_w) // 2 + box_pad_x)
        box_y2 = box_y1 + f_h + box_pad_y * 2

        draw.rounded_rectangle(
            [(box_x1, box_y1), (box_x2, box_y2)],
            radius=20,
            fill=(0, 0, 0, 70),
            outline=self.theme.card_border,
            width=2,
        )

        draw.text(
            ((self.width - f_w) // 2, box_y1 + box_pad_y - bbox[1] // 2),
            cleaned_formula,
            font=formula_font,
            fill=self.theme.text_accent,
        )
        curr_y = box_y2 + 40

        # 4. Divider
        curr_y = self.draw_divider(draw, y=curr_y, width=640)

        # 5. Variable Breakdown
        resolved_vars = variables
        if not resolved_vars:
            lower_clean = cleaned_formula.lower()
            for k, v in _KNOWN_FORMULAS.items():
                if k in lower_clean or lower_clean in k:
                    resolved_vars = v
                    break

        if resolved_vars:
            var_font = self.load_font(28, bold=False)
            bold_var_font = self.load_font(28, bold=True)
            for symbol, desc in resolved_vars.items():
                row_text = f"{symbol}  :  {desc}"
                bbox = draw.textbbox((0, 0), row_text, font=var_font)
                row_w = bbox[2] - bbox[0]
                row_x = (self.width - row_w) // 2
                draw.text((row_x, curr_y), f"{symbol}", font=bold_var_font, fill=self.theme.text_accent)
                desc_offset = draw.textbbox((0, 0), f"{symbol}  :  ", font=bold_var_font)[2]
                draw.text((row_x + desc_offset, curr_y), desc, font=var_font, fill=self.theme.text_primary)
                curr_y += bbox[3] - bbox[1] + 18
            curr_y += 20

        # 6. Explanation Narration
        if explanation:
            exp_font = self.load_font(28, bold=False)
            curr_y = self.draw_multiline_centered(
                draw,
                explanation,
                start_y=curr_y + 10,
                font=exp_font,
                fill=self.theme.text_secondary,
                max_width=820,
                line_spacing=12,
            )

        return img
