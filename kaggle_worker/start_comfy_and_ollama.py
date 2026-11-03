"""
Script Khởi Chạy Hybrid Worker Trên Kaggle ($2 x Tesla T4):
- GPU 0 (cuda:0): Chạy ComfyUI (Port 8188) cho Sinh ảnh nhân vật & phân cảnh
- GPU 1 (cuda:1): Chạy Ollama (Port 11434) cho Sinh kịch bản & concept (Model Qwen 2.5 7B)
Cả 2 dịch vụ đều được cấp phát Cloudflare Tunnel riêng biệt.
"""

import os
import re
import sys
import time
import subprocess
from pathlib import Path

WORKSPACE = Path("/kaggle/working")
COMFY_DIR = WORKSPACE / "ComfyUI"
DATASET_DIR = Path("/kaggle/input/comfyui-story-models")

def setup_environment():
    print("=" * 70)
    print("[*] 1. Khởi tạo môi trường ComfyUI & Custom Nodes trên GPU 0...")
    print("=" * 70)

    if not COMFY_DIR.exists():
        subprocess.run(["git", "clone", "--depth", "1", "https://github.com/comfyanonymous/ComfyUI.git", str(COMFY_DIR)], check=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(COMFY_DIR / "requirements.txt")], check=True)

        custom_nodes = COMFY_DIR / "custom_nodes"
        subprocess.run(["git", "clone", "--depth", "1", "https://github.com/cubiq/ComfyUI_IPAdapter_plus.git", str(custom_nodes / "ComfyUI_IPAdapter_plus")], check=True)
        subprocess.run(["git", "clone", "--depth", "1", "https://github.com/smthemex/ComfyUI_StoryDiffusion.git", str(custom_nodes / "ComfyUI_StoryDiffusion")], check=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "insightface", "onnxruntime-gpu", "einops"], check=True)

    # Thiết lập Symlinks hoặc tải model ComfyUI
    print("\n[*] 2. Thiết lập bộ trọng số mô hình ComfyUI...")
    mapping = {
        "checkpoints": COMFY_DIR / "models" / "checkpoints",
        "ipadapter": COMFY_DIR / "models" / "ipadapter",
        "clip_vision": COMFY_DIR / "models" / "clip_vision",
        "insightface": COMFY_DIR / "models" / "insightface"
    }

    if DATASET_DIR.exists():
        print(f"[+] Tìm thấy Kaggle Dataset tại {DATASET_DIR}. Đang tạo Symlinks...")
        for category, target_dir in mapping.items():
            src_dir = DATASET_DIR / category
            target_dir.mkdir(parents=True, exist_ok=True)
            if src_dir.exists():
                for item in src_dir.iterdir():
                    link = target_dir / item.name
                    if not link.exists():
                        link.symlink_to(item)
    else:
        print("[!] Không tìm thấy Kaggle Dataset, tải trực tiếp từ HuggingFace...")
        mapping["checkpoints"].mkdir(parents=True, exist_ok=True)
        mapping["ipadapter"].mkdir(parents=True, exist_ok=True)
        mapping["clip_vision"].mkdir(parents=True, exist_ok=True)
        mapping["insightface"].mkdir(parents=True, exist_ok=True)

        downloads = [
            (mapping["checkpoints"] / "juggernautXL_v9Lightning.safetensors", "https://huggingface.co/RunDiffusion/Juggernaut-XL-Lightning/resolve/main/Juggernaut_RunDiffusionPhoto2_Lightning_4Steps.safetensors"),
            (mapping["ipadapter"] / "ip-adapter-plus_sdxl_vit-h.safetensors", "https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors"),
            (mapping["clip_vision"] / "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors", "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors")
        ]
        for dest, url in downloads:
            if not dest.exists():
                print(f"[*] Đang tải: {dest.name}...")
                subprocess.run(["wget", "-q", "-c", url, "-O", str(dest)], check=False)

    # Cài đặt Cloudflared
    print("\n[*] 3. Thiết lập Cloudflare Tunnel...")
    if not Path("/usr/local/bin/cloudflared").exists():
        subprocess.run([
            "wget", "-q", "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
            "-O", "/usr/local/bin/cloudflared"
        ], check=True)
        subprocess.run(["chmod", "+x", "/usr/local/bin/cloudflared"], check=True)

    # Cài đặt Ollama
    print("\n[*] 4. Cài đặt & Chuẩn bị Ollama trên GPU 1...")
    if not Path("/usr/local/bin/ollama").exists() and not Path("/usr/bin/ollama").exists():
        print("[*] Đang tải Ollama binary...")
        subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)

def launch_comfy(gpu_id: int = 0, port: int = 8188):
    print(f"[*] Khởi chạy ComfyUI trên GPU cuda:{gpu_id} (Port {port})...")
    proc = subprocess.Popen(
        [sys.executable, "main.py", "--listen", "127.0.0.1", "--port", str(port), "--cuda-device", str(gpu_id), "--highvram"],
        cwd=str(COMFY_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT
    )
    log_path = WORKSPACE / f"tunnel_comfy.log"
    with open(log_path, "w") as log_file:
        subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{port}"],
            stdout=log_file,
            stderr=subprocess.STDOUT
        )
    return proc, log_path

def launch_ollama(gpu_id: int = 1, port: int = 11434, model_name: str = "qwen2.5:7b"):
    print(f"[*] Khởi chạy Ollama trên GPU cuda:{gpu_id} (Port {port})...")
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    env["OLLAMA_HOST"] = f"0.0.0.0:{port}"
    
    proc = subprocess.Popen(
        ["ollama", "serve"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT
    )
    time.sleep(3)

    print(f"[*] Đang kéo mô hình LLM ({model_name}) vào GPU 1 VRAM...")
    subprocess.run(["ollama", "pull", model_name], env=env, check=False)

    log_path = WORKSPACE / "tunnel_ollama.log"
    with open(log_path, "w") as log_file:
        subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{port}"],
            stdout=log_file,
            stderr=subprocess.STDOUT
        )
    return proc, log_path

def extract_tunnel_url(log_path: Path, timeout: int = 60) -> str:
    for _ in range(timeout // 2):
        time.sleep(2)
        if log_path.exists():
            content = log_path.read_text()
            match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", content)
            if match:
                return match.group(0)
    raise RuntimeError(f"Không lấy được URL Cloudflare từ {log_path}")

if __name__ == "__main__":
    setup_environment()
    
    # GPU 0: ComfyUI
    comfy_proc, comfy_log = launch_comfy(gpu_id=0, port=8188)
    # GPU 1: Ollama
    ollama_proc, ollama_log = launch_ollama(gpu_id=1, port=11434, model_name="qwen2.5:7b")

    comfy_url = extract_tunnel_url(comfy_log)
    ollama_url = extract_tunnel_url(ollama_log)

    print("\n" + "=" * 70)
    print("🎉 HYBRID KAGGLE WORKER (COMFYUI + OLLAMA) ĐÃ SẴN SÀNG!")
    print("=" * 70)
    print(f"1. COMFYUI WORKER (Dán vào WebUI -> 'Worker GPU 0'):")
    print(f"   👉 {comfy_url}")
    print()
    print(f"2. OLLAMA BASE URL (Chọn LLM 'ollama' -> Dán vào 'Base URL'):")
    print(f"   👉 {ollama_url}/v1")
    print(f"   Model đề xuất: qwen2.5:7b (đã tải sẵn trên GPU 1)")
    print("=" * 70 + "\n")

    try:
        comfy_proc.wait()
    except KeyboardInterrupt:
        print("\n[*] Đang tắt các tiến trình...")
