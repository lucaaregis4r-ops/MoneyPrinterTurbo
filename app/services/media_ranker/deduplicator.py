"""Candidate deduplication and diversity manager.

Ensures no scene receives duplicate URLs or asset IDs, and avoids reusing the
same footage in multiple scenes within the same video production.
"""

from __future__ import annotations
from typing import Iterable, List, Set

from .schemas import MediaCandidate


class MediaDeduplicator:
    def __init__(self):
        self._global_seen_assets: Set[str] = set()

    def deduplicate_within_scene(
        self, candidates: Iterable[MediaCandidate]
    ) -> List[MediaCandidate]:
        """Removes duplicates based on url, asset_id, or local_path within a single query/scene."""
        seen_keys = set()
        unique: List[MediaCandidate] = []

        for c in candidates:
            key = c.asset_id or c.url or c.local_path or ""
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            unique.append(c)

        return unique

    def filter_globally_unused(
        self, candidates: List[MediaCandidate]
    ) -> List[MediaCandidate]:
        """Separates candidates that haven't been picked by other scenes yet."""
        fresh = [c for c in candidates if (c.asset_id or c.url) not in self._global_seen_assets]
        return fresh if fresh else candidates

    def mark_used(self, candidate: MediaCandidate) -> None:
        key = candidate.asset_id or candidate.url
        if key:
            self._global_seen_assets.add(key)
