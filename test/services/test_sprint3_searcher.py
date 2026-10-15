"""Sprint 3 Automated Tests: Media Searcher & Candidate Collector.

Validates:
1. CandidateBuilder, MediaDeduplicator and Technical Filter.
2. MediaSearcher populating ScenePlan with top candidates and selected media.
3. ShortsFactory end-to-end prototype:
   ROTEIRO HUMANO -> SCENE DIRECTOR -> MEDIA SEARCHER -> VOICE ENGINE -> VIDEO DRAFT.
"""

import json
from pathlib import Path
import subprocess
import pytest

from app.services.director.schemas import Scene, ScenePlan
from app.services.factory import ShortsFactory
from app.services.media_ranker import (
    CandidateBuilder,
    MediaCandidate,
    MediaDeduplicator,
    MediaSearcher,
    rank_and_filter_candidates,
    score_technical_candidate,
)


def test_technical_filter_scoring():
    portrait = MediaCandidate(
        provider="test",
        asset_id="p1",
        query="cart",
        width=1080,
        height=1920,
        duration=6.0,
        url="http://example.com/p1.mp4",
    )
    landscape = MediaCandidate(
        provider="test",
        asset_id="l1",
        query="cart",
        width=1920,
        height=1080,
        duration=6.0,
        url="http://example.com/l1.mp4",
    )
    p_score = score_technical_candidate(portrait, target_duration=4.0)
    l_score = score_technical_candidate(landscape, target_duration=4.0)

    # Portrait 9:16 must score significantly higher than landscape
    assert p_score > l_score
    assert p_score >= 0.90


def test_deduplicator():
    dedup = MediaDeduplicator()
    c1 = MediaCandidate(provider="test", asset_id="101", query="q", width=1080, height=1920, duration=5.0, url="u1")
    c2 = MediaCandidate(provider="test", asset_id="101", query="q", width=1080, height=1920, duration=5.0, url="u1")
    c3 = MediaCandidate(provider="test", asset_id="102", query="q", width=1080, height=1920, duration=5.0, url="u2")

    unique = dedup.deduplicate_within_scene([c1, c2, c3])
    assert len(unique) == 2
    assert {c.asset_id for c in unique} == {"101", "102"}

    dedup.mark_used(c1)
    fresh = dedup.filter_globally_unused([c1, c3])
    assert len(fresh) == 1
    assert fresh[0].asset_id == "102"


def test_media_searcher_populates_plan(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    searcher = MediaSearcher(media_cache_dir=cache_dir)

    plan = ScenePlan(
        script_id="test_plan",
        script_version="script_v001",
        script_hash="hash123",
        total_scenes=2,
        estimated_duration=8.0,
        scenes=[
            Scene(
                scene_id="scene_001",
                narration="Cena 1 sobre física.",
                intent="mostrar física",
                queries=["physics lab experiment", "physics science"],
                visual_type="stock_video",
            ),
            Scene(
                scene_id="scene_002",
                narration="Cena 2 sobre corrida.",
                intent="mostrar corrida",
                queries=["sprinter running track", "athlete sprint"],
                visual_type="stock_video",
            ),
        ],
    )

    enriched_plan = searcher.populate_scene_plan(
        plan=plan,
        candidates_per_scene=3,
        save_plan_path=tmp_path / "scenes.json",
    )

    for sc in enriched_plan.scenes:
        assert len(sc.media_candidates) >= 1
        assert sc.selected_media is not None
        assert sc.selected_media.get("local_path") is not None
        assert Path(sc.selected_media["local_path"]).exists()

    assert (tmp_path / "scenes.json").exists()


def test_shorts_factory_full_prototype_e2e(tmp_path: Path):
    """End-to-end integration test of the complete Shorts Factory prototype (Sprint 3)."""
    factory = ShortsFactory(base_dir=tmp_path / "factory")

    test_script = (
        "Você provavelmente aprendeu que força é massa vezes aceleração. "
        "Mas empurrar um carrinho cheio é outra história."
    )

    result = factory.produce_draft(
        script_id="sprint3_prototype_demo",
        script_text=test_script,
        title="Protótipo Sprint 3",
        channel="fisica",
    )

    assert result["status"] == "succeeded"
    assert result["total_scenes"] >= 2
    video_path = Path(result["video_path"])
    assert video_path.exists() and video_path.stat().st_size > 0

    # Probe final output resolution and frame rate
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate",
        "-of", "json",
        str(video_path),
    ]
    probe_out = subprocess.check_output(probe_cmd).decode()
    v_stream = json.loads(probe_out)["streams"][0]
    assert v_stream["width"] == 1080
    assert v_stream["height"] == 1920

    # Validate that scenes.json was created and has media candidates
    plan_path = Path(result["plan_path"])
    assert plan_path.exists()
    with plan_path.open("r", encoding="utf-8") as f:
        plan_data = json.load(f)

    assert len(plan_data["scenes"]) == result["total_scenes"]
    for sc in plan_data["scenes"]:
        assert len(sc["media_candidates"]) > 0
        assert sc["selected_media"] is not None
