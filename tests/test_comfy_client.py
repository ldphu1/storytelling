import json
import time
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
    assert wf["18"]["inputs"]["weight"] == 0.75
    assert wf["21"]["inputs"]["weight"] == 0.50

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

def test_generate_character_plates_dry_run(client, tmp_path):
    from app.models.schema import StoryCharacter
    char = StoryCharacter(
        id="char_swordsman",
        name="Lâm Phong",
        concept="Kiếm khách lãng tử",
        appearance_prompt="a 25-year-old wandering swordsman",
        default_outfit="wearing a worn grey linen robe"
    )
    face_path, outfit_path = client.generate_character_plates(
        character=char,
        output_dir=tmp_path,
        dry_run=True
    )
    assert face_path.exists()
    assert outfit_path.exists()
    with Image.open(face_path) as img:
        assert img.size == (1024, 1024)
    with Image.open(outfit_path) as img:
        assert img.size == (1024, 1024)
    assert char.face_plate == "char_swordsman_face.png"
    assert char.outfit_plate == "char_swordsman_outfit.png"

def test_build_workflow_payload_with_dynamic_character(client, tmp_path):
    from app.models.schema import StoryCharacter
    char = StoryCharacter(
        id="char_swordsman",
        name="Lâm Phong",
        concept="Kiếm hiệp",
        appearance_prompt="a wandering swordsman with bamboo hat",
        default_outfit="wearing a worn grey linen robe",
        face_plate="char_swordsman_face.png",
        outfit_plate="char_swordsman_outfit.png",
        pulid_weight=0.70,
        ipadapter_weight=0.45
    )
    scene = {
        "scene_id": 1,
        "has_character": True,
        "character_id": "char_swordsman",
        "shot_type": "medium portrait shot",
        "action_prompt": "gripping sword hilt thoughtfully",
        "environment_prompt": "foggy bamboo forest",
        "camera_motion": "zoom_in"
    }
    wf = client._build_workflow_payload(scene, characters_override={"char_swordsman": char})
    prompt_text = wf["6"]["inputs"]["text"]
    assert "wandering swordsman with bamboo hat" in prompt_text
    assert wf["12"]["inputs"]["image"] == "char_swordsman_face.png"
    assert wf["15"]["inputs"]["image"] == "char_swordsman_outfit.png"
    assert wf["18"]["inputs"]["weight"] == 0.70
    assert wf["21"]["inputs"]["weight"] == 0.45


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
async def test_nvenc_semaphore_concurrency_limit(tmp_path):
    # Kiểm tra đảm bảo số lượng tiến trình render đồng thời không vượt quá nvenc_max_concurrency
    client = DualGPUComfyStoryClient(
        worker_urls=[],
        workflow_path="resource/workflows/pulid_ipadapter_api.json",
        bible_path="resource/character_bible/characters.json"
    )
    client.nvenc_max_concurrency = 2
    
    current_concurrency = 0
    max_concurrency_observed = 0
    
    orig_zoompan = client._render_zoompan_nvenc
    def tracking_zoompan(*args, **kwargs):
        nonlocal current_concurrency, max_concurrency_observed
        current_concurrency += 1
        if current_concurrency > max_concurrency_observed:
            max_concurrency_observed = current_concurrency
        time.sleep(0.05)
        res = orig_zoompan(*args, **kwargs)
        current_concurrency -= 1
        return res
    
    client._render_zoompan_nvenc = tracking_zoompan

    scenes = [
        {"scene_id": i, "has_character": False, "shot_type": "wide environmental shot", "action_prompt": "test", "environment_prompt": "test", "camera_motion": "zoom_in"}
        for i in range(1, 5)
    ]
    durations = [1.0, 1.0, 1.0, 1.0]

    await client.render_all_scenes_parallel(
        task_dir=tmp_path,
        scenes=scenes,
        durations=durations,
        dry_run=True
    )

    assert max_concurrency_observed <= 2, f"Expected peak concurrency <= 2, got {max_concurrency_observed}"

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
