import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
import requests
from loguru import logger

from app.models.schema import StoryScene, StoryScriptResponse, StoryCharacter, CharacterBible
from app.config import get_config

def generate_mock_story_scenes(topic: str, scene_count: int = 5) -> StoryScriptResponse:
    """Tạo kịch bản mẫu cho chế độ kiểm thử (dry-run) mà không cần gọi API LLM thật."""
    mock_characters = [
        StoryCharacter(
            id="char_1",
            name="Minh",
            concept="Chàng trai trẻ yêu nhiếp ảnh và phố cổ Hà Nội",
            appearance_prompt="a 22-year-old young handsome Vietnamese man, short messy black hair, sharp dark eyes, wearing thin round glasses, gentle neutral expression",
            default_outfit="wearing a dark navy blue oversized hoodie and black cargo pants",
            voice_id="vi-VN-NamMinhNeural",
            face_plate="minh_face_plate.png",
            outfit_plate="minh_outfit_plate.png",
            pulid_weight=0.75,
            ipadapter_weight=0.50
        ),
        StoryCharacter(
            id="char_2",
            name="Linh",
            concept="Thiếu nữ Hà Thành thanh lịch, dịu dàng mùa thu",
            appearance_prompt="a 20-year-old beautiful Vietnamese young woman, shoulder-length brown hair with bangs, gentle warm eyes, soft smile",
            default_outfit="wearing an elegant beige trench coat over a white turtleneck sweater",
            voice_id="vi-VN-HoaiMyNeural",
            face_plate="linh_face_plate.png",
            outfit_plate="linh_outfit_plate.png",
            pulid_weight=0.75,
            ipadapter_weight=0.50
        )
    ]

    scenes: List[StoryScene] = [
        StoryScene(
            scene_id=1,
            narration=f"Buổi sớm bình yên mở ra câu chuyện: {topic}.",
            has_character=False,
            character_id="char_1",
            shot_type="wide environmental shot",
            action_prompt="misty morning sunbeams breaking through clouds over ancient rooftops",
            environment_prompt="peaceful city street with golden morning light and dew",
            camera_motion="zoom_in"
        ),
        StoryScene(
            scene_id=2,
            narration="Minh bước từng nhịp chậm rãi trên con đường rợp bóng cây quen thuộc.",
            has_character=True,
            character_id="char_1",
            shot_type="medium portrait shot",
            action_prompt="walking thoughtfully with a gentle smile looking into the distance",
            environment_prompt="tree-lined sidewalk with soft dappled sunlight and falling leaves",
            camera_motion="zoom_out"
        ),
        StoryScene(
            scene_id=3,
            narration="Từ phía góc phố, Linh vẫy tay chào với nụ cười rạng rỡ ấm áp.",
            has_character=True,
            character_id="char_2",
            shot_type="cowboy shot",
            action_prompt="waving hand warmly with cheerful expression",
            environment_prompt="charming vintage cafe storefront with flower pots and autumn decor",
            camera_motion="pan_right"
        ),
        StoryScene(
            scene_id=4,
            narration="Hương hoa sữa thoang thoảng trong làn gió se lạnh đầu mùa.",
            has_character=False,
            character_id="char_1",
            shot_type="extreme close-up shot",
            action_prompt="white blooming flowers swaying gently in cool autumn breeze",
            environment_prompt="close macro view of delicate blooming milk flowers with soft bokeh",
            camera_motion="zoom_in"
        ),
        StoryScene(
            scene_id=5,
            narration="Cả hai cùng bước tiếp, bắt đầu một ngày mới ngập tràn niềm vui và hy vọng.",
            has_character=True,
            character_id="char_1",
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
        characters=mock_characters,
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

PROVIDER_DEFAULTS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini"
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-2.0-flash"
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat"
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "default_model": "qwen2.5"
    },
    "mock": {
        "base_url": "",
        "default_model": "mock"
    }
}

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
    provider = (provider or cfg.llm_provider).lower()
    
    # 1. Chế độ Mock / Thử nghiệm
    if provider == "mock" or (not api_key and not cfg.llm_api_key and provider != "ollama"):
        logger.info("Sử dụng kịch bản phân cảnh mẫu (Mock Generator, không gọi API)...")
        return generate_mock_story_scenes(topic, scene_count=scene_count)

    prov_info = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["openai"])
    
    # Tự động gán base_url phù hợp nếu người dùng chưa chỉ định rõ
    if not base_url or (base_url == "https://api.openai.com/v1" and provider != "openai"):
        base_url = prov_info["base_url"]
    
    api_key = api_key or cfg.llm_api_key
    model = model or prov_info["default_model"]

    bible_path = Path(character_bible_path)
    bible = CharacterBible.from_json_file(bible_path)
    available_chars = list(bible.characters.keys())

    system_prompt = f"""
Bạn là đạo diễn hình ảnh và biên kịch phim hoạt hình AI chuyên nghiệp.
Nhiệm vụ của bạn là viết kịch bản phân cảnh và thiết kế nhân vật cho chủ đề: "{topic}".

QUY TẮC BẮT BUỘC:
1. Thiết kế nhân vật (characters): Tự động sáng tạo 1 đến 2 nhân vật phù hợp với chủ đề:
   - id: 'char_1', 'char_2'
   - name: Tên nhân vật (ví dụ: 'Minh', 'Linh', 'Phong', 'Mai'...)
   - concept: Concept tạo hình cốt lõi (ví dụ: 'Kiếm hiệp lãng tử', 'Cyberpunk hacker', 'Học sinh thanh xuân', 'Doanh nhân lịch lãm'...)
   - appearance_prompt: Mô tả khuôn mặt, kiểu tóc, mắt, nét mặt bằng TIẾNG ANH (không ghi trang phục)
   - default_outfit: Mô tả trang phục đặc trưng bằng TIẾNG ANH
   - voice_id: Chọn 'vi-VN-NamMinhNeural' (nam) hoặc 'vi-VN-HoaiMyNeural' (nữ)

2. Số lượng phân cảnh: chính xác {scene_count} phân cảnh (scene_id từ 1 đến {scene_count}).
3. Lời bình (narration): viết bằng tiếng Việt tự nhiên, truyền cảm. Tuyệt đối KHÔNG viết số (viết "ba" thay vì "3"), KHÔNG viết tắt để bộ đọc Edge-TTS phát âm chuẩn xác.
4. Tỷ lệ B-Roll: Khoảng 20% số phân cảnh (ít nhất 1 cảnh) phải đặt has_character = false để làm cảnh ngoại bối, đặc tả không gian/ánh sáng.
5. Tránh Identity Bleed: Mỗi phân cảnh có nhân vật (has_character = true) chỉ được chọn DUY NHẤT 1 nhân vật xuất hiện (character_id tương ứng là 'char_1' hoặc 'char_2'). Nếu hai nhân vật nói chuyện, hãy phân chia thành các cú máy quay luân phiên từng người.
6. Trường action_prompt: Chỉ mô tả hành động, biểu cảm, hướng nhìn bằng TIẾNG ANH. KHÔNG mô tả lại quần áo hay màu tóc của nhân vật vì hệ thống đã khóa tự động.
7. Trường environment_prompt: Mô tả bối cảnh, ánh sáng, thời tiết bằng TIẾNG ANH.
8. shot_type: Chọn một trong ["extreme close-up shot", "medium portrait shot", "cowboy shot", "wide environmental shot", "low angle dramatic shot"].
9. camera_motion: Chọn một trong ["zoom_in", "zoom_out", "pan_right"].

Trả về duy nhất định dạng JSON khớp với cấu trúc sau:
{{
  "title": "{topic}",
  "characters": [
    {{
      "id": "char_1",
      "name": "...",
      "concept": "...",
      "appearance_prompt": "...",
      "default_outfit": "...",
      "voice_id": "vi-VN-NamMinhNeural"
    }}
  ],
  "scenes": [
    {{
      "scene_id": 1,
      "narration": "...",
      "has_character": false,
      "character_id": "char_1",
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
    logger.info(f"Đang gửi yêu cầu sinh kịch bản tới LLM ({provider} / {model}) tại {endpoint}...")
    
    try:
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        status_code = resp.status_code if resp is not None else 0
        if status_code == 401:
            raise RuntimeError(
                f"Lỗi xác thực (401 Unauthorized) từ nhà cung cấp '{provider.upper()}'.\n"
                f"- Nếu bạn dùng API Key của Google Gemini, hãy chuyển Nhà cung cấp LLM sang 'gemini'.\n"
                f"- Nếu bạn dùng API Key của DeepSeek, hãy chuyển sang 'deepseek'.\n"
                f"- Nếu bạn chưa có API Key hoặc muốn thử nghiệm miễn phí, hãy chọn Nhà cung cấp là 'mock'."
            ) from http_err
        elif status_code == 404:
            raise RuntimeError(
                f"Endpoint không tìm thấy (404) tại {endpoint}. Kiểm tra lại tên model '{model}' hoặc đường dẫn API."
            ) from http_err
        else:
            raise RuntimeError(f"Lỗi gọi API {provider.upper()} ({status_code}): {resp.text}") from http_err
    except Exception as e:
        raise RuntimeError(f"Không thể kết nối tới LLM ({provider.upper()}): {e}") from e

    raw_content = resp.json()["choices"][0]["message"]["content"]
    parsed_json = _extract_json_from_text(raw_content)
    return StoryScriptResponse(**parsed_json)
