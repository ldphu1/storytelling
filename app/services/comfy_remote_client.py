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
                                resp = requests.post(
                                    f"{worker_url}/upload/image",
                                    files=files,
                                    data={"overwrite": "true"},
                                    timeout=30
                                )
                                resp.raise_for_status()
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
        dry_run: bool = False,
        characters_override: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Sinh hoặc tải ảnh cho phân cảnh nếu chưa tồn tại (Checkpoint)."""
        if output_img_path.exists() and output_img_path.stat().st_size > 1024:
            return output_img_path

        if dry_run or not worker_url:
            logger.info(f"[Dry-Run] Tạo ảnh giả lập cho Cảnh {scene['scene_id']}...")
            self._create_placeholder_image(scene, output_img_path)
            return output_img_path

        logger.info(f"Đang gửi Cảnh {scene['scene_id']} tới ComfyUI worker ({worker_url})...")
        wf_payload = self._build_workflow_payload(scene, characters_override=characters_override)
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
        dry_run: bool = False,
        characters_override: Optional[Dict[str, Any]] = None,
        custom_plates: Optional[Dict[str, Path]] = None
    ) -> List[str]:
        """
        Chia tải bất đồng bộ chuẩn:
        - comfy_sem: Điều tiết số request đồng thời tới Cloudflare / Kaggle Workers.
        - nvenc_sem: Tách biệt điều tiết số tiến trình FFmpeg zoompan chạy trên GPU/CPU local.
        """
        task_dir.mkdir(parents=True, exist_ok=True)
        if not dry_run and self.worker_urls:
            self.sync_character_plates_to_workers(custom_plates=custom_plates)

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
                    worker_url, scene, img_out, dry_run, characters_override
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
