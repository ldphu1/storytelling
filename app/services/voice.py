import asyncio
import os
import re
import subprocess
import time
import uuid
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

def sanitize_narration(text: str, bible: Optional[CharacterBible] = None) -> str:
    """
    Chuẩn hóa lời dẫn truyện trước khi gửi đến TTS và phụ đề:
    - Thay thế các mã kỹ thuật (char_1, char_2, Char_1, Char_2, char_minh, v.v.)
      bằng tên nhân vật thực tế (vd: Hiro, Yuki, Minh, Linh).
    - Chuẩn hóa khoảng trắng và viết hoa đầu câu.
    """
    if not text:
        return text
    
    cleaned = text
    if bible and bible.characters:
        char_items = list(bible.characters.items())
        
        # 1. Thay thế theo ID nhân vật cụ thể trước (vd: char_minh -> Minh, char_1 -> Hiro)
        for cid, profile in char_items:
            if profile.name:
                cleaned = re.sub(rf"\b{re.escape(cid)}\b", profile.name, cleaned, flags=re.IGNORECASE)
                cid_space = cid.replace("_", " ")
                cleaned = re.sub(rf"\b{re.escape(cid_space)}\b", profile.name, cleaned, flags=re.IGNORECASE)
        
        # 2. Thay thế theo thứ tự xuất hiện (vd: char_1 / Char_1 -> nhân vật 1, char_2 -> nhân vật 2)
        for idx, (_, profile) in enumerate(char_items):
            if profile.name:
                pos = idx + 1
                cleaned = re.sub(rf"\bchar_?{pos}\b", profile.name, cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(rf"\bnhân vật {pos}\b", profile.name, cleaned, flags=re.IGNORECASE)
                
    # 3. Chuẩn hóa khoảng trắng dư thừa
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    
    # 4. Viết hoa ký tự đầu câu sau dấu chấm/chấm than/chấm hỏi hoặc đầu chuỗi
    cleaned = re.sub(
        r"(^|[.!?]\s+)([a-zđàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ])",
        lambda m: m.group(1) + m.group(2).upper(),
        cleaned
    )
    return cleaned

async def _edge_tts_async(text: str, voice_name: str, temp_file: Path, rate: str = "+0%"):
    communicate = edge_tts.Communicate(text=text, voice=voice_name, rate=rate)
    await communicate.save(str(temp_file))

def default_edge_tts(text: str, voice_name: str, voice_file: Path, rate: str = "+0%", max_retries: int = 3):
    """
    Sinh giọng đọc Edge-TTS và chuẩn hóa ngay sang 24000Hz Mono
    nhằm khử sai số đệm khung hình (frame padding) khi concat.
    - Hỗ trợ cơ chế Retry với Exponential Backoff khi Microsoft Edge TTS bị nghẽn mạng (NoAudioReceived).
    - Tự động luân chuyển giữa các giọng đọc dự phòng (vi-VN-HoaiMyNeural, vi-VN-NamMinhNeural).
    - Tạo marker .fallback nếu phải dùng âm thanh sine tổng hợp để cho phép tự động thử lại khi re-render.
    """
    voice_file.parent.mkdir(parents=True, exist_ok=True)
    fallback_marker = voice_file.with_suffix(".fallback")
    
    # Tên file raw tạm duy nhất để không bị xung đột tiến trình / đa luồng
    raw_tmp = voice_file.with_name(f"{voice_file.stem}_raw_{uuid.uuid4().hex[:8]}.mp3")
    
    # Danh sách thử nghiệm giọng đọc
    candidate_voices = [voice_name]
    if voice_name != "vi-VN-HoaiMyNeural":
        candidate_voices.append("vi-VN-HoaiMyNeural")
    if "vi-VN-NamMinhNeural" not in candidate_voices:
        candidate_voices.append("vi-VN-NamMinhNeural")

    success = False
    for candidate in candidate_voices:
        for attempt in range(max_retries):
            try:
                if raw_tmp.exists():
                    raw_tmp.unlink()
                asyncio.run(_edge_tts_async(text, candidate, raw_tmp, rate=rate))
                if raw_tmp.exists() and raw_tmp.stat().st_size > 1024:
                    success = True
                    break
                else:
                    logger.warning(f"Giọng {candidate} trả về dữ liệu rỗng (lần {attempt+1}/{max_retries}).")
            except Exception as e:
                logger.warning(f"Giọng {candidate} lần {attempt+1}/{max_retries} thất bại ({e}). Đang thử lại...")
            
            # Backoff delay giữa các lần thử lại để thoát khỏi cửa sổ rate-limit
            time.sleep(1.2 * (attempt + 1))
            
        if success:
            break

    if not success:
        # Fallback offline (sử dụng âm thanh tổng hợp giả lập nếu mất mạng hoặc Microsoft chặn endpoint)
        logger.warning(f"Toàn bộ giọng Edge-TTS không khả dụng. Sử dụng fallback âm thanh tổng hợp cho: '{text[:30]}...'")
        dur_est = max(1.5, len(text.split()) * 0.3)
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"sine=frequency=440:duration={dur_est:.2f}",
            "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "64k",
            str(voice_file)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if raw_tmp.exists():
            raw_tmp.unlink()
        fallback_marker.touch()
        return

    # Chuẩn hóa tần số lấy mẫu về 24000Hz mono
    subprocess.run([
        "ffmpeg", "-y", "-i", str(raw_tmp),
        "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "64k",
        str(voice_file)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    if raw_tmp.exists():
        raw_tmp.unlink()
    if fallback_marker.exists():
        fallback_marker.unlink()

def synthesize_scenes_audio_and_subtitles(
    scenes: List[StoryScene],
    task_dir: Path,
    bible: CharacterBible,
    voice_override: Optional[str] = None,
    tts_backend: Optional[Callable[[str, str, Path], None]] = None
) -> Tuple[Path, Path, List[float]]:
    """
    Sinh audio phân cảnh độc lập, đo thời lượng chính xác T_i và tạo master audio + master srt.
    - Tự động làm sạch và thay thế tên nhân vật thực tế vào narration.
    - Áp dụng giãn cách an toàn giữa các cảnh để tránh nghẽn Microsoft Edge TTS.
    - Tự động thay thế các file âm thanh fallback hỏng trước đó.
    """
    task_dir.mkdir(parents=True, exist_ok=True)
    durations: List[float] = []
    audio_files: List[Path] = []
    srt_entries: List[str] = []
    cumulative_offset = 0.0
    sub_idx = 1

    tts_func = tts_backend or default_edge_tts

    # 1. Chuẩn hóa lời thoại toàn bộ phân cảnh trước
    for scene in scenes:
        scene.narration = sanitize_narration(scene.narration, bible=bible)

    for scene in scenes:
        scene_audio = task_dir / f"audio_{scene.scene_id:03d}.mp3"
        fallback_marker = scene_audio.with_suffix(".fallback")

        # Quyết định giọng đọc: nếu là cảnh nhân vật thì dùng giọng nhân vật, ngược lại dùng narrator
        if voice_override:
            voice_id = voice_override
        elif scene.has_character and scene.character_id in bible.characters:
            voice_id = bible.characters[scene.character_id].voice_id
        else:
            voice_id = bible.narrator.voice_id

        # Chỉ sinh audio nếu file chưa tồn tại hoặc là file fallback lỗi trước đó
        needs_generation = not (scene_audio.exists() and scene_audio.stat().st_size > 512) or fallback_marker.exists()
        if needs_generation:
            logger.info(f"Đang tạo giọng đọc cho Cảnh {scene.scene_id} ({voice_id})...")
            tts_func(scene.narration, voice_id, scene_audio)
            
            # Cooldown 0.5s giữa các cảnh chỉ khi chạy TTS thực tế qua mạng
            if tts_backend is None:
                time.sleep(0.5)

        # Đo thời lượng thực tế của file MP3 chuẩn hóa
        dur = round(MP3(str(scene_audio)).info.length, 3)
        if dur < 1.0:
            # Nếu câu quá ngắn, thêm đệm im lặng vào file audio để đạt tối thiểu 1.0s, tránh lệch đồng bộ với SRT
            pad_dur = round(1.0 - dur, 3)
            padded_audio = scene_audio.with_suffix(".padded.mp3")
            subprocess.run([
                "ffmpeg", "-y", "-i", str(scene_audio),
                "-af", f"apad=pad_dur={pad_dur}",
                "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "64k",
                str(padded_audio)
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            padded_audio.replace(scene_audio)
            dur = 1.0

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
