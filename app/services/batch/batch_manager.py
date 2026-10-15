"""Batch Manager: Multi-script parsing, validation, and batch job ingestion.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from .export_organizer import slugify
from .job_queue import BatchJob, JobQueue


@dataclass
class ParsedScriptItem:
    title: str
    script_text: str
    channel: str
    voice_name: Optional[str] = None
    brand_style: Optional[str] = None


def parse_script_block(raw_block: str, default_channel: str = "default", default_voice: Optional[str] = None) -> Optional[ParsedScriptItem]:
    """Parses a single script block extracting title, channel, voice and narration."""
    lines = raw_block.strip().splitlines()
    if not lines:
        return None

    title = "Roteiro Sem Título"
    channel = default_channel
    voice = default_voice
    brand_style = None

    narration_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check for Markdown Header title: # Title
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            continue

        # Check for metadata directives like [channel: ...]
        m_channel = re.match(r"\[channel:\s*([^\]]+)\]", stripped, re.IGNORECASE)
        if m_channel:
            channel = m_channel.group(1).strip()
            continue

        m_voice = re.match(r"\[voice:\s*([^\]]+)\]", stripped, re.IGNORECASE)
        if m_voice:
            voice = m_voice.group(1).strip()
            continue

        m_brand = re.match(r"\[brand:\s*([^\]]+)\]", stripped, re.IGNORECASE)
        if m_brand:
            brand_style = m_brand.group(1).strip()
            continue

        narration_lines.append(line)

    full_narration = "\n".join(narration_lines).strip()
    if len(full_narration) < 20:
        return None

    return ParsedScriptItem(
        title=title,
        script_text=full_narration,
        channel=channel,
        voice_name=voice,
        brand_style=brand_style,
    )


class BatchManager:
    """Manages multi-script ingestion and batch queue operations."""

    def __init__(self, queue: Optional[JobQueue] = None):
        self.queue = queue or JobQueue()

    def parse_multi_script_text(
        self,
        text: str,
        default_channel: str = "default",
        default_voice: Optional[str] = None,
    ) -> List[ParsedScriptItem]:
        """Splits a multi-script document separated by '---' or '===' into discrete script items."""
        raw_blocks = re.split(r"(?m)^\s*(?:---|===)\s*$", text)
        parsed_items: List[ParsedScriptItem] = []

        for block in raw_blocks:
            item = parse_script_block(block, default_channel=default_channel, default_voice=default_voice)
            if item:
                parsed_items.append(item)

        return parsed_items

    def ingest_multi_script_text(
        self,
        text: str,
        default_channel: str = "default",
        default_voice: Optional[str] = None,
        priority: int = 0,
    ) -> List[BatchJob]:
        """Parses multi-script text and enqueues all items into the JobQueue."""
        items = self.parse_multi_script_text(text, default_channel=default_channel, default_voice=default_voice)
        enqueued: List[BatchJob] = []

        for idx, item in enumerate(items):
            script_id = f"batch_{slugify(item.title)}_{idx + 1}"
            job = self.queue.add_job(
                script_id=script_id,
                script_text=item.script_text,
                title=item.title,
                channel=item.channel,
                voice_name=item.voice_name,
                brand_style=item.brand_style,
                priority=priority,
            )
            enqueued.append(job)

        return enqueued

    def ingest_directory(
        self,
        dir_path: Path | str,
        default_channel: str = "default",
        default_voice: Optional[str] = None,
    ) -> List[BatchJob]:
        """Scans a directory for .md and .txt script files and enqueues them."""
        folder = Path(dir_path).resolve()
        if not folder.exists() or not folder.is_dir():
            raise NotADirectoryError(f"Directory not found: {folder}")

        enqueued: List[BatchJob] = []
        files = sorted(list(folder.glob("*.md")) + list(folder.glob("*.txt")))

        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8")
                # Parse whether it is a single script or multi-script file
                items = self.parse_multi_script_text(content, default_channel=default_channel, default_voice=default_voice)
                if not items:
                    # Treat entire file as single script with file stem as title
                    items = [
                        ParsedScriptItem(
                            title=file_path.stem.replace("_", " ").title(),
                            script_text=content.strip(),
                            channel=default_channel,
                            voice_name=default_voice,
                        )
                    ]

                for idx, item in enumerate(items):
                    script_id = f"{file_path.stem}_{idx + 1}"
                    job = self.queue.add_job(
                        script_id=script_id,
                        script_text=item.script_text,
                        title=item.title,
                        channel=item.channel,
                        voice_name=item.voice_name,
                        brand_style=item.brand_style,
                    )
                    enqueued.append(job)
            except Exception:
                pass

        return enqueued
