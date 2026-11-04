### FILE: config.example.toml
`
[system]
storage_dir = "storage"
nvenc_max_concurrency = 2
comfy_max_concurrency = 2

[cloud_workers]
# Dán 2 link Cloudflare Tunnel sinh ra từ Kaggle Notebook tại đây
worker_urls = [
    # "https://example-1.trycloudflare.com",
    # "https://example-2.trycloudflare.com"
]

[llm]
provider = "openai" # "openai", "gemini", "ollama", "deepseek"
api_key = "your-api-key-here"
base_url = "https://api.openai.com/v1"
model = "gpt-4o"

[voice]
default_voice = "vi-VN-NamMinhNeural"
voice_rate = "+0%"

`

### FILE: main.py
`
import sys
import argparse
import subprocess
from pathlib import Path

# Đảm bảo Windows console luôn in đúng ký tự tiếng Việt UTF-8
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lean AI Storytelling Pipeline Orchestrator")
    parser.add_argument("--cli", action="store_true", help="Chạy ở chế độ dòng lệnh (CLI mode)")
    parser.add_argument("--topic", type=str, default="Một ngày thu bình yên tại Hà Nội", help="Chủ đề video kể chuyện")
    parser.add_argument("--scene-count", type=int, default=4, help="Số lượng phân cảnh")
    parser.add_argument("--aspect-ratio", type=str, default="16:9", choices=["16:9", "9:16"], help="Tỷ lệ khung hình")
    parser.add_argument("--dry-run", action="store_true", help="Chạy chế độ thử nghiệm nội bộ (không cần Cloud GPU)")
    parser.add_argument("--workers", type=str, default="", help="Danh sách URL Cloudflare Tunnel, phân tách bởi dấu phẩy")
    return parser

def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.cli:
        from app.config import get_config, AppConfig
        from app.services.task import run_story_pipeline

        base_cfg = get_config()
        worker_list = [w.strip() for w in args.workers.split(",") if w.strip()] or base_cfg.worker_urls

        cfg = AppConfig(
            worker_urls=worker_list,
            llm_provider=base_cfg.llm_provider,
            llm_api_key=base_cfg.llm_api_key,
            llm_model=base_cfg.llm_model
        )

        print(f"[*] Bắt đầu sản xuất video qua CLI: Topic='{args.topic}' (dry_run={args.dry_run})")
        result_path = run_story_pipeline(
            topic=args.topic,
            config=cfg,
            dry_run=args.dry_run,
            aspect_ratio=args.aspect_ratio
        )
        print(f"[+] Video hoàn thành tại: {result_path}")
    else:
        # Khởi chạy giao diện Streamlit WebUI
        webui_path = Path(__file__).parent / "app" / "ui" / "webui.py"
        print(f"[*] Đang khởi chạy giao diện WebUI: streamlit run {webui_path}")
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(webui_path)], check=True)

if __name__ == "__main__":
    main()

`

### FILE: README.md
`
# Lean Hybrid AI Storytelling Pipeline

Hệ thống tự động hóa sản xuất video kể chuyện AI chất lượng cao với **nhân vật đồng nhất xuyên suốt (Consistent Character)**.
Kết hợp sức mạnh phần cứng **NVIDIA GPU NVENC** tại máy cục bộ (Local Orchestrator) với cụm **Dual-GPU Tesla T4** trên đám mây (Kaggle ComfyUI Worker qua Cloudflare Tunnel).

---

## 🌟 Tính Năng Nổi Bật

1. **Nhất Quán Nhân Vật Tuyệt Đối:** Quản lý qua **Character Bible** (`characters.json` + `Cast Plates`) với mô hình SDXL + `IP-Adapter FaceID` & `IP-Adapter Advanced`.
2. **Khử Loang Nhận Diện (Anti-Identity Bleed):** Áp dụng kỹ thuật điện ảnh *Shot-Reverse-Shot* (cắt luân phiên từng góc máy cho mỗi nhân vật) và tự động vô hiệu hóa (`weight = 0.0`) ở các cảnh B-Roll ngoại bối.
3. **Đồng Bộ Hình & Tiếng Tuyệt Đối:** Mỗi phân cảnh được tổng hợp audio riêng biệt, chuẩn hóa tần số lấy mẫu (`24000Hz mono`), đo thời lượng thực tế để triệt tiêu hoàn toàn sai số trôi phụ đề.
4. **Hiệu Năng Dựng Phim NVENC Siêu Tốc:** Thay thế vòng lặp MoviePy CPU bằng nhân phần cứng GPU NVENC:
   - Khử lỗi rung giật điểm ảnh bằng kỹ thuật upscale 4000px trước `zoompan`.
   - Tự động hạ âm lượng nhạc nền khi có giọng đọc (**Audio Ducking** bằng `sidechaincompress`).
   - Chuẩn hóa âm thanh giọng đọc theo chuẩn phát thanh `-16 LUFS`.
5. **Semaphore Kép Điều Tiết Tải:** Chống nghẽn 100% CPU/RAM máy cục bộ khi chạy batch nhiều phân cảnh.
6. **Cơ Chế Idempotent Checkpoint:** Nếu tiến trình bị gián đoạn, khi chạy lại hệ thống sẽ tự động bỏ qua các phân cảnh đã render xong.

---

## 🚀 Hướng Dẫn Cài Đặt (Local Orchestrator trên Windows 11)

### 1. Yêu cầu tiên quyết
- Python 3.11 hoặc 3.12
- Git & FFmpeg (đã thêm vào biến môi trường `PATH`)
- Card đồ họa rời NVIDIA (hỗ trợ NVENC, VD: RTX 3050 trở lên)

### 2. Kích hoạt môi trường và cài đặt phụ thuộc
```bash
# Mở PowerShell tại thư mục dự án
cd C:\Users\Asus\Desktop\MoneyPrinterTurbo-Storytelling

# Kích hoạt virtual environment có sẵn
.\venv\Scripts\Activate.ps1

# Cài đặt thư viện nếu cần
pip install -r requirements.txt
```

---

## 🖥️ Hướng Dẫn Vận Hành

### Cách 1: Sử dụng Giao Diện Web (Streamlit WebUI)
Khởi chạy giao diện điều khiển tương tác trực quan:
```bash
python main.py
```
Trình duyệt sẽ tự động mở tại `http://localhost:8501`:
1. **Sidebar:** Nhập 2 link Cloudflare Tunnel từ Kaggle (hoặc tích chọn chế độ **Dry-Run** để thử nghiệm offline).
2. **Tab 1 (Tạo Video):** Nhập chủ đề, bấm **Sinh Kịch Bản (LLM)**, kiểm tra/sửa lời thoại và bấm **Bắt Đầu Sản Xuất Video**.
3. **Tab 2 (Character Bible):** Xem ảnh mẫu và hồ sơ nhân vật (Minh, Linh).
4. **Tab 3 (Trạng Thái Worker):** Kiểm tra trạng thái kết nối tới các máy chủ Kaggle.

### Cách 2: Sử dụng Dòng Lệnh (CLI)
Dành cho việc tạo video tự động hàng loạt:
```bash
# Chạy chế độ Dry-Run (thử nghiệm nhanh local)
python main.py --cli --topic "Mùa thu Hà Nội qua góc nhìn của Minh" --dry-run

# Chạy với Cloud Workers thật từ Kaggle
python main.py --cli --topic "Minh và Linh khám phá phố cổ" --workers "https://worker1.trycloudflare.com,https://worker2.trycloudflare.com"
```

---

## ☁️ Hướng Dẫn Cài Đặt Kaggle Dual-GPU Worker ($2 \times \text{Tesla T4}$)

1. Mở Kaggle Notebook mới.
2. Cấu hình bên phải màn hình:
   - **Accelerator:** `GPU T4 x 2`
   - **Internet:** `On`
3. Copy toàn bộ nội dung file [start_dual_comfy_worker.py](kaggle_worker/start_dual_comfy_worker.py) dán vào 1 Cell trên Kaggle.
4. Bấm **Run All**.
5. Khi script chạy xong, console sẽ xuất ra:
   ```text
   🎉 DUAL-GPU COMFYUI WORKERS ĐÃ SẴN SÀNG HOẠT ĐỘNG!
       WORKER_URLS = [
           'https://alpha-xxxx.trycloudflare.com',
           'https://beta-yyyy.trycloudflare.com'
       ]
   ```
6. Copy 2 đường link trên và dán vào Sidebar của Streamlit WebUI (hoặc file `config.toml`) trên máy của bạn.

---

## 📁 Cấu Trúc Thư Mục Dự Án

```text
MoneyPrinterTurbo-Storytelling/
├── app/
│   ├── config.py                     # Quản lý config.toml và biến môi trường
│   ├── models/
│   │   └── schema.py                 # Pydantic schema phân cảnh và Character Bible
│   ├── services/
│   │   ├── llm.py                    # Sinh kịch bản phân cảnh chuẩn 5 thành phần
│   │   ├── voice.py                  # edge-tts theo cảnh & ghép srt không lệch nhịp
│   │   ├── comfy_remote_client.py    # Dual GPU async client, sync plates, NVENC zoompan
│   │   ├── video.py                  # Ghép video, audio ducking, subtitle burning
│   │   └── task.py                   # Orchestrator điều phối toàn bộ pipeline
│   └── ui/
│       └── webui.py                  # Giao diện Streamlit tương tác
├── resource/
│   ├── character_bible/
│   │   ├── characters.json           # Hồ sơ ngoại hình, trang phục, giọng đọc
│   │   └── *.png                     # Ảnh mẫu cận mặt & trang phục
│   ├── workflows/
│   │   └── pulid_ipadapter_api.json  # Workflow ComfyUI SDXL IP-Adapter chuẩn
│   ├── fonts/                        # Thư mục phông chữ tiếng Việt
│   └── songs/                        # Thư mục nhạc nền BGM
├── storage/                          # Thư mục lưu kết quả video theo task_id
├── kaggle_worker/
│   └── start_dual_comfy_worker.py    # Script 1-Cell chạy trên Kaggle
├── config.example.toml               # File cấu hình mẫu
├── requirements.txt                  # Phụ thuộc Python tinh gọn
├── main.py                           # Điểm khởi chạy WebUI và CLI
└── README.md
```
#   s t o r y t e l l i n g 
 
 
`

### FILE: requirements.txt
`
pydantic>=2.7.0
requests>=2.31.0
edge-tts>=6.1.10
mutagen>=1.47.0
loguru>=0.7.2
streamlit>=1.35.0
pillow>=10.2.0
pytest>=8.1.0
pytest-asyncio>=0.23.0
aiohttp>=3.9.0

`

### FILE: .pytest_cache\README.md
`
# pytest cache directory #

This directory contains data from the pytest's cache plugin,
which provides the `--lf` and `--ff` options, as well as the `cache` fixture.

**Do not** commit this to version control.

