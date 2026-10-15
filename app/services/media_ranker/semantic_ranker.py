"""Semantic Media Ranker with multimodal evaluation and configurable weighted scoring.

Implements Section 31:
score = 0.60 * semantic + 0.15 * resolution + 0.10 * orientation + 0.10 * motion + 0.05 * previous_approval
"""

from __future__ import annotations
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from app.config import config
from .schemas import MediaCandidate
from .thumbnailer import Thumbnailer


class SemanticRanker:
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        thumbnailer: Optional[Thumbnailer] = None,
    ):
        # Configurable weights (Section 31)
        self.weights = {
            "semantic": 0.60,
            "resolution": 0.15,
            "orientation": 0.10,
            "motion": 0.10,
            "previous_approval": 0.05,
        }
        if weights:
            self.weights.update(weights)

        self.thumbnailer = thumbnailer or Thumbnailer()

    def evaluate_semantic_fit(
        self,
        candidate: MediaCandidate,
        scene_narration: str,
        scene_intent: str,
    ) -> float:
        """Evaluates semantic similarity between the candidate and the scene narration/intent."""
        if candidate.semantic_score > 0.0:
            return candidate.semantic_score

        # Check keyword overlap between candidate query/tags and narration/intent
        query_words = set(re.findall(r"\w+", candidate.query.lower()))
        intent_words = set(re.findall(r"\w+", f"{scene_narration} {scene_intent}".lower()))

        overlap = query_words.intersection(intent_words)
        base_score = 0.50
        if overlap:
            base_score += min(0.40, len(overlap) * 0.15)

        # Smart library assets start with high semantic baseline
        if candidate.provider == "smart_library":
            base_score = max(base_score, 0.90)

        return min(1.0, max(0.2, round(base_score, 2)))

    def rank_candidates(
        self,
        scene_narration: str,
        scene_intent: str,
        candidates: List[MediaCandidate],
        top_k: int = 3,
    ) -> List[MediaCandidate]:
        """Applies multimodal/semantic scoring and produces the final ranked top_k candidates."""
        for c in candidates:
            # 1. Semantic score
            sem = self.evaluate_semantic_fit(c, scene_narration, scene_intent)
            c.semantic_score = sem

            # 2. Extract thumbnail if local clip exists
            if c.local_path and not c.thumbnail:
                thumb = self.thumbnailer.extract_thumbnail(c.local_path)
                if thumb:
                    c.thumbnail = thumb

            # 3. Component scores
            # Resolution: 1080p -> 1.0, 720p -> 0.7, other -> 0.4
            res_score = 1.0 if (c.height >= 1920 or c.width >= 1080) else (0.7 if c.height >= 1280 else 0.4)

            # Orientation: vertical 9:16 -> 1.0, square -> 0.6, landscape -> 0.3
            ratio = c.width / c.height if c.height > 0 else 0.5625
            if abs(ratio - 0.5625) < 0.05 or ratio < 0.7:
                ori_score = 1.0
            elif abs(ratio - 1.0) < 0.05:
                ori_score = 0.6
            else:
                ori_score = 0.3

            # Motion: default 0.8
            mot_score = 0.8

            # Previous approval: 1.0 for smart_library or approved cache, 0.0 otherwise
            app_score = 1.0 if c.provider in {"smart_library", "local"} else 0.0

            # Composite weighted score
            final = (
                self.weights["semantic"] * sem
                + self.weights["resolution"] * res_score
                + self.weights["orientation"] * ori_score
                + self.weights["motion"] * mot_score
                + self.weights["previous_approval"] * app_score
            )
            c.final_score = round(min(1.0, max(0.0, final)), 3)

        # Sort descending by final composite score
        ranked = sorted(candidates, key=lambda c: c.final_score, reverse=True)
        return ranked[:top_k]
