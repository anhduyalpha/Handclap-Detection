# 👏 HandClap Detection & Smart Light Web App (Dual-Stage AI & Personal Training Studio)

Hệ thống ứng dụng Web nhận diện tiếng vỗ tay thời gian thực (**Real-time Handclap Detection**) kết hợp giải thuật **Dual-Stage Hybrid (DSP Transient Detector + Deep Learning Mel-Spectrogram Classifier)**, tích hợp **Bóng đèn thông minh mô phỏng 3D phát sáng** và **Personalized Training Studio** giúp người dùng tự thu âm và huấn luyện mô hình tối ưu theo tiếng vỗ và phòng của riêng mình.

---

## 🌟 Tính Năng Nổi Bật

### 1. Dual-Stage Detection Pipeline (Xử Lý Âm Thanh Kép)
- **Stage 1: DSP Transient Detector (<5ms)**: Sử dụng lọc thông cao Highpass (>1.5kHz), tính toán Crest Factor (độ nhọn xung) và Spectral Energy Ratio để bắt nhanh xung âm thanh vỗ tay với chi phí CPU gần như bằng 0.
- **Stage 2: AI Mel-Spectrogram Classifier**: Khi Stage 1 kích hoạt, cửa sổ 250ms được trích xuất Mel-Spectrogram (40 filterbanks) và phân loại qua mạng nơ-ron **ClapCNN2D** / **Random Forest Ensemble** để loại trừ triệt để tiếng ho, tiếng gõ bàn, tiếng đóng cửa hay tiếng nói chuyện.
- **Pattern Matcher (Nhận diện chuỗi vỗ tay)**:
  - 👏 **1 Vỗ (Single Clap)**: Bật / Tắt đèn ảo (Toggle Power).
  - 👏👏 **2 Vỗ (Double Clap)**: Chuyển đổi màu sắc RGB Neon.
  - 👏👏👏 **3 Vỗ (Triple Clap)**: Kích hoạt chế độ Party Strobe / Pháo hoa chúc mừng.

### 2. Personalized Training Studio (Huấn Luyện Mô Hình Cá Nhân)
- **Wizard 3 bước ngay trên Web UI**:
  - **Bước 1**: Bấm thu 5–10 mẫu vỗ tay của riêng bạn từ micro.
  - **Bước 2**: Thu 5 giây tiếng ồn nền thực tế trong phòng bạn (tiếng gõ phím, nói chuyện, quạt).
  - **Bước 3**: Bấm "Huấn luyện ngay" -> Hệ thống tự động **Data Augmentation** x12 lần, train mô hình trong ~3 giây trên CPU và tự động **Hot-Reload** vào cỗ máy nhận diện mà không cần khởi động lại server.

### 3. Smart Light Web Dashboard
- **Bóng đèn 3D phát sáng chân thực (Neon Glow)** thay đổi độ sáng (0–100%), bảng chọn màu RGB phong phú và hiệu ứng Party.
- **Biểu đồ sóng âm (Oscilloscope) & Phổ tần số thời gian thực** hiển thị trực quan mức năng lượng đỉnh và độ tin cậy AI.
- **Cài đặt linh hoạt**: Tùy chỉnh ngưỡng nhạy, khoảng thời gian giữa 2 lần vỗ (timing window) và Webhook URL để kết nối với ESP32 / Home Assistant / Tasmota.

---

## 🏗️ Cấu Trúc Thư Mục

