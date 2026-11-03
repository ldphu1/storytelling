import json
import pytest
from unittest.mock import patch, MagicMock
from app.models.schema import StoryScriptResponse, StoryScene
from app.services.llm import generate_story_scenes, generate_mock_story_scenes

def test_generate_mock_story_scenes():
    topic = "Hành trình mùa thu Hà Nội"
    result = generate_mock_story_scenes(topic=topic, scene_count=5)
    
    assert isinstance(result, StoryScriptResponse)
    assert len(result.scenes) == 5
    assert result.scenes[0].scene_id == 1
    # Check that dynamic characters with concept are returned
    assert len(result.characters) >= 1
    for char in result.characters:
        assert char.concept != ""
        assert char.appearance_prompt != ""
        assert char.default_outfit != ""
    # Check that at least one scene is B-Roll (has_character == False)
    broll_scenes = [s for s in result.scenes if not s.has_character]
    assert len(broll_scenes) >= 1
    # Check that character scenes reference characters in script or fallback
    char_scenes = [s for s in result.scenes if s.has_character]
    char_ids = {c.id for c in result.characters} | {"char_minh", "char_linh"}
    for s in char_scenes:
        assert s.character_id in char_ids

def test_generate_story_scenes_with_mocked_llm_response():
    mock_response_data = {
        "title": "Chuyện Phố Cổ",
        "scenes": [
            {
                "scene_id": 1,
                "narration": "Mặt trời vừa ló rạng trên mái ngói rêu phong phố cổ Hà Nội.",
                "has_character": False,
                "character_id": "char_minh",
                "shot_type": "wide environmental shot",
                "action_prompt": "morning golden light illuminating misty ancient rooftops",
                "environment_prompt": "Hanoi old quarter with mossy roofs and autumn mist",
                "camera_motion": "zoom_in"
            },
            {
                "scene_id": 2,
                "narration": "Minh rảo bước qua ngõ nhỏ quen thuộc, tay cầm chiếc máy ảnh phim.",
                "has_character": True,
                "character_id": "char_minh",
                "shot_type": "medium portrait shot",
                "action_prompt": "walking gently through narrow alley holding vintage film camera",
                "environment_prompt": "quaint narrow alley with morning sunbeams cutting through steam",
                "camera_motion": "zoom_out"
            }
        ]
    }
    
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{
            "message": {
                "content": json.dumps(mock_response_data)
            }
        }]
    }
    mock_resp.status_code = 200

    with patch("requests.post", return_value=mock_resp):
        res = generate_story_scenes(
            topic="Chuyện Phố Cổ",
            api_key="mock-key",
            provider="openai"
        )
        assert res.title == "Chuyện Phố Cổ"
        assert len(res.scenes) == 2
        assert res.scenes[0].has_character is False
        assert res.scenes[1].character_id == "char_minh"

def test_generate_story_scenes_provider_routing():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{
            "message": {
                "content": json.dumps({"title": "Test", "scenes": []})
            }
        }]
    }
    mock_resp.status_code = 200

    with patch("requests.post", return_value=mock_resp) as mock_post:
        # 1. Test Gemini auto base_url
        generate_story_scenes(topic="Test", provider="gemini", api_key="test-key")
        called_url = mock_post.call_args[0][0]
        assert "generativelanguage.googleapis.com" in called_url

    with patch("requests.post", return_value=mock_resp) as mock_post:
        # 2. Test DeepSeek auto base_url
        generate_story_scenes(topic="Test", provider="deepseek", api_key="test-key")
        called_url = mock_post.call_args[0][0]
        assert "api.deepseek.com" in called_url

def test_generate_story_scenes_mock_provider():
    # Provider "mock" should return without network calls
    with patch("requests.post") as mock_post:
        res = generate_story_scenes(topic="Test Mock", provider="mock")
        assert res.title == "Test Mock"
        assert len(res.scenes) > 0
        mock_post.assert_not_called()

def test_time_shared_kaggle_director_free_comfyui_vram():
    from app.services.llm import TimeSharedKaggleDirector
    director = TimeSharedKaggleDirector(
        ollama_url="https://ollama.test",
        comfy_urls=["https://gpu0.test", "https://gpu1.test"]
    )
    with patch("requests.post") as mock_post, patch("time.sleep"):
        director.free_comfyui_vram_before_llm()
        assert mock_post.call_count == 2
        calls = [c[0][0] for c in mock_post.call_args_list]
        assert "https://gpu0.test/free" in calls
        assert "https://gpu1.test/free" in calls
        for c in mock_post.call_args_list:
            assert c[1]["json"] == {"unload_models": True, "free_memory": True}

def test_time_shared_kaggle_director_evict_llm():
    from app.services.llm import TimeSharedKaggleDirector
    director = TimeSharedKaggleDirector(
        ollama_url="https://ollama.test",
        comfy_urls=["https://gpu0.test", "https://gpu1.test"],
        model_name="qwen2.5:32b-instruct-q4_K_M"
    )
    with patch("requests.post") as mock_post, patch("time.sleep"):
        director.evict_llm_from_kaggle_vram()
        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == "https://ollama.test/api/generate"
        assert mock_post.call_args[1]["json"] == {
            "model": "qwen2.5:32b-instruct-q4_K_M",
            "keep_alive": 0
        }

