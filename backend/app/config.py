import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_SAMPLES_DIR = DATA_DIR / "default_samples"
USER_PROFILES_DIR = DATA_DIR / "user_profiles"
CHECKPOINTS_DIR = DATA_DIR / "checkpoints"

# Đảm bảo các thư mục dữ liệu tồn tại
for directory in [DATA_DIR, DEFAULT_SAMPLES_DIR, USER_PROFILES_DIR, CHECKPOINTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

class AudioConfig(BaseModel):
    sample_rate: int = 16000
    chunk_size: int = 512
    buffer_duration_sec: float = 1.5  # Ring buffer length in seconds
    clip_duration_sec: float = 0.25   # Window around clap for feature extraction (250ms)
    n_mels: int = 40
    n_fft: int = 512
    hop_length: int = 160             # 10ms hop
    n_mfcc: int = 20

class DSPConfig(BaseModel):
    # Stage 1: Transient & Peak detection
    energy_threshold: float = 0.025   # Ngưỡng biên độ đỉnh tối thiểu
    crest_factor_min: float = 2.4     # Tỉ lệ đỉnh / RMS (loại trừ tiếng nói, quạt, nhạc)
    hf_energy_ratio_min: float = 0.22 # Tỉ lệ năng lượng tần số cao (>1500Hz)
    min_silence_before_ms: float = 30.0 # Khoảng lặng trước khi có xung

class MLConfig(BaseModel):
    # Stage 2: AI Classifier (Độ chính xác cao chống báo giả)
    confidence_threshold: float = 0.75 # Ngưỡng xác nhận AI (0.75 = 75%)
    model_type: str = "hybrid_ensemble"  # "cnn" | "random_forest" | "hybrid_ensemble"
    active_profile: str = "default"

class SensitivityPresets:
    PRESETS = {
        "high_sensitivity": {
            "name": "Nhạy Cao (Vỗ nhẹ / Ở xa 2-3m)",
            "energy_threshold": 0.020,
            "crest_factor_min": 2.2,
            "confidence_threshold": 0.68,
            "hf_energy_ratio_min": 0.24
        },
        "balanced": {
            "name": "Cân Bằng (Phòng tiêu chuẩn)",
            "energy_threshold": 0.028,
            "crest_factor_min": 2.5,
            "confidence_threshold": 0.75,
            "hf_energy_ratio_min": 0.28
        },
        "strict_anti_noise": {
            "name": "Chống Nhiễu Cao (Phòng nhiều tạp âm)",
            "energy_threshold": 0.055,
            "crest_factor_min": 3.2,
            "confidence_threshold": 0.85,
            "hf_energy_ratio_min": 0.35
        }
    }

class PatternConfig(BaseModel):
    # Nhận diện chuỗi vỗ tay (Single, Double, Triple)
    min_inter_clap_ms: int = 180      # Khoảng thời gian tối thiểu giữa 2 lần vỗ (tránh dội âm)
    max_inter_clap_ms: int = 480      # Khoảng thời gian tối đa để tính là cùng 1 chuỗi (phản hồi nhanh)
    cooldown_ms: int = 700            # Thời gian nghỉ sau khi thực thi hành động (chống dội lệnh)

class SmartLightConfig(BaseModel):
    power: bool = True
    brightness: int = 80              # 0 - 100
    color: str = "#00e5ff"            # Hex color (Cyan neon default)
    mode: str = "solid"               # "solid" | "rainbow" | "pulse" | "party"
    single_clap_action: str = "toggle_power"
    double_clap_action: str = "next_color"
    triple_clap_action: str = "party_mode"
    webhook_url: str = "http://192.168.2.171:8123/api/webhook/vo_tay_toggle_den" # Webhook Home Assistant / ESP32

class AdaptiveNoiseConfig(BaseModel):
    enabled: bool = True                  # Bật/tắt tự động căn chỉnh độ ồn nền liên tục
    adaptation_speed: float = 0.05        # Tốc độ cập nhật EMA (alpha)
    margin_factor: float = 1.6            # Hệ số nhân biên an toàn trên đỉnh nhiễu nền
    min_energy_threshold: float = 0.016   # Ngưỡng tối thiểu khi phòng cực kỳ yên tĩnh
    max_energy_threshold: float = 0.120   # Ngưỡng tối đa cho phép khi phòng quá ồn
    transient_rejection_ratio: float = 2.2 # Tỉ lệ peak/noise_floor để loại bỏ không đưa vào học

class AppSettings(BaseModel):
    audio: AudioConfig = AudioConfig()
    dsp: DSPConfig = DSPConfig()
    adaptive_noise: AdaptiveNoiseConfig = AdaptiveNoiseConfig()
    ml: MLConfig = MLConfig()
    pattern: PatternConfig = PatternConfig()
    light: SmartLightConfig = SmartLightConfig()
    windows_studio_url: str = os.getenv("WINDOWS_STUDIO_URL", "http://192.168.2.134:8001")

settings = AppSettings()

