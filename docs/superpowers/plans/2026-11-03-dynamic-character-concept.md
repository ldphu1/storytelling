# Dynamic Character & Concept Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable dynamic story-specific character creation with visual concepts and real-time WebUI plate preview/generation before full video rendering.

**Architecture:** 
1. Expand Pydantic models with `StoryCharacter` and updated `StoryScriptResponse`.
2. Enhance LLM system/user prompts to craft bespoke characters with concept and styling for any user topic.
3. Add a dedicated txt2img character plate generator in `DualGPUComfyStoryClient` that generates 1024x1024 face and outfit plates on the remote Tesla T4 ComfyUI worker and syncs them for IP-Adapter scene conditioning.
4. Redesign Streamlit WebUI Studio Tab into a 3-step linear flow: (1) Generate Script & Concept, (2) Preview & Refine Characters with live ComfyUI plate generation button, (3) Review Scenes & Render Final Video.

**Tech Stack:** Python 3.11, Pydantic v2, Streamlit, ComfyUI API, Juggernaut XL Lightning, IP-Adapter Plus SDXL, Edge-TTS, FFmpeg NVENC, Pytest.

**Spec:** [docs/superpowers/specs/2026-11-03-dynamic-character-concept-design.md](file:///C:/Users/Asus/Desktop/MoneyPrinterTurbo-Storytelling/docs/superpowers/specs/2026-11-03-dynamic-character-concept-design.md)

---

## Global Constraints
- Python 3.11 with existing `venv` at `C:\Users\Asus\Desktop\MoneyPrinterTurbo-Storytelling\venv`.
- Preserve 100% backward compatibility with existing tests and fallback to `resource/character_bible` when no dynamic characters are present.
- Plate images must be 1024x1024 RGB PNGs.
- NVENC hardware encoding acceleration on NVIDIA RTX 3050 Laptop GPU.
- Remote ComfyUI worker on Tesla T4 via Cloudflare tunnel (`https://literature-closed-cia-environmental.trycloudflare.com`).

## Review Focus
1. Backward compatibility: Script with empty `characters` falls back safely to default Character Bible without crashing.
2. Incomplete or missing plates: If user clicks "Render Video" without explicitly clicking "Tạo ảnh nhân vật", pipeline automatically generates missing plates before scene generation.
3. Special character escaping: Concept prompt with quotes or Vietnamese characters must not break JSON payload or prompt formatting.
4. Edge-TTS voice assignment: Each character's `voice_id` defaults safely to valid Vietnamese voice if invalid or missing.
5. Concurrent ComfyUI requests: Generating plates does not collide with active scene rendering tasks.

---

### Task 1: Schema Extension (`app/models/schema.py`)

**Files:**
- Modify: `app/models/schema.py`
- Test: `tests/test_schema.py`

- [ ] **Step 1.1**: Write failing tests in `tests/test_schema.py` for `StoryCharacter` and `StoryScriptResponse` with `characters`.
- [ ] **Step 1.2**: Run pytest to verify test failure (`tests/test_schema.py`).
- [ ] **Step 1.3**: Implement `StoryCharacter` model and add `characters: List[StoryCharacter] = Field(default_factory=list)` to `StoryScriptResponse` in `app/models/schema.py`.
- [ ] **Step 1.4**: Run pytest to verify all tests in `tests/test_schema.py` pass.
- [ ] **Step 1.5**: Git commit schema changes (`feat(schema): add StoryCharacter and dynamic characters list to StoryScriptResponse`).

---

### Task 2: LLM Prompt & Mock Generator Extension (`app/services/llm.py`)

**Files:**
- Modify: `app/services/llm.py`
- Test: `tests/test_llm.py`

- [ ] **Step 2.1**: Write failing test in `tests/test_llm.py` asserting that `generate_mock_story_scenes` returns at least 1-2 characters with `concept`, `appearance_prompt`, and `default_outfit`.
- [ ] **Step 2.2**: Run pytest to verify test failure.
- [ ] **Step 2.3**: Update LLM system prompt and JSON schema in `app/services/llm.py` to instruct LLMs to generate `characters` with `concept` fitting the story theme, and update `generate_mock_story_scenes` with realistic mock characters.
- [ ] **Step 2.4**: Run pytest to verify all tests in `tests/test_llm.py` pass.
- [ ] **Step 2.5**: Git commit LLM service changes (`feat(llm): generate story-specific characters with concept in LLM prompt and mock`).

---

### Task 3: ComfyUI Dynamic Character Plate Generator (`app/services/comfy_remote_client.py`)

**Files:**
- Modify: `app/services/comfy_remote_client.py`
- Test: `tests/test_comfy_client.py`

- [ ] **Step 3.1**: Write failing test in `tests/test_comfy_client.py` for `generate_character_plates` (verifying dry-run creates 1024x1024 face and outfit plates in task directory) and for payload building with dynamic characters.
- [ ] **Step 3.2**: Run pytest to verify test failure.
- [ ] **Step 3.3**: Implement:
  - `generate_character_plate_image(...)`: Sends txt2img prompt to ComfyUI worker (Node 4 Checkpoint + Node 6/7 CLIPTextEncode + Node 5 Latent + Node 3 KSampler + Node 8 VAE + Node 9 SaveImage) and downloads resulting PNG.
  - `generate_character_plates(character: StoryCharacter, output_dir: Path, dry_run: bool = False)`: Generates both face and outfit plates.
  - Update `_build_workflow_payload` to check task-specific dynamic character plates first before falling back to `resource/character_bible`.
- [ ] **Step 3.4**: Run pytest to verify all tests in `tests/test_comfy_client.py` pass.
- [ ] **Step 3.5**: Git commit ComfyUI client changes (`feat(comfy): add dynamic character plate generation and task-level plate routing`).

---

### Task 4: Pipeline Orchestrator Integration (`app/services/task.py`)

**Files:**
- Modify: `app/services/task.py`
- Test: `tests/test_task.py` and `tests/test_e2e_pipeline.py`

- [ ] **Step 4.1**: Write test in `tests/test_task.py` verifying that when a custom script with dynamic characters is provided, character plates are generated/synced and audio synthesis uses character voice mapping.
- [ ] **Step 4.2**: Run pytest to verify test failure.
- [ ] **Step 4.3**: Update `run_story_pipeline` in `app/services/task.py`:
  - If `story_script.characters` exists, ensure all character plates exist in `task_dir / "characters"` (auto-generating any missing plates).
  - Sync task character plates to workers.
  - Pass dynamic character dictionary to audio synthesis and video rendering.
- [ ] **Step 4.4**: Run pytest to verify `tests/test_task.py` and `tests/test_e2e_pipeline.py` pass.
- [ ] **Step 4.5**: Git commit orchestrator changes (`feat(task): integrate dynamic characters and plates into story pipeline`).

---

### Task 5: WebUI Studio 3-Step Interactive Workflow (`app/ui/webui.py`)

**Files:**
- Modify: `app/ui/webui.py`

- [ ] **Step 5.1**: Add Step 2 "🎭 Diễn Viên & Concept Tạo Hình" to Studio Tab:
  - Render expandable card for each character in `st.session_state.script.characters`.
  - Provide text inputs for `concept`, `appearance_prompt`, `default_outfit`, and selectbox for `voice_id`.
  - Provide button "🎨 Tạo / Sinh Lại Ảnh Mẫu Nhân Vật": Calls `comfy_client.generate_character_plates` and saves to task/session directory.
  - Display side-by-side images of `face_plate` and `outfit_plate` once generated.
- [ ] **Step 5.2**: Update Step 3 "Sản Xuất Video": Passes the edited `StoryCharacter` list into `StoryScriptResponse` and launches `run_story_pipeline`.
- [ ] **Step 5.3**: Manually test WebUI in browser via Streamlit session on port 8501.
- [ ] **Step 5.4**: Git commit WebUI changes (`feat(ui): add 3-step dynamic character review and preview studio`).

---

### Task 6: Live Worker Verification & Regression Testing

**Files:**
- Test: Full test suite (`pytest -v`)
- Scratch verification script

- [ ] **Step 6.1**: Run `pytest -v` across all test files to ensure 100% pass rate.
- [ ] **Step 6.2**: Execute a live dry-run or targeted Kaggle test generating a custom concept character (e.g., "Cyberpunk Detective") and verify output plates.
- [ ] **Step 6.3**: Final git status check and clean commit history.
