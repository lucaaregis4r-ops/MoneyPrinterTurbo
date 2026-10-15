"""Sprint 2 Automated Tests: Scene Director & Script Manager.

Validates:
1. Editorial Directives parsing and stripping.
2. Pronunciation Engine translations.
3. Script Manager versioning and immutability (script_v001, v002).
4. Scene Director schema & JSON validation.
5. Local and Gemini Director Providers producing valid scenes.json.
"""

import json
from pathlib import Path
import pytest

from app.config import config
from app.services.editorial.directives import parse_directives, strip_directives
from app.services.editorial.pronunciation import PronunciationEngine
from app.services.editorial.script_manager import ScriptManager
from app.services.director.schemas import ScenePlan, VisualType
from app.services.director.scene_director import (
    GeminiDirectorProvider,
    LocalRuleDirectorProvider,
    SceneDirector,
)
from app.services.director.scene_validator import validate_scene_plan


def test_directives_parsing():
    raw = (
        "Você provavelmente aprendeu que força é massa vezes aceleração. "
        "[visual: formula F = m * a] [graphic] "
        "Mas o que isso quer dizer? [visual: carrinho de supermercado] "
        "Imagine empurrar um carrinho vazio. [pause: 300ms] [emphasis: vazio]"
    )
    clean, directives = parse_directives(raw)
    assert "[visual:" not in clean
    assert "[pause:" not in clean
    assert "[graphic]" not in clean
    assert "Você provavelmente aprendeu" in clean
    assert "Imagine empurrar um carrinho vazio." in clean
    assert len(directives) >= 4
    tags = [d.tag for d in directives]
    assert "visual" in tags
    assert "graphic" in tags
    assert "pause" in tags
    assert "emphasis" in tags


def test_pronunciation_engine():
    engine = PronunciationEngine()
    result = engine.prepare_pair("A fórmula F = m.a foi criada por Newton.")
    assert result["display"] == "A fórmula F = m.a foi criada por Newton."
    assert "Éfe é igual a ême vezes á" in result["spoken"]

    nba_res = engine.prepare_pair("Ele jogou na NBA.")
    assert "ene-bi-ei" in nba_res["spoken"]


def test_script_manager_immutability(tmp_path: Path):
    manager = ScriptManager(storage_dir=tmp_path / "scripts")
    raw_1 = "Newton explicou o movimento dos corpos no espaço."
    v1 = manager.save_script("fisica_01", raw_1, title="Leis de Newton")
    assert v1.version == 1
    assert v1.version_tag == "script_v001"
    assert v1.clean_narration == raw_1
    assert v1.sha256 is not None

    # Saving identical text should not create a duplicate version
    v1_repeat = manager.save_script("fisica_01", raw_1)
    assert v1_repeat.version == 1

    # Modifying text should create v002 without overwriting v001
    raw_2 = "Newton explicou o movimento dos corpos celestes no espaço."
    v2 = manager.save_script("fisica_01", raw_2)
    assert v2.version == 2
    assert v2.version_tag == "script_v002"
    assert v2.sha256 != v1.sha256

    # Verify both versions exist on disk
    retrieved_v1 = manager.get_version("fisica_01", 1)
    retrieved_v2 = manager.get_version("fisica_01", 2)
    assert retrieved_v1.clean_narration == raw_1
    assert retrieved_v2.clean_narration == raw_2


def test_scene_director_local_provider(tmp_path: Path):
    script_manager = ScriptManager(storage_dir=tmp_path / "scripts")
    director = SceneDirector(
        provider=LocalRuleDirectorProvider(),
        script_manager=script_manager,
    )
    raw_script = (
        "Você provavelmente aprendeu que força é massa vezes aceleração. "
        "Mas o que isso quer dizer na prática? "
        "Imagine empurrar um carrinho de supermercado vazio. "
        "Agora imagine empurrar o mesmo carrinho lotado."
    )
    plan = director.direct_script(
        script_id="newton_carrinho",
        script_text=raw_script,
        title="Newton e o Carrinho",
        channel="fisica",
        output_dir=tmp_path / "output",
    )

    assert plan.total_scenes >= 3
    assert (tmp_path / "output" / "scenes.json").exists()

    # Verify JSON structure
    with (tmp_path / "output" / "scenes.json").open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["script_id"] == "newton_carrinho"
    assert len(data["scenes"]) == plan.total_scenes

    # Validate fidelity
    is_valid, errors = validate_scene_plan(plan, raw_script)
    assert is_valid, f"Validation errors: {errors}"


def test_scene_director_gemini_provider(tmp_path: Path):
    """End-to-end test of the Gemini LLM provider creating a real scene plan."""
    gemini_key = config.app.get("gemini_api_key", "")
    if not gemini_key:
        pytest.skip("No Gemini API key configured in config.toml")

    script_manager = ScriptManager(storage_dir=tmp_path / "scripts")
    provider = GeminiDirectorProvider(api_key=gemini_key, model_name="gemini-3.5-flash")
    director = SceneDirector(provider=provider, script_manager=script_manager)

    test_script = (
        "Você provavelmente aprendeu que força é massa vezes aceleração. "
        "Mas empurrar um carrinho cheio é outra história. "
        "Com mais massa, você precisa de muito mais força para atingir a mesma aceleração. "
        "É a segunda lei de Newton acontecendo bem na sua frente."
    )

    out_dir = tmp_path / "gemini_output"
    plan = director.direct_script(
        script_id="newton_gemini_demo",
        script_text=test_script,
        title="Newton Gemini Demo",
        channel="fisica",
        output_dir=out_dir,
    )

    assert plan.total_scenes >= 3
    scenes_file = out_dir / "scenes.json"
    assert scenes_file.exists()

    with scenes_file.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    print(f"\nGenerated {len(manifest['scenes'])} scenes with Gemini:")
    for sc in manifest["scenes"]:
        print(f"  [{sc['scene_id']}] ({sc['visual_type']}) Narration: \"{sc['narration']}\"")
        print(f"    Intent: {sc['intent']}")
        print(f"    Queries: {sc['queries']}")

    # Validate that all scenes contain required fields
    for sc in manifest["scenes"]:
        assert sc["scene_id"].startswith("scene_")
        assert len(sc["narration"]) > 0
        assert len(sc["queries"]) >= 1
        assert sc["intent"]
        assert sc["visual_type"]
