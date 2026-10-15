"""Persistent SQLite Job Queue for batch short video production.
"""

from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, List, Optional
import uuid


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchJob:
    job_id: str
    script_id: str
    title: str
    channel: str
    script_text: str
    voice_name: Optional[str] = None
    brand_style: Optional[str] = None
    status: str = JobStatus.PENDING.value
    progress: float = 0.0
    progress_message: str = "Aguardando na fila"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    video_path: Optional[str] = None
    exported_path: Optional[str] = None
    error_message: Optional[str] = None
    total_scenes: int = 0
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> BatchJob:
        return cls(
            job_id=row["job_id"],
            script_id=row["script_id"],
            title=row["title"],
            channel=row["channel"],
            script_text=row["script_text"],
            voice_name=row["voice_name"],
            brand_style=row["brand_style"],
            status=row["status"],
            progress=float(row["progress"]),
            progress_message=row["progress_message"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            video_path=row["video_path"],
            exported_path=row["exported_path"],
            error_message=row["error_message"],
            total_scenes=int(row["total_scenes"]),
            priority=int(row["priority"]),
        )


class JobQueue:
    """Thread-safe SQLite persistent job queue."""

    def __init__(self, db_path: Path | str = "storage/batch/jobs.db"):
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS batch_jobs (
                    job_id TEXT PRIMARY KEY,
                    script_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    script_text TEXT NOT NULL,
                    voice_name TEXT,
                    brand_style TEXT,
                    status TEXT NOT NULL,
                    progress REAL DEFAULT 0.0,
                    progress_message TEXT DEFAULT 'Aguardando na fila',
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    video_path TEXT,
                    exported_path TEXT,
                    error_message TEXT,
                    total_scenes INTEGER DEFAULT 0,
                    priority INTEGER DEFAULT 0
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON batch_jobs(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON batch_jobs(created_at);")
            conn.commit()

    def add_job(
        self,
        script_id: str,
        script_text: str,
        title: str,
        channel: str = "default",
        voice_name: Optional[str] = None,
        brand_style: Optional[str] = None,
        priority: int = 0,
    ) -> BatchJob:
        """Enqueues a new video rendering job."""
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        job = BatchJob(
            job_id=job_id,
            script_id=script_id,
            title=title,
            channel=channel,
            script_text=script_text,
            voice_name=voice_name,
            brand_style=brand_style,
            status=JobStatus.PENDING.value,
            progress=0.0,
            progress_message="Aguardando na fila de produção",
            created_at=now,
            priority=priority,
        )

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO batch_jobs (
                    job_id, script_id, title, channel, script_text, voice_name,
                    brand_style, status, progress, progress_message, created_at, priority
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id,
                    job.script_id,
                    job.title,
                    job.channel,
                    job.script_text,
                    job.voice_name,
                    job.brand_style,
                    job.status,
                    job.progress,
                    job.progress_message,
                    job.created_at,
                    job.priority,
                ),
            )
            conn.commit()
        return job

    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Retrieves a single job by its ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM batch_jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if row:
                return BatchJob.from_row(row)
        return None

    def list_jobs(
        self,
        status: Optional[str | JobStatus] = None,
        channel: Optional[str] = None,
        limit: int = 100,
    ) -> List[BatchJob]:
        """Lists jobs with optional filtering."""
        query = "SELECT * FROM batch_jobs WHERE 1=1"
        params: List[Any] = []

        if status:
            val = status.value if isinstance(status, JobStatus) else str(status)
            query += " AND status = ?"
            params.append(val)

        if channel:
            query += " AND channel = ?"
            params.append(channel)

        query += " ORDER BY priority DESC, created_at ASC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [BatchJob.from_row(row) for row in cursor.fetchall()]

    def get_next_pending_job(self) -> Optional[BatchJob]:
        """Atomically grabs the next pending job and marks it as PROCESSING."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM batch_jobs
                WHERE status = ?
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
                """,
                (JobStatus.PENDING.value,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            job_id = row["job_id"]
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                UPDATE batch_jobs
                SET status = ?, started_at = ?, progress = 0.05, progress_message = 'Iniciando pipeline...'
                WHERE job_id = ?
                """,
                (JobStatus.PROCESSING.value, now, job_id),
            )
            conn.commit()

            cursor = conn.execute("SELECT * FROM batch_jobs WHERE job_id = ?", (job_id,))
            updated_row = cursor.fetchone()
            return BatchJob.from_row(updated_row) if updated_row else None

    def update_job_progress(
        self,
        job_id: str,
        progress: float,
        message: str,
        total_scenes: Optional[int] = None,
    ) -> None:
        """Updates live job progress and message."""
        with self._lock, self._get_connection() as conn:
            if total_scenes is not None:
                conn.execute(
                    """
                    UPDATE batch_jobs
                    SET progress = ?, progress_message = ?, total_scenes = ?
                    WHERE job_id = ?
                    """,
                    (progress, message, total_scenes, job_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE batch_jobs
                    SET progress = ?, progress_message = ?
                    WHERE job_id = ?
                    """,
                    (progress, message, job_id),
                )
            conn.commit()

    def mark_completed(
        self,
        job_id: str,
        video_path: str,
        exported_path: Optional[str] = None,
        total_scenes: Optional[int] = None,
    ) -> None:
        """Marks a job as completed."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                UPDATE batch_jobs
                SET status = ?, progress = 1.0, progress_message = 'Vídeo concluído com sucesso!',
                    completed_at = ?, video_path = ?, exported_path = ?,
                    total_scenes = COALESCE(?, total_scenes)
                WHERE job_id = ?
                """,
                (JobStatus.COMPLETED.value, now, video_path, exported_path, total_scenes, job_id),
            )
            conn.commit()

    def mark_failed(self, job_id: str, error_message: str) -> None:
        """Marks a job as failed with error trace."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                UPDATE batch_jobs
                SET status = ?, progress_message = 'Falha na produção',
                    completed_at = ?, error_message = ?
                WHERE job_id = ?
                """,
                (JobStatus.FAILED.value, now, error_message, job_id),
            )
            conn.commit()

    def retry_job(self, job_id: str) -> bool:
        """Resets a failed or cancelled job back to PENDING."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE batch_jobs
                SET status = ?, progress = 0.0, progress_message = 'Reenfileirado para produção',
                    started_at = NULL, completed_at = NULL, error_message = NULL
                WHERE job_id = ? AND status IN (?, ?)
                """,
                (JobStatus.PENDING.value, job_id, JobStatus.FAILED.value, JobStatus.CANCELLED.value),
            )
            conn.commit()
            return cursor.rowcount > 0

    def cancel_job(self, job_id: str) -> bool:
        """Cancels a pending or processing job."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE batch_jobs
                SET status = ?, progress_message = 'Cancelado pelo usuário', completed_at = ?
                WHERE job_id = ? AND status IN (?, ?)
                """,
                (JobStatus.CANCELLED.value, now, job_id, JobStatus.PENDING.value, JobStatus.PROCESSING.value),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_job(self, job_id: str) -> bool:
        """Deletes a job from the queue."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM batch_jobs WHERE job_id = ?", (job_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_queue_stats(self) -> Dict[str, int]:
        """Returns counts by status."""
        stats = {
            "total": 0,
            JobStatus.PENDING.value: 0,
            JobStatus.PROCESSING.value: 0,
            JobStatus.COMPLETED.value: 0,
            JobStatus.FAILED.value: 0,
            JobStatus.CANCELLED.value: 0,
        }
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT status, COUNT(*) as cnt FROM batch_jobs GROUP BY status")
            for row in cursor.fetchall():
                st = row["status"]
                cnt = row["cnt"]
                stats["total"] += cnt
                if st in stats:
                    stats[st] = cnt
        return stats