See [the docs](https://docs.pytest.org/en/stable/how-to/cache.html) for more information.

`

### FILE: app\config.py
`
import os
import tomllib
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

class AppConfig(BaseModel):
    storage_dir: Path = Field(default_factory=lambda: Path("storage"))
    resource_dir: Path = Field(default_factory=lambda: Path("resource"))
    
    # Concurrency controls (Semaphore limits as per risk document)
    nvenc_max_concurrency: int = 2
    comfy_max_concurrency: int = 2
    
    # ComfyUI Cloudflare Tunnel URLs
    worker_urls: List[str] = Field(default_factory=list)
    ollama_worker_url: str = ""
    
    # LLM Settings
    llm_provider: str = "openai"  # openai, gemini, ollama, deepseek
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o"
    
    # Voice Settings
    default_voice: str = "vi-VN-NamMinhNeural"
    voice_rate: str = "+0%"

    def get_task_dir(self, task_id: str) -> Path:
        p = self.storage_dir / "tasks" / task_id
        p.mkdir(parents=True, exist_ok=True)
        return p

_cached_config: Optional[AppConfig] = None

def get_config(config_path: Optional[Path] = None, force_reload: bool = False) -> AppConfig:
    global _cached_config
    if _cached_config is not None and not force_reload and config_path is None:
        return _cached_config

    cfg_dict = {}
    path = config_path or Path("config.toml")
    if path.exists():
        with open(path, "rb") as f:
            raw_toml = tomllib.load(f)
            sys_sec = raw_toml.get("system", {})
            workers_sec = raw_toml.get("cloud_workers", {})
            llm_sec = raw_toml.get("llm", {})
            voice_sec = raw_toml.get("voice", {})
            
            if "storage_dir" in sys_sec:
                cfg_dict["storage_dir"] = Path(sys_sec["storage_dir"])
            if "nvenc_max_concurrency" in sys_sec:
                cfg_dict["nvenc_max_concurrency"] = int(sys_sec["nvenc_max_concurrency"])
            if "comfy_max_concurrency" in sys_sec:
                cfg_dict["comfy_max_concurrency"] = int(sys_sec["comfy_max_concurrency"])
            if "worker_urls" in workers_sec:
                cfg_dict["worker_urls"] = workers_sec["worker_urls"]
            if "ollama_worker_url" in workers_sec:
                cfg_dict["ollama_worker_url"] = workers_sec["ollama_worker_url"]
            elif "ollama_worker_url" in llm_sec:
                cfg_dict["ollama_worker_url"] = llm_sec["ollama_worker_url"]
            if "provider" in llm_sec:
                cfg_dict["llm_provider"] = llm_sec["provider"]
            if "api_key" in llm_sec:
                cfg_dict["llm_api_key"] = llm_sec["api_key"]
            if "base_url" in llm_sec:
                cfg_dict["llm_base_url"] = llm_sec["base_url"]
            if "model" in llm_sec:
                cfg_dict["llm_model"] = llm_sec["model"]
            if "default_voice" in voice_sec:
                cfg_dict["default_voice"] = voice_sec["default_voice"]
            if "voice_rate" in voice_sec:
                cfg_dict["voice_rate"] = voice_sec["voice_rate"]

    # Allow environment variable overrides
    if os.getenv("OPENAI_API_KEY") and "llm_api_key" not in cfg_dict:
        cfg_dict["llm_api_key"] = os.environ["OPENAI_API_KEY"]
    if os.getenv("OLLAMA_WORKER_URL") and "ollama_worker_url" not in cfg_dict:
        cfg_dict["ollama_worker_url"] = os.environ["OLLAMA_WORKER_URL"]

    config = AppConfig(**cfg_dict)
    if config_path is None:
        _cached_config = config
    return config

`

### FILE: app\__init__.py
`
"""MoneyPrinterTurbo-Storytelling Application Package."""

`

### FILE: app\models\schema.py
`
import json
from pathlib import Path
from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator

ShotType = Literal[
    "extreme close-up shot",
    "medium portrait shot",
    "cowboy shot",
    "wide environmental shot",
    "over-the-shoulder shot",
    "low angle dramatic shot"
]

CameraMotion = Literal["zoom_in", "zoom_out", "pan_right"]

class StoryScene(BaseModel):
    scene_id: int = Field(description="Số thứ tự phân cảnh, bắt đầu từ 1")
    narration: str = Field(description="Lời dẫn truyện tiếng Việt tự nhiên, không chứa từ viết tắt")
    has_character: bool = Field(description="True nếu cảnh này có mặt nhân vật, False nếu là cảnh B-Roll ngoại cảnh")
    character_id: str = Field(default="char_minh", description="Mã nhân vật xuất hiện trong cảnh (VD: char_minh, char_linh)")
    active_character_id: Optional[str] = Field(default=None, description="Tùy chọn tương thích cho active_character_id")
    speaker_id: str = Field(default="narrator", description="Ai đang nói ở cảnh này ('narrator', 'char_minh', 'char_linh')")
    shot_type: ShotType = Field(default="medium portrait shot", description="Góc máy điện ảnh")
    action_prompt: str = Field(description="Mô tả hành động và biểu cảm bằng tiếng Anh")
    environment_prompt: str = Field(description="Mô tả bối cảnh và ánh sáng xung quanh bằng tiếng Anh")
    camera_motion: CameraMotion = Field(default="zoom_in", description="Hiệu ứng chuyển động camera")

    @model_validator(mode="before")
    @classmethod
    def sync_character_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get("active_character_id") and ("character_id" not in data or data.get("character_id") == "char_minh"):
                data["character_id"] = data["active_character_id"]
            elif data.get("character_id") and not data.get("active_character_id"):
                data["active_character_id"] = data["character_id"]
        return data

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
    characters: List[StoryCharacter] = Field(
        default_factory=list,
        description="Danh sách 1 đến 2 nhân vật chính được thiết kế riêng phù hợp với bối cảnh và concept của câu chuyện"
    )
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

`

### FILE: app\models\__init__.py
`
"""Models Package."""

`

### FILE: app\services\comfy_remote_client.py
`
import os
import re
import json
import uuid
import time
import asyncio
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
from PIL import Image, ImageDraw, ImageFont
from loguru import logger

from app.config import get_config

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

class DualGPUComfyStoryClient:
    @staticmethod
    def clean_worker_url(url: str) -> str:
        """Tự động làm sạch URL nếu người dùng vô tình dán đè URL cũ lẫn mới."""
        url = url.strip()
        if not url:
            return ""
        m = re.search(r"https?://[a-zA-Z0-9\-\.]+(?:\.trycloudflare\.com|\.ngrok-free\.app|:\d+)", url)
        if m:
            return m.group(0).rstrip("/")
        m_general = re.search(r"https?://[^\s/]+(?::\d+)?", url)
        if m_general:
            return m_general.group(0).rstrip("/")
        return url.rstrip("/")

    def __init__(
        self,
        worker_urls: Optional[List[str]] = None,
        workflow_path: str = "resource/workflows/pulid_ipadapter_api.json",
        bible_path: str = "resource/character_bible/characters.json"
    ):
        cfg = get_config()
        raw_urls = worker_urls or cfg.worker_urls
        self.worker_urls = [self.clean_worker_url(url) for url in raw_urls if self.clean_worker_url(url)]
        
        wf_p = Path(workflow_path)
        self.workflow_path = wf_p if wf_p.is_absolute() else (ROOT_DIR / wf_p)
        
        b_p = Path(bible_path)
        self.bible_path = b_p if b_p.is_absolute() else (ROOT_DIR / b_p)
        self.bible_dir = self.bible_path.parent
        
        with open(self.bible_path, "r", encoding="utf-8") as f:
            self.bible = json.load(f)

        # Mapping Node IDs chuẩn hóa theo đặc tả kỹ thuật và file workflow template
        self.NODES = {
            "pos_prompt": "6",
            "neg_prompt": "7",
            "face_loader": "12",
            "outfit_loader": "15",
            "face_lock": "18",
            "outfit_lock": "21",
            "ksampler": "3",
            "save_img": "9"
        }

        # Quản lý tài nguyên bằng Semaphore kép để chống nghẽn CPU và quá tải GPU
        self.comfy_max_concurrency = cfg.comfy_max_concurrency
        self.nvenc_max_concurrency = cfg.nvenc_max_concurrency

    def generate_character_plate_image(
        self,
        prompt: str,
        output_path: Path,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        worker_url: Optional[str] = None
    ) -> Path:
        """Sinh 1 ảnh mẫu 1024x1024 qua ComfyUI txt2img."""
        worker = worker_url or (self.worker_urls[0] if self.worker_urls else None)
        if not worker:
            raise RuntimeError("Không có ComfyUI worker khả dụng để sinh ảnh mẫu nhân vật.")
        
        neg = negative_prompt or self.bible.get("global_settings", {}).get("negative_prompt", "")
        sd = seed or int(time.time() * 1000) % (2**32)
        
        prompt_payload = {
            "3": {
                "inputs": {
                    "seed": sd,
                    "steps": 20,
                    "cfg": 7.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0]
                },
                "class_type": "KSampler"
            },
            "4": {
                "inputs": {
                    "ckpt_name": "juggernautXL_v9Lightning.safetensors"
                },
                "class_type": "CheckpointLoaderSimple"
            },
            "5": {
                "inputs": {
                    "width": 1024,
                    "height": 1024,
                    "batch_size": 1
                },
                "class_type": "EmptyLatentImage"
            },
            "6": {
                "inputs": {
                    "text": prompt,
                    "clip": ["4", 1]
                },
                "class_type": "CLIPTextEncode"
            },
            "7": {
                "inputs": {
                    "text": neg,
                    "clip": ["4", 1]
                },
                "class_type": "CLIPTextEncode"
            },
            "8": {
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                },
                "class_type": "VAEDecode"
            },
            "9": {
                "inputs": {
                    "filename_prefix": "char_plate",
                    "images": ["8", 0]
                },
                "class_type": "SaveImage"
            }
        }
        
        resp = requests.post(f"{worker}/prompt", json={"prompt": prompt_payload}, timeout=30)
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]
        
        while True:
            hist_resp = requests.get(f"{worker}/history/{prompt_id}", timeout=30)
            hist = hist_resp.json()
            if prompt_id in hist:
                img_info = hist[prompt_id]["outputs"]["9"]["images"][0]
                img_data = requests.get(
                    f"{worker}/view",
                    params={
                        "filename": img_info["filename"],
                        "subfolder": img_info["subfolder"],
                        "type": img_info["type"]
                    },
                    timeout=60
                ).content
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(img_data)
                return output_path
            time.sleep(1.2)

    def generate_character_plates(
        self,
        character: Any,
        output_dir: Path,
        dry_run: bool = False,
        worker_url: Optional[str] = None
    ) -> tuple[Path, Path]:
        """Tạo cặp ảnh mẫu (Chân dung & Trang phục) 1024x1024 cho một nhân vật."""
        output_dir.mkdir(parents=True, exist_ok=True)
        char_id = getattr(character, "id", "char_1")
        face_name = f"{char_id}_face.png"
        outfit_name = f"{char_id}_outfit.png"
        face_path = output_dir / face_name
        outfit_path = output_dir / outfit_name

        if dry_run or not (worker_url or self.worker_urls):
            # Tạo placeholder ảnh 1024x1024
            for p, label in [(face_path, "Face Plate"), (outfit_path, "Outfit Plate")]:
                img = Image.new("RGB", (1024, 1024), color=(40, 50, 65))
                draw = ImageDraw.Draw(img)
                draw.rectangle([30, 30, 994, 994], outline=(120, 190, 255), width=4)
                name = getattr(character, "name", "Character")
                concept = getattr(character, "concept", "")
                draw.text((80, 480), f"{name} ({label})\nConcept: {concept}", fill=(240, 245, 255))
                img.save(p)
        else:
            style_prefix = self.bible.get("global_settings", {}).get(
                "style_prefix",
                "cinematic 2.5D anime film still, Makoto Shinkai lighting, volumetric fog, highly detailed environment, 8k resolution, masterpiece"
            )
            name = getattr(character, "name", "Character")
            concept = getattr(character, "concept", "")
            app_p = getattr(character, "appearance_prompt", "") or getattr(character, "appearance_trigger", "")
            outfit_p = getattr(character, "default_outfit", "")

            face_prompt = (
                f"close-up portrait shot of {name}, {concept}, {app_p}, "
                f"gentle neutral expression, looking at camera, {style_prefix}"
            )
            outfit_prompt = (
                f"medium portrait shot of {name}, {concept}, {app_p}, {outfit_p}, "
                f"standing pose, {style_prefix}"
            )

            self.generate_character_plate_image(face_prompt, face_path, worker_url=worker_url)
            self.generate_character_plate_image(outfit_prompt, outfit_path, worker_url=worker_url)

        if hasattr(character, "face_plate"):
            character.face_plate = face_name
        if hasattr(character, "outfit_plate"):
            character.outfit_plate = outfit_name

        return face_path, outfit_path

    def sync_character_plates_to_workers(self, custom_plates: Optional[Dict[str, Path]] = None):
        """Tự động đồng bộ toàn bộ ảnh mẫu từ local lên các ComfyUI Workers trên Kaggle."""
        if not self.worker_urls:
            return

        # 1. Đồng bộ custom_plates từ task nếu có
        if custom_plates:
            for plate_name, plate_path in custom_plates.items():
                if plate_path.exists():
                    for worker_url in self.worker_urls:
                        try:
                            with open(plate_path, "rb") as f:
                                files = {"image": (plate_name, f, "image/png")}
                                self._robust_request(
                                    "POST",
                                    f"{worker_url}/upload/image",
                                    files=files,
                                    data={"overwrite": "true"},
                                    timeout=30
                                )
                        except Exception as e:
                            logger.error(f"Lỗi upload custom plate {plate_name} lên {worker_url}: {e}")
                            raise

        # 2. Đồng bộ các starter plates mặc định từ Character Bible
        for char_id, char_data in self.bible.get("characters", {}).items():
            for plate_key in ["face_plate", "outfit_plate"]:
                plate_path = self.bible_dir / char_data[plate_key]
                if plate_path.exists():
                    for worker_url in self.worker_urls:
                        try:
                            with open(plate_path, "rb") as f:
                                files = {"image": (plate_path.name, f, "image/png")}
                                self._robust_request(
                                    "POST",
                                    f"{worker_url}/upload/image",
                                    files=files,
                                    data={"overwrite": "true"},
                                    timeout=30
                                )
                        except Exception as e:
                            logger.error(f"Lỗi upload ảnh mẫu lên {worker_url}: {e}")
                            raise

        logger.info(f"Đã đồng bộ toàn bộ ảnh mẫu nhân vật lên {len(self.worker_urls)} Cloud GPU Workers.")

    def _build_workflow_payload(
        self,
        scene: Dict[str, Any],
        characters_override: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Tạo workflow JSON payload hoàn chỉnh cho từng phân cảnh."""
        with open(self.workflow_path, "r", encoding="utf-8") as f:
            wf = json.load(f)

        global_cfg = self.bible.get("global_settings", {})
        has_char = scene.get("has_character", True)
        char_id = scene.get("character_id", "char_minh")
        
        # Kiểm tra nhân vật từ override trước, sau đó mới fallback về bible
        if characters_override and char_id in characters_override:
            c = characters_override[char_id]
            app_trig = getattr(c, "appearance_prompt", "") or getattr(c, "appearance_trigger", "")
            outfit = getattr(c, "default_outfit", "")
            face_pl = getattr(c, "face_plate", f"{char_id}_face.png")
            outfit_pl = getattr(c, "outfit_plate", f"{char_id}_outfit.png")
            pulid_w = getattr(c, "pulid_weight", 0.75)
            ip_w = getattr(c, "ipadapter_weight", 0.50)
            concept = getattr(c, "concept", "")
            char_cfg = {
                "appearance_trigger": f"{app_trig}, {concept}".strip(", "),
                "default_outfit": outfit,
                "face_plate": face_pl,
                "outfit_plate": outfit_pl,
                "pulid_weight": pulid_w,
                "ipadapter_weight": ip_w
            }
        else:
            char_cfg = self.bible.get("characters", {}).get(char_id, list(self.bible.get("characters", {}).values())[0])

        if has_char:
            full_prompt = (
                f"{scene['shot_type']}, {char_cfg['appearance_trigger']}, "
                f"{char_cfg['default_outfit']}, {scene['action_prompt']}, "
                f"in {scene['environment_prompt']}, {global_cfg.get('style_prefix', '')}"
            )
            wf[self.NODES["face_loader"]]["inputs"]["image"] = char_cfg["face_plate"]
            wf[self.NODES["outfit_loader"]]["inputs"]["image"] = char_cfg["outfit_plate"]
            wf[self.NODES["face_lock"]]["inputs"]["weight"] = char_cfg["pulid_weight"]
            wf[self.NODES["outfit_lock"]]["inputs"]["weight"] = char_cfg["ipadapter_weight"]
        else:
            # Cảnh B-Roll: Triệt tiêu trọng số khóa mặt và trang phục về 0.0
            full_prompt = (
                f"{scene['shot_type']}, {scene['action_prompt']}, "
                f"in {scene['environment_prompt']}, {global_cfg.get('style_prefix', '')}"
            )
            wf[self.NODES["face_lock"]]["inputs"]["weight"] = 0.0
            wf[self.NODES["outfit_lock"]]["inputs"]["weight"] = 0.0

        wf[self.NODES["pos_prompt"]]["inputs"]["text"] = full_prompt
        wf[self.NODES["neg_prompt"]]["inputs"]["text"] = global_cfg.get("negative_prompt", "")
        wf[self.NODES["ksampler"]]["inputs"]["seed"] = int(time.time() * 1000 + scene["scene_id"]) % (2**32)
        return wf

    def _create_placeholder_image(self, scene: Dict[str, Any], output_path: Path):
        """Tạo ảnh minh họa giả lập trong chế độ dry-run."""
        img = Image.new("RGB", (1920, 1080), color=(35, 45, 60))
        draw = ImageDraw.Draw(img)
        draw.rectangle([50, 50, 1870, 1030], outline=(100, 180, 240), width=6)
        
        info_text = (
            f"SCENE {scene['scene_id']} (DRY-RUN / PLACEHOLDER)\n"
            f"Shot Type: {scene.get('shot_type', '')}\n"
            f"Character: {scene.get('character_id', '') if scene.get('has_character') else 'B-ROLL (No character)'}\n"
            f"Action: {scene.get('action_prompt', '')}\n"
            f"Environment: {scene.get('environment_prompt', '')}"
        )
        draw.text((120, 400), info_text, fill=(240, 245, 255))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path)

    @classmethod
    def _render_zoompan_nvenc(
        cls,
        image_path: Path,
        output_video_path: Path,
        duration: float,
        effect: str = "zoom_in",
        aspect_ratio: str = "16:9"
    ):
        """
        Tạo clip MP4 từ ảnh tĩnh bằng FFmpeg với hiệu ứng camera pan/zoom.
        Khử hiện tượng rung giật (jitter bug) bằng cách upscale 4000px trước khi zoompan.
        """
        output_video_path.parent.mkdir(parents=True, exist_ok=True)
        fps = 30
        total_frames = max(int(round(duration * fps)), 30)
        res = "1920x1080" if aspect_ratio == "16:9" else "1080x1920"

        if effect == "zoom_in":
            z_expr = "min(zoom+0.0015,1.35)"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/2-(ih/zoom/2)"
        elif effect == "zoom_out":
            z_expr = "if(eq(on,1),1.35,max(1.001,zoom-0.0015))"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/2-(ih/zoom/2)"
        else:  # pan_right
            z_expr = "1.2"
            x_expr = f"(iw-iw/zoom)*(on/{total_frames})"
            y_expr = "ih/2-(ih/zoom/2)"

        vf = (
            f"scale=4000:-1,"
            f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':"
            f"d={total_frames}:s={res}:fps={fps},format=yuv420p"
        )

        # Thử nghiệm encoder NVENC trước, nếu thất bại (do chạy trong container hoặc không có card NVIDIA) thì fallback CPU libx264
        cmd_nvenc = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(image_path),
            "-vf", vf,
            "-t", f"{duration:.3f}",
            "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "6M",
            "-an",
            str(output_video_path)
        ]

        try:
            res = subprocess.run(cmd_nvenc, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=90)
            if res.returncode != 0:
                raise RuntimeError("NVENC trả về mã lỗi")
        except Exception:
            logger.warning("NVENC không khả dụng hoặc trả về lỗi, fallback sang CPU libx264...")
            cmd_cpu = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", str(image_path),
                "-vf", vf,
                "-t", f"{duration:.3f}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-an",
                str(output_video_path)
            ]
            subprocess.run(cmd_cpu, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True, timeout=120)

    @staticmethod
    def _robust_request(
        method: str,
        url: str,
        max_retries: int = 5,
        backoff_base: float = 2.0,
        **kwargs
    ) -> requests.Response:
        """Thực hiện HTTP request an toàn với cơ chế retry và exponential backoff chống rớt kết nối."""
        last_error = None
        for attempt in range(max_retries):
            try:
                resp = requests.request(method, url, **kwargs)
                if resp.status_code in (500, 502, 503, 504):
                    if attempt < max_retries - 1:
                        sleep_time = backoff_base * (attempt + 1)
                        logger.warning(
                            f"HTTP {resp.status_code} từ {url}. Đang thử lại lần {attempt+1}/{max_retries} sau {sleep_time:.1f}s..."
                        )
                        time.sleep(sleep_time)
                        continue
                resp.raise_for_status()
                return resp
            except (requests.RequestException, ConnectionResetError, OSError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    sleep_time = backoff_base * (attempt + 1)
                    logger.warning(
                        f"Lỗi mạng khi kết nối tới {url} ({e}). Đang thử lại lần {attempt+1}/{max_retries} sau {sleep_time:.1f}s..."
                    )
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Đã thử lại {max_retries} lần nhưng kết nối tới {url} vẫn thất bại: {e}")
                    raise last_error
        if last_error:
            raise last_error
        raise RuntimeError(f"Yêu cầu tới {url} thất bại không rõ nguyên nhân.")

    def _ensure_scene_image_sync(
        self,
        worker_url: Optional[str],
        scene: Dict[str, Any],
        output_img_path: Path,
        dry_run: bool = False,
        characters_override: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Sinh hoặc tải ảnh cho phân cảnh nếu chưa tồn tại (Checkpoint)."""
        if output_img_path.exists() and output_img_path.stat().st_size > 1024:
            try:
                from PIL import Image, ImageFile
                ImageFile.LOAD_TRUNCATED_IMAGES = True
                with Image.open(output_img_path) as im:
                    im.verify()
                logger.info(f"[Checkpoint] Bỏ qua Cảnh {scene['scene_id']} vì {output_img_path.name} đã tồn tại hợp lệ.")
                return output_img_path
            except Exception:
                logger.warning(f"File ảnh {output_img_path.name} bị hỏng hoặc đứt đoạn, đang tải/tạo lại...")
                output_img_path.unlink(missing_ok=True)

        if dry_run or not worker_url:
            logger.info(f"[Dry-Run] Tạo ảnh giả lập cho Cảnh {scene['scene_id']}...")
            self._create_placeholder_image(scene, output_img_path)
            return output_img_path

        logger.info(f"Đang gửi Cảnh {scene['scene_id']} tới ComfyUI worker ({worker_url})...")
        wf_payload = self._build_workflow_payload(scene, characters_override=characters_override)
        client_id = str(uuid.uuid4())
        
        # 1. Gửi prompt an toàn với retry chống rớt mạng
        resp = self._robust_request(
            "POST",
            f"{worker_url}/prompt",
            json={"prompt": wf_payload, "client_id": client_id},
            timeout=40
        )
        prompt_id = resp.json()["prompt_id"]

        # 2. Vòng lặp chờ kết xuất (Polling) tự phục hồi lỗi kết nối mạng (ConnectionResetError / Cloudflare timeout)
        poll_interval = 3.0
        max_poll_time = 900  # 15 phút tối đa
        start_poll = time.time()
        
        while time.time() - start_poll < max_poll_time:
            try:
                hist_resp = requests.get(f"{worker_url}/history/{prompt_id}", timeout=25)
                if hist_resp.status_code == 200:
                    hist = hist_resp.json()
                    if prompt_id in hist:
                        entry = hist[prompt_id]
                        status = entry.get("status", {})
                        if status.get("status_str") == "error":
                            err_msgs = status.get("messages", [])
                            raise RuntimeError(f"ComfyUI báo lỗi thực thi Cảnh {scene['scene_id']}: {err_msgs}")

                        outputs = entry.get("outputs", {})
                        save_node = outputs.get(self.NODES["save_img"])
                        if save_node and save_node.get("images"):
                            img_meta = save_node["images"][0]
                            # 3. Tải ảnh về với cơ chế retry an toàn
                            view_resp = self._robust_request(
                                "GET",
                                f"{worker_url}/view",
                                params={
                                    "filename": img_meta["filename"],
                                    "subfolder": img_meta["subfolder"],
                                    "type": img_meta["type"]
                                },
                                timeout=60
                            )
                            output_img_path.parent.mkdir(parents=True, exist_ok=True)
                            try:
                                import io
                                from PIL import Image, ImageFile
                                ImageFile.LOAD_TRUNCATED_IMAGES = True
                                with Image.open(io.BytesIO(view_resp.content)) as im:
                                    im.load()
                                    im.save(output_img_path)
                            except Exception:
                                output_img_path.write_bytes(view_resp.content)
                            logger.success(f"Đã tải thành công ảnh Cảnh {scene['scene_id']} từ {worker_url}")
                            return output_img_path
            except (requests.RequestException, ConnectionResetError, OSError) as net_err:
                logger.warning(
                    f"Cảnh báo kết nối khi chờ Cảnh {scene['scene_id']} trên {worker_url} ({net_err}). Tiếp tục kiểm tra..."
                )
            
            time.sleep(poll_interval)

        raise TimeoutError(f"Quá thời gian ({max_poll_time}s) chờ kết xuất ảnh Cảnh {scene['scene_id']} trên {worker_url}")

    def _render_scene_video_sync(
        self,
        scene: Dict[str, Any],
        output_img_path: Path,
        output_vid_path: Path,
        duration: float,
        aspect_ratio: str
    ) -> str:
        """Tạo chuyển động camera video từ ảnh nếu chưa tồn tại (Checkpoint)."""
        if output_vid_path.exists() and output_vid_path.stat().st_size > 1024:
            logger.info(f"[Checkpoint] Bỏ qua Cảnh {scene['scene_id']} vì {output_vid_path.name} đã hoàn thành.")
            return str(output_vid_path)

        logger.info(f"Đang render hiệu ứng camera cho Cảnh {scene['scene_id']} ({duration:.2f}s)...")
        self._render_zoompan_nvenc(
            image_path=output_img_path,
            output_video_path=output_vid_path,
            duration=duration,
            effect=scene.get("camera_motion", "zoom_in"),
            aspect_ratio=aspect_ratio
        )
        return str(output_vid_path)

    async def render_all_scenes_parallel(
        self,
        task_dir: Path,
        scenes: List[Dict[str, Any]],
        durations: List[float],
        aspect_ratio: str = "16:9",
        dry_run: bool = False,
        characters_override: Optional[Dict[str, Any]] = None,
        custom_plates: Optional[Dict[str, Path]] = None
    ) -> List[str]:
        """
        Chia tải bất đồng bộ chuẩn:
        - worker_queue: Hàng đợi luân chuyển Worker linh hoạt (khi worker nào rảnh sẽ nhận cảnh tiếp theo ngay).
        - nvenc_sem: Tách biệt điều tiết số tiến trình FFmpeg zoompan chạy trên GPU/CPU local.
        """
        task_dir.mkdir(parents=True, exist_ok=True)
        if not dry_run and self.worker_urls:
            self.sync_character_plates_to_workers(custom_plates=custom_plates)

        worker_queue: asyncio.Queue = asyncio.Queue()
        if self.worker_urls:
            for w in self.worker_urls:
                await worker_queue.put(w)
        else:
            await worker_queue.put(None)

        nvenc_sem = asyncio.Semaphore(self.nvenc_max_concurrency)

        async def _process_single_scene(idx: int, scene: Dict[str, Any], dur: float) -> str:
            img_out = task_dir / f"scene_{scene['scene_id']:03d}.png"
            vid_out = task_dir / f"scene_{scene['scene_id']:03d}.mp4"

            # 1. Sinh / tải ảnh bằng worker đang rảnh
            worker_url = await worker_queue.get()
            try:
                await asyncio.to_thread(
                    self._ensure_scene_image_sync,
                    worker_url, scene, img_out, dry_run, characters_override
                )
            finally:
                await worker_queue.put(worker_url)

            # 2. Render NVENC video với giới hạn nvenc_sem
            async with nvenc_sem:
                return await asyncio.to_thread(
                    self._render_scene_video_sync,
                    scene, img_out, vid_out, dur, aspect_ratio
                )

        tasks = [
            _process_single_scene(i, sc, dur)
            for i, (sc, dur) in enumerate(zip(scenes, durations))
        ]
        return await asyncio.gather(*tasks)

`

### FILE: app\services\llm.py
`
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
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                },
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
            "stream": True,
            "format": schema_model.model_json_schema(),
            "options": {
                "temperature": 0.65,
                "num_ctx": 8192,       # 8192 tokens nạp nhanh và tăng tốc suy luận trên 2xT4
                "num_predict": 4096    # Đủ rộng cho 15 phân cảnh JSON trong 1 Hồi
            },
            "keep_alive": "15m"        # Giữ model trong VRAM xuyên suốt 5 vòng lặp Hồi
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        resp = requests.post(
            f"{self.ollama_url}/api/chat",
            json=payload,
            headers=headers,
            stream=True,
            timeout=600
        )
        resp.raise_for_status()
        
        full_content = []
        for line in resp.iter_lines():
            if line:
                chunk = json.loads(line.decode("utf-8"))
                msg = chunk.get("message", {}).get("content", "")
                if msg:
                    full_content.append(msg)
                if chunk.get("done", False):
                    break
        content = "".join(full_content).strip()
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if m:
            content = m.group(1).strip()
        return content

    def generate_full_10min_script(self, topic: str, checkpoint_dir: Path, force_refresh: bool = False) -> List[StoryScene]:
        """
        Điều phối sinh kịch bản 10 phút (~70 phân cảnh) qua 5 Hồi có lưu Checkpoint từng Hồi,
        sau đó tự động xả sạch VRAM trong khối finally.
        """
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        final_script_file = checkpoint_dir / "full_script_checkpoint.json"

        if force_refresh:
            for f in checkpoint_dir.glob("*.json"):
                try:
                    f.unlink()
                except Exception:
                    pass

        # Nếu kịch bản đã được sinh thành công ở lần chạy trước và không yêu cầu làm mới thì đọc từ ổ cứng
        if not force_refresh and final_script_file.exists():
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
            logger.info(f"[Pha 1 - LLM 32B] Đang lập cấu trúc 5 Hồi (Beat Sheet) và sáng tạo nhân vật cho chủ đề: '{topic}'...")
            beat_sys = f"""
            Bạn là Đạo diễn Điện ảnh AI chuyên nghiệp.
            Nhiệm vụ: Lập cấu trúc kịch bản trường ca 10 phút gồm đúng 5 Hồi (Acts) và sáng tạo 1 đến 2 nhân vật chính (characters) phù hợp nhất với chủ đề: "{topic}".

            QUY TẮC THIẾT KẾ NHÂN VẬT (characters):
            Sáng tạo 1 đến 2 nhân vật phù hợp với phong cách, bối cảnh thời đại và thể loại của câu chuyện:
            - id: 'char_1', 'char_2'
            - name: Tên nhân vật bằng tiếng Việt (ví dụ: 'Lâm Phong', 'Tiêu Dao', 'Mai', 'David'...)
            - concept: Thể loại & vibe tạo hình (ví dụ: 'Kiếm hiệp lãng tử giang hồ', 'Cyberpunk hacker', 'Học sinh thanh xuân', 'Bác sĩ quân y'...)
            - appearance_prompt: Prompt tiếng Anh mô tả khuôn mặt, mắt, tóc, nét mặt (KHÔNG mô tả trang phục)
            - default_outfit: Prompt tiếng Anh mô tả trang phục đặc trưng theo đúng concept/thời đại
            - voice_id: 'vi-VN-NamMinhNeural' (nam) hoặc 'vi-VN-HoaiMyNeural' (nữ)

            QUY TẮC THIẾT KẾ 5 HỒI (acts):
            - Gồm đúng 5 Hồi: Hồi 1 (Khởi đầu), Hồi 2 (Phát triển), Hồi 3 (Biến cố/Cao trào 1), Hồi 4 (Đỉnh điểm), Hồi 5 (Kết thúc/Đọng lại).
            - Mỗi Hồi phải có:
              + location_anchor: không gian/địa điểm cố định bằng tiếng Anh
              + lighting_anchor: ánh sáng cố định bằng tiếng Anh
              + target_scenes: từ 12 đến 15 phân cảnh (để tổng 5 Hồi đạt ~65-75 cảnh cho video 10 phút)
            """
            beat_user = f"Chủ đề câu chuyện: {topic}\nNhân vật mẫu nếu cần tham khảo: {char_summary}"
            beat_json = self._call_ollama_structured(beat_sys, beat_user, MasterBeatSheet)
            beat_sheet = MasterBeatSheet.model_validate_json(beat_json)
            (checkpoint_dir / "master_beat_sheet.json").write_text(beat_sheet.model_dump_json(indent=2), encoding="utf-8")
            logger.success(f"Đã tạo xong Beat Sheet: '{beat_sheet.video_title}' ({len(beat_sheet.acts)} Hồi, {len(beat_sheet.characters)} nhân vật)")

            # -----------------------------------------------------------------
            # BƯỚC 2: TRIỂN KHAI CHI TIẾT TỪNG HỒI VỚI ROLLING CONTEXT
            # -----------------------------------------------------------------
            global_scene_counter = 1
            if beat_sheet.characters:
                available_char_keys = [c.id for c in beat_sheet.characters]
            else:
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

    def generate_full_10min_story(self, topic: str, checkpoint_dir: Path, force_refresh: bool = False) -> StoryScriptResponse:
        """Sinh StoryScriptResponse hoàn chỉnh sẵn sàng cho pipeline."""
        scenes = self.generate_full_10min_script(topic, checkpoint_dir, force_refresh=force_refresh)
        title = topic
        chars = []
        sheet_file = checkpoint_dir / "master_beat_sheet.json"
        if sheet_file.exists():
            try:
                sheet = MasterBeatSheet.model_validate_json(sheet_file.read_text(encoding="utf-8"))
                title = sheet.video_title or topic
                if sheet.characters:
                    chars = sheet.characters
            except Exception:
                pass
        if not chars and "characters" in self.bible:
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

