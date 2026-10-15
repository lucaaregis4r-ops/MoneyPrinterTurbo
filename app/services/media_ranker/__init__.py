"""Media Ranker package for Fábrica de Shorts.
Searches, deduplicates, filters and ranks media candidates for video scenes.
"""

from .candidate_builder import CandidateBuilder
from .deduplicator import MediaDeduplicator
from .media_searcher import MediaSearcher
from .schemas import MediaCandidate
from .semantic_ranker import SemanticRanker
from .smart_library import LibraryAsset, SmartLibrary
from .technical_filter import rank_and_filter_candidates, score_technical_candidate
from .thumbnailer import Thumbnailer

__all__ = [
    "CandidateBuilder",
    "MediaDeduplicator",
    "MediaSearcher",
    "MediaCandidate",
    "SemanticRanker",
    "SmartLibrary",
    "LibraryAsset",
    "Thumbnailer",
    "rank_and_filter_candidates",
    "score_technical_candidate",
]
