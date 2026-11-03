import subprocess
from pathlib import Path
from typing import List, Optional
from loguru import logger

def get_safe_subtitle_path(subtitle_path: Path) -> str:
    r"""
    Chuẩn hóa và escape ký tự hai chấm (:) trên ổ đĩa Windows (VD: C:\ -> C\:/)
    để FFmpeg không hiểu nhầm là ký tự phân tách filter parameter.
    """
    posix_path = subtitle_path.resolve().as_posix()
    return posix_path.replace(":", r"\:")

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
