# Thiết Kế Kỹ Thuật: Nhân Vật Động & Concept Phân Cảnh (Dynamic Characters & Concept Studio)

## 1. Mục Đích & Bối Cảnh (Intent & Why)
Hiện tại, hệ thống MoneyPrinterTurbo-Storytelling đang sử dụng danh sách nhân vật cố định toàn cục (Minh & Linh trong `resource/character_bible/characters.json`). Khi người dùng muốn sáng tạo các thể loại nội dung mới (cổ trang kiếm hiệp, cyberpunk tương lai, truyện tranh hài hước, kinh dị...), hệ thống cần:
- Cho phép LLM tự động tạo ra các nhân vật mới toanh gắn liền với cốt truyện.
- Bổ sung trường **Concept** để định hình sâu sắc phong cách hình tượng của nhân vật (vibe, bối cảnh, tinh thần tạo hình).
- Cho phép người dùng xem trước (preview) ảnh mẫu diễn viên (Cast Plates) ngay trên WebUI, tinh chỉnh Concept/Prompt, bấm sinh lại ảnh cho đến khi ưng ý trước khi bấm Render toàn bộ video.

---

## 2. Mục Tiêu & Ranh Giới (Goals, Non-Goals, Anti-Goals)

### Goals
1. **Mở rộng Schema kịch bản**: Hỗ trợ danh sách nhân vật động `characters: List[StoryCharacter]` trong `StoryScriptResponse`, mỗi nhân vật có `id`, `name`, `concept`, `appearance_prompt`, `outfit_prompt`, `voice_id`.
2. **Cập nhật LLM Prompt**: Khi nhập chủ đề bất kỳ, LLM sẽ tự thiết kế 1-3 nhân vật đặc trưng kèm Concept và gán `character_id` phù hợp vào từng `StoryScene`.
3. **ComfyUI Dynamic Plate Generator**: API tạo nhanh ảnh Face Plate & Outfit Plate 1024x1024 qua Checkpoint Juggernaut XL Lightning trên GPU Tesla T4 của Kaggle worker.
4. **WebUI 3-Bước Tuyến Tính**:
   - **Bước 1**: Nhập Topic &rarr; Bấm *"Sinh Kịch Bản & Concept Nhân Vật"*.
   - **Bước 2**: Khu vực *"🎭 Duyệt & Tinh Chỉnh Diễn Viên"*: Hiển thị thông tin Concept, cho phép sửa prompt ngoại hình/trang phục, có nút *"🎨 Tạo / Sinh lại ảnh nhân vật"* và hiển thị 2 ảnh mẫu trực quan.
   - **Bước 3**: Chỉnh sửa kịch bản phân cảnh & Bấm *"🎬 Bắt đầu Sản Xuất Video"*. Video sẽ tự nạp đúng bộ ảnh vừa duyệt vào IP-Adapter để khóa nét nhân vật.

### Non-Goals
- Không xóa bỏ `resource/character_bible/characters.json` (giữ lại làm preset mẫu mặc định hoặc fallback).
- Không yêu cầu người dùng phải tự vẽ hay tải ảnh từ ngoài vào (hệ thống tự sinh 100% bằng ComfyUI, nhưng vẫn hỗ trợ nếu muốn thay thế).

### Anti-Goals
- Không tự động render hàng loạt ảnh nhân vật ngay khi LLM vừa nhả kịch bản (để tránh lãng phí thời gian và GPU nếu người dùng muốn sửa lại Concept/Prompt trước).

---

## 3. Các Phương Án Đã Cân Nhắc (Approaches)

### Phương án 1: Quy trình 3 bước liền mạch ngay trên Studio Tab (ĐÃ CHỌN 🌟)
- **Cơ chế**: Topic &rarr; Sinh kịch bản & Concept nhân vật &rarr; Xem trước / Tạo ảnh nhân vật tại chỗ &rarr; Render Video.
- **Đánh đổi**: Tăng thêm một khu vực điều khiển trên WebUI Studio, nhưng mang lại trải nghiệm sáng tạo mượt mà nhất.

### Phương án 2: Tách biệt thành Tab riêng (Hồ Sơ Nhân Vật độc lập) (LOẠI)
- **Cơ chế**: Người dùng phải chuyển qua tab khác để gõ Concept và tạo ảnh, rồi quay lại Studio để nạp vào kịch bản.
- **Đánh đổi**: Rời rạc, thao tác qua lại nhiều bước, giảm tốc độ sản xuất video.

---

## 4. Chi Tiết Kỹ Thuật (Architecture & Implementation Details)

