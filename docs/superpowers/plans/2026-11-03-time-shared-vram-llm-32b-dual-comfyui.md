# Time-Shared VRAM Handover (LLM 32B + Dual ComfyUI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Time-Shared VRAM Eviction strategy on Kaggle $2 \times \text{Tesla T4}$ ($32\text{GB}$ VRAM) enabling $Qwen-2.5-32B$ multi-act scriptwriting and Dual-Worker ComfyUI parallel image rendering without VRAM OOM.

**Architecture:**
1. **Kaggle 1-Cell Unified Server:** Runs Ollama across both GPUs (`CUDA_VISIBLE_DEVICES=0,1`) with flash-attention and $q8_0$ KV-cache + 2 ComfyUI instances (`cuda:0:8188`, `cuda:1:8189`) with `--normalvram` + 3 Cloudflare tunnels.
2. **Local Orchestrator VRAM Handover:** 
   - Before LLM: calls `POST /free` on both ComfyUI instances.
   - LLM Phase: `TimeSharedKaggleDirector` runs MasterBeatSheet (5 Acts) and rolling context generation with `qwen2.5:32b-instruct-q4_K_M`.
   - After LLM (guaranteed in `finally`): calls `POST /api/generate {"model": ..., "keep_alive": 0}` on Ollama, freeing $21.5\text{GB}$ VRAM to $0\text{MB}$.
   - ComfyUI Phase: Dual-GPU parallel scene rendering on clean $32\text{GB}$ VRAM.
3. **WebUI Integration:** Exposes 3 Cloudflare URLs (Ollama + ComfyUI 0 + ComfyUI 1), manual "🧹 Xả VRAM" button, and Story Mode selector (Short Story vs 10-minute Epic).

**Tech Stack:** Python 3.11, Pydantic v2, Ollama API, ComfyUI API, Streamlit, FFmpeg NVENC, Pytest.

**Spec Reference:** `c:\Users\Asus\Downloads\chi_n_l_c_1_chia_s_vram_theo_pha_llm_32b_dual_comfyui.md`

---

## Global Constraints
- Python 3.11 with existing `venv` at `C:\Users\Asus\Desktop\MoneyPrinterTurbo-Storytelling\venv`.
- Preserve 100% backward compatibility with existing tests and dynamic character concept support.
- `evict_llm_from_kaggle_vram()` MUST run inside a `finally` block so VRAM is guaranteed freed even on error.
- ComfyUI instances must run with `--normalvram` to honor `/free` memory eviction.

---

### Task 1: Kaggle 1-Cell Deployment Script (`kaggle_worker/start_dual_comfy_worker.py`)

**Files:**
- Modify: `kaggle_worker/start_dual_comfy_worker.py`
- Modify: `kaggle_worker/start_comfy_and_ollama.py`

- [ ] **Step 1.1**: Update `kaggle_worker/start_dual_comfy_worker.py` with the full unified script from Section 3 of the technical specification:
  - Setup environment with ComfyUI, IPAdapter_plus, insightface, onnxruntime-gpu.
  - Start Ollama with `CUDA_VISIBLE_DEVICES="0,1"`, `OLLAMA_FLASH_ATTENTION="1"`, `OLLAMA_KV_CACHE_TYPE="q8_0"`, `OLLAMA_NUM_PARALLEL="1"`, `OLLAMA_MAX_LOADED_MODELS="1"`.
  - Start ComfyUI worker 0 on `cuda:0` port 8188 with `--normalvram`.
  - Start ComfyUI worker 1 on `cuda:1` port 8189 with `--normalvram`.
  - Open 3 Cloudflare Tunnels (Ollama :11434, ComfyUI :8188, ComfyUI :8189) and log URLs.
- [ ] **Step 1.2**: Commit Task 1 changes to git (`feat(kaggle): implement unified time-shared Kaggle worker script`).

---

### Task 2: Config & Schema Extension (`app/config.py`, `app/models/schema.py`)

**Files:**
- Modify: `app/config.py`
- Modify: `app/models/schema.py`
- Test: `tests/test_schema.py`

