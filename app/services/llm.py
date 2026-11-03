import json
import re
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
import requests
from pydantic import BaseModel
from loguru import logger

from app.models.schema import (
    StoryScene,
    StoryScriptResponse,
    StoryCharacter,
    CharacterBible,
    MasterBeatSheet,
    ActBeat,
    ActScenesBatch
)
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


class TimeSharedKaggleDirector:
    """
    Điều phối việc vận hành mô hình ngôn ngữ lớn (Qwen-2.5-32B) trên Kaggle 2xT4,
    thực hiện phân bổ VRAM theo pha và giải phóng triệt để VRAM (evict) trước khi bàn giao cho ComfyUI.
    """
    def __init__(
        self,
        ollama_url: str,
        comfy_urls: List[str],
        model_name: str = "qwen2.5:32b-instruct-q4_K_M",
        bible_path: str = "resource/character_bible/characters.json"
    ):
        self.ollama_url = (ollama_url or "").rstrip("/")
        self.comfy_urls = [(u or "").rstrip("/") for u in comfy_urls if u]
        self.model_name = model_name
        bp = Path(bible_path)
        if bp.exists():
            with open(bp, "r", encoding="utf-8") as f:
                self.bible = json.load(f)
        else:
            self.bible = {"characters": {}}

    def free_comfyui_vram_before_llm(self):
        """
        Đảm bảo nếu trước đó ComfyUI đã chạy ở task cũ thì ép ComfyUI xả hết model khỏi VRAM
        trước khi nạp Qwen-2.5-32B lên 2 card T4.
        """
        for url in self.comfy_urls:
            try:
                requests.post(
                    f"{url}/free",
                    json={"unload_models": True, "free_memory": True},
                    timeout=10
                )
            except Exception as e:
                logger.warning(f"Không thể gọi /free trên ComfyUI {url}: {e}")
        time.sleep(1.5)

    def evict_llm_from_kaggle_vram(self):
        """
        BƯỚC QUAN TRỌNG NHẤT CỦA CHIẾN LƯỢC 1:
        Gửi keep_alive=0 để ép Ollama gỡ ngay lập tức trọng số Qwen-32B khỏi 2 GPU T4,
        nhường lại 100% VRAM (32GB) cho 2 instance ComfyUI bắt đầu vẽ ảnh.
        """
        logger.info("[VRAM Handover] Đang gửi lệnh giải phóng Qwen-32B khỏi VRAM Kaggle...")
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/generate",
                json={"model": self.model_name, "keep_alive": 0},
                timeout=30
            )
            resp.raise_for_status()
            # Đợi 2 giây để CUDA driver trên Kaggle thu hồi toàn bộ bộ nhớ
            time.sleep(2.0)
            logger.success("[VRAM Handover] Đã giải phóng hoàn toàn VRAM trên Kaggle! Sẵn sàng cho ComfyUI.")
        except Exception as e:
            logger.error(f"Lỗi khi giải phóng VRAM Ollama: {e}")

    def _call_ollama_structured(self, system_prompt: str, user_prompt: str, schema_model: type[BaseModel]) -> str:
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "format": schema_model.model_json_schema(),
            "options": {
                "temperature": 0.65,
                "num_ctx": 16384,      # Cửa sổ ngữ cảnh 16k đã được tối ưu bằng KV Cache q8_0
                "num_predict": 4096    # Đủ rộng cho 15 phân cảnh JSON trong 1 Hồi
            },
            "keep_alive": "15m"        # Giữ model trong VRAM xuyên suốt 5 vòng lặp Hồi
        }
        resp = requests.post(f"{self.ollama_url}/api/chat", json=payload, timeout=300)
        resp.raise_for_status()
        content = resp.json()["message"]["content"].strip()
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if m:
            content = m.group(1).strip()
        return content

    def generate_full_10min_script(self, topic: str, checkpoint_dir: Path) -> List[StoryScene]:
        """
        Điều phối sinh kịch bản 10 phút (~70 phân cảnh) qua 5 Hồi có lưu Checkpoint từng Hồi,
        sau đó tự động xả sạch VRAM trong khối finally.
        """
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        final_script_file = checkpoint_dir / "full_script_checkpoint.json"

        # Nếu kịch bản đã được sinh thành công ở lần chạy trước thì đọc luôn từ ổ cứng
        if final_script_file.exists():
            logger.info("[Checkpoint] Đã tìm thấy kịch bản hoàn chỉnh trên máy Local, bỏ qua Pha LLM.")
            raw_list = json.loads(final_script_file.read_text(encoding="utf-8"))
            return [StoryScene.model_validate(item) for item in raw_list]

        # Giải phóng VRAM của ComfyUI (nếu có từ phiên trước) trước khi load LLM 32B
        self.free_comfyui_vram_before_llm()

        all_scenes: List[StoryScene] = []
        char_summary = json.dumps(self.bible.get("characters", {}), ensure_ascii=False)

        try:
            # -----------------------------------------------------------------
            # BƯỚC 1: LẬP ĐỀ CƯƠNG 5 HỒI (MASTER BEAT SHEET)
            # -----------------------------------------------------------------
            logger.info(f"[Pha 1 - LLM 32B] Đang lập cấu trúc 5 Hồi (Beat Sheet) cho chủ đề: '{topic}'...")
            beat_sys = (
                "Bạn là Đạo diễn Điện ảnh AI. Hãy thiết kế cấu trúc kịch bản 10 phút gồm đúng 5 Hồi (Acts). "
                "Mỗi Hồi phải có một không gian cố định (location_anchor) và ánh sáng cố định (lighting_anchor) bằng tiếng Anh."
            )
            beat_user = f"Chủ đề câu chuyện: {topic}\nDanh sách nhân vật: {char_summary}"
            beat_json = self._call_ollama_structured(beat_sys, beat_user, MasterBeatSheet)
            beat_sheet = MasterBeatSheet.model_validate_json(beat_json)
            (checkpoint_dir / "master_beat_sheet.json").write_text(beat_sheet.model_dump_json(indent=2), encoding="utf-8")
            logger.success(f"Đã tạo xong Beat Sheet: '{beat_sheet.video_title}' ({len(beat_sheet.acts)} Hồi)")

            # -----------------------------------------------------------------
            # BƯỚC 2: TRIỂN KHAI CHI TIẾT TỪNG HỒI VỚI ROLLING CONTEXT
            # -----------------------------------------------------------------
            global_scene_counter = 1
            available_char_keys = list(self.bible.get("characters", {}).keys()) or ["char_1", "char_2"]
            for act in beat_sheet.acts:
                act_ckpt = checkpoint_dir / f"act_{act.act_id:02d}_scenes.json"
                if act_ckpt.exists():
                    logger.info(f"[Checkpoint] Đọc lại Hồi {act.act_id} từ cache...")
                    act_batch = ActScenesBatch.model_validate_json(act_ckpt.read_text(encoding="utf-8"))
                else:
                    logger.info(f"[Pha 1 - LLM 32B] Đang đạo diễn chi tiết Hồi {act.act_id}/{len(beat_sheet.acts)}: '{act.act_title}'...")
                    # Lấy 3 phân cảnh cuối của Hồi trước làm Rolling Context
                    rolling_tail = [s.model_dump() for s in all_scenes[-3:]] if all_scenes else []

                    act_sys = f"""
                    Bạn là Đạo diễn Hình ảnh & Biên kịch. Hãy viết chi tiết {act.target_scenes} phân cảnh cho Hồi {act.act_id}.
                    QUY TẮC BẮT BUỘC:
                    1. Bối cảnh cố định của Hồi này: "{act.location_anchor}".
                    2. Ánh sáng cố định của Hồi này: "{act.lighting_anchor}".
                       -> Mọi trường `environment_prompt` trong Hồi này PHẢI giữ nguyên không gian và ánh sáng trên!
                    3. Quy tắc Shot-Reverse-Shot: Mỗi cảnh chỉ có TỐI ĐA 1 nhân vật (`character_id` là một trong {available_char_keys}).
                       Khi 2 nhân vật đối thoại, hãy cắt cảnh luân phiên giữa 2 người.
                    4. Đặt `has_character = false` cho khoảng 20% số cảnh để làm cảnh B-Roll đặc tả không gian/đồ vật.
                    5. Lời bình `narration` bằng tiếng Việt tự nhiên, mọi con số phải viết bằng chữ.
                    """
                    act_user = (
                        f"Tóm tắt Hồi {act.act_id}: {act.plot_summary}\n"
                        f"3 phân cảnh cuối của Hồi trước (để nối tiếp mạch truyện): {json.dumps(rolling_tail, ensure_ascii=False)}"
                    )

                    batch_json = self._call_ollama_structured(act_sys, act_user, ActScenesBatch)
                    act_batch = ActScenesBatch.model_validate_json(batch_json)
                    act_ckpt.write_text(act_batch.model_dump_json(indent=2), encoding="utf-8")

                # Đánh lại số thứ tự scene_id liên tục từ 1 đến ~70
                for sc in act_batch.scenes:
                    sc.scene_id = global_scene_counter
                    global_scene_counter += 1
                    all_scenes.append(sc)

            # Lưu toàn bộ kịch bản hoàn chỉnh xuống ổ cứng Local
            final_script_file.write_text(
                json.dumps([s.model_dump() for s in all_scenes], ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            logger.success(f"Hoàn tất kịch bản 10 phút với tổng cộng {len(all_scenes)} phân cảnh đồng nhất!")
            return all_scenes

        finally:
            # -----------------------------------------------------------------
            # BƯỚC 3: LUÔN LUÔN XẢ SẠCH VRAM TRƯỚC KHI CHUYỂN SANG COMFYUI
            # -----------------------------------------------------------------
            self.evict_llm_from_kaggle_vram()

    def generate_full_10min_story(self, topic: str, checkpoint_dir: Path) -> StoryScriptResponse:
        """Sinh StoryScriptResponse hoàn chỉnh sẵn sàng cho pipeline."""
        scenes = self.generate_full_10min_script(topic, checkpoint_dir)
        title = topic
        sheet_file = checkpoint_dir / "master_beat_sheet.json"
        if sheet_file.exists():
            try:
                sheet = MasterBeatSheet.model_validate_json(sheet_file.read_text(encoding="utf-8"))
                title = sheet.video_title or topic
            except Exception:
                pass
        chars = []
        if "characters" in self.bible:
            for cid, cdata in self.bible["characters"].items():
                chars.append(
                    StoryCharacter(
                        id=cid,
                        name=cdata.get("name", cid),
                        concept=cdata.get("concept", "Nhân vật chính"),
                        appearance_prompt=cdata.get("appearance_trigger", ""),
                        default_outfit=cdata.get("default_outfit", ""),
                        voice_id=cdata.get("voice_id", "vi-VN-NamMinhNeural"),
                        face_plate=cdata.get("face_plate"),
                        outfit_plate=cdata.get("outfit_plate"),
                        pulid_weight=cdata.get("pulid_weight", 0.75),
                        ipadapter_weight=cdata.get("ipadapter_weight", 0.50)
                    )
                )
        return StoryScriptResponse(
            title=title,
            characters=chars,
            scenes=scenes
        )
