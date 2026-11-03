import subprocess
from pathlib import Path
import pytest

from app.config import AppConfig
from app.services.task import run_story_pipeline

def test_full_e2e_storytelling_pipeline(tmp_path):
    """
    Kiểm thử tích hợp End-to-End toàn diện:
    Từ chủ đề đầu vào -> Sinh kịch bản -> TTS Audio -> Comfy Parallel (Dry-run) -> Video NVENC.
    """
    cfg = AppConfig(
        storage_dir=tmp_path / "storage",
        worker_urls=[]
    )

    def mock_tts(text, voice_name, voice_file):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=1.2",
            "-c:a", "libmp3lame", "-ar", "24000", "-ac", "1",
            str(voice_file)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    reported_milestones = []
    def on_progress(msg, val):
        reported_milestones.append((msg, val))

    final_video = run_story_pipeline(
        topic="Khám phá mùa thu Hà Nội",
        config=cfg,
        progress_callback=on_progress,
        dry_run=True,
        tts_backend=mock_tts
    )

    # 1. Kiểm tra video thành phẩm tồn tại
    assert final_video.exists()
    assert final_video.name == "final_story.mp4"
    assert final_video.stat().st_size > 10240

    # 2. Kiểm tra tiến trình đạt 100%
    assert len(reported_milestones) >= 5
    assert reported_milestones[-1][1] == 1.0

    # 3. Kiểm tra các artifact trung gian trong thư mục task
    task_dir = final_video.parent
    assert (task_dir / "story_script.json").exists()
    assert (task_dir / "master_audio.mp3").exists()
    assert (task_dir / "master_subtitle.srt").exists()
    assert (task_dir / "merged_visual_only.mp4").exists()
