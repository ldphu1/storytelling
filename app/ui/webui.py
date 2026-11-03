import json
import os
import sys
from pathlib import Path
import streamlit as st
import requests
from PIL import Image

# Đảm bảo đường dẫn root nằm trong sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import get_config, AppConfig
from app.models.schema import StoryScriptResponse, StoryScene, CharacterBible
from app.services.llm import generate_story_scenes
from app.services.task import run_story_pipeline

st.set_page_config(
    page_title="AI Storytelling Studio",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 Lean AI Storytelling Studio")
st.caption("Hệ thống tự động hóa video kể chuyện AI với nhân vật đồng nhất (Consistent Character Pipeline)")

cfg = get_config()
bible_path = ROOT_DIR / "resource" / "character_bible" / "characters.json"
bible = CharacterBible.from_json_file(bible_path)

# --- SIDEBAR: CẤU HÌNH HỆ THỐNG ---
with st.sidebar:
    st.header("⚙️ Cấu Hình Hệ Thống")
    
    st.subheader("🌐 Cloudflare Tunnel Workers")
    w0_default = cfg.worker_urls[0] if len(cfg.worker_urls) > 0 else ""
    w1_default = cfg.worker_urls[1] if len(cfg.worker_urls) > 1 else ""
    worker_url_0 = st.text_input("Worker GPU 0 (cuda:0, Port 8188)", value=w0_default, placeholder="https://....trycloudflare.com")
    worker_url_1 = st.text_input("Worker GPU 1 (cuda:1, Port 8189)", value=w1_default, placeholder="https://....trycloudflare.com")
    
    active_workers = [u.strip() for u in [worker_url_0, worker_url_1] if u.strip()]
    
    dry_run_mode = st.checkbox("🧪 Chế độ Dry-Run (Không cần GPU Cloud)", value=(len(active_workers) == 0))
    if dry_run_mode:
        st.info("Đang bật chế độ Dry-Run: Hệ thống sẽ tạo ảnh giả lập và dùng FFmpeg local để kiểm tra luồng video.")

    st.subheader("🤖 Cấu hình LLM")
    llm_provider = st.selectbox("Nhà cung cấp LLM", ["openai", "gemini", "ollama", "deepseek"], index=0)
    llm_api_key = st.text_input("API Key", value=cfg.llm_api_key, type="password")
    llm_model = st.text_input("Tên Model", value=cfg.llm_model)

    st.subheader("🎙️ Giọng Đọc Mặc Định")
    voice_choice = st.selectbox("Giọng Đọc Narrator", [
        "vi-VN-NamMinhNeural",
        "vi-VN-HoaiMyNeural"
    ], index=0)

tab1, tab2, tab3 = st.tabs(["📝 Tạo Video", "👤 Character Bible", "📡 Trạng Thái Worker"])

# --- TAB 1: TẠO VIDEO ---
with tab1:
    col_input1, col_input2 = st.columns([3, 1])
    with col_input1:
        topic_input = st.text_input("Chủ đề câu chuyện:", value="Một ngày bình yên của Minh và Linh trên phố cổ Hà Nội")
    with col_input2:
        scene_count = st.slider("Số phân cảnh:", min_value=3, max_value=8, value=4)

    if st.button("✨ 1. Sinh Kịch Bản Phân Cảnh (LLM)"):
        with st.spinner("Đang kết nối LLM sinh kịch bản chi tiết..."):
            try:
                story_script = generate_story_scenes(
                    topic=topic_input,
                    character_bible_path=str(bible_path),
                    provider=llm_provider,
                    api_key=llm_api_key,
                    model=llm_model,
                    scene_count=scene_count
                )
                st.session_state["current_script"] = story_script
                st.success("Đã sinh kịch bản thành công! Hãy kiểm tra và chỉnh sửa bên dưới.")
            except Exception as e:
                st.error(f"Lỗi sinh kịch bản: {e}")

    # Hiển thị kịch bản có thể chỉnh sửa
    if "current_script" in st.session_state:
        script: StoryScriptResponse = st.session_state["current_script"]
        st.subheader(f"📖 Kịch bản: {script.title}")
        
        updated_scenes = []
        for idx, sc in enumerate(script.scenes):
            with st.expander(f"Phân cảnh {sc.scene_id}: {sc.narration[:40]}...", expanded=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    narration = st.text_area(f"Lời dẫn truyện (Cảnh {sc.scene_id})", value=sc.narration, key=f"narr_{idx}")
                with c2:
                    has_char = st.checkbox("Có nhân vật", value=sc.has_character, key=f"has_char_{idx}")
                    char_id = st.selectbox(
                        "Nhân vật",
                        list(bible.characters.keys()),
                        index=0 if sc.character_id == "char_minh" else 1,
                        key=f"char_id_{idx}",
                        disabled=not has_char
                    )
                with c3:
                    shot_type = st.selectbox(
                        "Góc máy",
                        ["extreme close-up shot", "medium portrait shot", "cowboy shot", "wide environmental shot", "low angle dramatic shot"],
                        index=1,
                        key=f"shot_{idx}"
                    )
                    camera_motion = st.selectbox(
                        "Chuyển động",
                        ["zoom_in", "zoom_out", "pan_right"],
                        index=0,
                        key=f"motion_{idx}"
                    )
                
                c4, c5 = st.columns(2)
                with c4:
                    action_prompt = st.text_input("Action prompt (Tiếng Anh)", value=sc.action_prompt, key=f"act_{idx}")
                with c5:
                    env_prompt = st.text_input("Environment prompt (Tiếng Anh)", value=sc.environment_prompt, key=f"env_{idx}")

                updated_scenes.append(StoryScene(
                    scene_id=sc.scene_id,
                    narration=narration,
                    has_character=has_char,
                    character_id=char_id,
                    shot_type=shot_type,
                    action_prompt=action_prompt,
                    environment_prompt=env_prompt,
                    camera_motion=camera_motion
                ))

        if st.button("🚀 2. Bắt Đầu Sản Xuất Video (Render)"):
            progress_bar = st.progress(0.0)
            status_text = st.empty()

            def on_progress(msg, val):
                progress_bar.progress(val)
                status_text.text(f"[{int(val*100)}%] {msg}")

            try:
                active_cfg = AppConfig(
                    worker_urls=active_workers,
                    llm_provider=llm_provider,
                    llm_api_key=llm_api_key,
                    llm_model=llm_model,
                    default_voice=voice_choice
                )

                final_script = StoryScriptResponse(title=script.title, scenes=updated_scenes)
                
                final_video_path = run_story_pipeline(
                    topic=topic_input,
                    config=active_cfg,
                    custom_script=final_script,
                    progress_callback=on_progress,
                    dry_run=dry_run_mode,
                    voice_override=voice_choice
                )

                st.success("🎉 Video đã sản xuất thành công!")
                st.video(str(final_video_path))
                
                with open(final_video_path, "rb") as f:
                    st.download_button(
                        label="⬇️ Tải Video Thành Phẩm (.mp4)",
                        data=f,
                        file_name=f"{script.title[:30]}.mp4",
                        mime="video/mp4"
                    )
            except Exception as e:
                st.error(f"Lỗi trong quá trình render video: {e}")

# --- TAB 2: CHARACTER BIBLE ---
with tab2:
    st.subheader("👥 Hồ Sơ Nhân Vật (Character Bible)")
    for cid, cdata in bible.characters.items():
        st.markdown(f"### Nhân vật: **{cdata.name}** (`{cid}`)")
        col_info, col_face, col_outfit = st.columns([2, 1, 1])
        with col_info:
            st.markdown(f"- **Voice ID:** `{cdata.voice_id}`")
            st.markdown(f"- **Appearance Trigger:** `{cdata.appearance_trigger}`")
            st.markdown(f"- **Default Outfit:** `{cdata.default_outfit}`")
            st.markdown(f"- **PuLID Weight:** `{cdata.pulid_weight}` | **IP-Adapter Weight:** `{cdata.ipadapter_weight}`")
        
        plates_dir = ROOT_DIR / "resource" / "character_bible"
        face_path = plates_dir / cdata.face_plate
        outfit_path = plates_dir / cdata.outfit_plate
        
        with col_face:
            if face_path.exists():
                try:
                    st.image(str(face_path), caption=f"Face Plate: {cdata.face_plate}", width="stretch")
                except TypeError:
                    st.image(str(face_path), caption=f"Face Plate: {cdata.face_plate}", use_container_width=True)
        with col_outfit:
            if outfit_path.exists():
                try:
                    st.image(str(outfit_path), caption=f"Outfit Plate: {cdata.outfit_plate}", width="stretch")
                except TypeError:
                    st.image(str(outfit_path), caption=f"Outfit Plate: {cdata.outfit_plate}", use_container_width=True)
        st.divider()

# --- TAB 3: TRẠNG THÁI WORKER ---
with tab3:
    st.subheader("📡 Kiểm Tra Kết Nối Cloudflare Workers")
    if not active_workers:
        st.warning("Chưa cấu hình Worker URL trong sidebar.")
    else:
        for idx, wurl in enumerate(active_workers):
            col_w1, col_w2 = st.columns([3, 1])
            with col_w1:
                st.write(f"Worker {idx}: `{wurl}`")
            with col_w2:
                if st.button(f"Ping Worker {idx}", key=f"ping_{idx}"):
                    try:
                        resp = requests.get(wurl, timeout=10)
                        if resp.status_code == 200:
                            st.success("🟢 Online")
                        else:
                            st.warning(f"🟡 Phản hồi mã: {resp.status_code}")
                    except Exception as err:
                        st.error(f"🔴 Offline: {err}")
