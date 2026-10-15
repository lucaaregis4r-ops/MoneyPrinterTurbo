"""Sprint 1 End-to-End Regression Test:
Validates the foundational pipeline for Fábrica de Shorts:
1. PT-BR Edge TTS voice synthesis with timestamps.
2. 9:16 vertical video assets (1080x1920).
3. VideoProject initial revision creation & render.
4. Single-scene footage replacement.
5. Verification of stage reuse and partial re-render.
"""

import json
from pathlib import Path
import subprocess
import pytest
from app.services import voice
from app.services.video_project import VideoProject


def test_sprint1_pipeline_and_partial_render(tmp_path: Path):
    work_dir = tmp_path / "sprint1"
    project_dir = work_dir / "project"
    raw_media_dir = work_dir / "raw"
    work_dir.mkdir(parents=True, exist_ok=True)
    raw_media_dir.mkdir(parents=True, exist_ok=True)

    # 1. Synthesize PT-BR narration for 2 scenes
    scenes_data = [
        {
            "id": "scene_001",
            "narration": "Você provavelmente aprendeu que força é massa vezes aceleração.",
            "color": "blue",
        },
        {
            "id": "scene_002",
            "narration": "Mas empurrar um carrinho cheio é outra história.",
            "color": "darkred",
        },
    ]

    for sc in scenes_data:
        audio_path = raw_media_dir / f"{sc['id']}.mp3"
        sub = voice.tts(
            text=sc["narration"],
            voice_name="pt-BR-AntonioNeural-Male",
            voice_rate=1.0,
            voice_file=str(audio_path),
        )
        assert audio_path.exists() and audio_path.stat().st_size > 0
        assert sub is not None
        sc["audio_file"] = str(audio_path)

    # 2. Create 9:16 vertical footage clips (1080x1920)
    for sc in scenes_data:
        footage_path = raw_media_dir / f"{sc['id']}_footage.mp4"
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c={sc['color']}:s=1080x1920:r=30",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-t", "3",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(footage_path),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert footage_path.exists() and footage_path.stat().st_size > 0
        sc["footage_file"] = str(footage_path)

    # 3. Create VideoProject Revision 1
    project = VideoProject(project_dir)
    rev1_spec = project.create_revision(
        {
            "project_id": "fabrica_sprint1_demo",
            "settings": {"width": 1080, "height": 1920, "fps": 30},
            "scenes": [
                {
                    "id": "scene_001",
                    "narration": scenes_data[0]["narration"],
                    "footage": scenes_data[0]["footage_file"],
                    "audio": scenes_data[0]["audio_file"],
                },
                {
                    "id": "scene_002",
                    "narration": scenes_data[1]["narration"],
                    "footage": scenes_data[1]["footage_file"],
                    "audio": scenes_data[1]["audio_file"],
                },
            ],
        }
    )
    rev1_id = rev1_spec["revision_id"]

    # 4. Render Revision 1
    status_rev1 = project.render(rev1_id)
    assert status_rev1["state"] == "succeeded"
    export_path_rev1 = Path(status_rev1["export"]["path"])
    assert export_path_rev1.exists() and export_path_rev1.stat().st_size > 0

    # Validate video resolution and frame rate
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate",
        "-of", "json",
        str(export_path_rev1),
    ]
    probe_out = subprocess.check_output(probe_cmd).decode()
    video_info = json.loads(probe_out)["streams"][0]
    assert video_info["width"] == 1080
    assert video_info["height"] == 1920

    # 5. Swap footage for scene 2 ONLY
    alt_footage = raw_media_dir / "scene_002_alt_footage.mp4"
    cmd_alt = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "color=c=darkgreen:s=1080x1920:r=30",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-t", "3",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        str(alt_footage),
    ]
    subprocess.run(cmd_alt, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    rev2_spec = project.create_revision(
        {
            "project_id": "fabrica_sprint1_demo",
            "settings": {"width": 1080, "height": 1920, "fps": 30},
            "scenes": [
                {
                    "id": "scene_001",
                    "narration": scenes_data[0]["narration"],
                    "footage": scenes_data[0]["footage_file"],
                    "audio": scenes_data[0]["audio_file"],
                },
                {
                    "id": "scene_002",
                    "narration": scenes_data[1]["narration"],
                    "footage": str(alt_footage),
                    "audio": scenes_data[1]["audio_file"],
                },
            ],
        }
    )
    rev2_id = rev2_spec["revision_id"]

    # 6. Verify plan dependency analysis (reuse vs build)
    plan = project.plan(rev2_id)
    actions = {p["key"]: p["action"] for p in plan}
    assert actions["scene_001:audio"] == "reuse"
    assert actions["scene_001:timing"] == "reuse"
    assert actions["scene_001:scene"] == "reuse"
    assert actions["scene_002:audio"] == "reuse"
    assert actions["scene_002:timing"] == "reuse"
    assert actions["scene_002:scene"] == "build"
    assert actions["assembly"] == "build"
    assert actions["export"] == "build"

    # 7. Render Revision 2 and verify reuse callback
    reused_stages = []
    def on_stage(stage, reused):
        if reused:
            reused_stages.append(stage.key)

    status_rev2 = project.render(rev2_id, on_stage=on_stage)
    assert status_rev2["state"] == "succeeded"
    assert "scene_001:scene" in reused_stages
    assert "scene_002:scene" not in reused_stages
