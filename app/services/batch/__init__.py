"""Batch production package for Fábrica de Shorts.

Handles multi-script parsing, persistent SQLite job queues,
asynchronous worker execution, and channel-based video exports.
"""

from .batch_manager import BatchManager, ParsedScriptItem, parse_script_block
from .export_organizer import ExportOrganizer, generate_hashtags, slugify
from .job_queue import BatchJob, JobQueue, JobStatus
from .worker import BatchWorker

__all__ = [
    "BatchJob",
    "BatchManager",
    "BatchWorker",
    "ExportOrganizer",
    "JobQueue",
    "JobStatus",
    "ParsedScriptItem",
    "generate_hashtags",
    "parse_script_block",
    "slugify",
]
