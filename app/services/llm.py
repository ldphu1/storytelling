import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
import requests
from loguru import logger

from app.models.schema import StoryScene, StoryScriptResponse, CharacterBible
from app.config import get_config

def generate_mock_story_scenes(topic: str, scene_count: int = 5) -> StoryScriptResponse:
    """Tạo kịch bản mẫu cho chế độ kiểm thử (dry-run) mà không cần gọi API LLM thật."""
    scenes: List[StoryScene] = [
        StoryScene(
            scene_id=1,
            narration=f"Buổi sớm bình yên mở ra câu chuyện: {topic}.",
            has_character=False,
            character_id="char_minh",
            shot_type="wide environmental shot",
            action_prompt="misty morning sunbeams breaking through clouds over ancient rooftops",
            environment_prompt="peaceful city street with golden morning light and dew",
            camera_motion="zoom_in"
        ),
        StoryScene(
            scene_id=2,
            narration="Minh bước từng nhịp chậm rãi trên con đường rợp bóng cây quen thuộc.",
            has_character=True,
            character_id="char_minh",
            shot_type="medium portrait shot",
            action_prompt="walking thoughtfully with a gentle smile looking into the distance",
            environment_prompt="tree-lined sidewalk with soft dappled sunlight and falling leaves",
            camera_motion="zoom_out"
        ),
        StoryScene(
            scene_id=3,
            narration="Từ phía góc phố, Linh vẫy tay chào với nụ cười rạng rỡ ấm áp.",
            has_character=True,
            character_id="char_linh",
            shot_type="cowboy shot",
            action_prompt="waving hand warmly with cheerful expression",
            environment_prompt="charming vintage cafe storefront with flower pots and autumn decor",
            camera_motion="pan_right"
        ),
        StoryScene(
            scene_id=4,
            narration="Hương hoa sữa thoang thoảng trong làn gió se lạnh đầu mùa.",
            has_character=False,
            character_id="char_minh",
            shot_type="extreme close-up shot",
            action_prompt="white blooming flowers swaying gently in cool autumn breeze",
            environment_prompt="close macro view of delicate blooming milk flowers with soft bokeh",
            camera_motion="zoom_in"
        ),
        StoryScene(
            scene_id=5,
            narration="Cả hai cùng bước tiếp, bắt đầu một ngày mới ngập tràn niềm vui và hy vọng.",
            has_character=True,
            character_id="char_minh",
            shot_type="low angle dramatic shot",
            action_prompt="standing proudly looking at the vibrant skyline together",
            environment_prompt="open lakeside promenade under beautiful sunrise sky",
            camera_motion="zoom_out"
        )
    ]
    
    # Adjust count if requested
    actual_scenes = scenes[:scene_count]
    return StoryScriptResponse(
        title=topic,
        scenes=actual_scenes
    )

def _extract_json_from_text(text: str) -> Dict[str, Any]:
    """Trích xuất khối JSON từ phản hồi LLM."""
    text = text.strip()
    # Match markdown json block ```json ... ```
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        text = m.group(1).strip()
    return json.loads(text)

def generate_story_scenes(
    topic: str,
    character_bible_path: str = "resource/character_bible/characters.json",
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    scene_count: int = 5
) -> StoryScriptResponse:
    """Sinh kịch bản phân cảnh chuẩn hóa từ LLM theo Character Bible."""
    cfg = get_config()
    provider = provider or cfg.llm_provider
    api_key = api_key or cfg.llm_api_key
    base_url = base_url or cfg.llm_base_url
    model = model or cfg.llm_model

    bible_path = Path(character_bible_path)
    bible = CharacterBible.from_json_file(bible_path)
    available_chars = list(bible.characters.keys())

    # Fallback to mock if no API key provided
    if not api_key and provider != "ollama":
        logger.warning("Không tìm thấy API Key cho LLM. Tự động sử dụng mock generator!")
        return generate_mock_story_scenes(topic, scene_count=scene_count)

    system_prompt = f"""
Bạn là đạo diễn hình ảnh và biên kịch phim hoạt hình AI chuyên nghiệp.
Nhiệm vụ của bạn là viết kịch bản phân cảnh cho chủ đề: "{topic}".
Danh sách mã nhân vật hiện có trong Character Bible: {available_chars}.

QUY TẮC BẮT BUỘC:
1. Số lượng phân cảnh: chính xác {scene_count} phân cảnh (scene_id từ 1 đến {scene_count}).
2. Lời bình (narration): viết bằng tiếng Việt tự nhiên, truyền cảm. Tuyệt đối KHÔNG viết số (viết "ba" thay vì "3"), KHÔNG viết tắt để bộ đọc Edge-TTS phát âm chuẩn xác.
3. Tỷ lệ B-Roll: Khoảng 20% số phân cảnh (ít nhất 1 cảnh) phải đặt has_character = false để làm cảnh ngoại bối, đặc tả không gian/ánh sáng.
4. Tránh Identity Bleed: Mỗi phân cảnh có nhân vật (has_character = true) chỉ được chọn DUY NHẤT 1 nhân vật xuất hiện (character_id là một trong các mã: {available_chars}). Nếu hai nhân vật nói chuyện, hãy phân chia thành các cú máy quay luân phiên từng người (shot-reverse-shot).
5. Trường action_prompt: Chỉ mô tả hành động, biểu cảm, hướng nhìn bằng TIẾNG ANH. KHÔNG mô tả lại quần áo hay màu tóc của nhân vật vì hệ thống đã khóa tự động.
6. Trường environment_prompt: Mô tả bối cảnh, ánh sáng, thời tiết bằng TIẾNG ANH.
7. shot_type: Chọn một trong ["extreme close-up shot", "medium portrait shot", "cowboy shot", "wide environmental shot", "low angle dramatic shot"].
8. camera_motion: Chọn một trong ["zoom_in", "zoom_out", "pan_right"].

Trả về duy nhất định dạng JSON khớp với cấu trúc sau:
{{
  "title": "{topic}",
  "scenes": [
    {{
      "scene_id": 1,
      "narration": "...",
      "has_character": false,
      "character_id": "char_minh",
      "shot_type": "wide environmental shot",
      "action_prompt": "...",
      "environment_prompt": "...",
      "camera_motion": "zoom_in"
    }}
  ]
}}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Hãy viết kịch bản chi tiết cho chủ đề: {topic}"}
        ],
        "temperature": 0.7
    }

    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    logger.info(f"Đang gửi yêu cầu sinh kịch bản tới LLM ({provider} / {model})...")
    
    resp = requests.post(endpoint, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    raw_content = resp.json()["choices"][0]["message"]["content"]
    
    parsed_json = _extract_json_from_text(raw_content)
    return StoryScriptResponse(**parsed_json)
