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
    if voice_override:
        bible.narrator.voice_id = voice_override

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
        voice_override=None,  # Đặt là None để ưu tiên giọng riêng của từng nhân vật trong bible.characters!
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
    if bgm_path is None:
        songs_dir = cfg.resource_dir / "songs"
        available_songs = list(songs_dir.glob("*.mp3")) if songs_dir.exists() else []
        if available_songs:
            bgm_path = available_songs[0]
            logger.info(f"Tự động sử dụng nhạc nền BGM: {bgm_path.name}")

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
