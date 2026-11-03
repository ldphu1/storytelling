import os
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
    def __init__(
        self,
        worker_urls: Optional[List[str]] = None,
        workflow_path: str = "resource/workflows/pulid_ipadapter_api.json",
        bible_path: str = "resource/character_bible/characters.json"
    ):
        cfg = get_config()
        self.worker_urls = [url.rstrip("/") for url in (worker_urls or cfg.worker_urls)]
        
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

    def sync_character_plates_to_workers(self):
        """Tự động đồng bộ toàn bộ ảnh mẫu từ local lên các ComfyUI Workers trên Kaggle."""
        if not self.worker_urls:
            return

        for char_id, char_data in self.bible.get("characters", {}).items():
            for plate_key in ["face_plate", "outfit_plate"]:
                plate_path = self.bible_dir / char_data[plate_key]
                if not plate_path.exists():
                    raise FileNotFoundError(f"Thiếu ảnh mẫu nhân vật: {plate_path}")

                for worker_url in self.worker_urls:
                    try:
                        with open(plate_path, "rb") as f:
                            files = {"image": (plate_path.name, f, "image/png")}
                            resp = requests.post(
                                f"{worker_url}/upload/image",
                                files=files,
                                data={"overwrite": "true"},
                                timeout=30
                            )
                            resp.raise_for_status()
                    except Exception as e:
                        logger.error(f"Lỗi upload ảnh mẫu lên {worker_url}: {e}")
                        raise

        logger.info(f"Đã đồng bộ toàn bộ ảnh mẫu nhân vật lên {len(self.worker_urls)} Cloud GPU Workers.")

    def _build_workflow_payload(self, scene: Dict[str, Any]) -> Dict[str, Any]:
        """Tạo workflow JSON payload hoàn chỉnh cho từng phân cảnh."""
        with open(self.workflow_path, "r", encoding="utf-8") as f:
            wf = json.load(f)

        global_cfg = self.bible.get("global_settings", {})
        has_char = scene.get("has_character", True)
        char_id = scene.get("character_id", "char_minh")
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

        res = subprocess.run(cmd_nvenc, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if res.returncode != 0:
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
            subprocess.run(cmd_cpu, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

    def _ensure_scene_image_sync(
        self,
        worker_url: Optional[str],
        scene: Dict[str, Any],
        output_img_path: Path,
        dry_run: bool = False
    ) -> Path:
        """Sinh hoặc tải ảnh cho phân cảnh nếu chưa tồn tại (Checkpoint)."""
        if output_img_path.exists() and output_img_path.stat().st_size > 1024:
            return output_img_path

        if dry_run or not worker_url:
            logger.info(f"[Dry-Run] Tạo ảnh giả lập cho Cảnh {scene['scene_id']}...")
            self._create_placeholder_image(scene, output_img_path)
            return output_img_path

        logger.info(f"Đang gửi Cảnh {scene['scene_id']} tới ComfyUI worker ({worker_url})...")
        wf_payload = self._build_workflow_payload(scene)
        client_id = str(uuid.uuid4())
        resp = requests.post(
            f"{worker_url}/prompt",
            json={"prompt": wf_payload, "client_id": client_id},
            timeout=30
        )
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]

        while True:
            hist = requests.get(f"{worker_url}/history/{prompt_id}", timeout=30).json()
            if prompt_id in hist:
                img_meta = hist[prompt_id]["outputs"][self.NODES["save_img"]]["images"][0]
                img_bytes = requests.get(
                    f"{worker_url}/view",
                    params={
                        "filename": img_meta["filename"],
                        "subfolder": img_meta["subfolder"],
                        "type": img_meta["type"]
                    },
                    timeout=60
                ).content
                output_img_path.parent.mkdir(parents=True, exist_ok=True)
                output_img_path.write_bytes(img_bytes)
                logger.success(f"Đã tải thành công ảnh Cảnh {scene['scene_id']} từ {worker_url}")
                break
            time.sleep(1.2)
        return output_img_path

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
        dry_run: bool = False
    ) -> List[str]:
        """
        Chia tải bất đồng bộ chuẩn:
        - comfy_sem: Điều tiết số request đồng thời tới Cloudflare / Kaggle Workers.
        - nvenc_sem: Tách biệt điều tiết số tiến trình FFmpeg zoompan chạy trên GPU/CPU local.
        """
        task_dir.mkdir(parents=True, exist_ok=True)
        if not dry_run and self.worker_urls:
            self.sync_character_plates_to_workers()

        num_workers = max(len(self.worker_urls), 1)
        comfy_sem = asyncio.Semaphore(self.comfy_max_concurrency)
        nvenc_sem = asyncio.Semaphore(self.nvenc_max_concurrency)

        async def _process_single_scene(idx: int, scene: Dict[str, Any], dur: float) -> str:
            worker_url = self.worker_urls[idx % num_workers] if self.worker_urls else None
            img_out = task_dir / f"scene_{scene['scene_id']:03d}.png"
            vid_out = task_dir / f"scene_{scene['scene_id']:03d}.mp4"

            # 1. Sinh / tải ảnh với giới hạn comfy_sem
            async with comfy_sem:
                await asyncio.to_thread(
                    self._ensure_scene_image_sync,
                    worker_url, scene, img_out, dry_run
                )

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
