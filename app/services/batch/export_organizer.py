"""Export organizer: structures completed short videos and metadata by channel and date.
"""

from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional
import unicodedata


def slugify(text: str) -> str:
    """Converts a title into a clean URL/filesystem-safe slug."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", text)


def generate_hashtags(title: str, channel: str) -> List[str]:
    """Generates appropriate hashtags for Shorts, Reels, and TikTok."""
    base_tags = ["#shorts", "#viral", "#fatos"]
    channel_tags = {
        "fisica": ["#fisica", "#ciencia", "#vocesabia", "#educacao", "#curiosidades"],
        "esportes": ["#esportes", "#futebol", "#atleta", "#recorde", "#treino"],
        "historia": ["#historia", "#fatosincriveis", "#curiosidadeshistoricas", "#conhecimento"],
        "curiosidades": ["#curiosidades", "#incrivel", "#interessante", "#fatosdesconhecidos"],
    }

    clean_ch = slugify(channel)
    selected = channel_tags.get(clean_ch, [f"#{clean_ch}"])

    clean_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    words = re.findall(r"\w{4,}", clean_title.lower())
    title_tags = [f"#{w}" for w in words[:3]]

    # Combine unique preserving order
    combined: List[str] = []
    for tag in ["#shorts"] + selected + title_tags + base_tags:
        if tag not in combined:
            combined.append(tag)
    return combined[:8]


class ExportOrganizer:
    """Organizes rendered video files into structured export directories by channel."""

    def __init__(self, exports_dir: Path | str = "storage/exports"):
        self.exports_dir = Path(exports_dir).resolve()
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    def organize_export(
        self,
        video_source_path: Path | str,
        script_id: str,
        title: str,
        channel: str = "default",
        total_scenes: int = 0,
        script_text: str = "",
    ) -> Dict[str, Any]:
        """Copies final video and generates metadata sidecar JSON in the channel export directory."""
        src_path = Path(video_source_path).resolve()
        if not src_path.exists() or src_path.stat().st_size == 0:
            raise FileNotFoundError(f"Source video does not exist or is empty: {src_path}")

        # Destination folder by channel
        channel_slug = slugify(channel or "geral")
        target_dir = self.exports_dir / channel_slug
        target_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d")
        title_slug = slugify(title or script_id)
        base_name = f"{date_str}_{title_slug}"

        # Collision avoidance
        dest_video = target_dir / f"{base_name}.mp4"
        counter = 2
        while dest_video.exists():
            dest_video = target_dir / f"{base_name}_v{counter}.mp4"
            counter += 1

        shutil.copy2(src_path, dest_video)

        # Probe duration and video info
        duration = 0.0
        try:
            probe_cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(dest_video),
            ]
            res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            duration = round(float(res.stdout.strip()), 2)
        except Exception:
            pass

        hashtags = generate_hashtags(title, channel)
        description = f"{title}\n\nAssista até o final! Gostou? Inscreva-se para mais fatos e curiosidades todos os dias.\n\n{' '.join(hashtags)}"

        metadata = {
            "title": title,
            "channel": channel,
            "script_id": script_id,
            "video_file": dest_video.name,
            "video_path": str(dest_video),
            "file_size_bytes": dest_video.stat().st_size,
            "duration_seconds": duration,
            "resolution": "1080x1920",
            "aspect_ratio": "9:16",
            "fps": 30,
            "total_scenes": total_scenes,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "hashtags": hashtags,
            "suggested_description": description,
            "script_excerpt": script_text[:200] if script_text else "",
        }

        dest_meta = dest_video.with_suffix(".json")
        with dest_meta.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        return metadata

    def list_exports(self, channel: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists all exported videos with metadata."""
        exports = []
        pattern = f"{slugify(channel)}/*.json" if channel else "*/*.json"

        for meta_file in sorted(self.exports_dir.glob(pattern), reverse=True):
            try:
                with meta_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Verify MP4 still exists
                    mp4_path = Path(data.get("video_path", meta_file.with_suffix(".mp4")))
                    if mp4_path.exists():
                        data["video_exists"] = True
                        data["metadata_path"] = str(meta_file)
                        exports.append(data)
            except Exception:
                pass
        return exports
