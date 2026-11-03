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
