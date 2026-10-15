"""Shorts Factory Master Pipeline Orchestrator.

Implements the end-to-end vision (Section 1 & Section 60):
HUMAN SCRIPT -> SCENE DIRECTOR -> MEDIA SEARCHER -> VOICE ENGINE -> VIDEO PROJECT -> VIDEO DRAFT.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Callable, Optional

from app.config import config
from app.services import voice
from app.services.director.scene_director import SceneDirector
from app.services.director.schemas import ScenePlan
from app.services.editorial.pronunciation import PronunciationEngine
from app.services.editorial.script_manager import ScriptManager
from app.services.media_ranker.media_searcher import MediaSearcher
from app.services.video_project import VideoProject


class ShortsFactory:
    """Master orchestrator for the Shorts Factory."""

    def __init__(
        self,
        base_dir: str | Path = "storage",
        voice_name: str = "pt-BR-AntonioNeural-Male",
    ):
        self.base_dir = Path(base_dir).resolve()
        self.projects_dir = self.base_dir / "projects"
        self.scripts_dir = self.base_dir / "scripts"
        self.media_cache_dir = self.base_dir / "media_cache"
        self.audio_cache_dir = self.base_dir / "audio_cache"

        for d in [self.projects_dir, self.scripts_dir, self.media_cache_dir, self.audio_cache_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.script_manager = ScriptManager(storage_dir=self.scripts_dir)
        self.pronunciation_engine = PronunciationEngine()
        self.director = SceneDirector(script_manager=self.script_manager)
        self.searcher = MediaSearcher(media_cache_dir=self.media_cache_dir)
        self.voice_name = voice_name

    def produce_draft(
        self,
        script_id: str,
        script_text: str,
        *,
        title: str = "",
        channel: str = "default",
        brand_style: str = "editorial",
        voice_name: Optional[str] = None,
        on_progress: Optional[Callable[[str, float], None]] = None,
    ) -> dict[str, Any]:
        """Executes the complete pipeline:

        1. Save & lock human script version
        2. Direct script into scenes (LLM)
        3. Synthesize voice audio with timestamps for each scene
        4. Search and select media candidates
        5. Initialize VideoProject and render draft video
        """
        chosen_voice = voice_name or self.voice_name
        project_folder = self.projects_dir / script_id
        project_folder.mkdir(parents=True, exist_ok=True)

        # 1. Direct Script (Saves script_v00X and generates ScenePlan)
        if on_progress:
            on_progress("Directing script into visual scenes...", 0.20)
        plan = self.director.direct_script(
            script_id=script_id,
            script_text=script_text,
            title=title,
            channel=channel,
            brand_preset=brand_style,
            output_dir=project_folder,
        )

        # 2. Voice Synthesis for each scene
        if on_progress:
            on_progress("Synthesizing voice audio with Edge TTS...", 0.40)
        audio_dir = project_folder / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        for scene in plan.scenes:
            audio_path = audio_dir / f"{scene.scene_id}.mp3"
            # Apply pronunciation engine to translate formulas/acronyms for the TTS
            spoken_text = self.pronunciation_engine.to_spoken(scene.narration)
            voice.tts(
                text=spoken_text,
                voice_name=chosen_voice,
                voice_rate=1.0,
                voice_file=str(audio_path),
            )
            scene.overlay = scene.overlay or {}
            scene.overlay["spoken_text"] = spoken_text
            scene.overlay["audio_file"] = str(audio_path)

        # 3. Media Search & Candidate Collection
        if on_progress:
            on_progress("Searching media candidates across queries...", 0.60)
        self.searcher.populate_scene_plan(
            plan=plan,
            candidates_per_scene=5,
            download_selected=True,
            save_plan_path=project_folder / "scenes.json",
        )

        # 4. Assemble Project Manifest for VideoProject
        if on_progress:
            on_progress("Creating editable project manifest...", 0.80)
        project_scenes = []
        for scene in plan.scenes:
            selected = scene.selected_media or {}
            footage_path = selected.get("local_path")
            audio_path = (scene.overlay or {}).get("audio_file")

            if not footage_path or not Path(footage_path).exists():
                # Fallback to synthetic clip if not local
                fallback_clip = self.media_cache_dir / f"fallback_{scene.scene_id}.mp4"
                from .media_ranker.candidate_builder import _generate_synthetic_clip
                _generate_synthetic_clip(scene.queries[0] if scene.queries else scene.narration, fallback_clip)
                footage_path = str(fallback_clip)

            project_scenes.append(
                {
                    "id": scene.scene_id,
                    "narration": scene.narration,
                    "duration": float(scene.end - scene.start) if (scene.end and scene.start) else 4.0,
                    "footage": footage_path,
                    "audio": audio_path,
                }
            )

        video_project = VideoProject(project_folder / "render_project")
        rev_spec = video_project.create_revision(
            {
                "project_id": script_id,
                "settings": {"width": 1080, "height": 1920, "fps": 30},
                "scenes": project_scenes,
            }
        )
        rev_id = rev_spec["revision_id"]

        # 5. Render Video Draft
        if on_progress:
            on_progress("Rendering draft video with FFmpeg...", 0.90)
        render_status = video_project.render(rev_id)

        if on_progress:
            on_progress("Production completed!", 1.0)

        export_info = render_status.get("export", {})
        return {
            "script_id": script_id,
            "revision_id": rev_id,
            "status": render_status["state"],
            "plan_path": str(project_folder / "scenes.json"),
            "video_path": export_info.get("path"),
            "total_scenes": plan.total_scenes,
            "estimated_duration": plan.estimated_duration,
        }