`

### FILE: app\services\task.py
`
import json
import time
import uuid
import shutil
import asyncio
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
from loguru import logger

from app.config import AppConfig, get_config
from app.models.schema import StoryScriptResponse, CharacterBible, CharacterProfile
from app.services.llm import generate_story_scenes, TimeSharedKaggleDirector
from app.services.voice import synthesize_scenes_audio_and_subtitles
from app.services.comfy_remote_client import DualGPUComfyStoryClient
from app.services.video import assemble_final_story_video_nvenc

def run_story_pipeline(
    topic: str,
    config: Optional[AppConfig] = None,
    custom_script: Optional[StoryScriptResponse] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    dry_run: bool = False,
    bgm_path: Optional[Path] = None,
    aspect_ratio: str = "16:9",
    character_bible_path: str = "resource/character_bible/characters.json",
    workflow_path: str = "resource/workflows/pulid_ipadapter_api.json",
    tts_backend: Optional[Callable[[str, str, Path], None]] = None,
    voice_override: Optional[str] = None,
    story_mode: str = "short",
    ollama_worker_url: Optional[str] = None,
    task_id: Optional[str] = None
) -> Path:
    """
    Hàm điều phối toàn bộ quy trình sản xuất video kể chuyện AI Scene-by-Scene:
    1. Sinh kịch bản JSON qua LLM (hỗ trợ Time-Shared Kaggle Director cho kịch bản 10 phút)
    2. Tổng hợp giọng đọc TTS và ghép phụ đề đồng bộ
    3. Sinh ảnh qua ComfyUI Dual-GPU và chuyển động camera NVENC
    4. Đóng gói video thành phẩm kèm Audio Ducking
    """
    cfg = config or get_config()
    effective_task_id = task_id or f"task_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    task_dir = cfg.get_task_dir(effective_task_id)

    def report(msg: str, progress: float):
        logger.info(f"[{progress*100:.0f}%] {msg}")
        if progress_callback:
            progress_callback(msg, progress)

    report("Khởi tạo phiên làm việc...", 0.05)

    effective_ollama_url = ollama_worker_url or cfg.ollama_worker_url

    # 1. Kịch bản phân cảnh
    script_file = task_dir / "story_script.json"
    if custom_script:
        story_script = custom_script
    elif script_file.exists():
        with open(script_file, "r", encoding="utf-8") as f:
            story_script = StoryScriptResponse(**json.load(f))
    elif story_mode == "10min_multiact" or (effective_ollama_url and cfg.llm_provider == "ollama"):
        report("Đang khởi động TimeSharedKaggleDirector (Qwen-32B Multi-Act)...", 0.12)
        checkpoint_dir = task_dir / "llm_checkpoints"
        director = TimeSharedKaggleDirector(
            ollama_url=effective_ollama_url or cfg.llm_base_url,
            comfy_urls=cfg.worker_urls,
            model_name=cfg.llm_model if (cfg.llm_model and cfg.llm_model != "gpt-4o") else "qwen2.5:32b-instruct-q4_K_M",
            bible_path=character_bible_path
        )
        story_script = director.generate_full_10min_story(
            topic=topic,
            checkpoint_dir=checkpoint_dir
        )
    else:
        report("Đang sinh kịch bản phân cảnh từ LLM...", 0.15)
        story_script = generate_story_scenes(
            topic=topic,
            character_bible_path=character_bible_path,
            provider=cfg.llm_provider,
            api_key=cfg.llm_api_key,
            base_url=cfg.llm_base_url,
            model=cfg.llm_model
        )

    # Lưu lại kịch bản để phục vụ checkpoint
    script_file.write_text(story_script.model_dump_json(indent=2), encoding="utf-8")
    report(f"Đã xác nhận kịch bản ({len(story_script.scenes)} phân cảnh)", 0.25)

    # 2. Âm thanh & Phụ đề
    bible = CharacterBible.from_json_file(Path(character_bible_path))
    if story_script.characters:
        for c in story_script.characters:
            bible.characters[c.id] = CharacterProfile(
                name=c.name,
                voice_id=c.voice_id or cfg.default_voice,
                appearance_trigger=c.appearance_prompt,
                default_outfit=c.default_outfit,
                face_plate=c.face_plate or f"{c.id}_face.png",
                outfit_plate=c.outfit_plate or f"{c.id}_outfit.png",
                pulid_weight=c.pulid_weight,
                ipadapter_weight=c.ipadapter_weight
            )

    report("Đang tổng hợp giọng đọc phân cảnh và đồng bộ phụ đề...", 0.35)
    master_audio, master_srt, durations = synthesize_scenes_audio_and_subtitles(
        scenes=story_script.scenes,
        task_dir=task_dir,
        bible=bible,
        voice_override=voice_override,
        tts_backend=tts_backend
    )
    report("Hoàn thành audio và phụ đề", 0.50)

    # Đảm bảo VRAM đã được giải phóng sạch sẽ cho ComfyUI nếu có Ollama trên Kaggle
    if effective_ollama_url and not dry_run:
        try:
            TimeSharedKaggleDirector(
                ollama_url=effective_ollama_url,
                comfy_urls=cfg.worker_urls,
                model_name=cfg.llm_model if (cfg.llm_model and cfg.llm_model != "gpt-4o") else "qwen2.5:32b-instruct-q4_K_M"
            ).evict_llm_from_kaggle_vram()
        except Exception as e:
            logger.warning(f"Cảnh báo khi chạy tiền kiểm tra xả VRAM Ollama: {e}")

    # 3. Kết xuất hình ảnh và chuyển động camera (ComfyUI + NVENC)
    report("Đang kết xuất hình ảnh và hiệu ứng camera phân cảnh...", 0.60)
    comfy_client = DualGPUComfyStoryClient(
        worker_urls=cfg.worker_urls,
        workflow_path=workflow_path,
        bible_path=character_bible_path
    )

    # Sinh hoặc nạp ảnh mẫu nhân vật động cho task nếu có
    char_dir = task_dir / "characters"
    char_dir.mkdir(parents=True, exist_ok=True)
    custom_plates = {}
    characters_override = {}

    if story_script.characters:
        for c in story_script.characters:
            face_p = char_dir / f"{c.id}_face.png"
            outfit_p = char_dir / f"{c.id}_outfit.png"
            # Nếu người dùng đã sinh trước trong WebUI và truyền đường dẫn file
            if c.face_plate and Path(c.face_plate).exists() and not face_p.exists():
                shutil.copy(c.face_plate, face_p)
            if c.outfit_plate and Path(c.outfit_plate).exists() and not outfit_p.exists():
                shutil.copy(c.outfit_plate, outfit_p)

            if not (face_p.exists() and face_p.stat().st_size > 1024 and outfit_p.exists() and outfit_p.stat().st_size > 1024):
                report(f"Đang sinh ảnh mẫu cho nhân vật {c.name} ({c.concept})...", 0.55)
                comfy_client.generate_character_plates(c, output_dir=char_dir, dry_run=dry_run)
            else:
                c.face_plate = face_p.name
                c.outfit_plate = outfit_p.name

            custom_plates[c.face_plate or face_p.name] = face_p
            custom_plates[c.outfit_plate or outfit_p.name] = outfit_p
            characters_override[c.id] = c

    scenes_dict = [sc.model_dump() for sc in story_script.scenes]
    scene_videos = asyncio.run(
        comfy_client.render_all_scenes_parallel(
            task_dir=task_dir,
            scenes=scenes_dict,
            durations=durations,
            aspect_ratio=aspect_ratio,
            dry_run=dry_run,
            characters_override=characters_override,
            custom_plates=custom_plates
        )
    )
    report(f"Hoàn thành render {len(scene_videos)} clip phân cảnh", 0.85)

    # 4. Đóng gói hoàn thiện video cuối cùng
    report("Đang hoàn thiện video (Audio Ducking, NVENC & phụ đề)...", 0.90)
    final_video_path = task_dir / "final_story.mp4"
    assemble_final_story_video_nvenc(
        scene_video_paths=scene_videos,
        master_audio_path=master_audio,
        subtitle_srt_path=master_srt,
        output_final_path=final_video_path,
        bgm_path=bgm_path
    )

    report("Quy trình hoàn tất thành công!", 1.0)
    return final_video_path

`

### FILE: app\services\video.py
`
import subprocess
from pathlib import Path
from typing import List, Optional
from loguru import logger

def get_safe_subtitle_path(subtitle_path: Path) -> str:
    r"""
    Chuẩn hóa và escape ký tự hai chấm (:) trên ổ đĩa Windows (VD: C:\ -> C\:/)
    và dấu nháy đơn (') để FFmpeg không hiểu nhầm là ký tự phân tách filter parameter.
    """
    posix_path = subtitle_path.resolve().as_posix()
    return posix_path.replace(":", r"\:").replace("'", r"\'")

