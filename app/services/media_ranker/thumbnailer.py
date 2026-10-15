"""Thumbnail generator for video candidates.

Uses FFmpeg fast seeking to extract clean visual snapshots from candidate video clips.
"""

from __future__ import annotations
import hashlib
from pathlib import Path
import subprocess
from typing import Optional


class Thumbnailer:
    def __init__(self, thumbnail_dir: str | Path = "storage/thumbnails"):
        self.thumbnail_dir = Path(thumbnail_dir).resolve()
        self.thumbnail_dir.mkdir(parents=True, exist_ok=True)

    def extract_thumbnail(
        self,
        video_path: str | Path,
        timestamp_sec: float = 1.0,
        width: int = 540,
        height: int = 960,
    ) -> Optional[str]:
        """Extracts a single frame from video at timestamp_sec and saves it as JPEG."""
        video_file = Path(video_path).resolve()
        if not video_file.exists():
            return None

        # Hash video path + timestamp for caching
        token = f"{video_file}_{timestamp_sec}_{width}x{height}"
        slug = hashlib.md5(token.encode("utf-8")).hexdigest()
        thumb_path = self.thumbnail_dir / f"thumb_{slug}.jpg"

        if thumb_path.exists() and thumb_path.stat().st_size > 0:
            return str(thumb_path)

        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", str(timestamp_sec),
            "-i", str(video_file),
            "-vframes", "1",
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
            "-q:v", "2",
            str(thumb_path),
        ]

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if thumb_path.exists() and thumb_path.stat().st_size > 0:
                return str(thumb_path)
        except Exception:
            pass

        return None
