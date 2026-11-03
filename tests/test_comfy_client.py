import json
import pytest
from pathlib import Path
from PIL import Image

from app.models.schema import StoryScene
from app.services.comfy_remote_client import DualGPUComfyStoryClient

@pytest.fixture
def client():
    return DualGPUComfyStoryClient(
        worker_urls=["https://worker1.trycloudflare.com", "https://worker2.trycloudflare.com"],
        workflow_path="resource/workflows/pulid_ipadapter_api.json",
        bible_path="resource/character_bible/characters.json"
    )

def test_build_workflow_payload_character_scene(client):
    scene = {
        "scene_id": 1,
        "has_character": True,
        "character_id": "char_minh",
        "shot_type": "medium portrait shot",
        "action_prompt": "walking looking around",
        "environment_prompt": "sunny autumn street",
        "camera_motion": "zoom_in"
    }
    wf = client._build_workflow_payload(scene)
    
    # Prompt is injected to Node 6
    prompt_text = wf["6"]["inputs"]["text"]
    assert "medium portrait shot" in prompt_text
    assert "walking looking around" in prompt_text
    assert "sunny autumn street" in prompt_text
    assert "short messy black hair" in prompt_text  # Minh's appearance trigger
    
    # Face & Outfit plates
    assert wf["12"]["inputs"]["image"] == "minh_face_plate.png"
    assert wf["15"]["inputs"]["image"] == "minh_outfit_plate.png"
    
    # Weights active
    assert wf["18"]["inputs"]["weight"] == 0.85
    assert wf["21"]["inputs"]["weight"] == 0.55

def test_broll_scene_disables_ipadapter_weights(client):
    scene = {
        "scene_id": 2,
        "has_character": False,
        "character_id": "char_minh",
        "shot_type": "wide environmental shot",
        "action_prompt": "leaves blowing in wind",
        "environment_prompt": "empty street in autumn dawn",
        "camera_motion": "zoom_out"
    }
    wf = client._build_workflow_payload(scene)
    
    # Weights MUST be 0.0 to prevent character hallucination in B-Roll
    assert wf["18"]["inputs"]["weight"] == 0.0
    assert wf["21"]["inputs"]["weight"] == 0.0

def test_render_zoompan_nvenc(tmp_path):
    # Tạo ảnh mẫu
    img_path = tmp_path / "test_scene.png"
    img = Image.new("RGB", (1024, 1024), color=(70, 130, 180))
    img.save(img_path)
    
    out_video = tmp_path / "test_scene.mp4"
    DualGPUComfyStoryClient._render_zoompan_nvenc(
        image_path=img_path,
        output_video_path=out_video,
        duration=1.5,
        effect="zoom_in",
        aspect_ratio="16:9"
    )
    
    assert out_video.exists()
    assert out_video.stat().st_size > 1024  # video > 1KB hợp lệ

@pytest.mark.asyncio
async def test_parallel_render_dry_run(tmp_path):
    client = DualGPUComfyStoryClient(
        worker_urls=[],
        workflow_path="resource/workflows/pulid_ipadapter_api.json",
        bible_path="resource/character_bible/characters.json"
    )
    scenes = [
        {
            "scene_id": 1,
            "has_character": True,
            "character_id": "char_minh",
            "shot_type": "medium portrait shot",
            "action_prompt": "looking at sky",
            "environment_prompt": "park",
            "camera_motion": "zoom_in"
        },
        {
            "scene_id": 2,
            "has_character": False,
            "character_id": "char_minh",
            "shot_type": "wide environmental shot",
            "action_prompt": "sun rising",
            "environment_prompt": "lake",
            "camera_motion": "zoom_out"
        }
    ]
    durations = [1.5, 1.5]
    
    results = await client.render_all_scenes_parallel(
        task_dir=tmp_path,
        scenes=scenes,
        durations=durations,
        dry_run=True
    )
    
    assert len(results) == 2
    assert Path(results[0]).exists()
    assert Path(results[1]).exists()
