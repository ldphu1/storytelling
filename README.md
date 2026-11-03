# Lean Hybrid AI Storytelling Pipeline

Hệ thống tự động hóa sản xuất video kể chuyện AI chất lượng cao với **nhân vật đồng nhất xuyên suốt (Consistent Character)**.
Kết hợp sức mạnh phần cứng **NVIDIA GPU NVENC** tại máy cục bộ (Local Orchestrator) với cụm **Dual-GPU Tesla T4** trên đám mây (Kaggle ComfyUI Worker qua Cloudflare Tunnel).

---

## 🌟 Tính Năng Nổi Bật

1. **Nhất Quán Nhân Vật Tuyệt Đối:** Quản lý qua **Character Bible** (`characters.json` + `Cast Plates`) với mô hình SDXL + `IP-Adapter FaceID` & `IP-Adapter Advanced`.
2. **Khử Loang Nhận Diện (Anti-Identity Bleed):** Áp dụng kỹ thuật điện ảnh *Shot-Reverse-Shot* (cắt luân phiên từng góc máy cho mỗi nhân vật) và tự động vô hiệu hóa (`weight = 0.0`) ở các cảnh B-Roll ngoại bối.
3. **Đồng Bộ Hình & Tiếng Tuyệt Đối:** Mỗi phân cảnh được tổng hợp audio riêng biệt, chuẩn hóa tần số lấy mẫu (`24000Hz mono`), đo thời lượng thực tế để triệt tiêu hoàn toàn sai số trôi phụ đề.
4. **Hiệu Năng Dựng Phim NVENC Siêu Tốc:** Thay thế vòng lặp MoviePy CPU bằng nhân phần cứng GPU NVENC:
   - Khử lỗi rung giật điểm ảnh bằng kỹ thuật upscale 4000px trước `zoompan`.
   - Tự động hạ âm lượng nhạc nền khi có giọng đọc (**Audio Ducking** bằng `sidechaincompress`).
   - Chuẩn hóa âm thanh giọng đọc theo chuẩn phát thanh `-16 LUFS`.
5. **Semaphore Kép Điều Tiết Tải:** Chống nghẽn 100% CPU/RAM máy cục bộ khi chạy batch nhiều phân cảnh.
6. **Cơ Chế Idempotent Checkpoint:** Nếu tiến trình bị gián đoạn, khi chạy lại hệ thống sẽ tự động bỏ qua các phân cảnh đã render xong.

---

## 🚀 Hướng Dẫn Cài Đặt (Local Orchestrator trên Windows 11)

### 1. Yêu cầu tiên quyết
- Python 3.11 hoặc 3.12
- Git & FFmpeg (đã thêm vào biến môi trường `PATH`)
- Card đồ họa rời NVIDIA (hỗ trợ NVENC, VD: RTX 3050 trở lên)

### 2. Kích hoạt môi trường và cài đặt phụ thuộc
```bash
# Mở PowerShell tại thư mục dự án
cd C:\Users\Asus\Desktop\MoneyPrinterTurbo-Storytelling

# Kích hoạt virtual environment có sẵn
.\venv\Scripts\Activate.ps1

# Cài đặt thư viện nếu cần
pip install -r requirements.txt
```

---

## 🖥️ Hướng Dẫn Vận Hành

### Cách 1: Sử dụng Giao Diện Web (Streamlit WebUI)
Khởi chạy giao diện điều khiển tương tác trực quan:
```bash
python main.py
```
Trình duyệt sẽ tự động mở tại `http://localhost:8501`:
1. **Sidebar:** Nhập 2 link Cloudflare Tunnel từ Kaggle (hoặc tích chọn chế độ **Dry-Run** để thử nghiệm offline).
2. **Tab 1 (Tạo Video):** Nhập chủ đề, bấm **Sinh Kịch Bản (LLM)**, kiểm tra/sửa lời thoại và bấm **Bắt Đầu Sản Xuất Video**.
3. **Tab 2 (Character Bible):** Xem ảnh mẫu và hồ sơ nhân vật (Minh, Linh).
4. **Tab 3 (Trạng Thái Worker):** Kiểm tra trạng thái kết nối tới các máy chủ Kaggle.

### Cách 2: Sử dụng Dòng Lệnh (CLI)
Dành cho việc tạo video tự động hàng loạt:
```bash
# Chạy chế độ Dry-Run (thử nghiệm nhanh local)
python main.py --cli --topic "Mùa thu Hà Nội qua góc nhìn của Minh" --dry-run

# Chạy với Cloud Workers thật từ Kaggle
python main.py --cli --topic "Minh và Linh khám phá phố cổ" --workers "https://worker1.trycloudflare.com,https://worker2.trycloudflare.com"
```

---

## ☁️ Hướng Dẫn Cài Đặt Kaggle Dual-GPU Worker ($2 \times \text{Tesla T4}$)

1. Mở Kaggle Notebook mới.
2. Cấu hình bên phải màn hình:
   - **Accelerator:** `GPU T4 x 2`
   - **Internet:** `On`
3. Copy toàn bộ nội dung file [start_dual_comfy_worker.py](kaggle_worker/start_dual_comfy_worker.py) dán vào 1 Cell trên Kaggle.
4. Bấm **Run All**.
5. Khi script chạy xong, console sẽ xuất ra:
   ```text
   🎉 DUAL-GPU COMFYUI WORKERS ĐÃ SẴN SÀNG HOẠT ĐỘNG!
       WORKER_URLS = [
           'https://alpha-xxxx.trycloudflare.com',
           'https://beta-yyyy.trycloudflare.com'
       ]
   ```
6. Copy 2 đường link trên và dán vào Sidebar của Streamlit WebUI (hoặc file `config.toml`) trên máy của bạn.

---

## 📁 Cấu Trúc Thư Mục Dự Án

```text
MoneyPrinterTurbo-Storytelling/
├── app/
│   ├── config.py                     # Quản lý config.toml và biến môi trường
│   ├── models/
│   │   └── schema.py                 # Pydantic schema phân cảnh và Character Bible
│   ├── services/
│   │   ├── llm.py                    # Sinh kịch bản phân cảnh chuẩn 5 thành phần
│   │   ├── voice.py                  # edge-tts theo cảnh & ghép srt không lệch nhịp
│   │   ├── comfy_remote_client.py    # Dual GPU async client, sync plates, NVENC zoompan
│   │   ├── video.py                  # Ghép video, audio ducking, subtitle burning
│   │   └── task.py                   # Orchestrator điều phối toàn bộ pipeline
│   └── ui/
│       └── webui.py                  # Giao diện Streamlit tương tác
├── resource/
│   ├── character_bible/
│   │   ├── characters.json           # Hồ sơ ngoại hình, trang phục, giọng đọc
│   │   └── *.png                     # Ảnh mẫu cận mặt & trang phục
│   ├── workflows/
│   │   └── pulid_ipadapter_api.json  # Workflow ComfyUI SDXL IP-Adapter chuẩn
│   ├── fonts/                        # Thư mục phông chữ tiếng Việt
│   └── songs/                        # Thư mục nhạc nền BGM
├── storage/                          # Thư mục lưu kết quả video theo task_id
├── kaggle_worker/
│   └── start_dual_comfy_worker.py    # Script 1-Cell chạy trên Kaggle
├── config.example.toml               # File cấu hình mẫu
├── requirements.txt                  # Phụ thuộc Python tinh gọn
├── main.py                           # Điểm khởi chạy WebUI và CLI
└── README.md
```
