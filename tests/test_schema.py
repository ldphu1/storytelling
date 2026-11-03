import json
import pytest
from pathlib import Path
from PIL import Image

from app.models.schema import StoryScene, StoryScriptResponse, CharacterBible

def test_story_scene_schema_valid():
    scene = StoryScene(
        scene_id=1,
        narration="Minh bước đi dưới hàng cây hoàng yến rực rỡ.",
        has_character=True,
        character_id="char_minh",
        shot_type="medium portrait shot",
        action_prompt="walking thoughtfully with hands in hoodie pockets",
        environment_prompt="under blooming golden shower trees in Hanoi sunlight",
        camera_motion="zoom_in"
    )
    assert scene.scene_id == 1
    assert scene.has_character is True
    assert scene.shot_type == "medium portrait shot"

def test_story_scene_schema_invalid_shot_type():
    with pytest.raises(Exception):
        StoryScene(
            scene_id=1,
            narration="Test",
            has_character=False,
            shot_type="invalid_shot_angle",
            action_prompt="walking",
            environment_prompt="park"
        )

def test_character_bible_loading():
    bible_path = Path("resource/character_bible/characters.json")
    assert bible_path.exists(), "characters.json must exist"
    
    bible = CharacterBible.from_json_file(bible_path)
    assert "char_minh" in bible.characters
    assert "char_linh" in bible.characters
    assert bible.narrator.voice_id != ""
    assert "style_prefix" in bible.global_settings

def test_starter_plates_exist_and_valid():
    plates_dir = Path("resource/character_bible")
    for plate_name in ["minh_face_plate.png", "minh_outfit_plate.png", "linh_face_plate.png", "linh_outfit_plate.png"]:
        p = plates_dir / plate_name
        assert p.exists(), f"Missing starter plate: {plate_name}"
        with Image.open(p) as img:
            assert img.size == (1024, 1024)

def test_workflow_template_node_ids():
    wf_path = Path("resource/workflows/pulid_ipadapter_api.json")
    assert wf_path.exists(), "Workflow template must exist"
    with open(wf_path, "r", encoding="utf-8") as f:
        wf = json.load(f)
    
    # Required Node IDs from technical blueprint & refinements:
    # 6: pos_prompt, 7: neg_prompt, 12: face_loader, 15: outfit_loader,
    # 18: face_lock (IPAdapterFaceID), 21: outfit_lock (IPAdapterAdvanced), 3: ksampler, 9: save_img
    for node_id in ["6", "7", "12", "15", "18", "21", "3", "9"]:
        assert node_id in wf, f"Node {node_id} missing from workflow API JSON"

def test_story_character_schema():
    from app.models.schema import StoryCharacter
    char = StoryCharacter(
        id="char_custom_1",
        name="Lâm Phong",
        concept="Kiếm khách lãng tử thời phong kiến",
        appearance_prompt="a 25-year-old wandering swordsman with a bamboo hat",
        default_outfit="wearing a worn grey linen robe and straw sandals",
        voice_id="vi-VN-NamMinhNeural"
    )
    assert char.id == "char_custom_1"
    assert char.concept == "Kiếm khách lãng tử thời phong kiến"
    assert char.pulid_weight == 0.75
    assert char.ipadapter_weight == 0.50

def test_story_script_response_with_dynamic_characters():
    from app.models.schema import StoryCharacter
    script = StoryScriptResponse(
        title="Truyền Thuyết Kiếm Khách",
        characters=[
            StoryCharacter(
                id="char_1",
                name="Lâm Phong",
                concept="Kiếm hiệp",
                appearance_prompt="swordsman face",
                default_outfit="linen robe"
            )
        ],
        scenes=[
            StoryScene(
                scene_id=1,
                narration="Gió thổi qua thảo nguyên",
                has_character=True,
                character_id="char_1",
                shot_type="medium portrait shot",
                action_prompt="standing with sword",
                environment_prompt="windy grassland",
                camera_motion="zoom_in"
            )
        ]
    )
    assert len(script.characters) == 1
    assert script.characters[0].concept == "Kiếm hiệp"
    assert script.scenes[0].character_id == "char_1"

def test_act_beat_and_master_beat_sheet_schema():
    from app.models.schema import ActBeat, MasterBeatSheet
    act = ActBeat(
        act_id=1,
        act_title="Mở đầu bí ẩn",
        plot_summary="Lâm Phong bước vào thị trấn trong đêm mưa",
        location_anchor="inside a dimly lit tavern with wooden tables",
        lighting_anchor="warm candlelight and rainy shadows",
        target_scenes=14
    )
    assert act.act_id == 1
    assert act.target_scenes == 14

    beat_sheet = MasterBeatSheet(
        video_title="Bí Mật Thanh Kiếm Cổ",
        overall_synopsis="Hành trình khám phá bảo kiếm giang hồ",
        acts=[act]
    )
    assert beat_sheet.video_title == "Bí Mật Thanh Kiếm Cổ"
    assert len(beat_sheet.acts) == 1

def test_act_scenes_batch_schema():
    from app.models.schema import ActScenesBatch, StoryScene
    batch = ActScenesBatch(
        act_id=1,
        scenes=[
            StoryScene(
                scene_id=1,
                narration="Mưa rơi nặng hạt trên mái ngói.",
                has_character=False,
                character_id="char_minh",
                shot_type="wide environmental shot",
                action_prompt="rain falling on roofs",
                environment_prompt="rainy town",
                camera_motion="zoom_in"
            )
        ]
    )
    assert batch.act_id == 1
    assert len(batch.scenes) == 1


