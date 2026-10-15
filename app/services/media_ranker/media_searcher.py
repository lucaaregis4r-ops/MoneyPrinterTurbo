"""Media Searcher: Orchestrates candidate searching and selection for all scenes.

Implements the end-to-end pipeline:
ScenePlan -> Queries -> CandidateBuilder -> Deduplicator -> Technical Filter -> Top Candidates -> Project Manifest.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from app.services import material
from app.services.director.schemas import Scene, ScenePlan
from .candidate_builder import CandidateBuilder
from .deduplicator import MediaDeduplicator
from .schemas import MediaCandidate
from .technical_filter import rank_and_filter_candidates


class MediaSearcher:
    def __init__(
        self,
        candidate_builder: Optional[CandidateBuilder] = None,
        media_cache_dir: str | Path = "storage/media_cache",
    ):
        self.media_cache_dir = Path(media_cache_dir).resolve()
        self.candidate_builder = candidate_builder or CandidateBuilder(
            media_cache_dir=self.media_cache_dir
        )
        self.deduplicator = MediaDeduplicator()

    def search_for_scene(
        self,
        scene: Scene,
        target_duration: float = 4.0,
        candidates_per_scene: int = 5,
    ) -> list[MediaCandidate]:
        """Searches across all queries for a single scene and returns top candidates."""
        all_raw_candidates: list[MediaCandidate] = []

        # Run each query
        for q in scene.queries:
            raw = self.candidate_builder.search_query(
                query=q,
                target_duration=target_duration,
            )
            all_raw_candidates.extend(raw)

        # 1. Deduplicate within scene
        deduped = self.deduplicator.deduplicate_within_scene(all_raw_candidates)

        # 2. Prefer candidates not yet used globally
        fresh = self.deduplicator.filter_globally_unused(deduped)

        # 3. Technical filter and ranking
        ranked = rank_and_filter_candidates(
            candidates=fresh,
            target_duration=target_duration,
            top_k=candidates_per_scene,
        )

        return ranked

    def populate_scene_plan(
        self,
        plan: ScenePlan,
        candidates_per_scene: int = 5,
        download_selected: bool = True,
        save_plan_path: Optional[str | Path] = None,
    ) -> ScenePlan:
        """Enriches all scenes in the plan with media_candidates and a selected_media default."""
        for scene in plan.scenes:
            # Estimate scene duration if start/end exist, else default to 4.0s
            duration = (scene.end - scene.start) if (scene.start is not None and scene.end is not None) else 4.0
            candidates = self.search_for_scene(
                scene=scene,
                target_duration=duration,
                candidates_per_scene=candidates_per_scene,
            )

            # Store candidates in scene
            scene.media_candidates = [c.to_dict() for c in candidates]

            if candidates:
                top_candidate = candidates[0]
                self.deduplicator.mark_used(top_candidate)

                # Download or stage locally if needed
                if download_selected and not top_candidate.local_path:
                    try:
                        # Remote URL download using material service
                        downloaded = material.save_video(
                            video_url=top_candidate.url,
                            save_dir=str(self.media_cache_dir),
                        )
                        top_candidate.local_path = downloaded
                    except Exception:
                        pass

                scene.selected_media = top_candidate.to_dict()

        if save_plan_path:
            p = Path(save_plan_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("w", encoding="utf-8") as f:
                f.write(plan.to_json(indent=2))

        return plan
