"""Package Exporter: Bundles video, thumbnail, script and metadata into ready-to-publish ZIP archives.
"""

from __future__ import annotations
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, List, Optional
import zipfile

from app.services.batch.export_organizer import slugify
from .metadata_generator import MetadataGenerator


class PackageExporter:
    """Exports structured publication packages with thumbnails, scripts, and ZIP bundles."""

    def __init__(
        self,
        packages_dir: Path | str = "storage/exports/packages",
        meta_generator: Optional[MetadataGenerator] = None,
    ):
        self.packages_dir = Path(packages_dir).resolve()
        self.packages_dir.mkdir(parents=True, exist_ok=True)
        self.meta_generator = meta_generator or MetadataGenerator()

    def create_publication_package(
        self,
        video_path: Path | str,
        title: str,
        channel: str,
        script_text: str,
        scenes: Optional[List[Dict[str, Any]]] = None,
        duration: Optional[float] = None,
        thumbnail_source: Optional[Path | str] = None,
    ) -> Dict[str, Any]:
        """Creates a complete publication folder and ZIP bundle."""
        v_file = Path(video_path).resolve()
        if not v_file.exists():
            raise FileNotFoundError(f"Video file not found: {v_file}")

        # Probe duration if missing
        vid_duration = duration
        if vid_duration is None:
            try:
                probe_cmd = [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(v_file),
                ]
                res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
                vid_duration = float(res.stdout.strip())
            except Exception:
                vid_duration = 30.0

        # Create package folder
        date_str = datetime.now().strftime("%Y-%m-%d")
        title_slug = slugify(title)
        package_name = f"{date_str}_{slugify(channel)}_{title_slug}"
        bundle_dir = self.packages_dir / slugify(channel) / package_name
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # 1. Copy Video
        dest_video = bundle_dir / "video_9_16.mp4"
        shutil.copy2(v_file, dest_video)

        # 2. Extract or Copy Thumbnail
        dest_thumb = bundle_dir / "thumbnail.jpg"
        if thumbnail_source and Path(thumbnail_source).exists():
            shutil.copy2(thumbnail_source, dest_thumb)
        else:
            # Extract crisp frame at 1.0s or midway
            thumb_ss = max(0.5, vid_duration * 0.2)
            cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{thumb_ss:.2f}",
                "-i", str(v_file),
                "-vframes", "1",
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                "-q:v", "2",
                str(dest_thumb),
            ]
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                # Fallback to simple touch if ffmpeg frame grab fails
                dest_thumb.write_text("thumbnail_placeholder", encoding="utf-8")

        # 3. Generate Metadata
        pub_meta = self.meta_generator.generate_metadata(
            title=title,
            channel=channel,
            duration=vid_duration,
            scenes=scenes,
            script_text=script_text,
        )

        dest_meta = bundle_dir / "metadata.json"
        with dest_meta.open("w", encoding="utf-8") as f:
            json.dump(pub_meta.to_dict(), f, indent=2, ensure_ascii=False)

        # 4. Generate Quick Upload Guide
        dest_guide = bundle_dir / "upload_ready.txt"
        guide_content = (
            f"=== PACOTE DE PUBLICAÇÃO: {title} ===\n\n"
            f"TÍTULO PRINCIPAL:\n{pub_meta.primary_title}\n\n"
            f"OPÇÕES DE TÍTULO PARA TESTE A/B:\n"
            + "\n".join(f"- {t}" for t in pub_meta.ab_titles)
            + f"\n\nTAGS SUGERIDAS:\n{' '.join(pub_meta.hashtags)}\n\n"
            f"DESCRIÇÃO PRONTA (COPIAR E COLAR):\n{pub_meta.description}\n"
        )
        dest_guide.write_text(guide_content, encoding="utf-8")

        # 5. Save Approved Human Script
        dest_script = bundle_dir / "script_locked.md"
        dest_script.write_text(
            f"# {title}\nCanal: {channel}\n\n{script_text.strip()}\n",
            encoding="utf-8",
        )

        # 6. Create ZIP bundle
        zip_path = bundle_dir.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(dest_video, arcname="video_9_16.mp4")
            zf.write(dest_thumb, arcname="thumbnail.jpg")
            zf.write(dest_meta, arcname="metadata.json")
            zf.write(dest_guide, arcname="upload_ready.txt")
            zf.write(dest_script, arcname="script_locked.md")

        return {
            "package_name": package_name,
            "bundle_dir": str(bundle_dir),
            "zip_path": str(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "video_path": str(dest_video),
            "thumbnail_path": str(dest_thumb),
            "metadata_path": str(dest_meta),
            "guide_path": str(dest_guide),
            "script_path": str(dest_script),
            "compliance": pub_meta.compliance,
        }
