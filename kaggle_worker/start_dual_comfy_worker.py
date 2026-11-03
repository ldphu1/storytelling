"""
Script Khởi Chạy ComfyUI Dual-Worker Trên Kaggle ($2 x Tesla T4)
Chế độ chạy: Accelerator: GPU T4 x 2, Internet: On
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
    print("[*] 1. Khởi tạo môi trường ComfyUI & Custom Nodes khóa nhân vật...")
    print("=" * 70)

    if not COMFY_DIR.exists():
        subprocess.run(["git", "clone", "--depth", "1", "https://github.com/comfyanonymous/ComfyUI.git", str(COMFY_DIR)], check=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(COMFY_DIR / "requirements.txt")], check=True)

        custom_nodes = COMFY_DIR / "custom_nodes"
        subprocess.run(["git", "clone", "--depth", "1", "https://github.com/cubiq/ComfyUI_IPAdapter_plus.git", str(custom_nodes / "ComfyUI_IPAdapter_plus")], check=True)
        subprocess.run(["git", "clone", "--depth", "1", "https://github.com/smthemex/ComfyUI_StoryDiffusion.git", str(custom_nodes / "ComfyUI_StoryDiffusion")], check=True)
        
        # Cài đặt insightface và onnxruntime-gpu
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "insightface", "onnxruntime-gpu", "einops"], check=True)

    # Kiểm tra bắt buộc: InsightFace phải chạy trên GPU (CUDAExecutionProvider)
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        print(f"[*] Available ONNX Providers: {providers}")
        if "CUDAExecutionProvider" not in providers:
            print("[!] CẢNH BÁO: CUDAExecutionProvider không xuất hiện! Đang thử cài lại onnxruntime-gpu...")
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--upgrade", "--force-reinstall", "onnxruntime-gpu"], check=True)
    except Exception as e:
        print(f"[!] Lỗi kiểm tra ONNX Runtime: {e}")

    # Tạo Symlink từ Kaggle Dataset (nạp 0 giây)
    print("\n[*] 2. Thiết lập bộ trọng số mô hình...")
    mapping = {
        "checkpoints": COMFY_DIR / "models" / "checkpoints",
        "ipadapter": COMFY_DIR / "models" / "ipadapter",
        "clip_vision": COMFY_DIR / "models" / "clip_vision",
        "insightface": COMFY_DIR / "models" / "insightface"
    }

    if DATASET_DIR.exists():
        print(f"[+] Tìm thấy Kaggle Dataset tại {DATASET_DIR}. Đang tạo Symlinks...")
        for src_name, dst_path in mapping.items():
            src_path = DATASET_DIR / src_name
            dst_path.mkdir(parents=True, exist_ok=True)
            if src_path.exists():
                for item in src_path.iterdir():
                    target_link = dst_path / item.name
                    if not target_link.exists():
                        os.symlink(str(item), str(target_link))
        print("[+] Đã nạp xong toàn bộ model từ Dataset vào ComfyUI.")
    else:
        print("[!] Không tìm thấy Dataset /kaggle/input/comfyui-story-models.")
        print("[*] Đang thực hiện Fallback: Tải trọng số cơ bản qua Internet...")
        for p in mapping.values():
            p.mkdir(parents=True, exist_ok=True)
        
        # Fallback wget weights nếu chưa kịp chuẩn bị dataset
        ckpt_dest = mapping["checkpoints"] / "juggernautXL_v9Lightning.safetensors"
        if not ckpt_dest.exists():
            print("[*] Đang tải Juggernaut XL Lightning checkpoint...")
            subprocess.run([
                "wget", "-q", "-c",
                "https://huggingface.co/RunDiffusion/Juggernaut-XL-Lightning/resolve/main/Juggernaut_RunDiffusionPhoto2_Lightning_4Steps.safetensors",
                "-O", str(ckpt_dest)
            ], check=False)

    # Cài đặt Cloudflared
    print("\n[*] 3. Thiết lập Cloudflare Tunnel...")
    if not Path("/usr/local/bin/cloudflared").exists():
        subprocess.run([
            "wget", "-q", "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
            "-O", "/usr/local/bin/cloudflared"
        ], check=True)
        subprocess.run(["chmod", "+x", "/usr/local/bin/cloudflared"], check=True)

def launch_worker(gpu_id: int, port: int):
    print(f"[*] Khởi chạy ComfyUI Worker {gpu_id} trên GPU cuda:{gpu_id} (Port {port})...")
    comfy_proc = subprocess.Popen(
        [sys.executable, "main.py", "--listen", "127.0.0.1", "--port", str(port), "--cuda-device", str(gpu_id), "--highvram"],
        cwd=str(COMFY_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT
    )

    log_path = WORKSPACE / f"tunnel_gpu{gpu_id}.log"
    with open(log_path, "w") as log_file:
        subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{port}"],
            stdout=log_file,
            stderr=subprocess.STDOUT
        )
    return comfy_proc, log_path

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
    proc0, log0 = launch_worker(gpu_id=0, port=8188)
    proc1, log1 = launch_worker(gpu_id=1, port=8189)

    url0 = extract_tunnel_url(log0)
    url1 = extract_tunnel_url(log1)

    print("\n" + "=" * 70)
    print("🎉 DUAL-GPU COMFYUI WORKERS ĐÃ SẴN SÀNG HOẠT ĐỘNG!")
    print(f"    WORKER_URLS = [\n        '{url0}',\n        '{url1}'\n    ]")
    print("=" * 70)
    print("[+] Hãy copy 2 đường dẫn trên dán vào WebUI (hoặc config.toml) trên máy Local.")
    print("=" * 70 + "\n")
    proc0.wait()
