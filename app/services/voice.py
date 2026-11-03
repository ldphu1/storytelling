import asyncio
import subprocess
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

async def _edge_tts_async(text: str, voice_name: str, temp_file: Path, rate: str = "+0%"):
    communicate = edge_tts.Communicate(text=text, voice=voice_name, rate=rate)
    await communicate.save(str(temp_file))

def default_edge_tts(text: str, voice_name: str, voice_file: Path, rate: str = "+0%"):
    """
    Sinh giọng đọc Edge-TTS và chuẩn hóa ngay sang 24000Hz Mono
    nhằm khử sai số đệm khung hình (frame padding) khi concat.
    """
    raw_tmp = voice_file.with_suffix(".raw.mp3")
    asyncio.run(_edge_tts_async(text, voice_name, raw_tmp, rate=rate))

    # Chuẩn hóa tần số lấy mẫu về 24000Hz mono
    subprocess.run([
        "ffmpeg", "-y", "-i", str(raw_tmp),
        "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "64k",
        str(voice_file)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    if raw_tmp.exists():
        raw_tmp.unlink()

def synthesize_scenes_audio_and_subtitles(
    scenes: List[StoryScene],
    task_dir: Path,
    bible: CharacterBible,
    voice_override: Optional[str] = None,
    tts_backend: Optional[Callable[[str, str, Path], None]] = None
) -> Tuple[Path, Path, List[float]]:
    """
    Sinh audio phân cảnh độc lập, đo thời lượng chính xác T_i và tạo master audio + master srt.
    """
    task_dir.mkdir(parents=True, exist_ok=True)
    durations: List[float] = []
    audio_files: List[Path] = []
    srt_entries: List[str] = []
    cumulative_offset = 0.0
    sub_idx = 1

    tts_func = tts_backend or default_edge_tts

    for scene in scenes:
        scene_audio = task_dir / f"audio_{scene.scene_id:03d}.mp3"

        # Quyết định giọng đọc: nếu là cảnh nhân vật thì dùng giọng nhân vật, ngược lại dùng narrator
        if voice_override:
            voice_id = voice_override
        elif scene.has_character and scene.character_id in bible.characters:
            voice_id = bible.characters[scene.character_id].voice_id
        else:
            voice_id = bible.narrator.voice_id

        # Chỉ sinh audio nếu file chưa tồn tại (Checkpoint)
        if not (scene_audio.exists() and scene_audio.stat().st_size > 512):
            logger.info(f"Đang tạo giọng đọc cho Cảnh {scene.scene_id} ({voice_id})...")
            tts_func(scene.narration, voice_id, scene_audio)

        # Đo thời lượng thực tế của file MP3 chuẩn hóa
        dur = round(MP3(str(scene_audio)).info.length, 3)
        # Đảm bảo thời lượng tối thiểu 1.0s cho mỗi cảnh
        dur = max(dur, 1.0)
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