```text
HandClap Detection/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── ws_audio.py             # WebSocket stream audio 16kHz PCM & điều khiển
│   │   │   ├── routes_training.py      # REST API thu mẫu và train model cá nhân
│   │   │   └── routes_devices.py       # REST API quản lý đèn và cài đặt
│   │   ├── core/
│   │   │   ├── audio_stream.py         # Audio Ring Buffer đệm âm thanh
│   │   │   ├── dsp_detector.py         # Stage 1: DSP Transient Detector
│   │   │   ├── feature_extractor.py    # Trích xuất Mel-Spectrogram & Acoustic vectors
│   │   │   ├── pattern_matcher.py      # Bộ nhận diện nhịp 1/2/3 lần vỗ
│   │   │   └── live_engine.py          # Dual-stage Live Engine
│   │   ├── models/
│   │   │   ├── architectures.py        # Mạng nơ-ron ClapCNN2D nhẹ
│   │   │   └── classifier.py           # Wrapper phân loại và Hot-reload
│   │   ├── training/
│   │   │   ├── augmentation.py         # Tăng cường dữ liệu âm thanh
│   │   │   ├── dataset_manager.py      # Quản lý dataset & Seed data
│   │   │   └── trainer.py              # Pipeline huấn luyện cá nhân hóa siêu tốc
│   │   ├── smart_home/
│   │   │   ├── virtual_bulb.py         # Trạng thái bóng đèn ảo
│   │   │   └── action_dispatcher.py    # Điều phối hành động & Webhook IoT
│   │   ├── config.py                   # Cấu hình ngưỡng nhạy & thông số
│   │   └── main.py                     # FastAPI entry point
│   ├── data/                           # Lưu trữ mẫu âm thanh & checkpoints
│   ├── requirements.txt
│   └── run_server.py
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── SmartLightBulb.js       # Bóng đèn 3D Glowing & bảng màu
│   │   │   ├── AudioVisualizer.js      # Biểu đồ dao động sóng & chỉ số AI
│   │   │   ├── TrainingStudio.js       # Wizard huấn luyện mô hình cá nhân
│   │   │   └── SettingsModal.js        # Cài đặt ngưỡng nhạy & action mapping
│   │   ├── services/
│   │   │   ├── audio_recorder.js       # Web Audio API thu âm micro 16kHz
│   │   │   ├── websocket_client.js     # WebSocket Client 2 chiều
│   │   │   └── api_client.js           # REST API Client
│   │   ├── styles/
│   │   │   ├── main.css                # Dark Glassmorphism Design System
│   │   │   ├── bulb.css                # Hiệu ứng phát sáng bóng đèn
│   │   │   └── visualizer.css
│   │   └── main.js
│   ├── index.html
│   └── vite.config.js
### 4. Continuous Room Noise Auto-Calibration (Tự Căn Chỉnh Độ Ồn Phòng Liên Tục)
- **Thuật toán Real-time Asymmetric EMA + Transient Filter**: Tự động đo lường mức ồn nền tĩnh (Noise Floor) liên tục trong thời gian thực.
- **Dynamic Threshold Adaptation**: Tự động nới lỏng ngưỡng khi phòng yên tĩnh để bắt tiếng vỗ tay nhẹ ở xa 3-4m, và nâng cao ngưỡng cùng siết chặt Crest Factor / AI Confidence khi phòng ồn ào (bật quạt, TV) nhằm chống báo giả tuyệt đối.
- **Trực quan hoá sống động**: Hiển thị vạch ngưỡng động (Dynamic Threshold) màu vàng neon trên Oscilloscope và Badge phân loại môi trường phòng ("🌿 Phòng yên tĩnh" / "🔉 Phòng chuẩn" / "🔊 Phòng ồn ào").

---

## 🏗️ Cấu Trúc Thư Mục

```text
HandClap Detection/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── ws_audio.py             # WebSocket stream audio 16kHz PCM & điều khiển
│   │   │   ├── routes_training.py      # REST API thu mẫu và train model cá nhân
│   │   │   └── routes_devices.py       # REST API quản lý đèn và cài đặt
│   │   ├── core/
│   │   │   ├── audio_stream.py         # Audio Ring Buffer đệm âm thanh
│   │   │   ├── noise_estimator.py      # Bộ tự căn chỉnh độ ồn nền liên tục (Adaptive Noise Floor)
│   │   │   ├── dsp_detector.py         # Stage 1: DSP Transient Detector
│   │   │   ├── feature_extractor.py    # Trích xuất Mel-Spectrogram & Acoustic vectors
│   │   │   ├── pattern_matcher.py      # Bộ nhận diện nhịp 1/2/3 lần vỗ
│   │   │   └── live_engine.py          # Dual-stage Live Engine
│   │   ├── models/
│   │   │   ├── architectures.py        # Mạng nơ-ron ClapCNN2D nhẹ
│   │   │   └── classifier.py           # Wrapper phân loại và Hot-reload
│   │   ├── training/
│   │   │   ├── augmentation.py         # Tăng cường dữ liệu âm thanh
│   │   │   ├── dataset_manager.py      # Quản lý dataset & Seed data
│   │   │   └── trainer.py              # Pipeline huấn luyện cá nhân hóa siêu tốc
│   │   ├── smart_home/
│   │   │   ├── virtual_bulb.py         # Trạng thái bóng đèn ảo
│   │   │   └── action_dispatcher.py    # Điều phối hành động & Webhook IoT
│   │   ├── config.py                   # Cấu hình ngưỡng nhạy & thông số
│   │   └── main.py                     # FastAPI entry point
│   ├── data/                           # Lưu trữ mẫu âm thanh & checkpoints
│   ├── requirements.txt
│   └── run_server.py
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── SmartLightBulb.js       # Bóng đèn 3D Glowing & bảng màu
│   │   │   ├── AudioVisualizer.js      # Biểu đồ dao động sóng, ngưỡng động & chỉ số AI
│   │   │   ├── TrainingStudio.js       # Wizard huấn luyện mô hình cá nhân
│   │   │   └── SettingsModal.js        # Cài đặt ngưỡng nhạy, adaptive noise & action mapping
│   │   ├── services/
│   │   │   ├── audio_recorder.js       # Web Audio API thu âm micro 16kHz
│   │   │   ├── websocket_client.js     # WebSocket Client 2 chiều
│   │   │   └── api_client.js           # REST API Client
│   │   ├── styles/
│   │   │   ├── main.css                # Dark Glassmorphism Design System
│   │   │   ├── bulb.css                # Hiệu ứng phát sáng bóng đèn
│   │   │   └── visualizer.css
│   │   └── main.js
│   ├── index.html
│   └── vite.config.js
│
├── run.py                              # Cross-platform Launcher (Windows, Linux, macOS)
├── run.sh                              # Linux/macOS launcher script
├── setup.sh                            # One-click environment setup script cho Linux
├── clap-detection.service              # File mẫu cấu hình Linux systemd service
└── README.md
```

---

## 🚀 Hướng Dẫn Cài Đặt & Khởi Chạy

### 1. Trên Windows
Tại thư mục gốc dự án, chạy lệnh:
```cmd
python run.py
```

### 2. Trên Linux / Ubuntu / Debian / Raspberry Pi
- **Bước 1: Cài đặt tự động (One-click Setup)**
  ```bash
  chmod +x setup.sh run.sh
  ./setup.sh
  ```
- **Bước 2: Khởi chạy ứng dụng**
  ```bash
  ./run.sh
  # Hoặc: python3 run.py
  ```

### 3. Chạy dưới dạng Dịch vụ ngầm (systemd Service trên Linux)
Copy file cấu hình vào thư mục dịch vụ của hệ thống:
```bash
sudo cp clap-detection.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now clap-detection
```

### 4. Truy cập ứng dụng
- **Web Frontend**: [http://localhost:5173](http://localhost:5173)
- **Backend API & Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **WebSocket Stream**: `ws://localhost:8000/ws/audio`

