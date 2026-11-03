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