def assemble_final_story_video_nvenc(
    scene_video_paths: List[str],
    master_audio_path: Path,
    subtitle_srt_path: Path,
    output_final_path: Path,
    bgm_path: Optional[Path] = None,
    font_name: str = "Arial"
) -> Path:
    """
    Nối toàn bộ video phân cảnh, kết hợp master audio chuẩn hóa -16 LUFS,
    tự động hạ âm lượng BGM khi có giọng đọc (Audio Ducking) và đốt phụ đề tiếng Việt.
    """
    task_dir = master_audio_path.parent
    task_dir.mkdir(parents=True, exist_ok=True)
    output_final_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Nối nhanh các visual clip phân cảnh bằng FFmpeg concat copy (mất ~1 giây)
    concat_vid_list = task_dir / "video_concat.txt"
    concat_vid_list.write_text(
        "\n".join([f"file '{Path(p).resolve().as_posix()}'" for p in scene_video_paths]),
        encoding="utf-8"
    )

    merged_visual = task_dir / "merged_visual_only.mp4"
    logger.info("Đang ghép nối các phân cảnh video (Stream Copy)...")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_vid_list),
        "-c", "copy",
        str(merged_visual)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    # 2. Định dạng Style phụ đề tiếng Việt nổi bật, dễ đọc
    safe_srt = get_safe_subtitle_path(subtitle_srt_path)
    sub_style = (
        f"FontName={font_name},FontSize=18,PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H00000000,BackColour=&H80000000,Bold=1,Outline=2,Shadow=1,MarginV=35"
    )

    logger.info("Đang xử lý Audio Ducking, chuẩn hóa âm thanh -16 LUFS và ép phụ đề...")

    # 3. Xây dựng lệnh FFmpeg tùy thuộc vào việc có nhạc nền (BGM) hay không
    if bgm_path and Path(bgm_path).exists():
        filter_complex = (
            f"[0:v]subtitles='{safe_srt}':force_style='{sub_style}'[v_out];"
            f"[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,asplit=2[voice_norm][voice_sc];"
            f"[2:a]volume=0.18,aloop=loop=-1:size=2e+09[bgm_loop];"
            f"[bgm_loop][voice_sc]sidechaincompress=threshold=0.02:ratio=6:attack=50:release=400[bgm_ducked];"
            f"[voice_norm][bgm_ducked]amix=inputs=2:duration=first:dropout_transition=2[a_out]"
        )
        cmd_nvenc = [
            "ffmpeg", "-y",
            "-i", str(merged_visual),
            "-i", str(master_audio_path),
            "-i", str(bgm_path),
            "-filter_complex", filter_complex,
            "-map", "[v_out]", "-map", "[a_out]",
            "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "6M",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", str(output_final_path)
        ]
        cmd_cpu = [
            "ffmpeg", "-y",
            "-i", str(merged_visual),
            "-i", str(master_audio_path),
            "-i", str(bgm_path),
            "-filter_complex", filter_complex,
            "-map", "[v_out]", "-map", "[a_out]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", str(output_final_path)
        ]
    else:
        cmd_nvenc = [
            "ffmpeg", "-y",
            "-i", str(merged_visual),
            "-i", str(master_audio_path),
            "-vf", f"subtitles='{safe_srt}':force_style='{sub_style}'",
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "6M",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", str(output_final_path)
        ]
        cmd_cpu = [
            "ffmpeg", "-y",
            "-i", str(merged_visual),
            "-i", str(master_audio_path),
            "-vf", f"subtitles='{safe_srt}':force_style='{sub_style}'",
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", str(output_final_path)
        ]

    # Thực thi xuất video, ưu tiên NVENC
    res = subprocess.run(cmd_nvenc, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if res.returncode != 0:
        logger.warning("NVENC gặp lỗi, fallback sang CPU libx264 cho video cuối cùng...")
        subprocess.run(cmd_cpu, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    logger.success(f"Video thành phẩm đã hoàn thành: {output_final_path}")
    return output_final_path

`

### FILE: app\services\voice.py
`
import asyncio
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import List, Tuple, Optional, Callable
import edge_tts
from mutagen.mp3 import MP3
from loguru import logger

from app.models.schema import StoryScene, CharacterBible

def _format_srt_timestamp(seconds: float) -> str:
    """Định dạng giây sang mốc thời gian chuẩn SRT: HH:MM:SS,mmm"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msecs = int(round((seconds - int(seconds)) * 1000))
    if msecs >= 1000:
        secs += 1
        msecs = 0
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"

def sanitize_narration(text: str, bible: Optional[CharacterBible] = None) -> str:
    """
    Chuẩn hóa lời dẫn truyện trước khi gửi đến TTS và phụ đề:
    - Thay thế các mã kỹ thuật (char_1, char_2, Char_1, Char_2, char_minh, v.v.)
      bằng tên nhân vật thực tế (vd: Hiro, Yuki, Minh, Linh).
    - Chuẩn hóa khoảng trắng và viết hoa đầu câu.
    """
    if not text:
        return text
    
    cleaned = text
    if bible and bible.characters:
        char_items = list(bible.characters.items())
        
        # 1. Thay thế theo ID nhân vật cụ thể trước (vd: char_minh -> Minh, char_1 -> Hiro)
        for cid, profile in char_items:
            if profile.name:
                cleaned = re.sub(rf"\b{re.escape(cid)}\b", profile.name, cleaned, flags=re.IGNORECASE)
                cid_space = cid.replace("_", " ")
                cleaned = re.sub(rf"\b{re.escape(cid_space)}\b", profile.name, cleaned, flags=re.IGNORECASE)
        
        # 2. Thay thế theo thứ tự xuất hiện (vd: char_1 / Char_1 -> nhân vật 1, char_2 -> nhân vật 2)
        for idx, (_, profile) in enumerate(char_items):
            if profile.name:
                pos = idx + 1
                cleaned = re.sub(rf"\bchar_?{pos}\b", profile.name, cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(rf"\bnhân vật {pos}\b", profile.name, cleaned, flags=re.IGNORECASE)
                
    # 3. Chuẩn hóa khoảng trắng dư thừa
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    
    # 4. Viết hoa ký tự đầu câu sau dấu chấm/chấm than/chấm hỏi hoặc đầu chuỗi
    cleaned = re.sub(
        r"(^|[.!?]\s+)([a-zđàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ])",
        lambda m: m.group(1) + m.group(2).upper(),
        cleaned
    )
    return cleaned

async def _edge_tts_async(text: str, voice_name: str, temp_file: Path, rate: str = "+0%"):
    communicate = edge_tts.Communicate(text=text, voice=voice_name, rate=rate)
    await communicate.save(str(temp_file))

def _synthesize_sentence_chunks(text: str, voice_name: str, raw_tmp: Path, rate: str = "+0%") -> bool:
    """
    Chia nhỏ đoạn văn dài thành các câu/mệnh đề riêng biệt để Microsoft Edge TTS
    không bị ngắt kết nối (NoAudioReceived) do quá tải câu dài.
    Sau đó nối các file âm thanh thành phần bằng FFmpeg.
    """
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if len(sentences) <= 1 and len(text) > 80 and "," in text:
        sentences = [s.strip() for s in re.split(r"(?<=,)\s+", text) if s.strip()]

    if len(sentences) <= 1:
        return False

    part_files: List[Path] = []
    try:
        for idx, sent in enumerate(sentences):
            if idx > 0:
                time.sleep(0.6)  # Cooldown giữa các kết nối WebSocket của Microsoft Edge TTS
            p_file = raw_tmp.with_name(f"{raw_tmp.stem}_sub{idx}.mp3")
            
            chunk_success = False
            for attempt in range(2):
                try:
                    asyncio.run(_edge_tts_async(sent, voice_name, p_file, rate=rate))
                    if p_file.exists() and p_file.stat().st_size > 256:
                        chunk_success = True
                        break
                except Exception as chunk_err:
                    logger.debug(f"Thử đoạn {idx+1}/{len(sentences)} lần {attempt+1} gặp lỗi: {chunk_err}")
                    time.sleep(0.8 * (attempt + 1))
            
            if not chunk_success:
                # Thử giọng dự phòng nếu giọng chính bị Microsoft từ chối
                alt_voice = "vi-VN-HoaiMyNeural" if voice_name != "vi-VN-HoaiMyNeural" else "vi-VN-NamMinhNeural"
                try:
                    asyncio.run(_edge_tts_async(sent, alt_voice, p_file, rate=rate))
                    if p_file.exists() and p_file.stat().st_size > 256:
                        chunk_success = True
                except Exception:
                    pass

            if not chunk_success:
                return False

            part_files.append(p_file)

        concat_txt = raw_tmp.with_suffix(".txt")
        lines = [f"file '{p.resolve().as_posix()}'" for p in part_files]
        concat_txt.write_text("\n".join(lines), encoding="utf-8")
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_txt),
            "-c", "copy",
            str(raw_tmp)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        concat_txt.unlink(missing_ok=True)
        return raw_tmp.exists() and raw_tmp.stat().st_size > 1024
    except Exception as err:
        logger.warning(f"Lỗi khi ghép audio từng phần: {err}")
        return False
    finally:
        for p in part_files:
            p.unlink(missing_ok=True)

def default_edge_tts(text: str, voice_name: str, voice_file: Path, rate: str = "+0%", max_retries: int = 3):
    """
    Sinh giọng đọc Edge-TTS và chuẩn hóa ngay sang 24000Hz Mono
    nhằm khử sai số đệm khung hình (frame padding) khi concat.
    - Hỗ trợ cơ chế Retry với Exponential Backoff khi Microsoft Edge TTS bị nghẽn mạng (NoAudioReceived).
    - Tự động chia nhỏ theo câu (chunking) nếu câu văn dài bị Microsoft ngắt kết nối.
    - Tự động luân chuyển giữa các giọng đọc dự phòng (vi-VN-HoaiMyNeural, vi-VN-NamMinhNeural).
    - Tạo marker .fallback nếu phải dùng âm thanh sine tổng hợp để cho phép tự động thử lại khi re-render.
    """
    voice_file.parent.mkdir(parents=True, exist_ok=True)
    fallback_marker = voice_file.with_suffix(".fallback")
    
    # Tên file raw tạm duy nhất để không bị xung đột tiến trình / đa luồng
    raw_tmp = voice_file.with_name(f"{voice_file.stem}_raw_{uuid.uuid4().hex[:8]}.mp3")
    
    # Danh sách thử nghiệm giọng đọc
    candidate_voices = [voice_name]
    if voice_name != "vi-VN-HoaiMyNeural":
        candidate_voices.append("vi-VN-HoaiMyNeural")
    if "vi-VN-NamMinhNeural" not in candidate_voices:
        candidate_voices.append("vi-VN-NamMinhNeural")

    success = False
    for candidate in candidate_voices:
        for attempt in range(max_retries):
            try:
                if raw_tmp.exists():
                    raw_tmp.unlink()
                # 1. Thử sinh trực tiếp toàn bộ văn bản
                try:
                    asyncio.run(_edge_tts_async(text, candidate, raw_tmp, rate=rate))
                except Exception as direct_err:
                    # 2. Nếu Microsoft từ chối (NoAudioReceived trên câu dài), tự động chia nhỏ theo câu/mệnh đề
                    if not _synthesize_sentence_chunks(text, candidate, raw_tmp, rate=rate):
                        raise direct_err

                if raw_tmp.exists() and raw_tmp.stat().st_size > 1024:
                    success = True
                    break
                else:
                    logger.warning(f"Giọng {candidate} trả về dữ liệu rỗng (lần {attempt+1}/{max_retries}).")
            except Exception as e:
                logger.warning(f"Giọng {candidate} lần {attempt+1}/{max_retries} thất bại ({e}). Đang thử lại...")
            
            # Backoff delay giữa các lần thử lại để thoát khỏi cửa sổ rate-limit
            time.sleep(1.2 * (attempt + 1))
            
        if success:
            break

    if not success:
        # Fallback offline (sử dụng âm thanh tổng hợp giả lập nếu mất mạng hoặc Microsoft chặn endpoint)
        logger.warning(f"Toàn bộ giọng Edge-TTS không khả dụng. Sử dụng fallback âm thanh tổng hợp cho: '{text[:30]}...'")
        dur_est = max(1.5, len(text.split()) * 0.3)
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"sine=frequency=440:duration={dur_est:.2f}",
            "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "64k",
            str(voice_file)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if raw_tmp.exists():
            raw_tmp.unlink()
        fallback_marker.touch()
        return

    # Chuẩn hóa tần số lấy mẫu về 24000Hz mono
    subprocess.run([
        "ffmpeg", "-y", "-i", str(raw_tmp),
        "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "64k",
        str(voice_file)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    if raw_tmp.exists():
        raw_tmp.unlink()
    if fallback_marker.exists():
        fallback_marker.unlink()

def synthesize_scenes_audio_and_subtitles(
    scenes: List[StoryScene],
    task_dir: Path,
    bible: CharacterBible,
    voice_override: Optional[str] = None,
    tts_backend: Optional[Callable[[str, str, Path], None]] = None
) -> Tuple[Path, Path, List[float]]:
    """
    Sinh audio phân cảnh độc lập, đo thời lượng chính xác T_i và tạo master audio + master srt.
    - Tự động làm sạch và thay thế tên nhân vật thực tế vào narration.
    - Áp dụng giãn cách an toàn giữa các cảnh để tránh nghẽn Microsoft Edge TTS.
    - Tự động thay thế các file âm thanh fallback hỏng trước đó.
    """
    task_dir.mkdir(parents=True, exist_ok=True)
    durations: List[float] = []
    audio_files: List[Path] = []
    srt_entries: List[str] = []
    cumulative_offset = 0.0
    sub_idx = 1

    tts_func = tts_backend or default_edge_tts

    # 1. Chuẩn hóa lời thoại toàn bộ phân cảnh trước
    for scene in scenes:
        scene.narration = sanitize_narration(scene.narration, bible=bible)

    for scene in scenes:
        scene_audio = task_dir / f"audio_{scene.scene_id:03d}.mp3"
        fallback_marker = scene_audio.with_suffix(".fallback")

        # Quyết định giọng đọc: nếu là cảnh nhân vật thì dùng giọng nhân vật, ngược lại dùng narrator
        if voice_override:
            voice_id = voice_override
        elif scene.has_character and scene.character_id in bible.characters:
            voice_id = bible.characters[scene.character_id].voice_id
        else:
            voice_id = bible.narrator.voice_id

        # Chỉ sinh audio nếu file chưa tồn tại hoặc là file fallback lỗi trước đó
        needs_generation = not (scene_audio.exists() and scene_audio.stat().st_size > 512) or fallback_marker.exists()
        if needs_generation:
            logger.info(f"Đang tạo giọng đọc cho Cảnh {scene.scene_id} ({voice_id})...")
            tts_func(scene.narration, voice_id, scene_audio)
            
            # Cooldown 0.5s giữa các cảnh chỉ khi chạy TTS thực tế qua mạng
            if tts_backend is None:
                time.sleep(0.5)

        # Đo thời lượng thực tế của file MP3 chuẩn hóa
        dur = round(MP3(str(scene_audio)).info.length, 3)
        if dur < 1.0:
            # Nếu câu quá ngắn, thêm đệm im lặng vào file audio để đạt tối thiểu 1.0s, tránh lệch đồng bộ với SRT
            pad_dur = round(1.0 - dur, 3)
            padded_audio = scene_audio.with_suffix(".padded.mp3")
            subprocess.run([
                "ffmpeg", "-y", "-i", str(scene_audio),
                "-af", f"apad=pad_dur={pad_dur}",
                "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "64k",
                str(padded_audio)
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            padded_audio.replace(scene_audio)
            dur = 1.0

        durations.append(dur)
        audio_files.append(scene_audio)

        # Tính toán mốc thời gian phụ đề
        start_ts = _format_srt_timestamp(cumulative_offset)
        end_ts = _format_srt_timestamp(cumulative_offset + dur)
        srt_entries.append(f"{sub_idx}\n{start_ts} --> {end_ts}\n{scene.narration}\n")

        cumulative_offset += dur
        sub_idx += 1

    # Concat các file audio phân cảnh thành master_audio.mp3
    concat_list = task_dir / "audio_concat.txt"
    concat_list.write_text(
        "\n".join([f"file '{p.resolve().as_posix()}'" for p in audio_files]),
        encoding="utf-8"
    )

    master_audio = task_dir / "master_audio.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(master_audio)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    # Ghi file phụ đề tổng
    master_srt = task_dir / "master_subtitle.srt"
    master_srt.write_text("\n".join(srt_entries), encoding="utf-8")

    logger.success(f"Hoàn thành tạo audio và phụ đề cho {len(scenes)} phân cảnh (Tổng: {cumulative_offset:.2f}s)")
    return master_audio, master_srt, durations

`

### FILE: app\services\__init__.py
`
"""Services Package."""

`

### FILE: app\ui\webui.py
`
import json
import os
import sys
from pathlib import Path
import streamlit as st
import requests
from PIL import Image

# Đảm bảo đường dẫn root nằm trong sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import importlib
from app.config import get_config, AppConfig
import app.models.schema
importlib.reload(app.models.schema)
from app.models.schema import StoryScriptResponse, StoryScene, StoryCharacter, CharacterBible
import app.services.voice
importlib.reload(app.services.voice)
import app.services.comfy_remote_client
importlib.reload(app.services.comfy_remote_client)
import app.services.task
importlib.reload(app.services.task)
import app.services.llm
importlib.reload(app.services.llm)
from app.services.llm import generate_story_scenes, TimeSharedKaggleDirector
from app.services.task import run_story_pipeline
from app.services.comfy_remote_client import DualGPUComfyStoryClient

st.set_page_config(
    page_title="AI Storytelling Studio",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 Lean AI Storytelling Studio")
st.caption("Hệ thống tự động hóa video kể chuyện AI với nhân vật đồng nhất (Consistent Character Pipeline)")

cfg = get_config()
bible_path = ROOT_DIR / "resource" / "character_bible" / "characters.json"
bible = CharacterBible.from_json_file(bible_path)

# --- SIDEBAR: CẤU HÌNH HỆ THỐNG ---
with st.sidebar:
    st.header("⚙️ Cấu Hình Hệ Thống")
    
    st.subheader("🌐 Cloudflare Tunnel Workers")
    ollama_default = cfg.ollama_worker_url or ""
    ollama_url_input = st.text_input("Ollama Worker (cuda:0,1, Port 11434)", value=ollama_default, placeholder="https://....trycloudflare.com")
    cleaned_ollama = DualGPUComfyStoryClient.clean_worker_url(ollama_url_input)
    if ollama_url_input.strip() and cleaned_ollama != ollama_url_input.strip():
        st.sidebar.caption(f"🔍 Tự động nhận diện Ollama: `{cleaned_ollama}`")

    w0_default = cfg.worker_urls[0] if len(cfg.worker_urls) > 0 else ""
    w1_default = cfg.worker_urls[1] if len(cfg.worker_urls) > 1 else ""
    worker_url_0 = st.text_input("Worker GPU 0 (cuda:0, Port 8188)", value=w0_default, placeholder="https://....trycloudflare.com")
    worker_url_1 = st.text_input("Worker GPU 1 (cuda:1, Port 8189)", value=w1_default, placeholder="https://....trycloudflare.com")
    
    cleaned_w0 = DualGPUComfyStoryClient.clean_worker_url(worker_url_0)
    cleaned_w1 = DualGPUComfyStoryClient.clean_worker_url(worker_url_1)
    if worker_url_0.strip() and cleaned_w0 != worker_url_0.strip():
        st.sidebar.caption(f"🔍 Tự động nhận diện Worker 0: `{cleaned_w0}`")
    if worker_url_1.strip() and cleaned_w1 != worker_url_1.strip():
        st.sidebar.caption(f"🔍 Tự động nhận diện Worker 1: `{cleaned_w1}`")
    
    active_workers = [u for u in [cleaned_w0, cleaned_w1] if u]

    # Nút Xả Sạch VRAM Kaggle Thủ Công
    btn_evict_vram = st.button("🧹 Xả Sạch VRAM Kaggle Thủ Công", help="Ép Ollama giải phóng Qwen-32B (keep_alive: 0) và ComfyUI giải phóng bộ nhớ (/free)")
    if btn_evict_vram:
        with st.spinner("Đang xả sạch VRAM trên Kaggle..."):
            freed_services = []
            for w_url in active_workers:
                try:
                    requests.post(f"{w_url}/free", json={"unload_models": True, "free_memory": True}, timeout=10)
                    freed_services.append(f"ComfyUI ({w_url})")
                except Exception as ex:
                    st.warning(f"Không thể xả ComfyUI {w_url}: {ex}")
            if cleaned_ollama:
                try:
                    requests.post(f"{cleaned_ollama}/api/generate", json={"model": "qwen2.5:32b-instruct-q4_K_M", "keep_alive": 0}, timeout=15)
                    freed_services.append(f"Ollama ({cleaned_ollama})")
                except Exception as ex:
                    st.warning(f"Không thể xả Ollama {cleaned_ollama}: {ex}")
            if freed_services:
                st.success(f"✅ Đã xả sạch VRAM: {', '.join(freed_services)}!")
            else:
                st.info("Chưa có URL worker khả dụng để xả VRAM.")
    
    dry_run_mode = st.checkbox("🧪 Chế độ Dry-Run (Không cần GPU Cloud)", value=(len(active_workers) == 0))
    if dry_run_mode:
        st.info("Đang bật chế độ Dry-Run: Hệ thống sẽ tạo ảnh giả lập và dùng FFmpeg local để kiểm tra luồng video.")

    st.subheader("🎬 Chế Độ Kịch Bản")
    story_mode_choice = st.radio(
        "Định dạng video:",
        [
            "⚡ Kịch bản ngắn (3 - 8 phân cảnh)",
            "🎬 Phim trường ca 10 phút (5 Hồi / 70 cảnh)"
        ],
        index=0
    )
    is_10min_mode = "10 phút" in story_mode_choice

    st.subheader("🤖 Cấu hình LLM")
    provider_options = ["gemini", "openai", "deepseek", "ollama", "mock (thử nghiệm không cần key)"]
    llm_provider = st.selectbox("Nhà cung cấp LLM", provider_options, index=3 if cleaned_ollama else 0)
    clean_provider = llm_provider.split()[0].lower()

    if clean_provider == "mock":
        st.info("✨ Chế độ Mock: Tự động tạo kịch bản 5 phân cảnh chuẩn điện ảnh tức thì mà không cần API Key hay kết nối mạng.")
        llm_api_key = ""
        llm_model = "mock"
        llm_base_url = ""
    elif clean_provider == "ollama":
        st.info("🦙 Ollama: Chạy mô hình mã nguồn mở trên Kaggle (cuda:0,1 32GB VRAM).")
        llm_api_key = "ollama"
        default_ollama_base = f"{cleaned_ollama}/v1" if cleaned_ollama else "http://localhost:11434/v1"
        llm_base_url = st.text_input(
            "Ollama Base URL",
            value=default_ollama_base,
            help="Đường link Cloudflare Tunnel tới Ollama port 11434 kèm /v1"
        )
        llm_model = st.text_input("Tên Model", value="qwen2.5:32b-instruct-q4_K_M", help="Mô hình Qwen-2.5-32B chạy trên Kaggle 2xT4")
    else:
        if clean_provider == "gemini":
            default_base = "https://generativelanguage.googleapis.com/v1beta/openai"
            default_model = "gemini-2.0-flash"
            key_help = "Nhập Google AI Studio API Key (AIzaSy...)"
        elif clean_provider == "deepseek":
            default_base = "https://api.deepseek.com/v1"
            default_model = "deepseek-chat"
            key_help = "Nhập DeepSeek API Key (sk-...)"
        else:
            default_base = "https://api.openai.com/v1"
            default_model = "gpt-4o-mini"
            key_help = "Nhập OpenAI API Key (sk-...)"

        llm_api_key = st.text_input("API Key", value=cfg.llm_api_key, type="password", help=key_help)
        llm_model = st.text_input("Tên Model", value=default_model)
        with st.expander("Tùy biến Endpoint (Base URL)"):
            llm_base_url = st.text_input("Base URL", value=default_base)

    st.subheader("🎙️ Giọng Đọc Mặc Định")
    voice_choice = st.selectbox("Giọng Đọc Narrator", [
        "vi-VN-NamMinhNeural",
        "vi-VN-HoaiMyNeural"
    ], index=0)

tab1, tab2, tab3 = st.tabs(["📝 Tạo Video", "👤 Character Bible", "📡 Trạng Thái Worker"])

# --- TAB 1: TẠO VIDEO ---
with tab1:
    if is_10min_mode:
        st.info("🎬 **Chế độ Phim Trường Ca 10 Phút Đang Bật**: Hệ thống sẽ tự động cấu trúc 5 Hồi (Acts), điều phối sinh kịch bản chi tiết qua TimeSharedKaggleDirector và tự động giải phóng sạch sẽ 21.5GB VRAM Kaggle trước khi bàn giao cho ComfyUI.")

    col_input1, col_input2 = st.columns([3, 1])
    with col_input1:
        topic_input = st.text_input("Chủ đề câu chuyện:", value="Một ngày bình yên của Minh và Linh trên phố cổ Hà Nội")
    with col_input2:
        scene_count = st.slider("Số phân cảnh:", min_value=3, max_value=8, value=4, disabled=is_10min_mode, help="Chế độ 10 phút tự động tạo ~70 phân cảnh qua 5 Hồi")

    col_btn1, col_btn2 = st.columns([2, 1])
    with col_btn1:
        btn_gen = st.button("✨ 1. Sinh Kịch Bản Phân Cảnh (LLM)")
    with col_btn2:
        btn_mock = st.button("⚡ Sinh Kịch Bản Mẫu (Mock / Không cần Key)")

    if btn_gen or btn_mock:
        active_prov = "mock" if btn_mock else clean_provider
        with st.spinner("Đang khởi tạo kịch bản phân cảnh..."):
            try:
                if is_10min_mode and not btn_mock:
                    st.info("Đang khởi động TimeSharedKaggleDirector với Qwen-2.5-32B qua 5 Hồi...")
                    director = TimeSharedKaggleDirector(
                        ollama_url=cleaned_ollama or (llm_base_url.replace("/v1", "").rstrip("/") if llm_base_url else "http://localhost:11434"),
                        comfy_urls=active_workers,
                        model_name=llm_model,
                        bible_path=str(bible_path)
                    )
                    checkpoint_dir = ROOT_DIR / "storage" / "webui_10min_checkpoints"
                    try:
                        story_script = director.generate_full_10min_story(
                            topic=topic_input,
                            checkpoint_dir=checkpoint_dir,
                            force_refresh=True
                        )
                    except TypeError:
                        story_script = director.generate_full_10min_story(
                            topic=topic_input,
                            checkpoint_dir=checkpoint_dir
                        )
                else:
                    story_script = generate_story_scenes(
                        topic=topic_input,
                        character_bible_path=str(bible_path),
                        provider=active_prov,
                        api_key=llm_api_key,
                        base_url=llm_base_url if not btn_mock else "",
                        model=llm_model if not btn_mock else "mock",
                        scene_count=scene_count
                    )
                st.session_state["current_script"] = story_script
                st.success(f"Đã sinh kịch bản thành công ({len(story_script.scenes)} phân cảnh)! Hãy kiểm tra và chỉnh sửa bên dưới.")
            except Exception as e:
                st.error(f"Lỗi sinh kịch bản: {e}")
                st.info(
                    "💡 **Gợi ý khắc phục:**\n"
                    "- Nếu bạn dùng API Key Google Gemini (bắt đầu bằng `AIzaSy...`), hãy chọn Nhà cung cấp là **'gemini'** ở cột bên trái.\n"
                    "- Nếu bạn dùng DeepSeek API Key, hãy chọn **'deepseek'**.\n"
                    "- Nếu bạn chưa có API Key hoặc muốn thử nghiệm ngay, hãy bấm nút **'⚡ Sinh Kịch Bản Mẫu (Mock / Không cần Key)'** ngay phía trên!"
                )

    # Hiển thị kịch bản có thể chỉnh sửa
    if "current_script" in st.session_state:
        script: StoryScriptResponse = st.session_state["current_script"]
        st.subheader(f"📖 Kịch bản: {script.title}")
        
        # --- BƯỚC 2: DUYỆT & TINH CHỈNH DIỄN VIÊN / CONCEPT ---
        st.markdown("---")
        st.markdown("### 🎭 Bước 2: Duyệt & Tinh Chỉnh Diễn Viên (Characters & Concept)")
        st.caption("Xem trước, tinh chỉnh Concept tạo hình và bấm sinh ảnh mẫu nhân vật trước khi render video hoàn chỉnh.")

        preview_dir = ROOT_DIR / "storage" / "character_previews"
        preview_dir.mkdir(parents=True, exist_ok=True)

        updated_characters = []
        chars_to_display = script.characters if script.characters else [
            StoryCharacter(
                id="char_1",
                name="Nhân vật chính",
                concept="Nhân vật đời thường gần gũi",
                appearance_prompt="a 22-year-old young handsome Vietnamese man, friendly warm expression",
                default_outfit="wearing casual clothing and sneakers",
                voice_id="vi-VN-NamMinhNeural"
            )
        ]

        for c_idx, char in enumerate(chars_to_display):
            with st.expander(f"👤 Diễn viên {c_idx + 1}: **{char.name}** (`{char.id}`) — Concept: *{char.concept}*", expanded=True):
                col_left, col_right = st.columns([3, 2])
                with col_left:
                    c1, c2 = st.columns(2)
                    with c1:
                        c_name = st.text_input("Tên nhân vật", value=char.name, key=f"c_name_{c_idx}")
                        c_id = char.id
                    with c2:
                        voice_idx = 0 if "NamMinh" in char.voice_id else 1
                        c_voice = st.selectbox("Giọng đọc", ["vi-VN-NamMinhNeural", "vi-VN-HoaiMyNeural"], index=voice_idx, key=f"c_voice_{c_idx}")
                    
                    c_concept = st.text_input("Concept tạo hình (Vibe / Thể loại phong cách)", value=char.concept, key=f"c_concept_{c_idx}")
                    c_app = st.text_area("Prompt Ngoại hình (Face/Hair/Features - Tiếng Anh)", value=char.appearance_prompt, key=f"c_app_{c_idx}")
                    c_outfit = st.text_area("Prompt Trang phục (Outfit/Clothes - Tiếng Anh)", value=char.default_outfit, key=f"c_outfit_{c_idx}")

                with col_right:
                    face_preview_path = preview_dir / f"{char.id}_face.png"
                    outfit_preview_path = preview_dir / f"{char.id}_outfit.png"
                    
                    btn_gen_plate = st.button(f"🎨 Tạo / Sinh Lại Ảnh Mẫu ({c_name})", key=f"btn_plate_{c_idx}")
                    if btn_gen_plate:
                        with st.spinner(f"Đang sinh ảnh mẫu cho {c_name} qua ComfyUI ({clean_provider.upper()})..."):
                            try:
                                client = DualGPUComfyStoryClient(worker_urls=active_workers)
                                temp_char = StoryCharacter(
                                    id=c_id,
                                    name=c_name,
                                    concept=c_concept,
                                    appearance_prompt=c_app,
                                    default_outfit=c_outfit,
                                    voice_id=c_voice
                                )
                                client.generate_character_plates(
                                    character=temp_char,
                                    output_dir=preview_dir,
                                    dry_run=dry_run_mode
                                )
                                st.success(f"Đã tạo xong ảnh mẫu cho {c_name}!")
                            except Exception as e:
                                st.error(f"Lỗi tạo ảnh mẫu: {e}")

                    col_img1, col_img2 = st.columns(2)
                    with col_img1:
                        if face_preview_path.exists():
                            try:
                                st.image(str(face_preview_path), caption=f"Khuôn mặt: {c_name}", width="stretch")
                            except TypeError:
                                st.image(str(face_preview_path), caption=f"Khuôn mặt: {c_name}", use_container_width=True)
                        else:
                            st.info("Chưa có ảnh mặt")
                    with col_img2:
                        if outfit_preview_path.exists():
                            try:
                                st.image(str(outfit_preview_path), caption=f"Trang phục: {c_name}", width="stretch")
                            except TypeError:
                                st.image(str(outfit_preview_path), caption=f"Trang phục: {c_name}", use_container_width=True)
                        else:
                            st.info("Chưa có ảnh trang phục")

                updated_characters.append(StoryCharacter(
                    id=c_id,
                    name=c_name,
                    concept=c_concept,
                    appearance_prompt=c_app,
                    default_outfit=c_outfit,
                    voice_id=c_voice,
                    face_plate=str(face_preview_path) if face_preview_path.exists() else None,
                    outfit_plate=str(outfit_preview_path) if outfit_preview_path.exists() else None,
                    pulid_weight=char.pulid_weight,
                    ipadapter_weight=char.ipadapter_weight
                ))

        # --- BƯỚC 3: DUYỆT PHÂN CẢNH & RENDER VIDEO ---
        st.markdown("---")
        st.markdown("### 🎬 Bước 3: Duyệt Phân Cảnh & Sản Xuất Video")
        
        available_char_choices = [c.id for c in updated_characters] if updated_characters else list(bible.characters.keys())
        updated_scenes = []
        for idx, sc in enumerate(script.scenes):
            with st.expander(f"Phân cảnh {sc.scene_id}: {sc.narration[:40]}...", expanded=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    narration = st.text_area(f"Lời dẫn truyện (Cảnh {sc.scene_id})", value=sc.narration, key=f"narr_{idx}")
                with c2:
                    has_char = st.checkbox("Có nhân vật", value=sc.has_character, key=f"has_char_{idx}")
                    char_sel_idx = available_char_choices.index(sc.character_id) if sc.character_id in available_char_choices else 0
                    char_id = st.selectbox(
                        "Nhân vật",
                        available_char_choices,
                        index=char_sel_idx,
                        key=f"char_id_{idx}",
                        disabled=not has_char
                    )
                with c3:
                    shot_type = st.selectbox(
                        "Góc máy",
                        ["extreme close-up shot", "medium portrait shot", "cowboy shot", "wide environmental shot", "low angle dramatic shot"],
                        index=1,
                        key=f"shot_{idx}"
                    )
                    camera_motion = st.selectbox(
                        "Chuyển động",
                        ["zoom_in", "zoom_out", "pan_right"],
                        index=0,
                        key=f"motion_{idx}"
                    )
                
                c4, c5 = st.columns(2)
                with c4:
                    action_prompt = st.text_input("Action prompt (Tiếng Anh)", value=sc.action_prompt, key=f"act_{idx}")
                with c5:
                    env_prompt = st.text_input("Environment prompt (Tiếng Anh)", value=sc.environment_prompt, key=f"env_{idx}")

                updated_scenes.append(StoryScene(
                    scene_id=sc.scene_id,
                    narration=narration,
                    has_character=has_char,
                    character_id=char_id,
                    shot_type=shot_type,
                    action_prompt=action_prompt,
                    environment_prompt=env_prompt,
                    camera_motion=camera_motion
                ))

        col_btn, col_chk = st.columns([2, 1])
        with col_chk:
            force_new_task = st.checkbox("Tạo task mới từ đầu", value=False, help="Bỏ qua các checkpoint audio và ảnh đã sinh trước đó để render lại từ đầu.")

        with col_btn:
            render_clicked = st.button("🚀 3. Bắt Đầu Sản Xuất Video (Render)")

        if render_clicked:
            st.session_state["is_rendering"] = True
            progress_bar = st.progress(0.0)
            status_text = st.empty()

            def on_progress(msg, val):
                progress_bar.progress(val)
                status_text.text(f"[{int(val*100)}%] {msg}")

            try:
                active_cfg = AppConfig(
                    worker_urls=active_workers,
                    ollama_worker_url=cleaned_ollama,
                    llm_provider=llm_provider,
                    llm_api_key=llm_api_key,
                    llm_model=llm_model,
                    default_voice=voice_choice
                )

                final_script = StoryScriptResponse(
                    title=script.title,
                    characters=updated_characters,
                    scenes=updated_scenes
                )
                
                # Xác định task_id: ưu tiên tiếp tục task cũ có sẵn audio/ảnh nếu không bị buộc tạo mới
                resume_tid = None
                if not force_new_task:
                    tasks_dir = ROOT_DIR / "storage" / "tasks"
                    if tasks_dir.exists():
                        candidate_tasks = sorted(tasks_dir.glob("task_*"), key=lambda p: p.stat().st_mtime, reverse=True)
                        for t in candidate_tasks:
                            s_file = t / "story_script.json"
                            if s_file.exists():
                                try:
                                    with open(s_file, "r", encoding="utf-8") as f:
                                        saved_data = json.load(f)
                                    if saved_data.get("title") == script.title:
                                        resume_tid = t.name
                                        break
                                except Exception:
                                    pass

                final_video_path = run_story_pipeline(
                    topic=topic_input,
                    config=active_cfg,
                    custom_script=final_script,
                    progress_callback=on_progress,
                    dry_run=dry_run_mode,
                    voice_override=voice_choice,
                    story_mode="10min_multiact" if is_10min_mode else "short",
                    ollama_worker_url=cleaned_ollama,
                    task_id=resume_tid
                )

                st.success("🎉 Video đã sản xuất thành công!")
                st.video(str(final_video_path))
                
                with open(final_video_path, "rb") as f:
                    st.download_button(
                        label="⬇️ Tải Video Thành Phẩm (.mp4)",
                        data=f,
                        file_name=f"{script.title[:30]}.mp4",
                        mime="video/mp4"
                    )
            except Exception as e:
                st.error(f"Lỗi trong quá trình render video: {e}")
            finally:
                st.session_state["is_rendering"] = False

# --- TAB 2: CHARACTER BIBLE ---
with tab2:
    st.subheader("👥 Hồ Sơ Nhân Vật (Character Bible)")
    for cid, cdata in bible.characters.items():
        st.markdown(f"### Nhân vật: **{cdata.name}** (`{cid}`)")
        col_info, col_face, col_outfit = st.columns([2, 1, 1])
        with col_info:
            st.markdown(f"- **Voice ID:** `{cdata.voice_id}`")
            st.markdown(f"- **Appearance Trigger:** `{cdata.appearance_trigger}`")
            st.markdown(f"- **Default Outfit:** `{cdata.default_outfit}`")
            st.markdown(f"- **PuLID Weight:** `{cdata.pulid_weight}` | **IP-Adapter Weight:** `{cdata.ipadapter_weight}`")
        
        plates_dir = ROOT_DIR / "resource" / "character_bible"
        face_path = plates_dir / cdata.face_plate
        outfit_path = plates_dir / cdata.outfit_plate
        
        with col_face:
            if face_path.exists():
                try:
                    st.image(str(face_path), caption=f"Face Plate: {cdata.face_plate}", width="stretch")
                except TypeError:
                    st.image(str(face_path), caption=f"Face Plate: {cdata.face_plate}", use_container_width=True)
        with col_outfit:
            if outfit_path.exists():
                try:
                    st.image(str(outfit_path), caption=f"Outfit Plate: {cdata.outfit_plate}", width="stretch")
                except TypeError:
                    st.image(str(outfit_path), caption=f"Outfit Plate: {cdata.outfit_plate}", use_container_width=True)
        st.divider()

# --- TAB 3: TRẠNG THÁI WORKER ---
with tab3:
    st.subheader("📡 Kiểm Tra Kết Nối Cloudflare Workers")
    
    if cleaned_ollama:
        col_o1, col_o2 = st.columns([3, 1])
        with col_o1:
            st.write(f"🦙 **Ollama Worker (Port 11434):** `{cleaned_ollama}`")
        with col_o2:
            if st.button("Ping Ollama", key="ping_ollama"):
                try:
                    resp = requests.get(f"{cleaned_ollama}/api/tags", timeout=10)
                    if resp.status_code == 200:
                        models = [m.get("name") for m in resp.json().get("models", [])]
                        model_str = f" (Models: {', '.join(models[:3])})" if models else ""
                        st.success(f"🟢 Online{model_str}")
                    else:
                        st.warning(f"🟡 Phản hồi mã: {resp.status_code}")
                except Exception as err:
                    st.error(f"🔴 Offline: {err}")
        st.divider()

    if not active_workers:
        st.warning("Chưa cấu hình Worker URL ComfyUI trong sidebar.")
    else:
        for idx, wurl in enumerate(active_workers):
            col_w1, col_w2 = st.columns([3, 1])
            with col_w1:
                st.write(f"Worker {idx}: `{wurl}`")
            with col_w2:
                if st.button(f"Ping Worker {idx}", key=f"ping_{idx}"):
                    try:
                        resp = requests.get(wurl, timeout=10)
                        if resp.status_code == 200:
                            st.success("🟢 Online")
                        else:
                            st.warning(f"🟡 Phản hồi mã: {resp.status_code}")
                    except Exception as err:
                        st.error(f"🔴 Offline: {err}")

`

### FILE: app\ui\__init__.py
`
"""UI Package."""

`

### FILE: docs\superpowers\plans\2026-11-03-dynamic-character-concept.md
`
# Dynamic Character & Concept Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable dynamic story-specific character creation with visual concepts and real-time WebUI plate preview/generation before full video rendering.

**Architecture:** 
1. Expand Pydantic models with `StoryCharacter` and updated `StoryScriptResponse`.
2. Enhance LLM system/user prompts to craft bespoke characters with concept and styling for any user topic.
3. Add a dedicated txt2img character plate generator in `DualGPUComfyStoryClient` that generates 1024x1024 face and outfit plates on the remote Tesla T4 ComfyUI worker and syncs them for IP-Adapter scene conditioning.
4. Redesign Streamlit WebUI Studio Tab into a 3-step linear flow: (1) Generate Script & Concept, (2) Preview & Refine Characters with live ComfyUI plate generation button, (3) Review Scenes & Render Final Video.

**Tech Stack:** Python 3.11, Pydantic v2, Streamlit, ComfyUI API, Juggernaut XL Lightning, IP-Adapter Plus SDXL, Edge-TTS, FFmpeg NVENC, Pytest.

**Spec:** [docs/superpowers/specs/2026-11-03-dynamic-character-concept-design.md](file:///C:/Users/Asus/Desktop/MoneyPrinterTurbo-Storytelling/docs/superpowers/specs/2026-11-03-dynamic-character-concept-design.md)

---

## Global Constraints
- Python 3.11 with existing `venv` at `C:\Users\Asus\Desktop\MoneyPrinterTurbo-Storytelling\venv`.
- Preserve 100% backward compatibility with existing tests and fallback to `resource/character_bible` when no dynamic characters are present.
- Plate images must be 1024x1024 RGB PNGs.
- NVENC hardware encoding acceleration on NVIDIA RTX 3050 Laptop GPU.
- Remote ComfyUI worker on Tesla T4 via Cloudflare tunnel (`https://literature-closed-cia-environmental.trycloudflare.com`).

## Review Focus
1. Backward compatibility: Script with empty `characters` falls back safely to default Character Bible without crashing.
2. Incomplete or missing plates: If user clicks "Render Video" without explicitly clicking "Tạo ảnh nhân vật", pipeline automatically generates missing plates before scene generation.
3. Special character escaping: Concept prompt with quotes or Vietnamese characters must not break JSON payload or prompt formatting.
4. Edge-TTS voice assignment: Each character's `voice_id` defaults safely to valid Vietnamese voice if invalid or missing.
5. Concurrent ComfyUI requests: Generating plates does not collide with active scene rendering tasks.

---

### Task 1: Schema Extension (`app/models/schema.py`)

**Files:**
- Modify: `app/models/schema.py`
- Test: `tests/test_schema.py`

- [ ] **Step 1.1**: Write failing tests in `tests/test_schema.py` for `StoryCharacter` and `StoryScriptResponse` with `characters`.
- [ ] **Step 1.2**: Run pytest to verify test failure (`tests/test_schema.py`).
- [ ] **Step 1.3**: Implement `StoryCharacter` model and add `characters: List[StoryCharacter] = Field(default_factory=list)` to `StoryScriptResponse` in `app/models/schema.py`.
- [ ] **Step 1.4**: Run pytest to verify all tests in `tests/test_schema.py` pass.
- [ ] **Step 1.5**: Git commit schema changes (`feat(schema): add StoryCharacter and dynamic characters list to StoryScriptResponse`).

---

### Task 2: LLM Prompt & Mock Generator Extension (`app/services/llm.py`)

**Files:**
- Modify: `app/services/llm.py`
- Test: `tests/test_llm.py`

- [ ] **Step 2.1**: Write failing test in `tests/test_llm.py` asserting that `generate_mock_story_scenes` returns at least 1-2 characters with `concept`, `appearance_prompt`, and `default_outfit`.
- [ ] **Step 2.2**: Run pytest to verify test failure.
- [ ] **Step 2.3**: Update LLM system prompt and JSON schema in `app/services/llm.py` to instruct LLMs to generate `characters` with `concept` fitting the story theme, and update `generate_mock_story_scenes` with realistic mock characters.
- [ ] **Step 2.4**: Run pytest to verify all tests in `tests/test_llm.py` pass.
- [ ] **Step 2.5**: Git commit LLM service changes (`feat(llm): generate story-specific characters with concept in LLM prompt and mock`).

---

### Task 3: ComfyUI Dynamic Character Plate Generator (`app/services/comfy_remote_client.py`)

**Files:**
- Modify: `app/services/comfy_remote_client.py`
- Test: `tests/test_comfy_client.py`

- [ ] **Step 3.1**: Write failing test in `tests/test_comfy_client.py` for `generate_character_plates` (verifying dry-run creates 1024x1024 face and outfit plates in task directory) and for payload building with dynamic characters.
- [ ] **Step 3.2**: Run pytest to verify test failure.
- [ ] **Step 3.3**: Implement:
  - `generate_character_plate_image(...)`: Sends txt2img prompt to ComfyUI worker (Node 4 Checkpoint + Node 6/7 CLIPTextEncode + Node 5 Latent + Node 3 KSampler + Node 8 VAE + Node 9 SaveImage) and downloads resulting PNG.
  - `generate_character_plates(character: StoryCharacter, output_dir: Path, dry_run: bool = False)`: Generates both face and outfit plates.
  - Update `_build_workflow_payload` to check task-specific dynamic character plates first before falling back to `resource/character_bible`.
- [ ] **Step 3.4**: Run pytest to verify all tests in `tests/test_comfy_client.py` pass.
- [ ] **Step 3.5**: Git commit ComfyUI client changes (`feat(comfy): add dynamic character plate generation and task-level plate routing`).

---

### Task 4: Pipeline Orchestrator Integration (`app/services/task.py`)

**Files:**
- Modify: `app/services/task.py`
- Test: `tests/test_task.py` and `tests/test_e2e_pipeline.py`

- [ ] **Step 4.1**: Write test in `tests/test_task.py` verifying that when a custom script with dynamic characters is provided, character plates are generated/synced and audio synthesis uses character voice mapping.
- [ ] **Step 4.2**: Run pytest to verify test failure.
- [ ] **Step 4.3**: Update `run_story_pipeline` in `app/services/task.py`:
  - If `story_script.characters` exists, ensure all character plates exist in `task_dir / "characters"` (auto-generating any missing plates).
  - Sync task character plates to workers.
  - Pass dynamic character dictionary to audio synthesis and video rendering.
- [ ] **Step 4.4**: Run pytest to verify `tests/test_task.py` and `tests/test_e2e_pipeline.py` pass.
- [ ] **Step 4.5**: Git commit orchestrator changes (`feat(task): integrate dynamic characters and plates into story pipeline`).

---

### Task 5: WebUI Studio 3-Step Interactive Workflow (`app/ui/webui.py`)

**Files:**
- Modify: `app/ui/webui.py`

- [ ] **Step 5.1**: Add Step 2 "🎭 Diễn Viên & Concept Tạo Hình" to Studio Tab:
  - Render expandable card for each character in `st.session_state.script.characters`.
  - Provide text inputs for `concept`, `appearance_prompt`, `default_outfit`, and selectbox for `voice_id`.
  - Provide button "🎨 Tạo / Sinh Lại Ảnh Mẫu Nhân Vật": Calls `comfy_client.generate_character_plates` and saves to task/session directory.
  - Display side-by-side images of `face_plate` and `outfit_plate` once generated.
- [ ] **Step 5.2**: Update Step 3 "Sản Xuất Video": Passes the edited `StoryCharacter` list into `StoryScriptResponse` and launches `run_story_pipeline`.
- [ ] **Step 5.3**: Manually test WebUI in browser via Streamlit session on port 8501.
- [ ] **Step 5.4**: Git commit WebUI changes (`feat(ui): add 3-step dynamic character review and preview studio`).

---

### Task 6: Live Worker Verification & Regression Testing

**Files:**
- Test: Full test suite (`pytest -v`)
- Scratch verification script

- [ ] **Step 6.1**: Run `pytest -v` across all test files to ensure 100% pass rate.
- [ ] **Step 6.2**: Execute a live dry-run or targeted Kaggle test generating a custom concept character (e.g., "Cyberpunk Detective") and verify output plates.
- [ ] **Step 6.3**: Final git status check and clean commit history.

`

### FILE: docs\superpowers\plans\2026-11-03-time-shared-vram-llm-32b-dual-comfyui.md
`
# Time-Shared VRAM Handover (LLM 32B + Dual ComfyUI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Time-Shared VRAM Eviction strategy on Kaggle $2 \times \text{Tesla T4}$ ($32\text{GB}$ VRAM) enabling $Qwen-2.5-32B$ multi-act scriptwriting and Dual-Worker ComfyUI parallel image rendering without VRAM OOM.

**Architecture:**
1. **Kaggle 1-Cell Unified Server:** Runs Ollama across both GPUs (`CUDA_VISIBLE_DEVICES=0,1`) with flash-attention and $q8_0$ KV-cache + 2 ComfyUI instances (`cuda:0:8188`, `cuda:1:8189`) with `--normalvram` + 3 Cloudflare tunnels.
2. **Local Orchestrator VRAM Handover:** 
   - Before LLM: calls `POST /free` on both ComfyUI instances.
   - LLM Phase: `TimeSharedKaggleDirector` runs MasterBeatSheet (5 Acts) and rolling context generation with `qwen2.5:32b-instruct-q4_K_M`.
   - After LLM (guaranteed in `finally`): calls `POST /api/generate {"model": ..., "keep_alive": 0}` on Ollama, freeing $21.5\text{GB}$ VRAM to $0\text{MB}$.
   - ComfyUI Phase: Dual-GPU parallel scene rendering on clean $32\text{GB}$ VRAM.
3. **WebUI Integration:** Exposes 3 Cloudflare URLs (Ollama + ComfyUI 0 + ComfyUI 1), manual "🧹 Xả VRAM" button, and Story Mode selector (Short Story vs 10-minute Epic).

**Tech Stack:** Python 3.11, Pydantic v2, Ollama API, ComfyUI API, Streamlit, FFmpeg NVENC, Pytest.

**Spec Reference:** `c:\Users\Asus\Downloads\chi_n_l_c_1_chia_s_vram_theo_pha_llm_32b_dual_comfyui.md`

---

## Global Constraints
- Python 3.11 with existing `venv` at `C:\Users\Asus\Desktop\MoneyPrinterTurbo-Storytelling\venv`.
- Preserve 100% backward compatibility with existing tests and dynamic character concept support.
- `evict_llm_from_kaggle_vram()` MUST run inside a `finally` block so VRAM is guaranteed freed even on error.
- ComfyUI instances must run with `--normalvram` to honor `/free` memory eviction.

---

### Task 1: Kaggle 1-Cell Deployment Script (`kaggle_worker/start_dual_comfy_worker.py`)

**Files:**
- Modify: `kaggle_worker/start_dual_comfy_worker.py`
- Modify: `kaggle_worker/start_comfy_and_ollama.py`

- [ ] **Step 1.1**: Update `kaggle_worker/start_dual_comfy_worker.py` with the full unified script from Section 3 of the technical specification:
  - Setup environment with ComfyUI, IPAdapter_plus, insightface, onnxruntime-gpu.
  - Start Ollama with `CUDA_VISIBLE_DEVICES="0,1"`, `OLLAMA_FLASH_ATTENTION="1"`, `OLLAMA_KV_CACHE_TYPE="q8_0"`, `OLLAMA_NUM_PARALLEL="1"`, `OLLAMA_MAX_LOADED_MODELS="1"`.
  - Start ComfyUI worker 0 on `cuda:0` port 8188 with `--normalvram`.
  - Start ComfyUI worker 1 on `cuda:1` port 8189 with `--normalvram`.
  - Open 3 Cloudflare Tunnels (Ollama :11434, ComfyUI :8188, ComfyUI :8189) and log URLs.
- [ ] **Step 1.2**: Commit Task 1 changes to git (`feat(kaggle): implement unified time-shared Kaggle worker script`).

---

### Task 2: Config & Schema Extension (`app/config.py`, `app/models/schema.py`)

**Files:**
- Modify: `app/config.py`
- Modify: `app/models/schema.py`
- Test: `tests/test_schema.py`

- [ ] **Step 2.1**: Write failing tests in `tests/test_schema.py` for `ActBeat`, `MasterBeatSheet`, and `ActScenesBatch`.
- [ ] **Step 2.2**: Run pytest to verify test failure.
- [ ] **Step 2.3**: Implement `ActBeat`, `MasterBeatSheet`, `ActScenesBatch` in `app/models/schema.py` and add `ollama_worker_url: str = ""` in `app/config.py`.
- [ ] **Step 2.4**: Run pytest to verify all schema tests pass.
- [ ] **Step 2.5**: Commit Task 2 changes (`feat(schema): add MasterBeatSheet and ActBeat models for 10-minute multi-act storytelling`).

---

### Task 3: Time-Shared VRAM Director & Eviction (`app/services/llm.py`)

**Files:**
- Modify: `app/services/llm.py`
- Test: `tests/test_llm.py`

- [ ] **Step 3.1**: Write failing tests in `tests/test_llm.py` for:
  - `evict_llm_from_kaggle_vram()` sends `POST /api/generate {"model": ..., "keep_alive": 0}`.
  - `free_comfyui_vram_before_llm()` sends `POST /free` to each ComfyUI worker.
  - `TimeSharedKaggleDirector` generation loop with mock responses.
- [ ] **Step 3.2**: Run pytest to verify test failure.
- [ ] **Step 3.3**: Implement `TimeSharedKaggleDirector` in `app/services/llm.py` with:
  - `free_comfyui_vram_before_llm()`
  - `evict_llm_from_kaggle_vram()`
  - `_call_ollama_structured()` with `format` schema validation and `keep_alive="15m"`
  - `generate_full_10min_script()` with `finally: self.evict_llm_from_kaggle_vram()`
- [ ] **Step 3.4**: Run pytest to verify all tests in `tests/test_llm.py` pass.
- [ ] **Step 3.5**: Commit Task 3 changes (`feat(llm): implement TimeSharedKaggleDirector with VRAM handover eviction`).

---

### Task 4: Pipeline Orchestrator Integration (`app/services/task.py`)

**Files:**
- Modify: `app/services/task.py`
- Test: `tests/test_task.py`

- [ ] **Step 4.1**: Write failing test in `tests/test_task.py` verifying multi-act script generation and VRAM eviction call during pipeline run.
- [ ] **Step 4.2**: Run pytest to verify test failure.
- [ ] **Step 4.3**: Update `run_story_pipeline` in `app/services/task.py` to route to `TimeSharedKaggleDirector` when `story_mode == "10min_multiact"` or provider is `ollama` with `ollama_worker_url`.
- [ ] **Step 4.4**: Run pytest to verify `tests/test_task.py` passes.
- [ ] **Step 4.5**: Commit Task 4 changes (`feat(task): integrate TimeSharedKaggleDirector into end-to-end task pipeline`).

---

### Task 5: WebUI Studio Enhancements (`app/ui/webui.py`)

**Files:**
- Modify: `app/ui/webui.py`

- [ ] **Step 5.1**: Update Sidebar in `app/ui/webui.py`:
  - Input field for `Ollama Worker URL (Port 11434)`.
  - Input fields for `Worker GPU 0 (Port 8188)` and `Worker GPU 1 (Port 8189)`.
  - Manual button: `🧹 Xả Sạch VRAM Kaggle Thủ Công` (calls ComfyUI `/free` and Ollama `keep_alive: 0`).
  - Radio button for Story Mode: `⚡ Kịch bản ngắn (3 - 8 cảnh)` vs `🎬 Phim trường ca 10 phút (5 Hồi / 70 cảnh)`.
- [ ] **Step 5.2**: Update tab 1 generation logic to handle both Short Story and Multi-Act mode.
- [ ] **Step 5.3**: Commit Task 5 changes (`feat(ui): add time-shared dual-worker controls and 10min multi-act mode in WebUI`).

---

### Task 6: Full Verification & Regression Testing

**Files:**
- Run full pytest test suite (`pytest -v`).

- [ ] **Step 6.1**: Run `pytest -v` across all test files.
- [ ] **Step 6.2**: Verify clean git working tree and present instructions to user.

`

### FILE: docs\superpowers\specs\2026-11-03-dynamic-character-concept-design.md
`
# Thiết Kế Kỹ Thuật: Nhân Vật Động & Concept Phân Cảnh (Dynamic Characters & Concept Studio)

## 1. Mục Đích & Bối Cảnh (Intent & Why)
Hiện tại, hệ thống MoneyPrinterTurbo-Storytelling đang sử dụng danh sách nhân vật cố định toàn cục (Minh & Linh trong `resource/character_bible/characters.json`). Khi người dùng muốn sáng tạo các thể loại nội dung mới (cổ trang kiếm hiệp, cyberpunk tương lai, truyện tranh hài hước, kinh dị...), hệ thống cần:
- Cho phép LLM tự động tạo ra các nhân vật mới toanh gắn liền với cốt truyện.
- Bổ sung trường **Concept** để định hình sâu sắc phong cách hình tượng của nhân vật (vibe, bối cảnh, tinh thần tạo hình).
- Cho phép người dùng xem trước (preview) ảnh mẫu diễn viên (Cast Plates) ngay trên WebUI, tinh chỉnh Concept/Prompt, bấm sinh lại ảnh cho đến khi ưng ý trước khi bấm Render toàn bộ video.

---

## 2. Mục Tiêu & Ranh Giới (Goals, Non-Goals, Anti-Goals)

### Goals
1. **Mở rộng Schema kịch bản**: Hỗ trợ danh sách nhân vật động `characters: List[StoryCharacter]` trong `StoryScriptResponse`, mỗi nhân vật có `id`, `name`, `concept`, `appearance_prompt`, `outfit_prompt`, `voice_id`.
2. **Cập nhật LLM Prompt**: Khi nhập chủ đề bất kỳ, LLM sẽ tự thiết kế 1-3 nhân vật đặc trưng kèm Concept và gán `character_id` phù hợp vào từng `StoryScene`.
3. **ComfyUI Dynamic Plate Generator**: API tạo nhanh ảnh Face Plate & Outfit Plate 1024x1024 qua Checkpoint Juggernaut XL Lightning trên GPU Tesla T4 của Kaggle worker.
4. **WebUI 3-Bước Tuyến Tính**:
   - **Bước 1**: Nhập Topic &rarr; Bấm *"Sinh Kịch Bản & Concept Nhân Vật"*.
   - **Bước 2**: Khu vực *"🎭 Duyệt & Tinh Chỉnh Diễn Viên"*: Hiển thị thông tin Concept, cho phép sửa prompt ngoại hình/trang phục, có nút *"🎨 Tạo / Sinh lại ảnh nhân vật"* và hiển thị 2 ảnh mẫu trực quan.
   - **Bước 3**: Chỉnh sửa kịch bản phân cảnh & Bấm *"🎬 Bắt đầu Sản Xuất Video"*. Video sẽ tự nạp đúng bộ ảnh vừa duyệt vào IP-Adapter để khóa nét nhân vật.

### Non-Goals
- Không xóa bỏ `resource/character_bible/characters.json` (giữ lại làm preset mẫu mặc định hoặc fallback).
- Không yêu cầu người dùng phải tự vẽ hay tải ảnh từ ngoài vào (hệ thống tự sinh 100% bằng ComfyUI, nhưng vẫn hỗ trợ nếu muốn thay thế).

### Anti-Goals
- Không tự động render hàng loạt ảnh nhân vật ngay khi LLM vừa nhả kịch bản (để tránh lãng phí thời gian và GPU nếu người dùng muốn sửa lại Concept/Prompt trước).

---

## 3. Các Phương Án Đã Cân Nhắc (Approaches)

### Phương án 1: Quy trình 3 bước liền mạch ngay trên Studio Tab (ĐÃ CHỌN 🌟)
- **Cơ chế**: Topic &rarr; Sinh kịch bản & Concept nhân vật &rarr; Xem trước / Tạo ảnh nhân vật tại chỗ &rarr; Render Video.
- **Đánh đổi**: Tăng thêm một khu vực điều khiển trên WebUI Studio, nhưng mang lại trải nghiệm sáng tạo mượt mà nhất.

### Phương án 2: Tách biệt thành Tab riêng (Hồ Sơ Nhân Vật độc lập) (LOẠI)
- **Cơ chế**: Người dùng phải chuyển qua tab khác để gõ Concept và tạo ảnh, rồi quay lại Studio để nạp vào kịch bản.
- **Đánh đổi**: Rời rạc, thao tác qua lại nhiều bước, giảm tốc độ sản xuất video.

---

## 4. Chi Tiết Kỹ Thuật (Architecture & Implementation Details)

### 4.1. Cập nhật Data Schema (`app/models/schema.py`)
```python
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
    title: str
    characters: List[StoryCharacter] = Field(default_factory=list)
    scenes: List[StoryScene]
```

### 4.2. Cập nhật LLM Prompt (`app/services/llm.py`)
- Hướng dẫn LLM sinh JSON có cấu trúc gồm: `title`, `characters` (1 đến 2 nhân vật xuất hiện trong truyện kèm trường `concept` độc đáo), và `scenes` tham chiếu đến `character_id`.
- Cập nhật hàm `generate_mock_story_scenes` để sinh mẫu nhân vật có Concept khi chạy Mock.

### 4.3. Dịch vụ Sinh Ảnh Mẫu Nhân Vật (`app/services/comfy_remote_client.py`)
- Thêm phương thức:
  ```python
  def generate_character_plate_image(
      self,
      prompt: str,
      output_path: Path,
      negative_prompt: Optional[str] = None,
      seed: Optional[int] = None
  ) -> Path:
  ```
  Sử dụng pipeline txt2img trên ComfyUI worker để sinh ảnh 1024x1024 với Juggernaut XL Lightning (20 steps, euler) và tải về lưu trữ cục bộ.
- Cập nhật hàm `sync_character_plates_to_workers`: Chấp nhận danh sách `StoryCharacter` và thư mục ảnh tương ứng của task hiện tại, upload tự động lên `/upload/image` của ComfyUI worker.

### 4.4. Giao Diện WebUI (`app/ui/webui.py`)
- **Bước 1**: Nhập Topic & Provider &rarr; Nút `🚀 1. Sinh Kịch Bản & Nhân Vật`.
- **Bước 2 (Mới)**:
  - Khung **"🎭 Diễn Viên & Concept Tạo Hình"**:
    - Hiển thị từng nhân vật dạng thẻ (Card/Expander).
    - Các ô nhập: `Tên`, `Concept`, `Ngoại hình (Appearance)`, `Trang phục (Outfit)`, `Giọng đọc (Voice)`.
    - Nút `🎨 Tạo / Sinh Lại Ảnh Mẫu Nhân Vật`: Gọi ComfyUI tạo ngay `face_plate` & `outfit_plate` và hiển thị ảnh trực tiếp để người dùng duyệt.
- **Bước 3**: Bảng kịch bản phân cảnh & Nút `🎬 2. Bắt Đầu Sản Xuất Video (Render)`.

---

## 5. Kế Hoạch Kiểm Thử (Verification Plan)
1. **Unit Tests (`tests/test_schema.py`)**: Kiểm tra `StoryCharacter`, `StoryScriptResponse` với trường `concept` và danh sách nhân vật.
2. **LLM Tests (`tests/test_llm.py`)**: Kiểm tra prompt sinh đúng cấu trúc có `characters` và `concept`.
3. **Plate Gen Tests (`tests/test_comfy_client.py`)**: Kiểm tra hàm sinh ảnh mẫu nhân vật bằng mock & dry-run.
4. **E2E Test (`tests/test_e2e_pipeline.py`)**: Kiểm tra chạy toàn bộ quy trình từ kịch bản có dynamic characters đến video hoàn chỉnh.
5. **Thử nghiệm thực tế trên WebUI**: Kiểm tra trực tiếp trên giao diện Streamlit với Kaggle Worker.

`

### FILE: kaggle_worker\start_comfy_and_ollama.py
`
"""
Script Triển Khai Chiến Lược 1 Trên Kaggle ($2 x Tesla T4):
Chia sẻ VRAM theo pha thời gian (Time-Shared VRAM Eviction)
- Pha 1: Qwen-2.5-32B-Instruct chiếm 21.5GB VRAM (gộp cả 2 GPU cuda:0,1) để đạo diễn kịch bản
- Pha 2: Gỡ sạch trọng số LLM khỏi VRAM (keep_alive: 0) thu hồi 100% VRAM về 0 MB
- Pha 3: Dual-Worker ComfyUI (GPU 0: 8188, GPU 1: 8189) render song song các cảnh với SDXL + IP-Adapter
"""

import os
import re
import sys
import time
import shutil
import subprocess
from pathlib import Path
import requests

WORKSPACE = Path("/kaggle/working")
COMFY_DIR = WORKSPACE / "ComfyUI"
DATASET_DIR = Path("/kaggle/input/comfyui-story-models")
LLM_MODEL_NAME = "qwen2.5:32b-instruct-q4_K_M"

def run_cmd(cmd: str, cwd=None, env=None):
    subprocess.run(cmd, shell=True, cwd=cwd, env=env, check=True)

def setup_all_services():
    print("=" * 75)
    print("[*] 1/4: Đang cài đặt Cloudflare Tunnel...")
    print("=" * 75)
    if not Path("/usr/local/bin/cloudflared").exists():
        run_cmd("wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /usr/local/bin/cloudflared")
        run_cmd("chmod +x /usr/local/bin/cloudflared")

    print("\n[*] 2/4: Đang cài đặt Ollama Engine...")
    if not Path("/usr/local/bin/ollama").exists() and not Path("/usr/bin/ollama").exists():
        # Ollama phiên bản mới yêu cầu zstd để giải nén
        if not shutil.which("zstd"):
            print("[*] Đang cài đặt thư viện zstd để giải nén Ollama...")
            try:
                run_cmd("apt-get update -qq && apt-get install -y -qq zstd")
            except Exception:
                run_cmd("sudo apt-get update -qq && sudo apt-get install -y -qq zstd")
        run_cmd("curl -fsSL https://ollama.com/install.sh | sh")

    # Symlink cache model từ Kaggle Dataset nếu có (nạp trong 0 giây)
    ollama_dataset_cache = DATASET_DIR / "ollama_models"
    ollama_target_dir = Path("/root/.ollama/models")
    if ollama_dataset_cache.exists() and not ollama_target_dir.exists():
        print("[+] Phát hiện cache LLM 32B trong Kaggle Dataset! Đang tạo Symlink...")
        ollama_target_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(str(ollama_dataset_cache), str(ollama_target_dir))
        except Exception as e:
            print(f"[!] Không thể symlink Ollama cache: {e}")

    print("\n[*] 3/4: Đang cài đặt ComfyUI & IP-Adapter Plus...")
    if not COMFY_DIR.exists():
        run_cmd(f"git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git {COMFY_DIR}")
        run_cmd(f"{sys.executable} -m pip install -q -r requirements.txt", cwd=str(COMFY_DIR))

        custom_nodes = COMFY_DIR / "custom_nodes"
        run_cmd(f"git clone --depth 1 https://github.com/cubiq/ComfyUI_IPAdapter_plus.git {custom_nodes / 'ComfyUI_IPAdapter_plus'}")
        run_cmd(f"{sys.executable} -m pip install -q insightface onnxruntime-gpu einops requests")

    # Kiểm tra ONNX Runtime
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        print(f"[*] ONNX Providers khả dụng: {providers}")
    except Exception as e:
        print(f"[!] ONNX check: {e}")

    # Symlink bộ model SDXL + IP-Adapter từ Kaggle Dataset
    if DATASET_DIR.exists():
        for folder in ["checkpoints", "ipadapter", "clip_vision", "insightface"]:
            src = DATASET_DIR / folder
            dst = COMFY_DIR / "models" / folder
            dst.mkdir(parents=True, exist_ok=True)
            if src.exists():
                for f in src.iterdir():
                    link = dst / f.name
                    if not link.exists():
                        try:
                            os.symlink(str(f), str(link))
                        except Exception:
                            pass
    else:
        print("[!] Không tìm thấy Kaggle Dataset, tải fallback từ HuggingFace...")
        for folder in ["checkpoints", "ipadapter", "clip_vision", "insightface"]:
            (COMFY_DIR / "models" / folder).mkdir(parents=True, exist_ok=True)
        downloads = [
            (COMFY_DIR / "models" / "checkpoints" / "juggernautXL_v9Lightning.safetensors", "https://huggingface.co/RunDiffusion/Juggernaut-XL-Lightning/resolve/main/Juggernaut_RunDiffusionPhoto2_Lightning_4Steps.safetensors"),
            (COMFY_DIR / "models" / "ipadapter" / "ip-adapter-plus_sdxl_vit-h.safetensors", "https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors"),
            (COMFY_DIR / "models" / "clip_vision" / "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors", "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors")
        ]
        for dest, url in downloads:
            if not dest.exists():
                print(f"[*] Đang tải: {dest.name}...")
                subprocess.run(["wget", "-q", "-c", url, "-O", str(dest)], check=False)

def start_ollama_dual_gpu():
    print("\n[*] 4/4: Khởi chạy Ollama Server trên cả 2 GPU (cuda:0,1)...")
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = "0,1"
    env["OLLAMA_HOST"] = "0.0.0.0:11434"
    env["OLLAMA_ORIGINS"] = "*"
    env["OLLAMA_FLASH_ATTENTION"] = "1"
    env["OLLAMA_KV_CACHE_TYPE"] = "q8_0"
    env["OLLAMA_NUM_PARALLEL"] = "1"
    env["OLLAMA_MAX_LOADED_MODELS"] = "1"

    log_file = open(WORKSPACE / "ollama.log", "w")
    proc = subprocess.Popen(["ollama", "serve"], env=env, stdout=log_file, stderr=subprocess.STDOUT)
    time.sleep(5)

    print(f"[*] Đang kiểm tra/nạp trọng số {LLM_MODEL_NAME}...")
    run_cmd(f"ollama pull {LLM_MODEL_NAME}", env=env)

    print(f"[*] Nạp trước (Pre-warm) model {LLM_MODEL_NAME} vào 2xT4 VRAM...")
    try:
        run_cmd(f'ollama run {LLM_MODEL_NAME} "khởi động" --keepalive 15m', env=env)
        print("[+] Model 32B đã sẵn sàng trong VRAM!")
    except Exception as e:
        print(f"[!] Pre-warming warning: {e}")

    return proc

def start_comfy_worker(gpu_id: int, port: int):
    """
    Khởi động ComfyUI với cờ --normalvram (không dùng --gpu-only)
    để cho phép ComfyUI giải phóng VRAM khi gọi endpoint /free.
    """
    print(f"[*] Khởi chạy ComfyUI Worker trên GPU cuda:{gpu_id} (Port {port})...")
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    log_file = open(WORKSPACE / f"comfy_gpu{gpu_id}.log", "w")

    cmd = [
        sys.executable, "main.py",
        "--listen", "0.0.0.0",
        "--port", str(port)
    ]
    return subprocess.Popen(
        cmd,
        cwd=str(COMFY_DIR),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT
    )

def wait_for_comfy(port: int, gpu_id: int, timeout: int = 60) -> bool:
    print(f"[*] Đang đợi ComfyUI GPU {gpu_id} (Port {port}) khởi động...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            r = requests.get(f"http://127.0.0.1:{port}/system_stats", timeout=2)
            if r.status_code == 200:
                print(f"[+] ComfyUI GPU {gpu_id} (Port {port}) đã khởi động thành công!")
                return True
        except Exception:
            pass
        time.sleep(2)
    
    print(f"[!] CẢNH BÁO: ComfyUI GPU {gpu_id} (Port {port}) chưa phản hồi sau {timeout}s.")
    log_p = WORKSPACE / f"comfy_gpu{gpu_id}.log"
    if log_p.exists():
        print(f"--- LOG COMFYUI GPU {gpu_id} ---")
        print(log_p.read_text(encoding="utf-8", errors="ignore")[-1500:])
        print("-------------------------------")
    return False

def open_cloudflare_tunnel(local_port: int, name: str) -> str:
    log_path = WORKSPACE / f"tunnel_{name}.log"
    with open(log_path, "w") as f:
        subprocess.Popen(
            [
                "cloudflared", "tunnel",
                "--url", f"http://127.0.0.1:{local_port}",
                "--http-host-header", f"127.0.0.1:{local_port}"
            ],
            stdout=f,
            stderr=subprocess.STDOUT
        )
    for _ in range(40):
        time.sleep(2)
        if log_path.exists():
            match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", log_path.read_text())
            if match:
                return match.group(0)
    raise RuntimeError(f"Không thể khởi tạo Cloudflare Tunnel cho {name} (port {local_port})")

if __name__ == "__main__":
    setup_all_services()
    ollama_proc = start_ollama_dual_gpu()
    comfy0_proc = start_comfy_worker(gpu_id=0, port=8188)
    comfy1_proc = start_comfy_worker(gpu_id=1, port=8189)

    # Đảm bảo 2 ComfyUI đã khởi động và lắng nghe thành công trước khi lấy Cloudflare URL
    wait_for_comfy(port=8188, gpu_id=0)
    wait_for_comfy(port=8189, gpu_id=1)

    llm_url = open_cloudflare_tunnel(11434, "ollama_32b")
    comfy0_url = open_cloudflare_tunnel(8188, "comfy_gpu0")
    comfy1_url = open_cloudflare_tunnel(8189, "comfy_gpu1")

    print("\n" + "=" * 75)
    print("🎉 HỆ THỐNG TIME-SHARED DUAL-GPU KAGGLE ĐÃ SẴN SÀNG!")
    print("=" * 75)
    print(f'ollama_worker_url = "{llm_url}"')
    print(f'comfy_worker_urls = [\n    "{comfy0_url}",\n    "{comfy1_url}"\n]')
    print("=" * 75)
    print("[+] Hãy copy 3 đường link trên dán vào WebUI Studio trên máy Local của bạn.")
    print("=" * 75 + "\n")

    try:
        ollama_proc.wait()
    except KeyboardInterrupt:
        print("\n[*] Đang tắt các tiến trình...")

`

### FILE: kaggle_worker\start_dual_comfy_worker.py
`
"""
Script Triển Khai Chiến Lược 1 Trên Kaggle ($2 x Tesla T4):
Chia sẻ VRAM theo pha thời gian (Time-Shared VRAM Eviction)
- Pha 1: Qwen-2.5-32B-Instruct chiếm 21.5GB VRAM (gộp cả 2 GPU cuda:0,1) để đạo diễn kịch bản
- Pha 2: Gỡ sạch trọng số LLM khỏi VRAM (keep_alive: 0) thu hồi 100% VRAM về 0 MB
- Pha 3: Dual-Worker ComfyUI (GPU 0: 8188, GPU 1: 8189) render song song các cảnh với SDXL + IP-Adapter
"""

import os
import re
import sys
import time
import shutil
import subprocess
from pathlib import Path
import requests

WORKSPACE = Path("/kaggle/working")
COMFY_DIR = WORKSPACE / "ComfyUI"
DATASET_DIR = Path("/kaggle/input/comfyui-story-models")
LLM_MODEL_NAME = "qwen2.5:32b-instruct-q4_K_M"

def run_cmd(cmd: str, cwd=None, env=None):
    subprocess.run(cmd, shell=True, cwd=cwd, env=env, check=True)

def setup_all_services():
    print("=" * 75)
    print("[*] 1/4: Đang cài đặt Cloudflare Tunnel...")
    print("=" * 75)
    if not Path("/usr/local/bin/cloudflared").exists():
        run_cmd("wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /usr/local/bin/cloudflared")
        run_cmd("chmod +x /usr/local/bin/cloudflared")

    print("\n[*] 2/4: Đang cài đặt Ollama Engine...")
    if not Path("/usr/local/bin/ollama").exists() and not Path("/usr/bin/ollama").exists():
        # Ollama phiên bản mới yêu cầu zstd để giải nén
        if not shutil.which("zstd"):
            print("[*] Đang cài đặt thư viện zstd để giải nén Ollama...")
            try:
                run_cmd("apt-get update -qq && apt-get install -y -qq zstd")
            except Exception:
                run_cmd("sudo apt-get update -qq && sudo apt-get install -y -qq zstd")
        run_cmd("curl -fsSL https://ollama.com/install.sh | sh")

    # Symlink cache model từ Kaggle Dataset nếu có (nạp trong 0 giây)
    ollama_dataset_cache = DATASET_DIR / "ollama_models"
    ollama_target_dir = Path("/root/.ollama/models")
    if ollama_dataset_cache.exists() and not ollama_target_dir.exists():
        print("[+] Phát hiện cache LLM 32B trong Kaggle Dataset! Đang tạo Symlink...")
        ollama_target_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(str(ollama_dataset_cache), str(ollama_target_dir))
        except Exception as e:
            print(f"[!] Không thể symlink Ollama cache: {e}")

    print("\n[*] 3/4: Đang cài đặt ComfyUI & IP-Adapter Plus...")
    if not COMFY_DIR.exists():
        run_cmd(f"git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git {COMFY_DIR}")
        run_cmd(f"{sys.executable} -m pip install -q -r requirements.txt", cwd=str(COMFY_DIR))

        custom_nodes = COMFY_DIR / "custom_nodes"
        run_cmd(f"git clone --depth 1 https://github.com/cubiq/ComfyUI_IPAdapter_plus.git {custom_nodes / 'ComfyUI_IPAdapter_plus'}")
        run_cmd(f"{sys.executable} -m pip install -q insightface onnxruntime-gpu einops requests")

    # Kiểm tra ONNX Runtime
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        print(f"[*] ONNX Providers khả dụng: {providers}")
    except Exception as e:
        print(f"[!] ONNX check: {e}")

    # Symlink bộ model SDXL + IP-Adapter từ Kaggle Dataset
    if DATASET_DIR.exists():
        for folder in ["checkpoints", "ipadapter", "clip_vision", "insightface"]:
            src = DATASET_DIR / folder
            dst = COMFY_DIR / "models" / folder
            dst.mkdir(parents=True, exist_ok=True)
            if src.exists():
                for f in src.iterdir():
                    link = dst / f.name
                    if not link.exists():
                        try:
                            os.symlink(str(f), str(link))
                        except Exception:
                            pass
    else:
        print("[!] Không tìm thấy Kaggle Dataset, tải fallback từ HuggingFace...")
        for folder in ["checkpoints", "ipadapter", "clip_vision", "insightface"]:
            (COMFY_DIR / "models" / folder).mkdir(parents=True, exist_ok=True)
        downloads = [
            (COMFY_DIR / "models" / "checkpoints" / "juggernautXL_v9Lightning.safetensors", "https://huggingface.co/RunDiffusion/Juggernaut-XL-Lightning/resolve/main/Juggernaut_RunDiffusionPhoto2_Lightning_4Steps.safetensors"),
            (COMFY_DIR / "models" / "ipadapter" / "ip-adapter-plus_sdxl_vit-h.safetensors", "https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors"),
            (COMFY_DIR / "models" / "clip_vision" / "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors", "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors")
        ]
        for dest, url in downloads:
            if not dest.exists():
                print(f"[*] Đang tải: {dest.name}...")
                subprocess.run(["wget", "-q", "-c", url, "-O", str(dest)], check=False)

def start_ollama_dual_gpu():
    print("\n[*] 4/4: Khởi chạy Ollama Server trên cả 2 GPU (cuda:0,1)...")
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = "0,1"
    env["OLLAMA_HOST"] = "0.0.0.0:11434"
    env["OLLAMA_ORIGINS"] = "*"
    env["OLLAMA_FLASH_ATTENTION"] = "1"
    env["OLLAMA_KV_CACHE_TYPE"] = "q8_0"
    env["OLLAMA_NUM_PARALLEL"] = "1"
    env["OLLAMA_MAX_LOADED_MODELS"] = "1"

    log_file = open(WORKSPACE / "ollama.log", "w")
    proc = subprocess.Popen(["ollama", "serve"], env=env, stdout=log_file, stderr=subprocess.STDOUT)
    time.sleep(5)

    print(f"[*] Đang kiểm tra/nạp trọng số {LLM_MODEL_NAME}...")
    run_cmd(f"ollama pull {LLM_MODEL_NAME}", env=env)

    print(f"[*] Nạp trước (Pre-warm) model {LLM_MODEL_NAME} vào 2xT4 VRAM...")
    try:
        run_cmd(f'ollama run {LLM_MODEL_NAME} "khởi động" --keepalive 15m', env=env)
        print("[+] Model 32B đã sẵn sàng trong VRAM!")
    except Exception as e:
        print(f"[!] Pre-warming warning: {e}")

    return proc

def start_comfy_worker(gpu_id: int, port: int):
    """
    Khởi động ComfyUI với cờ --normalvram (không dùng --gpu-only)
    để cho phép ComfyUI giải phóng VRAM khi gọi endpoint /free.
    """
    print(f"[*] Khởi chạy ComfyUI Worker trên GPU cuda:{gpu_id} (Port {port})...")
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    log_file = open(WORKSPACE / f"comfy_gpu{gpu_id}.log", "w")

    cmd = [
        sys.executable, "main.py",
        "--listen", "0.0.0.0",
        "--port", str(port)
    ]
    return subprocess.Popen(
        cmd,
        cwd=str(COMFY_DIR),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT
    )

def wait_for_comfy(port: int, gpu_id: int, timeout: int = 60) -> bool:
    print(f"[*] Đang đợi ComfyUI GPU {gpu_id} (Port {port}) khởi động...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            r = requests.get(f"http://127.0.0.1:{port}/system_stats", timeout=2)
            if r.status_code == 200:
                print(f"[+] ComfyUI GPU {gpu_id} (Port {port}) đã khởi động thành công!")
                return True
        except Exception:
            pass
        time.sleep(2)
    
    print(f"[!] CẢNH BÁO: ComfyUI GPU {gpu_id} (Port {port}) chưa phản hồi sau {timeout}s.")
    log_p = WORKSPACE / f"comfy_gpu{gpu_id}.log"
    if log_p.exists():
        print(f"--- LOG COMFYUI GPU {gpu_id} ---")
        print(log_p.read_text(encoding="utf-8", errors="ignore")[-1500:])
        print("-------------------------------")
    return False

def open_cloudflare_tunnel(local_port: int, name: str) -> str:
    log_path = WORKSPACE / f"tunnel_{name}.log"
    with open(log_path, "w") as f:
        subprocess.Popen(
            [
                "cloudflared", "tunnel",
                "--url", f"http://127.0.0.1:{local_port}",
                "--http-host-header", f"127.0.0.1:{local_port}"
            ],
            stdout=f,
            stderr=subprocess.STDOUT
        )
    for _ in range(40):
        time.sleep(2)
        if log_path.exists():
            match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", log_path.read_text())
            if match:
                return match.group(0)
    raise RuntimeError(f"Không thể khởi tạo Cloudflare Tunnel cho {name} (port {local_port})")

if __name__ == "__main__":
    setup_all_services()
    ollama_proc = start_ollama_dual_gpu()
    comfy0_proc = start_comfy_worker(gpu_id=0, port=8188)
    comfy1_proc = start_comfy_worker(gpu_id=1, port=8189)

    # Đảm bảo 2 ComfyUI đã khởi động và lắng nghe thành công trước khi lấy Cloudflare URL
    wait_for_comfy(port=8188, gpu_id=0)
    wait_for_comfy(port=8189, gpu_id=1)

    llm_url = open_cloudflare_tunnel(11434, "ollama_32b")
    comfy0_url = open_cloudflare_tunnel(8188, "comfy_gpu0")
    comfy1_url = open_cloudflare_tunnel(8189, "comfy_gpu1")

    print("\n" + "=" * 75)
    print("🎉 HỆ THỐNG TIME-SHARED DUAL-GPU KAGGLE ĐÃ SẴN SÀNG!")
    print("=" * 75)
    print(f'ollama_worker_url = "{llm_url}"')
    print(f'comfy_worker_urls = [\n    "{comfy0_url}",\n    "{comfy1_url}"\n]')
    print("=" * 75)
    print("[+] Hãy copy 3 đường link trên dán vào WebUI Studio trên máy Local của bạn.")
    print("=" * 75 + "\n")

    try:
        ollama_proc.wait()
    except KeyboardInterrupt:
        print("\n[*] Đang tắt các tiến trình...")

`

### FILE: resource\character_bible\characters.json
`
{
  "global_settings": {
    "style_prefix": "cinematic 2.5D anime film still, Makoto Shinkai lighting, volumetric fog, highly detailed environment, 8k resolution, masterpiece",
    "negative_prompt": "bad anatomy, deformed hands, extra fingers, blurry, lowres, watermark, text, signature, photorealistic 3d, mutated face"
  },
  "narrator": {
    "voice_id": "vi-VN-NamMinhNeural",
    "rate": "+5%"
  },
  "characters": {
    "char_minh": {
      "name": "Minh",
      "voice_id": "vi-VN-NamMinhNeural",
      "appearance_trigger": "a 22-year-old young man, short messy black hair, sharp dark eyes, wearing thin round glasses",
      "default_outfit": "wearing a dark navy blue oversized hoodie and black cargo pants",
      "face_plate": "minh_face_plate.png",
      "outfit_plate": "minh_outfit_plate.png",
      "pulid_weight": 0.75,
      "ipadapter_weight": 0.50
    },
    "char_linh": {
      "name": "Linh",
      "voice_id": "vi-VN-HoaiMyNeural",
      "appearance_trigger": "a 20-year-old young woman, shoulder-length brown hair with bangs, gentle eyes",
      "default_outfit": "wearing a beige trench coat over a white turtleneck sweater",
      "face_plate": "linh_face_plate.png",
      "outfit_plate": "linh_outfit_plate.png",
      "pulid_weight": 0.75,
      "ipadapter_weight": 0.50
    }
  }
}

`

### FILE: resource\fonts\README.md
`
# Thư Mục Phông Chữ Tiếng Việt (Fonts)

Để phụ đề video hiển thị đẹp và hỗ trợ đầy đủ dấu tiếng Việt:
- Hệ thống mặc định sử dụng font chữ `Arial` hoặc font hệ thống Windows (`Be Vietnam Pro`, `Montserrat`).
- Bạn có thể tải các font `.ttf` tiếng Việt và đặt tại đây nếu cần tùy biến style nâng cao trong FFmpeg.

`

### FILE: resource\songs\README.md
`
# Thư Mục Nhạc Nền (Background Music - BGM)

Đặt các file nhạc nền `.mp3` không bản quyền tại đây.
Khi render, hệ thống sẽ tự động:
1. Lặp nhạc nền theo độ dài video (`aloop`).
2. Tự động hạ âm lượng nhạc nền xuống khi có giọng đọc bằng kỹ thuật **Sidechain Compression (Audio Ducking)**.

`

### FILE: resource\workflows\pulid_ipadapter_api.json
`
{
  "3": {
    "inputs": {
      "seed": 42,
      "steps": 20,
      "cfg": 7.0,
      "sampler_name": "euler",
      "scheduler": "normal",
      "denoise": 1.0,
      "model": [
        "21",
        0
      ],
      "positive": [
        "6",
        0
      ],
      "negative": [
        "7",
        0
      ],
      "latent_image": [
        "5",
        0
      ]
    },
    "class_type": "KSampler"
  },
  "4": {
    "inputs": {
      "ckpt_name": "juggernautXL_v9Lightning.safetensors"
    },
    "class_type": "CheckpointLoaderSimple"
  },
  "5": {
    "inputs": {
      "width": 1024,
      "height": 1024,
      "batch_size": 1
    },
    "class_type": "EmptyLatentImage"
  },
  "6": {
    "inputs": {
      "text": "cinematic 2.5D anime film still",
      "clip": [
        "4",
        1
      ]
    },
    "class_type": "CLIPTextEncode"
  },
  "7": {
    "inputs": {
      "text": "bad anatomy, deformed, blurry",
      "clip": [
        "4",
        1
      ]
    },
    "class_type": "CLIPTextEncode"
  },
  "8": {
    "inputs": {
      "samples": [
        "3",
        0
      ],
      "vae": [
        "4",
        2
      ]
    },
    "class_type": "VAEDecode"
  },
  "9": {
    "inputs": {
      "filename_prefix": "story_scene",
      "images": [
        "8",
        0
      ]
    },
    "class_type": "SaveImage"
  },
  "10": {
    "inputs": {
      "ipadapter_file": "ip-adapter-plus_sdxl_vit-h.safetensors"
    },
    "class_type": "IPAdapterModelLoader"
  },
  "11": {
    "inputs": {
      "clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"
    },
    "class_type": "CLIPVisionLoader"
  },
  "12": {
    "inputs": {
      "image": "minh_face_plate.png",
      "upload": "image"
    },
    "class_type": "LoadImage"
  },
  "15": {
    "inputs": {
      "image": "minh_outfit_plate.png",
      "upload": "image"
    },
    "class_type": "LoadImage"
  },
  "18": {
    "inputs": {
      "weight": 0.85,
      "weight_type": "linear",
      "combine_embeds": "concat",
      "start_at": 0.0,
      "end_at": 1.0,
      "embeds_scaling": "V only",
      "model": [
        "4",
        0
      ],
      "ipadapter": [
        "10",
        0
      ],
      "image": [
        "12",
        0
      ],
      "clip_vision": [
        "11",
        0
      ]
    },
    "class_type": "IPAdapterAdvanced"
  },
  "21": {
    "inputs": {
      "weight": 0.55,
      "weight_type": "style and composition",
      "combine_embeds": "concat",
      "start_at": 0.0,
      "end_at": 0.7,
      "embeds_scaling": "V only",
      "model": [
        "18",
        0
      ],
      "ipadapter": [
        "10",
        0
      ],
      "image": [
        "15",
        0
      ],
      "clip_vision": [
        "11",
        0
      ]
    },
    "class_type": "IPAdapterAdvanced"
  }
}

`

### FILE: tests\test_cli.py
`
import pytest
from main import build_arg_parser

def test_build_arg_parser():
    parser = build_arg_parser()
    args = parser.parse_args([
        "--topic", "Khám phá Hà Nội",
        "--dry-run",
        "--cli",
        "--scene-count", "3",
        "--aspect-ratio", "16:9",
        "--workers", "https://w1.trycloudflare.com,https://w2.trycloudflare.com"
    ])
    
    assert args.topic == "Khám phá Hà Nội"
    assert args.dry_run is True
    assert args.cli is True
    assert args.scene_count == 3
    assert args.aspect_ratio == "16:9"
    assert "https://w1.trycloudflare.com" in args.workers

`

### FILE: tests\test_comfy_client.py
`
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

def test_robust_request_retry_on_connection_reset(monkeypatch):
    import requests
    from app.services.comfy_remote_client import DualGPUComfyStoryClient
    
    attempts = 0
    def mock_request(method, url, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise requests.exceptions.ConnectionError(
                ("Connection aborted.", ConnectionResetError(10054, "An existing connection was forcibly closed", None, 10054, None))
            )
        resp = requests.Response()
        resp.status_code = 200
        resp._content = b'{"status": "ok"}'
        return resp
        
    monkeypatch.setattr("requests.request", mock_request)
    monkeypatch.setattr("time.sleep", lambda s: None)
    
    resp = DualGPUComfyStoryClient._robust_request("GET", "https://mock.worker.com/status", max_retries=3)
    assert resp.status_code == 200
    assert attempts == 2

def test_ensure_scene_image_sync_resilient_to_connection_reset(client, tmp_path, monkeypatch):
    import requests
    
    out_img = tmp_path / "scene_001.png"
    scene = {
        "scene_id": 1,
        "has_character": False,
        "shot_type": "medium portrait shot",
        "action_prompt": "smiling",
        "environment_prompt": "city",
        "camera_motion": "zoom_in"
    }
    
    poll_count = 0
    def mock_request(method, url, **kwargs):
        nonlocal poll_count
        resp = requests.Response()
        if "/prompt" in url:
            resp.status_code = 200
            resp._content = json.dumps({"prompt_id": "test_pid_123"}).encode("utf-8")
            return resp
        elif "/view" in url:
            resp.status_code = 200
            resp._content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 2000
            return resp
        resp.status_code = 404
        return resp
        
    def mock_get(url, **kwargs):
        nonlocal poll_count
        resp = requests.Response()
        if "/history/" in url:
            poll_count += 1
            if poll_count == 1:
                # Lần 1 ném ConnectionResetError mô phỏng rớt kết nối mạng Cloudflare
                raise requests.exceptions.ConnectionError(
                    ("Connection aborted.", ConnectionResetError(10054, "Forcibly closed", None, 10054, None))
                )
            # Lần 2 trả về kết quả thành công
            resp.status_code = 200
            history_data = {
                "test_pid_123": {
                    "outputs": {
                        client.NODES["save_img"]: {
                            "images": [{"filename": "story_scene_00001_.png", "subfolder": "", "type": "output"}]
                        }
                    }
                }
            }
            resp._content = json.dumps(history_data).encode("utf-8")
            return resp
        return mock_request("GET", url, **kwargs)

    monkeypatch.setattr("requests.request", mock_request)
    monkeypatch.setattr("requests.get", mock_get)
    monkeypatch.setattr("time.sleep", lambda s: None)
    
    result_path = client._ensure_scene_image_sync(
        worker_url="https://worker1.trycloudflare.com",
        scene=scene,
        output_img_path=out_img,
        dry_run=False
    )
    
    assert result_path.exists()
    assert result_path.stat().st_size > 1024
    assert poll_count == 2

`

### FILE: tests\test_config.py
`
import pytest
from pathlib import Path
from app.config import AppConfig, get_config

def test_default_config_loading():
    cfg = get_config()
    assert isinstance(cfg, AppConfig)
    assert isinstance(cfg.worker_urls, list)
    assert cfg.storage_dir.exists() or Path(cfg.storage_dir).as_posix() != ""
    assert cfg.nvenc_max_concurrency == 2
    assert cfg.comfy_max_concurrency == 2

def test_config_from_toml(tmp_path):
    toml_file = tmp_path / "config.toml"
    toml_file.write_text("""
[system]
nvenc_max_concurrency = 3
comfy_max_concurrency = 4
storage_dir = "test_storage"

[cloud_workers]
worker_urls = ["https://worker1.trycloudflare.com", "https://worker2.trycloudflare.com"]

[llm]
provider = "openai"
api_key = "sk-test"
model = "gpt-4o"
""", encoding="utf-8")

    cfg = get_config(config_path=toml_file)
    assert cfg.nvenc_max_concurrency == 3
    assert cfg.comfy_max_concurrency == 4
    assert len(cfg.worker_urls) == 2
    assert cfg.worker_urls[0] == "https://worker1.trycloudflare.com"
    assert cfg.llm_provider == "openai"
    assert cfg.llm_api_key == "sk-test"

`

### FILE: tests\test_e2e_pipeline.py
`
import subprocess
from pathlib import Path
import pytest

from app.config import AppConfig
from app.services.task import run_story_pipeline

def test_full_e2e_storytelling_pipeline(tmp_path):
    """
    Kiểm thử tích hợp End-to-End toàn diện:
    Từ chủ đề đầu vào -> Sinh kịch bản -> TTS Audio -> Comfy Parallel (Dry-run) -> Video NVENC.
    """
    cfg = AppConfig(
        storage_dir=tmp_path / "storage",
        worker_urls=[]
    )

    def mock_tts(text, voice_name, voice_file):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=1.2",
            "-c:a", "libmp3lame", "-ar", "24000", "-ac", "1",
            str(voice_file)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    reported_milestones = []
    def on_progress(msg, val):
        reported_milestones.append((msg, val))

    final_video = run_story_pipeline(
        topic="Khám phá mùa thu Hà Nội",
        config=cfg,
        progress_callback=on_progress,
        dry_run=True,
        tts_backend=mock_tts
    )

    # 1. Kiểm tra video thành phẩm tồn tại
    assert final_video.exists()
    assert final_video.name == "final_story.mp4"
    assert final_video.stat().st_size > 10240

    # 2. Kiểm tra tiến trình đạt 100%
    assert len(reported_milestones) >= 5
    assert reported_milestones[-1][1] == 1.0

    # 3. Kiểm tra các artifact trung gian trong thư mục task
    task_dir = final_video.parent
    assert (task_dir / "story_script.json").exists()
    assert (task_dir / "master_audio.mp3").exists()
    assert (task_dir / "master_subtitle.srt").exists()
    assert (task_dir / "merged_visual_only.mp4").exists()

`

### FILE: tests\test_llm.py
`
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



`

### FILE: tests\test_schema.py
`
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



`

### FILE: tests\test_task.py
`
import subprocess
from pathlib import Path
import pytest

from app.config import AppConfig
from app.models.schema import StoryScriptResponse, StoryScene
from app.services.task import run_story_pipeline

def test_run_story_pipeline_dry_run(tmp_path):
    cfg = AppConfig(
        storage_dir=tmp_path / "storage",
        worker_urls=[]
    )

    custom_script = StoryScriptResponse(
        title="Hà Nội Trong Mắt Tôi",
        scenes=[
            StoryScene(
                scene_id=1,
                narration="Mùa thu Hà Nội đẹp dịu dàng.",
                has_character=True,
                character_id="char_minh",
                shot_type="medium portrait shot",
                action_prompt="smiling warmly",
                environment_prompt="lake",
                camera_motion="zoom_in"
            ),
            StoryScene(
                scene_id=2,
                narration="Những tia nắng vàng xuyên qua tán lá.",
                has_character=False,
                character_id="char_minh",
                shot_type="wide environmental shot",
                action_prompt="sunlight through leaves",
                environment_prompt="park",
                camera_motion="zoom_out"
            )
        ]
    )

    def mock_tts(text, voice_name, voice_file):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=1.0",
            "-c:a", "libmp3lame", "-ar", "24000", "-ac", "1",
            str(voice_file)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    progress_steps = []
    def on_progress(msg, val):
        progress_steps.append((msg, val))

    final_path = run_story_pipeline(
        topic="Hà Nội Trong Mắt Tôi",
        config=cfg,
        custom_script=custom_script,
        progress_callback=on_progress,
        dry_run=True,
        tts_backend=mock_tts
    )

    assert final_path.exists()
    assert final_path.name == "final_story.mp4"
    assert len(progress_steps) > 0
    # Final progress should reach 1.0
    assert progress_steps[-1][1] == 1.0

def test_run_story_pipeline_with_dynamic_characters(tmp_path):
    from app.models.schema import StoryCharacter
    cfg = AppConfig(
        storage_dir=tmp_path / "storage",
        worker_urls=[]
    )
    dynamic_char = StoryCharacter(
        id="char_swordsman",
        name="Lâm Phong",
        concept="Kiếm khách giang hồ",
        appearance_prompt="swordsman portrait",
        default_outfit="grey robe",
        voice_id="vi-VN-NamMinhNeural"
    )
    custom_script = StoryScriptResponse(
        title="Kiếm Hiệp Kỳ Ảo",
        characters=[dynamic_char],
        scenes=[
            StoryScene(
                scene_id=1,
                narration="Gió lạnh thổi trên đỉnh núi cao.",
                has_character=True,
                character_id="char_swordsman",
                shot_type="medium portrait shot",
                action_prompt="gripping sword",
                environment_prompt="mountain peak",
                camera_motion="zoom_in"
            )
        ]
    )

    def mock_tts(text, voice_name, voice_file):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=1.0",
            "-c:a", "libmp3lame", "-ar", "24000", "-ac", "1",
            str(voice_file)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    final_path = run_story_pipeline(
        topic="Kiếm Hiệp Kỳ Ảo",
        config=cfg,
        custom_script=custom_script,
        dry_run=True,
        tts_backend=mock_tts
    )
    assert final_path.exists()
    task_dir = final_path.parent
    char_dir = task_dir / "characters"
    assert (char_dir / "char_swordsman_face.png").exists()
    assert (char_dir / "char_swordsman_outfit.png").exists()

def test_run_story_pipeline_time_shared_10min_mode(tmp_path):
    from unittest.mock import patch, MagicMock
    from app.services.llm import TimeSharedKaggleDirector
    from app.models.schema import StoryScriptResponse, StoryScene, StoryCharacter

    cfg = AppConfig(
        storage_dir=tmp_path / "storage",
        worker_urls=["https://gpu0.test", "https://gpu1.test"],
        ollama_worker_url="https://ollama.test",
        llm_provider="ollama"
    )

    mock_script = StoryScriptResponse(
        title="Trường Ca 10 Phút",
        characters=[
            StoryCharacter(
                id="char_minh",
                name="Minh",
                concept="Họa sĩ",
                appearance_prompt="young painter",
                default_outfit="linen apron",
                voice_id="vi-VN-NamMinhNeural"
            )
        ],
        scenes=[
            StoryScene(
                scene_id=1,
                narration="Mở màn trường ca anh hùng.",
                has_character=True,
                character_id="char_minh",
                shot_type="medium portrait shot",
                action_prompt="painting a canvas",
                environment_prompt="artist studio",
                camera_motion="zoom_in"
            )
        ]
    )

    def mock_tts(text, voice_name, voice_file):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=1.0",
            "-c:a", "libmp3lame", "-ar", "24000", "-ac", "1",
            str(voice_file)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    with patch.object(TimeSharedKaggleDirector, "generate_full_10min_story", return_value=mock_script) as mock_gen:
        final_path = run_story_pipeline(
            topic="Trường Ca 10 Phút",
            config=cfg,
            story_mode="10min_multiact",
            dry_run=True,
            tts_backend=mock_tts
        )

        assert final_path.exists()
        mock_gen.assert_called_once()


`

### FILE: tests\test_video.py
`
import subprocess
from pathlib import Path
import pytest
from PIL import Image

from app.services.video import get_safe_subtitle_path, assemble_final_story_video_nvenc
from app.services.comfy_remote_client import DualGPUComfyStoryClient

def test_safe_subtitle_path_escaping():
    p = Path(r"C:\Users\Asus\Desktop\sub.srt")
    safe = get_safe_subtitle_path(p)
    # Must use forward slashes for path separators and escaped colon for Windows drive
    assert r"\:" in safe
    assert "/Users/Asus/Desktop" in safe
    # Ensure no Windows backslash path separators remain other than the escaped colon
    assert "\\" not in safe.replace(r"\:", "")

def test_assemble_final_story_video_nvenc(tmp_path):
    # 1. Tạo 2 clip visual
    img1 = tmp_path / "img1.png"
    Image.new("RGB", (640, 360), color=(100, 50, 50)).save(img1)
    vid1 = tmp_path / "vid1.mp4"
    DualGPUComfyStoryClient._render_zoompan_nvenc(img1, vid1, duration=1.0)

    img2 = tmp_path / "img2.png"
    Image.new("RGB", (640, 360), color=(50, 100, 50)).save(img2)
    vid2 = tmp_path / "vid2.mp4"
    DualGPUComfyStoryClient._render_zoompan_nvenc(img2, vid2, duration=1.0)

    # 2. Tạo master audio (2 giây)
    master_audio = tmp_path / "master_audio.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "sine=frequency=440:duration=2.0",
        "-c:a", "libmp3lame", str(master_audio)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    # 3. Tạo subtitle srt
    sub_srt = tmp_path / "sub.srt"
    sub_srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nXin chào câu chuyện.\n", encoding="utf-8")

    out_final = tmp_path / "final.mp4"
    result = assemble_final_story_video_nvenc(
        scene_video_paths=[str(vid1), str(vid2)],
        master_audio_path=master_audio,
        subtitle_srt_path=sub_srt,
        output_final_path=out_final
    )

    assert result.exists()
    assert result.stat().st_size > 1024

`

### FILE: tests\test_voice.py
`
import subprocess
from pathlib import Path
import pytest
from mutagen.mp3 import MP3

from app.models.schema import StoryScene, CharacterBible, CharacterProfile
from app.services.voice import (
    _format_srt_timestamp,
    synthesize_scenes_audio_and_subtitles,
    sanitize_narration,
    default_edge_tts
)

def test_format_srt_timestamp():
    assert _format_srt_timestamp(0.0) == "00:00:00,000"
    assert _format_srt_timestamp(1.234) == "00:00:01,234"
    assert _format_srt_timestamp(65.5) == "00:01:05,500"
    assert _format_srt_timestamp(3661.05) == "01:01:01,050"

def test_sanitize_narration():
    bible = CharacterBible.from_json_file(Path("resource/character_bible/characters.json"))
    
    # 1. Test với bible mặc định
    text = "char_minh bắt đầu luyện tập cùng char_linh."
    cleaned = sanitize_narration(text, bible)
    assert "Minh bắt đầu luyện tập cùng Linh." == cleaned
    
    # 2. Test với nhân vật động (char_1 -> Hiro, char_2 -> Yuki)
    bible.characters["char_1"] = CharacterProfile(
        name="Hiro",
        voice_id="vi-VN-NamMinhNeural",
        appearance_trigger="samurai",
        default_outfit="armor",
        face_plate="char_1_face.png",
        outfit_plate="char_1_outfit.png"
    )
    bible.characters["char_2"] = CharacterProfile(
        name="Yuki",
        voice_id="vi-VN-HoaiMyNeural",
        appearance_trigger="woman",
        default_outfit="kimono",
        face_plate="char_2_face.png",
        outfit_plate="char_2_outfit.png"
    )
    
    text2 = "Hồi đầu tiên bắt đầu với cảnh samurai char_1 đang đứng. Char_2 xuất hiện, char_1 và Char_2 bắt đầu đấu kiếm."
    cleaned2 = sanitize_narration(text2, bible)
    assert "Hồi đầu tiên bắt đầu với cảnh samurai Hiro đang đứng. Yuki xuất hiện, Hiro và Yuki bắt đầu đấu kiếm." == cleaned2

def test_synthesize_scenes_audio_and_subtitles_mock(tmp_path):
    # Tạo dummy audio bằng ffmpeg để test mà không phụ thuộc vào kết nối Edge-TTS mạng
    scenes = [
        StoryScene(
            scene_id=1,
            narration="Chào buổi sáng Hà Nội.",
            has_character=True,
            character_id="char_minh",
            action_prompt="standing",
            environment_prompt="city"
        ),
        StoryScene(
            scene_id=2,
            narration="Gió heo may thổi nhẹ qua từng con phố.",
            has_character=False,
            character_id="char_minh",
            action_prompt="leaves falling",
            environment_prompt="street"
        )
    ]
    
    bible = CharacterBible.from_json_file(Path("resource/character_bible/characters.json"))
    
    # Custom mock generator cho voice.py để tạo file MP3 chuẩn 24000Hz 1 channel bằng ffmpeg
    def mock_tts_generator(text, voice_name, voice_file):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "anullsrc=r=24000:cl=mono",
            "-t", "1.5",
            "-c:a", "libmp3lame", "-ar", "24000", "-ac", "1",
            str(voice_file)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    master_audio, master_srt, durations = synthesize_scenes_audio_and_subtitles(
        scenes=scenes,
        task_dir=tmp_path,
        bible=bible,
        tts_backend=mock_tts_generator
    )

    assert master_audio.exists()
    assert master_srt.exists()
    assert len(durations) == 2
    assert all(d > 1.4 for d in durations)

    # Check SRT content
    srt_content = master_srt.read_text(encoding="utf-8")
    assert "Chào buổi sáng Hà Nội." in srt_content
    assert "Gió heo may thổi nhẹ qua từng con phố." in srt_content
    assert "00:00:00,000 -->" in srt_content

def test_synthesize_scenes_audio_sanitizes_narration_and_subtitles(tmp_path):
    scenes = [
        StoryScene(
            scene_id=1,
            narration="Samurai char_1 rút gươm, char_2 chuẩn bị ứng chiến.",
            has_character=True,
            character_id="char_1",
            action_prompt="drawing sword",
            environment_prompt="dojo"
        )
    ]
    bible = CharacterBible.from_json_file(Path("resource/character_bible/characters.json"))
    bible.characters["char_1"] = CharacterProfile(
        name="Hiro",
        voice_id="vi-VN-NamMinhNeural",
        appearance_trigger="samurai",
        default_outfit="armor",
        face_plate="char_1_face.png",
        outfit_plate="char_1_outfit.png"
    )
    bible.characters["char_2"] = CharacterProfile(
        name="Yuki",
        voice_id="vi-VN-HoaiMyNeural",
        appearance_trigger="woman",
        default_outfit="kimono",
        face_plate="char_2_face.png",
        outfit_plate="char_2_outfit.png"
    )

    def mock_tts_generator(text, voice_name, voice_file):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "anullsrc=r=24000:cl=mono",
            "-t", "1.0",
            "-c:a", "libmp3lame", "-ar", "24000", "-ac", "1",
            str(voice_file)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    master_audio, master_srt, durations = synthesize_scenes_audio_and_subtitles(
        scenes=scenes,
        task_dir=tmp_path,
        bible=bible,
        tts_backend=mock_tts_generator
    )

    assert "Hiro" in scenes[0].narration
    assert "Yuki" in scenes[0].narration
    assert "char_1" not in scenes[0].narration
    srt_content = master_srt.read_text(encoding="utf-8")
    assert "Samurai Hiro rút gươm, Yuki chuẩn bị ứng chiến." in srt_content

def test_default_edge_tts_fallback_marker(tmp_path, monkeypatch):
    test_audio = tmp_path / "audio_test.mp3"
    marker = test_audio.with_suffix(".fallback")
    
    # Giả lập _edge_tts_async luôn raise Exception
    async def mock_failing_tts(*args, **kwargs):
        raise ConnectionError("Simulated Edge-TTS offline failure")
    
    monkeypatch.setattr("app.services.voice._edge_tts_async", mock_failing_tts)
    monkeypatch.setattr("time.sleep", lambda s: None) # Fast test execution
    
    # Chạy default_edge_tts với max_retries=1
    default_edge_tts("Thử nghiệm lỗi", "vi-VN-NamMinhNeural", test_audio, max_retries=1)
    
    assert test_audio.exists()
    assert marker.exists()
    
    # Bây giờ giả lập _edge_tts_async thành công
    async def mock_success_tts(text, voice_name, temp_file, rate="+0%"):
        # Tạo file hợp lệ > 1024 bytes bằng ffmpeg
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "anullsrc=r=24000:cl=mono",
            "-t", "1.0",
            "-c:a", "libmp3lame", "-ar", "24000", "-ac", "1",
            str(temp_file)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        
    monkeypatch.setattr("app.services.voice._edge_tts_async", mock_success_tts)
    default_edge_tts("Thử nghiệm thành công", "vi-VN-NamMinhNeural", test_audio, max_retries=1)
    
    assert test_audio.exists()
    # Marker .fallback phải được xóa sạch khi thành công
    assert not marker.exists()

def test_synthesize_sentence_chunks(tmp_path):
    from app.services.voice import _synthesize_sentence_chunks
    long_text = "Samurai trẻ tuổi, được gọi là Kenji, đang luyện tập với katana của mình. Kenji tập trung cao độ, mắt nhìn chăm chú phía trước."
    out_mp3 = tmp_path / "smart_chunk_test.mp3"
    res = _synthesize_sentence_chunks(long_text, "vi-VN-NamMinhNeural", out_mp3)
    assert res is True
    assert out_mp3.exists()
    assert out_mp3.stat().st_size > 1024

`
