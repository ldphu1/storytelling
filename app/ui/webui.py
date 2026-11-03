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

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.config import get_config, AppConfig
from app.models.schema import StoryScriptResponse, StoryScene, StoryCharacter, CharacterBible
from app.services.llm import generate_story_scenes
from app.services.task import run_story_pipeline
from app.services.comfy_remote_client import DualGPUComfyStoryClient

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
    
    cleaned_w0 = DualGPUComfyStoryClient.clean_worker_url(worker_url_0)
    cleaned_w1 = DualGPUComfyStoryClient.clean_worker_url(worker_url_1)
    if worker_url_0.strip() and cleaned_w0 != worker_url_0.strip():
        st.sidebar.caption(f"🔍 Tự động nhận diện Worker 0: `{cleaned_w0}`")
    if worker_url_1.strip() and cleaned_w1 != worker_url_1.strip():
        st.sidebar.caption(f"🔍 Tự động nhận diện Worker 1: `{cleaned_w1}`")
    
    active_workers = [u for u in [cleaned_w0, cleaned_w1] if u]
    
    dry_run_mode = st.checkbox("🧪 Chế độ Dry-Run (Không cần GPU Cloud)", value=(len(active_workers) == 0))
    if dry_run_mode:
        st.info("Đang bật chế độ Dry-Run: Hệ thống sẽ tạo ảnh giả lập và dùng FFmpeg local để kiểm tra luồng video.")

    st.subheader("🤖 Cấu hình LLM")
    provider_options = ["gemini", "openai", "deepseek", "ollama", "mock (thử nghiệm không cần key)"]
    llm_provider = st.selectbox("Nhà cung cấp LLM", provider_options, index=0)
    clean_provider = llm_provider.split()[0].lower()

    if clean_provider == "mock":
        st.info("✨ Chế độ Mock: Tự động tạo kịch bản 5 phân cảnh chuẩn điện ảnh tức thì mà không cần API Key hay kết nối mạng.")
        llm_api_key = ""
        llm_model = "mock"
        llm_base_url = ""
    elif clean_provider == "ollama":
        st.info("🦙 Ollama: Chạy mô hình mã nguồn mở (Local hoặc Remote trên Kaggle GPU 1).")
        llm_api_key = "ollama"
        llm_base_url = st.text_input(
            "Ollama Base URL",
            value="http://localhost:11434/v1",
            help="Nếu chạy trên Kaggle, dán đường link Cloudflare Tunnel vào đây kèm đuôi /v1 (ví dụ: https://...trycloudflare.com/v1)"
        )
        llm_model = st.text_input("Tên Model", value="qwen2.5:7b", help="Model khuyến nghị: qwen2.5:7b hoặc qwen2.5:14b")
    else:
        if clean_provider == "gemini":
            default_base = "https://generativelanguage.googleapis.com/v1beta/openai"
            default_model = "gemini-2.0-flash"
            key_help = "Nhập Google AI Studio API Key (AIzaSy...)"
        elif clean_provider == "deepseek":
            default_base = "https://api.deepseek.com/v1"
            default_model = "deepseek-chat"
            key_help = "Nhập DeepSeek API Key (sk-...)"
        else:
            default_base = "https://api.openai.com/v1"
            default_model = "gpt-4o-mini"
            key_help = "Nhập OpenAI API Key (sk-...)"

        llm_api_key = st.text_input("API Key", value=cfg.llm_api_key, type="password", help=key_help)
        llm_model = st.text_input("Tên Model", value=default_model)
        with st.expander("Tùy biến Endpoint (Base URL)"):
            llm_base_url = st.text_input("Base URL", value=default_base)

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

    col_btn1, col_btn2 = st.columns([2, 1])
    with col_btn1:
        btn_gen = st.button("✨ 1. Sinh Kịch Bản Phân Cảnh (LLM)")
    with col_btn2:
        btn_mock = st.button("⚡ Sinh Kịch Bản Mẫu (Mock / Không cần Key)")

    if btn_gen or btn_mock:
        active_prov = "mock" if btn_mock else clean_provider
        with st.spinner("Đang khởi tạo kịch bản phân cảnh..."):
            try:
                story_script = generate_story_scenes(
                    topic=topic_input,
                    character_bible_path=str(bible_path),
                    provider=active_prov,
                    api_key=llm_api_key,
                    base_url=llm_base_url if not btn_mock else "",
                    model=llm_model if not btn_mock else "mock",
                    scene_count=scene_count
                )
                st.session_state["current_script"] = story_script
                st.success("Đã sinh kịch bản thành công! Hãy kiểm tra và chỉnh sửa bên dưới.")
            except Exception as e:
                st.error(f"Lỗi sinh kịch bản: {e}")
                st.info(
                    "💡 **Gợi ý khắc phục:**\n"
                    "- Nếu bạn dùng API Key Google Gemini (bắt đầu bằng `AIzaSy...`), hãy chọn Nhà cung cấp là **'gemini'** ở cột bên trái.\n"
                    "- Nếu bạn dùng DeepSeek API Key, hãy chọn **'deepseek'**.\n"
                    "- Nếu bạn chưa có API Key hoặc muốn thử nghiệm ngay, hãy bấm nút **'⚡ Sinh Kịch Bản Mẫu (Mock / Không cần Key)'** ngay phía trên!"
                )

    # Hiển thị kịch bản có thể chỉnh sửa
    if "current_script" in st.session_state:
        script: StoryScriptResponse = st.session_state["current_script"]
        st.subheader(f"📖 Kịch bản: {script.title}")
        
        # --- BƯỚC 2: DUYỆT & TINH CHỈNH DIỄN VIÊN / CONCEPT ---
        st.markdown("---")
        st.markdown("### 🎭 Bước 2: Duyệt & Tinh Chỉnh Diễn Viên (Characters & Concept)")
        st.caption("Xem trước, tinh chỉnh Concept tạo hình và bấm sinh ảnh mẫu nhân vật trước khi render video hoàn chỉnh.")

        preview_dir = ROOT_DIR / "storage" / "character_previews"
        preview_dir.mkdir(parents=True, exist_ok=True)

        updated_characters = []
        chars_to_display = script.characters if script.characters else [
            StoryCharacter(
                id="char_1",
                name="Nhân vật chính",
                concept="Nhân vật đời thường gần gũi",
                appearance_prompt="a 22-year-old young handsome Vietnamese man, friendly warm expression",
                default_outfit="wearing casual clothing and sneakers",
                voice_id="vi-VN-NamMinhNeural"
            )
        ]

        for c_idx, char in enumerate(chars_to_display):
            with st.expander(f"👤 Diễn viên {c_idx + 1}: **{char.name}** (`{char.id}`) — Concept: *{char.concept}*", expanded=True):
                col_left, col_right = st.columns([3, 2])
                with col_left:
                    c1, c2 = st.columns(2)
                    with c1:
                        c_name = st.text_input("Tên nhân vật", value=char.name, key=f"c_name_{c_idx}")
                        c_id = char.id
                    with c2:
                        voice_idx = 0 if "NamMinh" in char.voice_id else 1
                        c_voice = st.selectbox("Giọng đọc", ["vi-VN-NamMinhNeural", "vi-VN-HoaiMyNeural"], index=voice_idx, key=f"c_voice_{c_idx}")
                    
                    c_concept = st.text_input("Concept tạo hình (Vibe / Thể loại phong cách)", value=char.concept, key=f"c_concept_{c_idx}")
                    c_app = st.text_area("Prompt Ngoại hình (Face/Hair/Features - Tiếng Anh)", value=char.appearance_prompt, key=f"c_app_{c_idx}")
                    c_outfit = st.text_area("Prompt Trang phục (Outfit/Clothes - Tiếng Anh)", value=char.default_outfit, key=f"c_outfit_{c_idx}")

                with col_right:
                    face_preview_path = preview_dir / f"{char.id}_face.png"
                    outfit_preview_path = preview_dir / f"{char.id}_outfit.png"
                    
                    btn_gen_plate = st.button(f"🎨 Tạo / Sinh Lại Ảnh Mẫu ({c_name})", key=f"btn_plate_{c_idx}")
                    if btn_gen_plate:
                        with st.spinner(f"Đang sinh ảnh mẫu cho {c_name} qua ComfyUI ({clean_provider.upper()})..."):
                            try:
                                client = DualGPUComfyStoryClient(worker_urls=active_workers)
                                temp_char = StoryCharacter(
                                    id=c_id,
                                    name=c_name,
                                    concept=c_concept,
                                    appearance_prompt=c_app,
                                    default_outfit=c_outfit,
                                    voice_id=c_voice
                                )
                                client.generate_character_plates(
                                    character=temp_char,
                                    output_dir=preview_dir,
                                    dry_run=dry_run_mode
                                )
                                st.success(f"Đã tạo xong ảnh mẫu cho {c_name}!")
                            except Exception as e:
                                st.error(f"Lỗi tạo ảnh mẫu: {e}")

                    col_img1, col_img2 = st.columns(2)
                    with col_img1:
                        if face_preview_path.exists():
                            st.image(str(face_preview_path), caption=f"Khuôn mặt: {c_name}", use_container_width=True)
                        else:
                            st.info("Chưa có ảnh mặt")
                    with col_img2:
                        if outfit_preview_path.exists():
                            st.image(str(outfit_preview_path), caption=f"Trang phục: {c_name}", use_container_width=True)
                        else:
                            st.info("Chưa có ảnh trang phục")

                updated_characters.append(StoryCharacter(
                    id=c_id,
                    name=c_name,
                    concept=c_concept,
                    appearance_prompt=c_app,
                    default_outfit=c_outfit,
                    voice_id=c_voice,
                    face_plate=str(face_preview_path) if face_preview_path.exists() else None,
                    outfit_plate=str(outfit_preview_path) if outfit_preview_path.exists() else None,
                    pulid_weight=char.pulid_weight,
                    ipadapter_weight=char.ipadapter_weight
                ))

        # --- BƯỚC 3: DUYỆT PHÂN CẢNH & RENDER VIDEO ---
        st.markdown("---")
        st.markdown("### 🎬 Bước 3: Duyệt Phân Cảnh & Sản Xuất Video")
        
        available_char_choices = [c.id for c in updated_characters] if updated_characters else list(bible.characters.keys())
        updated_scenes = []
        for idx, sc in enumerate(script.scenes):
            with st.expander(f"Phân cảnh {sc.scene_id}: {sc.narration[:40]}...", expanded=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    narration = st.text_area(f"Lời dẫn truyện (Cảnh {sc.scene_id})", value=sc.narration, key=f"narr_{idx}")
                with c2:
                    has_char = st.checkbox("Có nhân vật", value=sc.has_character, key=f"has_char_{idx}")
                    char_sel_idx = available_char_choices.index(sc.character_id) if sc.character_id in available_char_choices else 0
                    char_id = st.selectbox(
                        "Nhân vật",
                        available_char_choices,
                        index=char_sel_idx,
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

        if st.button("🚀 3. Bắt Đầu Sản Xuất Video (Render)"):
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

                final_script = StoryScriptResponse(
                    title=script.title,
                    characters=updated_characters,
                    scenes=updated_scenes
                )
                
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
