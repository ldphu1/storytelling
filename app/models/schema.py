import json
from pathlib import Path
from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field

ShotType = Literal[
    "extreme close-up shot",
    "medium portrait shot",
    "cowboy shot",
    "wide environmental shot",
    "low angle dramatic shot"
]

CameraMotion = Literal["zoom_in", "zoom_out", "pan_right"]

class StoryScene(BaseModel):
    scene_id: int = Field(description="Số thứ tự phân cảnh, bắt đầu từ 1")
    narration: str = Field(description="Lời dẫn truyện tiếng Việt tự nhiên, không chứa từ viết tắt")
    has_character: bool = Field(description="True nếu cảnh này có mặt nhân vật, False nếu là cảnh B-Roll ngoại cảnh")
    character_id: str = Field(default="char_minh", description="Mã nhân vật xuất hiện trong cảnh (VD: char_minh, char_linh)")
    shot_type: ShotType = Field(default="medium portrait shot", description="Góc máy điện ảnh")
    action_prompt: str = Field(description="Mô tả hành động và biểu cảm bằng tiếng Anh")
    environment_prompt: str = Field(description="Mô tả bối cảnh và ánh sáng xung quanh bằng tiếng Anh")
    camera_motion: CameraMotion = Field(default="zoom_in", description="Hiệu ứng chuyển động camera")

class StoryScriptResponse(BaseModel):
    title: str = Field(description="Tiêu đề câu chuyện")
    scenes: List[StoryScene] = Field(description="Danh sách các phân cảnh theo thứ tự thời gian")

class CharacterProfile(BaseModel):
    name: str
    voice_id: str = "vi-VN-NamMinhNeural"
    appearance_trigger: str
    default_outfit: str
    face_plate: str
    outfit_plate: str
    pulid_weight: float = 0.85
    ipadapter_weight: float = 0.55

class NarratorProfile(BaseModel):
    voice_id: str = "vi-VN-NamMinhNeural"
    rate: str = "+0%"

class CharacterBible(BaseModel):
    global_settings: Dict[str, str]
    narrator: NarratorProfile
    characters: Dict[str, CharacterProfile]

    @classmethod
    def from_json_file(cls, path: Path) -> "CharacterBible":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)
