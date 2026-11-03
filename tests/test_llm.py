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

