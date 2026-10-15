"""Background Batch Worker consuming the JobQueue and rendering videos via ShortsFactory.
"""

from __future__ import annotations
import logging
from pathlib import Path
import threading
import time
import traceback
from typing import Callable, Optional

from app.services.factory import ShortsFactory
from .export_organizer import ExportOrganizer
from .job_queue import BatchJob, JobQueue, JobStatus

logger = logging.getLogger(__name__)


class BatchWorker:
    """Asynchronous worker that pulls and processes video jobs from JobQueue."""

    def __init__(
        self,
        queue: Optional[JobQueue] = None,
        factory: Optional[ShortsFactory] = None,
        organizer: Optional[ExportOrganizer] = None,
        poll_interval: float = 2.0,
    ):
        self.queue = queue or JobQueue()
        self.factory = factory or ShortsFactory()
        self.organizer = organizer or ExportOrganizer()
        self.poll_interval = poll_interval

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._current_job_id: Optional[str] = None

    def is_running(self) -> bool:
        """Returns True if background worker thread is active."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Starts the background worker thread."""
        if self.is_running():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="BatchWorkerThread", daemon=True)
        self._thread.start()
        logger.info("BatchWorker thread started.")

    def stop(self, timeout: float = 5.0) -> None:
        """Signals the background worker to stop and waits for it."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        logger.info("BatchWorker thread stopped.")

    def _run_loop(self) -> None:
        """Worker loop continuously polling for jobs."""
        while not self._stop_event.is_set():
            try:
                processed = self.process_one()
                if not processed:
                    time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Unexpected error in BatchWorker loop: {e}", exc_info=True)
                time.sleep(self.poll_interval)

    def process_one(self) -> Optional[BatchJob]:
        """Pulls and executes one pending job from the queue synchronously.

        Returns the processed BatchJob, or None if the queue was empty.
        """
        job = self.queue.get_next_pending_job()
        if not job:
            return None

        self._current_job_id = job.job_id
        logger.info(f"BatchWorker starting job {job.job_id} ({job.title})...")

        try:
            # Setup live progress callback forwarding to queue
            def on_progress(msg: str, pct: float) -> None:
                self.queue.update_job_progress(job.job_id, progress=pct, message=msg)

            # Produce draft through ShortsFactory
            result = self.factory.produce_draft(
                script_id=job.script_id,
                script_text=job.script_text,
                title=job.title,
                channel=job.channel,
                voice_name=job.voice_name,
                brand_style=job.brand_style,
                on_progress=on_progress,
            )

            if result.get("status") != "succeeded":
                raise RuntimeError(f"Pipeline failed: {result.get('error', 'Unknown error')}")

            raw_video_path = result["video_path"]
            total_scenes = result.get("total_scenes", 0)

            # Organize into channel export directory
            export_meta = self.organizer.organize_export(
                video_source_path=raw_video_path,
                script_id=job.script_id,
                title=job.title,
                channel=job.channel,
                total_scenes=total_scenes,
                script_text=job.script_text,
            )

            # Mark completed in queue
            self.queue.mark_completed(
                job_id=job.job_id,
                video_path=raw_video_path,
                exported_path=export_meta["video_path"],
                total_scenes=total_scenes,
            )
            logger.info(f"Job {job.job_id} completed successfully! Exported to: {export_meta['video_path']}")
            return self.queue.get_job(job.job_id)

        except Exception as err:
            err_msg = f"{type(err).__name__}: {str(err)}\n{traceback.format_exc()}"
            logger.error(f"Job {job.job_id} failed: {err_msg}")
            self.queue.mark_failed(job.job_id, error_message=err_msg)
            return self.queue.get_job(job.job_id)
        finally:
            self._current_job_id = None