### 4.1. Cập nhật Data Schema (`app/models/schema.py`)
```python
class StoryCharacter(BaseModel):
    id: str = Field(description="Mã định danh, ví dụ: char_1, char_2")
    name: str = Field(description="Tên nhân vật, ví dụ: Tiêu Phong, Tuấn Anh")
    concept: str = Field(description="Concept tạo hình, ví dụ: Kiếm hiệp cổ trang, Cyberpunk hacker, Học sinh thanh xuân")
    appearance_prompt: str = Field(description="Prompt tiếng Anh mô tả chi tiết khuôn mặt, kiểu tóc, độ tuổi")
    default_outfit: str = Field(description="Prompt tiếng Anh mô tả trang phục đặc trưng")
    voice_id: str = Field(default="vi-VN-NamMinhNeural", description="Giọng đọc Edge-TTS")
    face_plate: Optional[str] = Field(default=None, description="Tên file ảnh mặt, vd: char_1_face.png")
    outfit_plate: Optional[str] = Field(default=None, description="Tên file ảnh trang phục, vd: char_1_outfit.png")
    pulid_weight: float = Field(default=0.75, ge=0.0, le=1.0)
    ipadapter_weight: float = Field(default=0.50, ge=0.0, le=1.0)

class StoryScriptResponse(BaseModel):
    title: str
    characters: List[StoryCharacter] = Field(default_factory=list)
    scenes: List[StoryScene]
```

### 4.2. Cập nhật LLM Prompt (`app/services/llm.py`)
- Hướng dẫn LLM sinh JSON có cấu trúc gồm: `title`, `characters` (1 đến 2 nhân vật xuất hiện trong truyện kèm trường `concept` độc đáo), và `scenes` tham chiếu đến `character_id`.
- Cập nhật hàm `generate_mock_story_scenes` để sinh mẫu nhân vật có Concept khi chạy Mock.

### 4.3. Dịch vụ Sinh Ảnh Mẫu Nhân Vật (`app/services/comfy_remote_client.py`)
- Thêm phương thức:
  ```python
  def generate_character_plate_image(
      self,
      prompt: str,
      output_path: Path,
      negative_prompt: Optional[str] = None,
      seed: Optional[int] = None
  ) -> Path:
  ```
  Sử dụng pipeline txt2img trên ComfyUI worker để sinh ảnh 1024x1024 với Juggernaut XL Lightning (20 steps, euler) và tải về lưu trữ cục bộ.
- Cập nhật hàm `sync_character_plates_to_workers`: Chấp nhận danh sách `StoryCharacter` và thư mục ảnh tương ứng của task hiện tại, upload tự động lên `/upload/image` của ComfyUI worker.

### 4.4. Giao Diện WebUI (`app/ui/webui.py`)
- **Bước 1**: Nhập Topic & Provider &rarr; Nút `🚀 1. Sinh Kịch Bản & Nhân Vật`.
- **Bước 2 (Mới)**:
  - Khung **"🎭 Diễn Viên & Concept Tạo Hình"**:
    - Hiển thị từng nhân vật dạng thẻ (Card/Expander).
    - Các ô nhập: `Tên`, `Concept`, `Ngoại hình (Appearance)`, `Trang phục (Outfit)`, `Giọng đọc (Voice)`.
    - Nút `🎨 Tạo / Sinh Lại Ảnh Mẫu Nhân Vật`: Gọi ComfyUI tạo ngay `face_plate` & `outfit_plate` và hiển thị ảnh trực tiếp để người dùng duyệt.
- **Bước 3**: Bảng kịch bản phân cảnh & Nút `🎬 2. Bắt Đầu Sản Xuất Video (Render)`.

---

## 5. Kế Hoạch Kiểm Thử (Verification Plan)
1. **Unit Tests (`tests/test_schema.py`)**: Kiểm tra `StoryCharacter`, `StoryScriptResponse` với trường `concept` và danh sách nhân vật.
2. **LLM Tests (`tests/test_llm.py`)**: Kiểm tra prompt sinh đúng cấu trúc có `characters` và `concept`.
3. **Plate Gen Tests (`tests/test_comfy_client.py`)**: Kiểm tra hàm sinh ảnh mẫu nhân vật bằng mock & dry-run.
4. **E2E Test (`tests/test_e2e_pipeline.py`)**: Kiểm tra chạy toàn bộ quy trình từ kịch bản có dynamic characters đến video hoàn chỉnh.
5. **Thử nghiệm thực tế trên WebUI**: Kiểm tra trực tiếp trên giao diện Streamlit với Kaggle Worker.
