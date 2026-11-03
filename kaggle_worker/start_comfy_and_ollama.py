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
        "--port", str(port),
        "--normalvram"
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
