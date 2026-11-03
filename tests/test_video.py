import subprocess
from pathlib import Path
import pytest
from PIL import Image

from app.services.video import get_safe_subtitle_path, assemble_final_story_video_nvenc
from app.services.comfy_remote_client import DualGPUComfyStoryClient

def test_safe_subtitle_path_escaping():
    p = Path(r"C:\Users\Asus\Desktop\sub.srt")
    safe = get_safe_subtitle_path(p)
    # Must use forward slashes for path separators and escaped colon for Windows drive
    assert r"\:" in safe
    assert "/Users/Asus/Desktop" in safe
    # Ensure no Windows backslash path separators remain other than the escaped colon
    assert "\\" not in safe.replace(r"\:", "")

def test_assemble_final_story_video_nvenc(tmp_path):
    # 1. Tạo 2 clip visual
    img1 = tmp_path / "img1.png"
    Image.new("RGB", (640, 360), color=(100, 50, 50)).save(img1)
    vid1 = tmp_path / "vid1.mp4"
    DualGPUComfyStoryClient._render_zoompan_nvenc(img1, vid1, duration=1.0)

    img2 = tmp_path / "img2.png"
    Image.new("RGB", (640, 360), color=(50, 100, 50)).save(img2)
    vid2 = tmp_path / "vid2.mp4"
    DualGPUComfyStoryClient._render_zoompan_nvenc(img2, vid2, duration=1.0)

    # 2. Tạo master audio (2 giây)
    master_audio = tmp_path / "master_audio.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "sine=frequency=440:duration=2.0",
        "-c:a", "libmp3lame", str(master_audio)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    # 3. Tạo subtitle srt
    sub_srt = tmp_path / "sub.srt"
    sub_srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nXin chào câu chuyện.\n", encoding="utf-8")

    out_final = tmp_path / "final.mp4"
    result = assemble_final_story_video_nvenc(
        scene_video_paths=[str(vid1), str(vid2)],
        master_audio_path=master_audio,
        subtitle_srt_path=sub_srt,
        output_final_path=out_final
    )

    assert result.exists()
    assert result.stat().st_size > 1024
