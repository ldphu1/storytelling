import subprocess
from pathlib import Path
import pytest

from app.config import AppConfig
from app.models.schema import StoryScriptResponse, StoryScene
from app.services.task import run_story_pipeline

def test_run_story_pipeline_dry_run(tmp_path):
    cfg = AppConfig(
        storage_dir=tmp_path / "storage",
        worker_urls=[]
    )

    custom_script = StoryScriptResponse(
        title="Hà Nội Trong Mắt Tôi",
        scenes=[
            StoryScene(
                scene_id=1,
                narration="Mùa thu Hà Nội đẹp dịu dàng.",
                has_character=True,
                character_id="char_minh",
                shot_type="medium portrait shot",
                action_prompt="smiling warmly",
                environment_prompt="lake",
                camera_motion="zoom_in"
            ),
            StoryScene(
                scene_id=2,
                narration="Những tia nắng vàng xuyên qua tán lá.",
                has_character=False,
                character_id="char_minh",
                shot_type="wide environmental shot",
                action_prompt="sunlight through leaves",
                environment_prompt="park",
                camera_motion="zoom_out"
            )
        ]
    )

    def mock_tts(text, voice_name, voice_file):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=1.0",
            "-c:a", "libmp3lame", "-ar", "24000", "-ac", "1",
            str(voice_file)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    progress_steps = []
    def on_progress(msg, val):
        progress_steps.append((msg, val))

    final_path = run_story_pipeline(
        topic="Hà Nội Trong Mắt Tôi",
        config=cfg,
        custom_script=custom_script,
        progress_callback=on_progress,
        dry_run=True,
        tts_backend=mock_tts
    )

    assert final_path.exists()
    assert final_path.name == "final_story.mp4"
    assert len(progress_steps) > 0
    # Final progress should reach 1.0
    assert progress_steps[-1][1] == 1.0

def test_run_story_pipeline_with_dynamic_characters(tmp_path):
    from app.models.schema import StoryCharacter
    cfg = AppConfig(
        storage_dir=tmp_path / "storage",
        worker_urls=[]
    )
    dynamic_char = StoryCharacter(
        id="char_swordsman",
        name="Lâm Phong",
        concept="Kiếm khách giang hồ",
        appearance_prompt="swordsman portrait",
        default_outfit="grey robe",
        voice_id="vi-VN-NamMinhNeural"
    )
    custom_script = StoryScriptResponse(
        title="Kiếm Hiệp Kỳ Ảo",
        characters=[dynamic_char],
        scenes=[
            StoryScene(
                scene_id=1,
                narration="Gió lạnh thổi trên đỉnh núi cao.",
                has_character=True,
                character_id="char_swordsman",
                shot_type="medium portrait shot",
                action_prompt="gripping sword",
                environment_prompt="mountain peak",
                camera_motion="zoom_in"
            )
        ]
    )

    def mock_tts(text, voice_name, voice_file):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=1.0",
            "-c:a", "libmp3lame", "-ar", "24000", "-ac", "1",
            str(voice_file)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    final_path = run_story_pipeline(
        topic="Kiếm Hiệp Kỳ Ảo",
        config=cfg,
        custom_script=custom_script,
        dry_run=True,
        tts_backend=mock_tts
    )
    assert final_path.exists()
    task_dir = final_path.parent
    char_dir = task_dir / "characters"
    assert (char_dir / "char_swordsman_face.png").exists()
    assert (char_dir / "char_swordsman_outfit.png").exists()

def test_run_story_pipeline_time_shared_10min_mode(tmp_path):
    from unittest.mock import patch, MagicMock
    from app.services.llm import TimeSharedKaggleDirector
    from app.models.schema import StoryScriptResponse, StoryScene, StoryCharacter

    cfg = AppConfig(
        storage_dir=tmp_path / "storage",
        worker_urls=["https://gpu0.test", "https://gpu1.test"],
        ollama_worker_url="https://ollama.test",
        llm_provider="ollama"
    )

    mock_script = StoryScriptResponse(
        title="Trường Ca 10 Phút",
        characters=[
            StoryCharacter(
                id="char_minh",
                name="Minh",
                concept="Họa sĩ",
                appearance_prompt="young painter",
                default_outfit="linen apron",
                voice_id="vi-VN-NamMinhNeural"
            )
        ],
        scenes=[
            StoryScene(
                scene_id=1,
                narration="Mở màn trường ca anh hùng.",
                has_character=True,
                character_id="char_minh",
                shot_type="medium portrait shot",
                action_prompt="painting a canvas",
                environment_prompt="artist studio",
                camera_motion="zoom_in"
            )
        ]
    )

    def mock_tts(text, voice_name, voice_file):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=1.0",
            "-c:a", "libmp3lame", "-ar", "24000", "-ac", "1",
            str(voice_file)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    with patch.object(TimeSharedKaggleDirector, "generate_full_10min_story", return_value=mock_script) as mock_gen:
        final_path = run_story_pipeline(
            topic="Trường Ca 10 Phút",
            config=cfg,
            story_mode="10min_multiact",
            dry_run=True,
            tts_backend=mock_tts
        )

        assert final_path.exists()
        mock_gen.assert_called_once()