- [ ] **Step 2.1**: Write failing tests in `tests/test_schema.py` for `ActBeat`, `MasterBeatSheet`, and `ActScenesBatch`.
- [ ] **Step 2.2**: Run pytest to verify test failure.
- [ ] **Step 2.3**: Implement `ActBeat`, `MasterBeatSheet`, `ActScenesBatch` in `app/models/schema.py` and add `ollama_worker_url: str = ""` in `app/config.py`.
- [ ] **Step 2.4**: Run pytest to verify all schema tests pass.
- [ ] **Step 2.5**: Commit Task 2 changes (`feat(schema): add MasterBeatSheet and ActBeat models for 10-minute multi-act storytelling`).

---

### Task 3: Time-Shared VRAM Director & Eviction (`app/services/llm.py`)

**Files:**
- Modify: `app/services/llm.py`
- Test: `tests/test_llm.py`

- [ ] **Step 3.1**: Write failing tests in `tests/test_llm.py` for:
  - `evict_llm_from_kaggle_vram()` sends `POST /api/generate {"model": ..., "keep_alive": 0}`.
  - `free_comfyui_vram_before_llm()` sends `POST /free` to each ComfyUI worker.
  - `TimeSharedKaggleDirector` generation loop with mock responses.
- [ ] **Step 3.2**: Run pytest to verify test failure.
- [ ] **Step 3.3**: Implement `TimeSharedKaggleDirector` in `app/services/llm.py` with:
  - `free_comfyui_vram_before_llm()`
  - `evict_llm_from_kaggle_vram()`
  - `_call_ollama_structured()` with `format` schema validation and `keep_alive="15m"`
  - `generate_full_10min_script()` with `finally: self.evict_llm_from_kaggle_vram()`
- [ ] **Step 3.4**: Run pytest to verify all tests in `tests/test_llm.py` pass.
- [ ] **Step 3.5**: Commit Task 3 changes (`feat(llm): implement TimeSharedKaggleDirector with VRAM handover eviction`).

---

### Task 4: Pipeline Orchestrator Integration (`app/services/task.py`)

**Files:**
- Modify: `app/services/task.py`
- Test: `tests/test_task.py`

- [ ] **Step 4.1**: Write failing test in `tests/test_task.py` verifying multi-act script generation and VRAM eviction call during pipeline run.
- [ ] **Step 4.2**: Run pytest to verify test failure.
- [ ] **Step 4.3**: Update `run_story_pipeline` in `app/services/task.py` to route to `TimeSharedKaggleDirector` when `story_mode == "10min_multiact"` or provider is `ollama` with `ollama_worker_url`.
- [ ] **Step 4.4**: Run pytest to verify `tests/test_task.py` passes.
- [ ] **Step 4.5**: Commit Task 4 changes (`feat(task): integrate TimeSharedKaggleDirector into end-to-end task pipeline`).

---

### Task 5: WebUI Studio Enhancements (`app/ui/webui.py`)

**Files:**
- Modify: `app/ui/webui.py`

- [ ] **Step 5.1**: Update Sidebar in `app/ui/webui.py`:
  - Input field for `Ollama Worker URL (Port 11434)`.
  - Input fields for `Worker GPU 0 (Port 8188)` and `Worker GPU 1 (Port 8189)`.
  - Manual button: `🧹 Xả Sạch VRAM Kaggle Thủ Công` (calls ComfyUI `/free` and Ollama `keep_alive: 0`).
  - Radio button for Story Mode: `⚡ Kịch bản ngắn (3 - 8 cảnh)` vs `🎬 Phim trường ca 10 phút (5 Hồi / 70 cảnh)`.
- [ ] **Step 5.2**: Update tab 1 generation logic to handle both Short Story and Multi-Act mode.
- [ ] **Step 5.3**: Commit Task 5 changes (`feat(ui): add time-shared dual-worker controls and 10min multi-act mode in WebUI`).

---

### Task 6: Full Verification & Regression Testing

**Files:**
- Run full pytest test suite (`pytest -v`).

- [ ] **Step 6.1**: Run `pytest -v` across all test files.
- [ ] **Step 6.2**: Verify clean git working tree and present instructions to user.
