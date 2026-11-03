import subprocess
from pathlib import Path
import pytest
from mutagen.mp3 import MP3

from app.models.schema import StoryScene, CharacterBible
from app.services.voice import _format_srt_timestamp, synthesize_scenes_audio_and_subtitles

def test_format_srt_timestamp():
    assert _format_srt_timestamp(0.0) == "00:00:00,000"
    assert _format_srt_timestamp(1.234) == "00:00:01,234"
    assert _format_srt_timestamp(65.5) == "00:01:05,500"
    assert _format_srt_timestamp(3661.05) == "01:01:01,050"

def test_synthesize_scenes_audio_and_subtitles_mock(tmp_path):
    # Tạo dummy audio bằng ffmpeg để test mà không phụ thuộc vào kết nối Edge-TTS mạng
    scenes = [
        StoryScene(
            scene_id=1,
            narration="Chào buổi sáng Hà Nội.",
            has_character=True,
            character_id="char_minh",
            action_prompt="standing",
            environment_prompt="city"
        ),
        StoryScene(
            scene_id=2,
            narration="Gió heo may thổi nhẹ qua từng con phố.",
            has_character=False,
            character_id="char_minh",
            action_prompt="leaves falling",
            environment_prompt="street"
        )
    ]
    
    bible = CharacterBible.from_json_file(Path("resource/character_bible/characters.json"))
    
    # Custom mock generator cho voice.py để tạo file MP3 chuẩn 24000Hz 1 channel bằng ffmpeg
    def mock_tts_generator(text, voice_name, voice_file):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "anullsrc=r=24000:cl=mono",
            "-t", "1.5",
            "-c:a", "libmp3lame", "-ar", "24000", "-ac", "1",
            str(voice_file)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    master_audio, master_srt, durations = synthesize_scenes_audio_and_subtitles(
        scenes=scenes,
        task_dir=tmp_path,
        bible=bible,
        tts_backend=mock_tts_generator
    )

    assert master_audio.exists()
    assert master_srt.exists()
    assert len(durations) == 2
    assert all(d > 1.4 for d in durations)

    # Check SRT content
    srt_content = master_srt.read_text(encoding="utf-8")
    assert "Chào buổi sáng Hà Nội." in srt_content
    assert "Gió heo may thổi nhẹ qua từng con phố." in srt_content
    assert "00:00:00,000 -->" in srt_content
