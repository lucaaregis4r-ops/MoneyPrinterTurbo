"""Graphics Engine orchestrator for programmatic visual cards.

Routes abstract scenes (formulas, statistics, quotes, titles, concepts)
to dedicated programmatic renderers and generates smooth 9:16 vertical MP4 clips.
"""

from __future__ import annotations
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from app.services.director.schemas import Scene, VisualType
from .base_card import BaseCardRenderer
from .formula_card import FormulaCardRenderer
from .number_card import NumberCardRenderer
from .quote_card import QuoteCardRenderer
from .text_card import TextCardRenderer
from .theme import get_theme

if TYPE_CHECKING:
    from app.services.media_ranker.schemas import MediaCandidate


class GraphicsEngine:
    """Central engine for rendering programmatic motion graphic cards."""

    GRAPHIC_TYPES = {
        VisualType.FORMULA.value,
        VisualType.NUMBER.value,
        VisualType.QUOTE.value,
        VisualType.GRAPHIC.value,
        VisualType.TITLE.value,
    }

    def __init__(self, cache_dir: Optional[Path | str] = None):
        self.cache_dir = Path(cache_dir or "storage/media_cache/graphics").resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def is_graphic_type(cls, visual_type: Union[VisualType, str, None]) -> bool:
        """Determines if a visual type is handled by the Graphics Engine."""
        if not visual_type:
            return False
        val = visual_type.value if hasattr(visual_type, "value") else str(visual_type).lower()
        return val in cls.GRAPHIC_TYPES

    @classmethod
    def is_graphic_scene(cls, scene: Scene) -> bool:
        """Checks if a scene should be rendered via the graphics engine."""
        if cls.is_graphic_type(scene.visual_type):
            return True
        text = (scene.narration or "").lower()
        if any(marker in text for marker in ["[formula", "[graphic", "[quote", "[number", "[card"]):
            return True
        return False

    def render_scene_card(
        self,
        scene: Scene,
        output_path: Optional[Path | str] = None,
        duration: float = 4.0,
        theme_name: Optional[str] = None,
        motion: str = "zoom_in",
    ) -> Path:
        """Renders an appropriate graphic card video for the given scene."""
        if output_path is None:
            safe_id = hashlib.md5(f"{scene.scene_id}_{scene.narration}_{duration}".encode()).hexdigest()[:12]
            output_path = self.cache_dir / f"card_{scene.scene_id}_{safe_id}.mp4"

        target_file = Path(output_path).resolve()
        if target_file.exists() and target_file.stat().st_size > 1000:
            return target_file

        vtype = scene.visual_type.value if hasattr(scene.visual_type, "value") else str(scene.visual_type)
        theme = get_theme(theme_name) if theme_name else None

        # Route by visual type
        if vtype == VisualType.FORMULA.value:
            renderer = FormulaCardRenderer(theme=theme or get_theme("chalkboard"))
            img = renderer.render_card_image(
                formula=scene.narration,
                title=scene.intent if scene.intent else "FÓRMULA FUNDAMENTAL",
                explanation=scene.narration,
            )
        elif vtype == VisualType.NUMBER.value:
            renderer = NumberCardRenderer(theme=theme or get_theme("neon_sports"))
            img = renderer.render_card_image(
                text=scene.narration,
                context_label=scene.intent if scene.intent else "MÉTRICA CHAVE",
                explanation=scene.narration,
            )
        elif vtype == VisualType.QUOTE.value:
            renderer = QuoteCardRenderer(theme=theme or get_theme("editorial"))
            img = renderer.render_card_image(text=scene.narration)
        elif vtype == VisualType.TITLE.value:
            renderer = TextCardRenderer(theme=theme or get_theme("sunset_burst"))
            img = renderer.render_card_image(
                title=scene.intent or scene.narration[:40],
                subtitle=scene.narration if len(scene.narration) > 40 else None,
                badge_label="🎬 CAPÍTULO",
            )
        else:
            # Default / Graphic / Concept card
            renderer = TextCardRenderer(theme=theme or get_theme("dark_modern"))
            img = renderer.render_card_image(
                title=scene.intent or "CONCEITO CHAVE",
                subtitle=scene.narration,
                badge_label="📌 INFOGRÁFICO",
            )

        # Convert image to video clip
        return renderer.image_to_video(
            image=img,
            output_path=target_file,
            duration=duration,
            motion=motion,
            fps=30,
        )

    def create_card_candidate(
        self,
        scene: Scene,
        duration: float = 4.0,
        theme_name: Optional[str] = None,
    ) -> MediaCandidate:
        """Renders the scene card and packages it into a top-priority MediaCandidate."""
        from app.services.media_ranker.schemas import MediaCandidate

        card_path = self.render_scene_card(
            scene=scene,
            duration=duration,
            theme_name=theme_name,
            motion="zoom_in",
        )

        return MediaCandidate(
            provider="graphics_engine",
            asset_id=f"card_{scene.scene_id}",
            query=scene.intent or scene.narration[:30],
            width=1080,
            height=1920,
            duration=duration,
            url=str(card_path),
            local_path=str(card_path),
            technical_score=1.0,
            semantic_score=0.98,
            final_score=0.99,
            source_page="Graphics Engine Programmatic Card",
        )
