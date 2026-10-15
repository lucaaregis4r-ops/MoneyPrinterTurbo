"""Sprint 9 Test Suite: Export Studio, Publisher Package Bundler & Final 1.0 Release.
"""

from pathlib import Path
import zipfile
import pytest

from app.services.media_ranker.candidate_builder import _generate_synthetic_clip
from app.services.publisher.metadata_generator import MetadataGenerator, generate_ab_titles
from app.services.publisher.package_exporter import PackageExporter


@pytest.fixture
def tmp_publish_dir(tmp_path: Path) -> Path:
    pdir = tmp_path / "publisher_test"
    pdir.mkdir(parents=True, exist_ok=True)
    return pdir


def test_metadata_generator():
    generator = MetadataGenerator()

    scenes = [
        {"intent": "Introdução da Força", "duration": 3.0},
        {"intent": "A Fórmula Fundamental", "duration": 4.5},
        {"intent": "Exemplo do Carrinho", "duration": 5.0},
    ]

    meta = generator.generate_metadata(
        title="Por que a Força Depende da Massa?",
        channel="fisica",
        duration=12.5,
        scenes=scenes,
        script_text="Texto completo do roteiro aprovado.",
    )

    assert meta.primary_title == "Por que a Força Depende da Massa?"
    assert len(meta.ab_titles) == 3
    assert any("A Física Explica:" in t for t in meta.ab_titles)

    # Chapters check
    assert len(meta.timestamps) == 3
    assert meta.timestamps[0]["time"] == "00:00"
    assert meta.timestamps[1]["time"] == "00:03"
    assert meta.timestamps[2]["time"] == "00:07"

    # Compliance check
    assert meta.compliance["aspect_ratio_valid"] is True
    assert meta.compliance["resolution"] == "1080x1920"
    assert meta.compliance["duration_valid_for_shorts"] is True

    # Hashtags check
    assert "#shorts" in meta.hashtags
    assert "#fisica" in meta.hashtags


def test_package_exporter_zip_bundle(tmp_publish_dir: Path):
    # 1. Create a synthetic test video
    src_video = tmp_publish_dir / "test_render.mp4"
    _generate_synthetic_clip("teste publish bundle", src_video, duration=2.0)
    assert src_video.exists()

    exporter = PackageExporter(packages_dir=tmp_publish_dir / "packages")

    scenes = [
        {"intent": "Cena 1", "duration": 2.0},
    ]

    result = exporter.create_publication_package(
        video_path=src_video,
        title="O Segredo da Velocidade de Usain Bolt",
        channel="esportes",
        script_text="Usain Bolt atingiu 44 km/h na final dos 100m rasos.",
        scenes=scenes,
        duration=2.0,
    )

    # Verify return paths
    zip_path = Path(result["zip_path"])
    assert zip_path.exists()
    assert zip_path.stat().st_size > 500

    bundle_dir = Path(result["bundle_dir"])
    assert (bundle_dir / "video_9_16.mp4").exists()
    assert (bundle_dir / "thumbnail.jpg").exists()
    assert (bundle_dir / "metadata.json").exists()
    assert (bundle_dir / "upload_ready.txt").exists()
    assert (bundle_dir / "script_locked.md").exists()

    # Open and verify ZIP contents
    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        assert "video_9_16.mp4" in namelist
        assert "thumbnail.jpg" in namelist
        assert "metadata.json" in namelist
        assert "upload_ready.txt" in namelist
        assert "script_locked.md" in namelist
