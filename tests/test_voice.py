import subprocess
from pathlib import Path
import pytest
from mutagen.mp3 import MP3

from app.models.schema import StoryScene, CharacterBible, CharacterProfile
from app.services.voice import (
    _format_srt_timestamp,
    synthesize_scenes_audio_and_subtitles,
    sanitize_narration,
    default_edge_tts
)

def test_format_srt_timestamp():
    assert _format_srt_timestamp(0.0) == "00:00:00,000"
    assert _format_srt_timestamp(1.234) == "00:00:01,234"
    assert _format_srt_timestamp(65.5) == "00:01:05,500"
    assert _format_srt_timestamp(3661.05) == "01:01:01,050"

def test_sanitize_narration():
    bible = CharacterBible.from_json_file(Path("resource/character_bible/characters.json"))
    
    # 1. Test với bible mặc định
    text = "char_minh bắt đầu luyện tập cùng char_linh."
    cleaned = sanitize_narration(text, bible)
    assert "Minh bắt đầu luyện tập cùng Linh." == cleaned
    
    # 2. Test với nhân vật động (char_1 -> Hiro, char_2 -> Yuki)
    bible.characters["char_1"] = CharacterProfile(
        name="Hiro",
        voice_id="vi-VN-NamMinhNeural",
        appearance_trigger="samurai",
        default_outfit="armor",
        face_plate="char_1_face.png",
        outfit_plate="char_1_outfit.png"
    )
    bible.characters["char_2"] = CharacterProfile(
        name="Yuki",
        voice_id="vi-VN-HoaiMyNeural",
        appearance_trigger="woman",
        default_outfit="kimono",
        face_plate="char_2_face.png",
        outfit_plate="char_2_outfit.png"
    )
    
    text2 = "Hồi đầu tiên bắt đầu với cảnh samurai char_1 đang đứng. Char_2 xuất hiện, char_1 và Char_2 bắt đầu đấu kiếm."
    cleaned2 = sanitize_narration(text2, bible)
    assert "Hồi đầu tiên bắt đầu với cảnh samurai Hiro đang đứng. Yuki xuất hiện, Hiro và Yuki bắt đầu đấu kiếm." == cleaned2

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

def test_synthesize_scenes_audio_sanitizes_narration_and_subtitles(tmp_path):
    scenes = [
        StoryScene(
            scene_id=1,
            narration="Samurai char_1 rút gươm, char_2 chuẩn bị ứng chiến.",
            has_character=True,
            character_id="char_1",
            action_prompt="drawing sword",
            environment_prompt="dojo"
        )
    ]
    bible = CharacterBible.from_json_file(Path("resource/character_bible/characters.json"))
    bible.characters["char_1"] = CharacterProfile(
        name="Hiro",
        voice_id="vi-VN-NamMinhNeural",
        appearance_trigger="samurai",
        default_outfit="armor",
        face_plate="char_1_face.png",
        outfit_plate="char_1_outfit.png"
    )
    bible.characters["char_2"] = CharacterProfile(
        name="Yuki",
        voice_id="vi-VN-HoaiMyNeural",
        appearance_trigger="woman",
        default_outfit="kimono",
        face_plate="char_2_face.png",
        outfit_plate="char_2_outfit.png"
    )

    def mock_tts_generator(text, voice_name, voice_file):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "anullsrc=r=24000:cl=mono",
            "-t", "1.0",
            "-c:a", "libmp3lame", "-ar", "24000", "-ac", "1",
            str(voice_file)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    master_audio, master_srt, durations = synthesize_scenes_audio_and_subtitles(
        scenes=scenes,
        task_dir=tmp_path,
        bible=bible,
        tts_backend=mock_tts_generator
    )

    assert "Hiro" in scenes[0].narration
    assert "Yuki" in scenes[0].narration
    assert "char_1" not in scenes[0].narration
    srt_content = master_srt.read_text(encoding="utf-8")
    assert "Samurai Hiro rút gươm, Yuki chuẩn bị ứng chiến." in srt_content

def test_default_edge_tts_fallback_marker(tmp_path, monkeypatch):
    test_audio = tmp_path / "audio_test.mp3"
    marker = test_audio.with_suffix(".fallback")
    
    # Giả lập _edge_tts_async luôn raise Exception
    async def mock_failing_tts(*args, **kwargs):
        raise ConnectionError("Simulated Edge-TTS offline failure")
    
    monkeypatch.setattr("app.services.voice._edge_tts_async", mock_failing_tts)
    monkeypatch.setattr("time.sleep", lambda s: None) # Fast test execution
    
    # Chạy default_edge_tts với max_retries=1
    default_edge_tts("Thử nghiệm lỗi", "vi-VN-NamMinhNeural", test_audio, max_retries=1)
    
    assert test_audio.exists()
    assert marker.exists()
    
    # Bây giờ giả lập _edge_tts_async thành công
    async def mock_success_tts(text, voice_name, temp_file, rate="+0%"):
        # Tạo file hợp lệ > 1024 bytes bằng ffmpeg
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "anullsrc=r=24000:cl=mono",
            "-t", "1.0",
            "-c:a", "libmp3lame", "-ar", "24000", "-ac", "1",
            str(temp_file)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        
    monkeypatch.setattr("app.services.voice._edge_tts_async", mock_success_tts)
    default_edge_tts("Thử nghiệm thành công", "vi-VN-NamMinhNeural", test_audio, max_retries=1)
    
    assert test_audio.exists()
    # Marker .fallback phải được xóa sạch khi thành công
    assert not marker.exists()
