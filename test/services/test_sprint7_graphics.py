"""Sprint 7 Test Suite: Programmatic Graphics Engine and Typography Cards.

Validates:
1. BaseCardRenderer rendering 1080x1920 canvas with vertical gradients and FFmpeg video generation.
2. FormulaCardRenderer for physical and mathematical equations.
3. NumberCardRenderer for statistics and hero numbers.
4. QuoteCardRenderer for author citations and phrases.
5. TextCardRenderer for chapter titles and concepts.
6. GraphicsEngine routing and caching.
7. MediaSearcher integration injecting high-priority card candidates.
"""

import json
from pathlib import Path
import subprocess
import pytest
from PIL import Image

from app.services.director.schemas import Scene, VisualType
from app.services.graphics.base_card import BaseCardRenderer, resolve_font_path
from app.services.graphics.formula_card import FormulaCardRenderer, clean_formula_text
from app.services.graphics.graphics_engine import GraphicsEngine
from app.services.graphics.number_card import NumberCardRenderer, extract_hero_number
from app.services.graphics.quote_card import QuoteCardRenderer, parse_quote_and_author
from app.services.graphics.text_card import TextCardRenderer
from app.services.graphics.theme import CardTheme, get_theme, THEMES
from app.services.media_ranker.media_searcher import MediaSearcher


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    out_dir = tmp_path / "graphics_tests"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _probe_video(path: Path) -> dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=width,height,r_frame_rate,duration",
        "-of", "json",
        str(path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(res.stdout)
    streams = data.get("streams", [])
    assert len(streams) > 0
    return streams[0]


def test_theme_system():
    assert "chalkboard" in THEMES
    assert "dark_modern" in THEMES
    assert "editorial" in THEMES
    assert "neon_sports" in THEMES
    assert "sunset_burst" in THEMES

    default_theme = get_theme("non_existent_theme")
    assert default_theme.name == "dark_modern"

    chalk = get_theme("chalkboard")
    assert chalk.name == "chalkboard"
    assert len(chalk.bg_top) == 3


def test_helpers():
    f_clean = clean_formula_text("F = m.a")
    assert " · " in f_clean or "=" in f_clean

    num, _ = extract_hero_number("Usain Bolt correu a 44 km/h na pista")
    assert "44" in num

    q, a = parse_quote_and_author('Como disse Albert Einstein: "A imaginação é tudo."')
    assert "imaginação" in q.lower()
    assert "einstein" in a.lower()


def test_base_card_rendering_and_video(tmp_output_dir: Path):
    renderer = BaseCardRenderer()
    bg = renderer.create_background()
    assert bg.size == (1080, 1920)

    out_mp4 = tmp_output_dir / "test_base.mp4"
    rendered_path = renderer.image_to_video(bg, out_mp4, duration=1.5, motion="zoom_in")
    assert rendered_path.exists()
    assert rendered_path.stat().st_size > 1000

    info = _probe_video(rendered_path)
    assert info["width"] == 1080
    assert info["height"] == 1920
    assert info["r_frame_rate"] == "30/1"


def test_formula_card_renderer(tmp_output_dir: Path):
    renderer = FormulaCardRenderer()
    img = renderer.render_card_image(
        formula="F = m · a",
        title="Segunda Lei de Newton",
        explanation="A força resultante é o produto da massa pela aceleração.",
    )
    assert img.size == (1080, 1920)

    out_mp4 = tmp_output_dir / "formula.mp4"
    video_path = renderer.image_to_video(img, out_mp4, duration=2.0)
    assert video_path.exists()

    info = _probe_video(video_path)
    assert info["width"] == 1080
    assert info["height"] == 1920


def test_number_card_renderer(tmp_output_dir: Path):
    renderer = NumberCardRenderer()
    img = renderer.render_card_image(
        text="Ele bateu o recorde mundial completando a prova em 9.58s.",
        hero_number="9.58s",
        context_label="Recorde Mundial dos 100 Metros",
    )
    assert img.size == (1080, 1920)

    out_mp4 = tmp_output_dir / "number.mp4"
    video_path = renderer.image_to_video(img, out_mp4, duration=2.0)
    assert video_path.exists()

    info = _probe_video(video_path)
    assert info["width"] == 1080
    assert info["height"] == 1920


def test_quote_card_renderer(tmp_output_dir: Path):
    renderer = QuoteCardRenderer()
    img = renderer.render_card_image(
        text='"Penso, logo existo."',
        quote="Penso, logo existo.",
        author="René Descartes",
    )
    assert img.size == (1080, 1920)

    out_mp4 = tmp_output_dir / "quote.mp4"
    video_path = renderer.image_to_video(img, out_mp4, duration=2.0)
    assert video_path.exists()

    info = _probe_video(video_path)
    assert info["width"] == 1080
    assert info["height"] == 1920


def test_text_card_renderer(tmp_output_dir: Path):
    renderer = TextCardRenderer()
    img = renderer.render_card_image(
        title="A Lei da Inércia",
        subtitle="Primeiro princípio fundamental",
        bullet_points=[
            "Objetos em repouso permanecem em repouso",
            "Movimento retilíneo uniforme permanece sem força externa",
        ],
    )
    assert img.size == (1080, 1920)

    out_mp4 = tmp_output_dir / "text_card.mp4"
    video_path = renderer.image_to_video(img, out_mp4, duration=2.0)
    assert video_path.exists()

    info = _probe_video(video_path)
    assert info["width"] == 1080
    assert info["height"] == 1920


def test_graphics_engine_caching_and_candidate(tmp_output_dir: Path):
    engine = GraphicsEngine(cache_dir=tmp_output_dir)

    scene = Scene(
        scene_id="scene_physics_01",
        narration="E = mc² representa a equivalência entre massa e energia.",
        intent="Equação de Einstein",
        queries=["einstein", "energia"],
        visual_type=VisualType.FORMULA,
    )

    assert GraphicsEngine.is_graphic_type(scene.visual_type)
    assert GraphicsEngine.is_graphic_scene(scene)

    candidate = engine.create_card_candidate(scene, duration=2.0)
    assert candidate.provider == "graphics_engine"
    assert candidate.final_score >= 0.95
    assert Path(candidate.local_path).exists()

    # Re-rendering must hit cache and return existing path
    cached_candidate = engine.create_card_candidate(scene, duration=2.0)
    assert cached_candidate.local_path == candidate.local_path


def test_media_searcher_integration_with_graphics(tmp_output_dir: Path):
    searcher = MediaSearcher(media_cache_dir=tmp_output_dir)

    formula_scene = Scene(
        scene_id="scene_calc_01",
        narration="A fórmula da aceleração é F = m.a aplicada à massa do corpo.",
        intent="Fórmula Dinâmica",
        queries=["newton", "fisica"],
        visual_type=VisualType.FORMULA,
    )

    candidates = searcher.search_for_scene(formula_scene, target_duration=2.5, candidates_per_scene=3)
    assert len(candidates) > 0
    # Candidate #0 must be the programmatic card
    assert candidates[0].provider == "graphics_engine"
    assert candidates[0].local_path is not None
    assert Path(candidates[0].local_path).exists()
