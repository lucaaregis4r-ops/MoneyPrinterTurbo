"""Sprint 8 Test Suite: Batch Production, Persistent Queue and Channel Export Organizer.
"""

from pathlib import Path
import subprocess
import pytest

from app.services.batch.batch_manager import BatchManager, parse_script_block
from app.services.batch.export_organizer import ExportOrganizer, generate_hashtags, slugify
from app.services.batch.job_queue import BatchJob, JobQueue, JobStatus
from app.services.batch.worker import BatchWorker
from app.services.factory import ShortsFactory
from app.services.media_ranker.candidate_builder import _generate_synthetic_clip


@pytest.fixture
def tmp_batch_dir(tmp_path: Path) -> Path:
    bdir = tmp_path / "batch_test"
    bdir.mkdir(parents=True, exist_ok=True)
    return bdir


def test_slugify_and_hashtags():
    assert slugify("A Lei da Inércia!") == "a_lei_da_inercia"
    assert slugify("Usain Bolt: 44 km/h") == "usain_bolt_44_kmh"

    tags = generate_hashtags("A Lei da Inércia", "fisica")
    assert "#shorts" in tags
    assert "#fisica" in tags
    assert any("inercia" in t for t in tags)


def test_job_queue_crud_and_lifecycle(tmp_batch_dir: Path):
    db_file = tmp_batch_dir / "test_jobs.db"
    queue = JobQueue(db_path=db_file)

    # 1. Add jobs
    j1 = queue.add_job(
        script_id="s1",
        script_text="Texto do roteiro 1 com detalhes suficientes para produção.",
        title="Roteiro 1",
        channel="fisica",
        priority=0,
    )
    j2 = queue.add_job(
        script_id="s2",
        script_text="Texto do roteiro 2 com detalhes suficientes para produção.",
        title="Roteiro 2 (Prioritário)",
        channel="esportes",
        priority=10,
    )

    stats = queue.get_queue_stats()
    assert stats["total"] == 2
    assert stats["pending"] == 2

    # 2. Priority check: j2 must be popped first
    next_job = queue.get_next_pending_job()
    assert next_job is not None
    assert next_job.job_id == j2.job_id
    assert next_job.status == JobStatus.PROCESSING.value

    # 3. Update progress
    queue.update_job_progress(next_job.job_id, progress=0.5, message="Sintetizando áudio...", total_scenes=3)
    updated = queue.get_job(next_job.job_id)
    assert updated.progress == 0.5
    assert updated.total_scenes == 3

    # 4. Mark completed
    queue.mark_completed(
        job_id=next_job.job_id,
        video_path="/tmp/video.mp4",
        exported_path="/tmp/exported.mp4",
        total_scenes=3,
    )
    comp_job = queue.get_job(next_job.job_id)
    assert comp_job.status == JobStatus.COMPLETED.value
    assert comp_job.progress == 1.0

    # 5. Fail remaining job and retry
    j1_proc = queue.get_next_pending_job()
    assert j1_proc.job_id == j1.job_id
    queue.mark_failed(j1_proc.job_id, error_message="Simulated error")
    failed_job = queue.get_job(j1_proc.job_id)
    assert failed_job.status == JobStatus.FAILED.value

    assert queue.retry_job(j1_proc.job_id) is True
    retried_job = queue.get_job(j1_proc.job_id)
    assert retried_job.status == JobStatus.PENDING.value

    # 6. Cancel and Delete
    assert queue.cancel_job(j1_proc.job_id) is True
    assert queue.get_job(j1_proc.job_id).status == JobStatus.CANCELLED.value
    assert queue.delete_job(j1_proc.job_id) is True
    assert queue.get_job(j1_proc.job_id) is None


def test_batch_manager_parsing():
    raw_doc = (
        "# Primeiro Roteiro de Teste\n"
        "[channel: fisica]\n"
        "[voice: pt-BR-AntonioNeural]\n"
        "Este é o primeiro roteiro explicativo sobre mecânica clássica e inércia.\n"
        "---\n"
        "# Segundo Roteiro de Esportes\n"
        "[channel: esportes]\n"
        "Este é o segundo roteiro sobre as maiores corridas da história olímpica.\n"
    )

    manager = BatchManager()
    items = manager.parse_multi_script_text(raw_doc)
    assert len(items) == 2

    assert items[0].title == "Primeiro Roteiro de Teste"
    assert items[0].channel == "fisica"
    assert items[0].voice_name == "pt-BR-AntonioNeural"
    assert "mecânica clássica" in items[0].script_text

    assert items[1].title == "Segundo Roteiro de Esportes"
    assert items[1].channel == "esportes"
    assert "maiores corridas" in items[1].script_text