def test_time_shared_kaggle_director_full_generation_and_eviction(tmp_path):
    from app.services.llm import TimeSharedKaggleDirector
    from app.models.schema import MasterBeatSheet, ActBeat, ActScenesBatch, StoryScene

    director = TimeSharedKaggleDirector(
        ollama_url="https://ollama.test",
        comfy_urls=["https://gpu0.test", "https://gpu1.test"]
    )

    beat_sheet = MasterBeatSheet(
        video_title="Truyền Thuyết Kiếm Sĩ",
        overall_synopsis="Hành trình của kiếm sĩ",
        acts=[
            ActBeat(
                act_id=1,
                act_title="Hồi 1: Rời Núi",
                plot_summary="Kiếm sĩ xuống núi",
                location_anchor="mountain temple path with stone steps",
                lighting_anchor="misty morning sunrise",
                target_scenes=2
            ),
            ActBeat(
                act_id=2,
                act_title="Hồi 2: Vào Trấn",
                plot_summary="Gặp hiểm nguy",
                location_anchor="crowded ancient marketplace",
                lighting_anchor="bright midday sunlight",
                target_scenes=2
            )
        ]
    )

    act1_batch = ActScenesBatch(
        act_id=1,
        scenes=[
            StoryScene(
                scene_id=1,
                narration="Cảnh một xuống núi.",
                has_character=True,
                character_id="char_minh",
                shot_type="medium portrait shot",
                action_prompt="walking down stone stairs",
                environment_prompt="misty morning sunrise at mountain temple path",
                camera_motion="zoom_in"
            ),
            StoryScene(
                scene_id=2,
                narration="Tiếng chuông ngân vang.",
                has_character=False,
                character_id="char_minh",
                shot_type="wide environmental shot",
                action_prompt="ancient bell swinging gently",
                environment_prompt="misty mountain temple",
                camera_motion="zoom_out"
            )
        ]
    )

    act2_batch = ActScenesBatch(
        act_id=2,
        scenes=[
            StoryScene(
                scene_id=1,
                narration="Chợ đông đúc người qua lại.",
                has_character=False,
                character_id="char_minh",
                shot_type="wide environmental shot",
                action_prompt="bustling crowd in street",
                environment_prompt="crowded ancient marketplace",
                camera_motion="pan_right"
            ),
            StoryScene(
                scene_id=2,
                narration="Minh bước vào quán trọ.",
                has_character=True,
                character_id="char_minh",
                shot_type="cowboy shot",
                action_prompt="stepping through wooden door",
                environment_prompt="ancient tavern entrance",
                camera_motion="zoom_in"
            )
        ]
    )

    mock_evict = MagicMock()
    mock_free_comfy = MagicMock()
    director.evict_llm_from_kaggle_vram = mock_evict
    director.free_comfyui_vram_before_llm = mock_free_comfy

    def mock_call_structured(sys_prompt, user_prompt, schema_model):
        if schema_model == MasterBeatSheet:
            return beat_sheet.model_dump_json()
        elif schema_model == ActScenesBatch:
            if "Hồi 1" in sys_prompt:
                return act1_batch.model_dump_json()
            else:
                return act2_batch.model_dump_json()
        raise ValueError(f"Unexpected schema: {schema_model}")

    director._call_ollama_structured = mock_call_structured

    scenes = director.generate_full_10min_script(
        topic="Truyền Thuyết Kiếm Sĩ",
        checkpoint_dir=tmp_path / "checkpoints"
    )

    assert len(scenes) == 4
    # Re-indexing scenes 1 to 4
    assert [s.scene_id for s in scenes] == [1, 2, 3, 4]
    mock_free_comfy.assert_called_once()
    mock_evict.assert_called_once()
    # Check that checkpoint file was written
    assert (tmp_path / "checkpoints" / "full_script_checkpoint.json").exists()

def test_time_shared_kaggle_director_guaranteed_eviction_on_error(tmp_path):
    from app.services.llm import TimeSharedKaggleDirector

    director = TimeSharedKaggleDirector(
        ollama_url="https://ollama.test",
        comfy_urls=["https://gpu0.test", "https://gpu1.test"]
    )

    mock_evict = MagicMock()
    director.evict_llm_from_kaggle_vram = mock_evict
    director.free_comfyui_vram_before_llm = MagicMock()

    director._call_ollama_structured = MagicMock(side_effect=RuntimeError("Ollama network timeout!"))

    with pytest.raises(RuntimeError, match="Ollama network timeout"):
        director.generate_full_10min_script(
            topic="Crash Test",
            checkpoint_dir=tmp_path / "checkpoints"
        )

    # Eviction MUST have been called despite the error!
    mock_evict.assert_called_once()


