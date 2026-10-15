"""Scene Director for Fábrica de Shorts.

Main coordinator that transforms a locked human script into an executable scenes.json manifest.
Provides interchangeable LLM adapters (Gemini, OpenAI, Local Fallback) via DirectorProvider.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Optional

from app.config import config
from app.services.editorial.script_manager import ScriptManager, ScriptVersion
from .prompt_builder import SYSTEM_INSTRUCTION, build_director_prompt
from .schemas import Scene, ScenePlan, VisualType
from .scene_validator import realign_narration_with_original, validate_scene_plan
from .visual_intent import estimate_duration_seconds, infer_visual_type


class DirectorProvider(ABC):
    """Abstract interface for Scene Director LLM providers."""

    @abstractmethod
    def generate_plan(
        self, script: ScriptVersion, settings: Optional[dict[str, Any]] = None
    ) -> ScenePlan:
        pass


class LocalRuleDirectorProvider(DirectorProvider):
    """Deterministic, rule-based director provider.

    Does not require an external API connection. Splits by punctuation/clauses and generates
    search queries using NLP heuristics. Ideal for regression tests and offline mode.
    """

    def generate_plan(
        self, script: ScriptVersion, settings: Optional[dict[str, Any]] = None
    ) -> ScenePlan:
        clean_text = script.clean_narration.strip()
        # Split text into meaningful sentences
        raw_sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+|\n+", clean_text)
            if s.strip()
        ]
        if not raw_sentences:
            raw_sentences = [clean_text]

        scenes: list[Scene] = []
        accumulated_time = 0.0

        for idx, sentence in enumerate(raw_sentences):
            scene_id = f"scene_{idx + 1:03d}"
            dur = estimate_duration_seconds(sentence)
            v_type = infer_visual_type(sentence)

            # Extract basic keywords for queries
            words = [w.lower() for w in re.findall(r"\b[a-zA-ZÀ-ÿ]{4,}\b", sentence)]
            top_words = words[:4] if words else ["short", "video"]
            queries = [
                " ".join(top_words),
                f"{top_words[0]} visual" if top_words else "concept",
                f"{script.channel} {top_words[-1]}" if top_words else "background",
            ]

            scene = Scene(
                scene_id=scene_id,
                narration=sentence,
                intent=f"Apresentar '{sentence[:35]}...'" if len(sentence) > 35 else f"Apresentar '{sentence}'",
                queries=queries,
                visual_type=v_type.value,
                preferred_motion="lateral",
                start=round(accumulated_time, 2),
                end=round(accumulated_time + dur, 2),
                confidence=0.85,
            )
            scenes.append(scene)
            accumulated_time += dur

        plan = ScenePlan(
            script_id=script.script_id,
            script_version=script.version_tag,
            script_hash=script.sha256,
            total_scenes=len(scenes),
            estimated_duration=round(accumulated_time, 2),
            scenes=scenes,
            brand_preset=settings.get("brand_preset", "editorial") if settings else "editorial",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        return plan


class GeminiDirectorProvider(DirectorProvider):
    """Google Gemini LLM provider for Scene Director."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = api_key or config.app.get("gemini_api_key", "")
        self.model_name = model_name or config.app.get("gemini_model_name", "gemini-3.5-flash")

    def generate_plan(
        self, script: ScriptVersion, settings: Optional[dict[str, Any]] = None
    ) -> ScenePlan:
        from google import genai
        from google.genai import types

        brand_style = settings.get("brand_preset", "editorial") if settings else "editorial"
        user_prompt = build_director_prompt(
            clean_script=script.clean_narration,
            channel=script.channel,
            brand_style=brand_style,
        )

        full_prompt = f"{SYSTEM_INSTRUCTION}\n\n{user_prompt}"

        # Request JSON generation with automatic model fallback on temporary 503 high demand
        candidate_models = [self.model_name] + [
            m for m in ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.5-flash"]
            if m != self.model_name
        ]

        client = genai.Client(api_key=self.api_key)
        response = None
        last_error = None

        for model in candidate_models:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.3,
                    ),
                )
                if response and response.text:
                    break
            except Exception as exc:
                last_error = exc
                continue

        if not response or not response.text:
            raise ValueError(f"All Gemini candidate models failed. Last error: {last_error}")

        response_text = response.text.strip()
        # Parse JSON
        parsed = json.loads(response_text)
        raw_scenes = parsed.get("scenes", [])
        if not raw_scenes and isinstance(parsed, list):
            raw_scenes = parsed

        # Enforce exact character alignment with approved human text
        realigned = realign_narration_with_original(raw_scenes, script.clean_narration)

        # Build Scene objects and compute timestamps
        scenes: list[Scene] = []
        accumulated_time = 0.0

        for idx, sc in enumerate(realigned):
            scene_id = sc.get("scene_id") or f"scene_{idx + 1:03d}"
            dur = estimate_duration_seconds(sc["narration"])
            scene = Scene(
                scene_id=scene_id,
                narration=sc["narration"],
                intent=sc.get("intent", ""),
                queries=sc.get("queries", [sc["narration"][:20]]),
                visual_type=sc.get("visual_type", "stock_video"),
                preferred_motion=sc.get("preferred_motion", "lateral"),
                start=round(accumulated_time, 2),
                end=round(accumulated_time + dur, 2),
                confidence=float(sc.get("confidence", 0.9)),
            )
            scenes.append(scene)
            accumulated_time += dur

        plan = ScenePlan(
            script_id=script.script_id,
            script_version=script.version_tag,
            script_hash=script.sha256,
            total_scenes=len(scenes),
            estimated_duration=round(accumulated_time, 2),
            scenes=scenes,
            brand_preset=brand_style,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        # Validate fidelity
        valid, errors = validate_scene_plan(plan, script.clean_narration)
        if not valid:
            raise ValueError(f"Scene plan validation failed: {'; '.join(errors)}")

        return plan


class SceneDirector:
    """High-level Facade for directing scripts into scene plans."""

    def __init__(
        self,
        provider: Optional[DirectorProvider] = None,
        script_manager: Optional[ScriptManager] = None,
    ):
        self.script_manager = script_manager or ScriptManager()
        if provider:
            self.provider = provider
        else:
            # Pick provider based on config
            gemini_key = config.app.get("gemini_api_key", "")
            if gemini_key:
                self.provider = GeminiDirectorProvider(api_key=gemini_key)
            else:
                self.provider = LocalRuleDirectorProvider()

    def direct_script(
        self,
        script_id: str,
        script_text: str,
        *,
        title: str = "",
        channel: str = "default",
        brand_preset: str = "editorial",
        save_plan: bool = True,
        output_dir: Optional[str | Path] = None,
    ) -> ScenePlan:
        # 1. Save and lock script version (Human Script Mode)
        script_version = self.script_manager.save_script(
            script_id=script_id,
            raw_text=script_text,
            title=title,
            channel=channel,
        )

        # 2. Invoke provider
        settings = {"brand_preset": brand_preset}
        plan = self.provider.generate_plan(script_version, settings)

        # 3. Save scenes.json
        if save_plan:
            out_folder = Path(output_dir) if output_dir else Path(f"storage/projects/{script_id}")
            out_folder.mkdir(parents=True, exist_ok=True)
            plan_file = out_folder / "scenes.json"
            with plan_file.open("w", encoding="utf-8") as f:
                f.write(plan.to_json(indent=2))

        return plan