def test_batch_manager_directory_ingest(tmp_batch_dir: Path):
    scripts_folder = tmp_batch_dir / "scripts"
    scripts_folder.mkdir(parents=True, exist_ok=True)

    (scripts_folder / "script1.md").write_text(
        "# Roteiro do Arquivo 1\n[channel: historia]\nHistória fascinante sobre civilizações antigas e monumentos mundiais.",
        encoding="utf-8",
    )
    (scripts_folder / "script2.txt").write_text(
        "# Roteiro do Arquivo 2\n[channel: ciencia]\nCiência moderna revelando os mistérios das partículas subatômicas.",
        encoding="utf-8",
    )

    db_path = tmp_batch_dir / "dir_jobs.db"
    queue = JobQueue(db_path=db_path)
    manager = BatchManager(queue=queue)

    enqueued = manager.ingest_directory(scripts_folder)
    assert len(enqueued) == 2
    assert queue.get_queue_stats()["total"] == 2


def test_export_organizer(tmp_batch_dir: Path):
    # 1. Create dummy input video
    src_video = tmp_batch_dir / "raw_video.mp4"
    _generate_synthetic_clip("teste export", src_video, duration=2.0)
    assert src_video.exists()

    exports_folder = tmp_batch_dir / "exports"
    organizer = ExportOrganizer(exports_dir=exports_folder)

    meta = organizer.organize_export(
        video_source_path=src_video,
        script_id="fisica_001",
        title="A Lei Fundamental de Newton",
        channel="fisica",
        total_scenes=2,
        script_text="A força resultante é massa vezes aceleração.",
    )

    assert meta["channel"] == "fisica"
    assert Path(meta["video_path"]).exists()
    assert Path(meta["video_path"]).suffix == ".mp4"

    meta_file = Path(meta["video_path"]).with_suffix(".json")
    assert meta_file.exists()

    # List exports check
    all_exports = organizer.list_exports(channel="fisica")
    assert len(all_exports) == 1
    assert all_exports[0]["title"] == "A Lei Fundamental de Newton"


def test_batch_worker_process_one(tmp_batch_dir: Path):
    db_path = tmp_batch_dir / "worker_jobs.db"
    queue = JobQueue(db_path=db_path)

    base_factory_dir = tmp_batch_dir / "factory"
    factory = ShortsFactory(base_dir=base_factory_dir)
    organizer = ExportOrganizer(exports_dir=tmp_batch_dir / "exports")

    worker = BatchWorker(queue=queue, factory=factory, organizer=organizer)

    # Enqueue a valid script
    test_script = (
        "Você provavelmente aprendeu que força é massa vezes aceleração. "
        "Mas empurrar um carrinho cheio é outra história."
    )
    job = queue.add_job(
        script_id="batch_worker_demo",
        script_text=test_script,
        title="Demo do Batch Worker",
        channel="fisica",
    )

    assert queue.get_queue_stats()["pending"] == 1

    # Process one job
    finished_job = worker.process_one()
    assert finished_job is not None
    assert finished_job.status == JobStatus.COMPLETED.value
    assert finished_job.progress == 1.0
    assert finished_job.exported_path is not None
    assert Path(finished_job.exported_path).exists()


def test_batch_worker_handles_failure(tmp_batch_dir: Path):
    db_path = tmp_batch_dir / "failure_jobs.db"
    queue = JobQueue(db_path=db_path)

    # Invalid factory pointing to unwriteable location or throwing
    worker = BatchWorker(queue=queue, factory=None)

    # Empty script that fails validation in factory
    job = queue.add_job(
        script_id="fail_demo",
        script_text="",
        title="Roteiro Vazio",
        channel="fisica",
    )

    failed_job = worker.process_one()
    assert failed_job is not None
    assert failed_job.status == JobStatus.FAILED.value
    assert failed_job.error_message is not None
