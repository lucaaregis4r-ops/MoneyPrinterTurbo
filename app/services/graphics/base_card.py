"""Base class and common drawing helpers for programmatic 9:16 graphic cards.
"""

from __future__ import annotations
import math
import os
from pathlib import Path
import subprocess
import tempfile
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .theme import CardTheme, get_theme

# Search candidate fonts in project and system
_REPO_FONT_BOLD = Path("resource/fonts/BeVietnamPro-Bold.ttf")
_REPO_FONT_MEDIUM = Path("resource/fonts/BeVietnamPro-Medium.ttf")
_SYS_FONTS = [
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]


def resolve_font_path(prefer_bold: bool = True) -> str:
    """Finds best available TrueType font."""
    repo_font = _REPO_FONT_BOLD if prefer_bold else _REPO_FONT_MEDIUM
    if repo_font.exists():
        return str(repo_font.resolve())
    for sf in _SYS_FONTS:
        if sf.exists():
            return str(sf)
    return ""


class BaseCardRenderer:
    """Renders 1080x1920 vertical graphic cards and converts them to animated MP4 clips."""

    def __init__(
        self,
        theme: Optional[CardTheme] = None,
        width: int = 1080,
        height: int = 1920,
    ):
        self.theme = theme or get_theme("dark_modern")
        self.width = width
        self.height = height
        self.font_bold_path = resolve_font_path(prefer_bold=True)
        self.font_medium_path = resolve_font_path(prefer_bold=False)

    def load_font(self, size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
        """Loads a font at specified point size with fallback."""
        path = self.font_bold_path if bold else self.font_medium_path
        if path and Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
        return ImageFont.load_default()

    def create_background(self) -> Image.Image:
        """Creates a modern 1080x1920 canvas with vertical gradient and centered card overlay."""
        img = Image.new("RGBA", (self.width, self.height))
        draw = ImageDraw.Draw(img)

        # 1. Smooth vertical gradient
        r1, g1, b1 = self.theme.bg_top
        r2, g2, b2 = self.theme.bg_bottom
        for y in range(self.height):
            ratio = y / float(self.height)
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            draw.line([(0, y), (self.width, y)], fill=(r, g, b, 255))

        # 2. Subtle decorative corner accents / soft ambient glow
        accent_r, accent_g, accent_b = self.theme.text_accent
        glow_layer = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)
        glow_draw.ellipse(
            [(self.width // 2 - 400, self.height // 2 - 400), (self.width // 2 + 400, self.height // 2 + 400)],
            fill=(accent_r, accent_g, accent_b, 18),
        )
        img = Image.alpha_composite(img, glow_layer)
        draw = ImageDraw.Draw(img)

        # 3. Floating centered card container
        card_x1 = 70
        card_y1 = 320
        card_x2 = self.width - 70
        card_y2 = self.height - 320
        radius = 36

        # Draw card background
        card_layer = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        c_draw = ImageDraw.Draw(card_layer)
        c_draw.rounded_rectangle(
            [(card_x1, card_y1), (card_x2, card_y2)],
            radius=radius,
            fill=self.theme.card_bg,
            outline=self.theme.card_border,
            width=3,
        )
        img = Image.alpha_composite(img, card_layer)
        return img

    def draw_badge(self, draw: ImageDraw.ImageDraw, label: str, center_y: int = 400) -> int:
        """Renders an elegant pill badge at the top of the card."""
        font = self.load_font(26, bold=True)
        clean_text = label.upper().strip()
        bbox = draw.textbbox((0, 0), clean_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        pad_x = 28
        pad_y = 12
        pill_w = text_w + pad_x * 2
        pill_h = text_h + pad_y * 2
        pill_x1 = (self.width - pill_w) // 2
        pill_y1 = center_y - pill_h // 2
        pill_x2 = pill_x1 + pill_w
        pill_y2 = pill_y1 + pill_h

        draw.rounded_rectangle(
            [(pill_x1, pill_y1), (pill_x2, pill_y2)],
            radius=18,
            fill=self.theme.badge_bg,
            outline=self.theme.card_border,
            width=2,
        )
        text_x = pill_x1 + pad_x
        text_y = pill_y1 + pad_y - bbox[1] // 2
        draw.text((text_x, text_y), clean_text, font=font, fill=self.theme.badge_text)
        return pill_y2 + 30

    def draw_divider(self, draw: ImageDraw.ImageDraw, y: int, width: int = 560) -> int:
        """Renders a soft glowing horizontal divider."""
        x1 = (self.width - width) // 2
        x2 = x1 + width
        draw.line([(x1, y), (x2, y)], fill=self.theme.divider_color, width=2)
        return y + 30

    def wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
        """Wraps text into lines that fit within max_width pixels."""
        words = text.split()
        if not words:
            return []

        lines = []
        current_line = []

        dummy = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)

        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w <= max_width or not current_line:
                current_line.append(word)
            else:
                lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))
        return lines

    def draw_multiline_centered(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        start_y: int,
        font: ImageFont.FreeTypeFont,
        fill: Tuple[int, int, int],
        max_width: int = 840,
        line_spacing: int = 14,
    ) -> int:
        """Draws wrapped multiline text centered horizontally."""
        lines = self.wrap_text(text, font, max_width)
        curr_y = start_y
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_w = bbox[2] - bbox[0]
            line_h = bbox[3] - bbox[1]
            x = (self.width - line_w) // 2
            draw.text((x, curr_y), line, font=font, fill=fill)
            curr_y += line_h + line_spacing
        return curr_y

    def image_to_video(
        self,
        image: Image.Image,
        output_path: Path | str,
        duration: float = 4.0,
        motion: str = "zoom_in",
        fps: int = 30,
    ) -> Path:
        """Converts the static card image into an animated 1080x1920 MP4 video clip."""
        target_path = Path(output_path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        rgb_image = image.convert("RGB")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
            tmp_img_path = Path(tmp_img.name)
            rgb_image.save(tmp_img_path, format="PNG")

        try:
            # Build FFmpeg command with subtle camera push and silent audio track
            dur_str = f"{max(1.0, float(duration)):.2f}"
            if motion in {"zoom_in", "ken_burns"}:
                vf_filter = (
                    "zoompan=z='min(zoom+0.0006,1.05)':"
                    "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                    f"d=1:s={self.width}x{self.height}:fps={fps}"
                )
            else:
                vf_filter = f"scale={self.width}:{self.height},setsar=1"

            cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-loop", "1", "-i", str(tmp_img_path),
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", dur_str,
                "-vf", vf_filter,
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest",
                "-r", str(fps),
                str(target_path),
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            # Fallback simple render if zoompan fails
            fallback_cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-loop", "1", "-i", str(tmp_img_path),
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", dur_str,
                "-vf", f"scale={self.width}:{self.height}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest",
                "-r", str(fps),
                str(target_path),
            ]
            subprocess.run(fallback_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        finally:
            if tmp_img_path.exists():
                tmp_img_path.unlink()

        return target_path