---

## 🎯 Hướng Dẫn Sử Dụng

1. **Bật Microphone**: Mở trình duyệt tại [http://localhost:5173](http://localhost:5173), nhấn nút **"Bật Microphone"** ở góc phải trên cùng và cho phép trình duyệt truy cập micro.
2. **Quan sát Căn chỉnh Độ Ồn Tự Động**:
   - Nhìn vào badge trạng thái ("🌿 Phòng yên tĩnh" / "🔉 Phòng chuẩn" / "🔊 Phòng ồn ào").
   - Vạch nét đứt màu vàng trên Oscilloscope sẽ tự động nâng lên/hạ xuống theo độ ồn phòng để đảm bảo độ nhạy tốt nhất.
3. **Thử nghiệm vỗ tay**:
   - Vỗ 1 lần trước micro: Đèn ảo sẽ Bật / Tắt.
   - Vỗ 2 lần liên tiếp: Đèn đổi sang màu RGB tiếp theo.
   - Vỗ 3 lần liên tiếp: Kích hoạt chế độ Party Strobe rực rỡ kèm pháo hoa!
4. **Huấn luyện mô hình cá nhân**:
   - Chuyển sang tab **"Training Studio (Huấn Luyện)"**.
   - Bấm thu 5-8 mẫu vỗ tay của bạn ở Bước 1.
   - Bấm thu 3-5 mẫu tiếng ồn / gõ bàn ở Bước 2.
   - Bấm **"Bắt đầu Huấn Luyện Ngay"** ở Bước 3 -> Mô hình mới sẽ được kích hoạt ngay lập tức!
5. **Tích hợp IoT bên ngoài**:
   - Bấm icon ⚙️ Cài đặt ở góc trên cùng.
   - Nhập URL Webhook (ví dụ Webhook của Home Assistant hoặc ESP32 HTTP Server). Mỗi khi nhận diện vỗ tay, Backend sẽ gửi payload JSON cập nhật trạng thái ra thiết bị thật.
