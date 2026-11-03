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

class StoryCharacter(BaseModel):
    id: str = Field(description="Mã định danh, ví dụ: char_1, char_2")
    name: str = Field(description="Tên nhân vật, ví dụ: Tiêu Phong, Tuấn Anh")
    concept: str = Field(description="Concept tạo hình, ví dụ: Kiếm hiệp cổ trang, Cyberpunk hacker, Học sinh thanh xuân")
    appearance_prompt: str = Field(description="Prompt tiếng Anh mô tả chi tiết khuôn mặt, kiểu tóc, độ tuổi")
    default_outfit: str = Field(description="Prompt tiếng Anh mô tả trang phục đặc trưng")
    voice_id: str = Field(default="vi-VN-NamMinhNeural", description="Giọng đọc Edge-TTS")
    face_plate: Optional[str] = Field(default=None, description="Tên file ảnh mặt, vd: char_1_face.png")
    outfit_plate: Optional[str] = Field(default=None, description="Tên file ảnh trang phục, vd: char_1_outfit.png")
    pulid_weight: float = Field(default=0.75, ge=0.0, le=1.0)
    ipadapter_weight: float = Field(default=0.50, ge=0.0, le=1.0)

class StoryScriptResponse(BaseModel):
    title: str = Field(description="Tiêu đề câu chuyện")
    characters: List[StoryCharacter] = Field(default_factory=list, description="Danh sách nhân vật trong câu chuyện kèm Concept")
    scenes: List[StoryScene] = Field(description="Danh sách các phân cảnh theo thứ tự thời gian")

class ActBeat(BaseModel):
    act_id: int = Field(description="Số thứ tự Hồi (từ 1 đến 5)")
    act_title: str = Field(description="Tiêu đề ngắn của Hồi")
    plot_summary: str = Field(description="Tóm tắt diễn biến chính trong Hồi này bằng tiếng Việt")
    location_anchor: str = Field(
        description="Mô tả cố định bằng tiếng Anh về không gian/địa điểm diễn ra Hồi này"
    )
    lighting_anchor: str = Field(
        description="Mô tả cố định bằng tiếng Anh về ánh sáng và thời gian của Hồi này"
    )
    target_scenes: int = Field(default=14, description="Số lượng phân cảnh cần viết trong Hồi này (12-15 cảnh)")

class MasterBeatSheet(BaseModel):
    video_title: str = Field(description="Tiêu đề video chuẩn SEO hấp dẫn")
    overall_synopsis: str = Field(description="Tóm tắt cốt truyện tổng thể")
    acts: List[ActBeat] = Field(description="Danh sách các Hồi của kịch bản")

class ActScenesBatch(BaseModel):
    act_id: int = Field(description="Số thứ tự Hồi")
    scenes: List[StoryScene] = Field(description="Danh sách phân cảnh của Hồi")

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
