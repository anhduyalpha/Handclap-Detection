import os
import json
import logging
from pathlib import Path
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

logger = logging.getLogger("handclap.config")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_SAMPLES_DIR = DATA_DIR / "default_samples"
USER_PROFILES_DIR = DATA_DIR / "user_profiles"
CHECKPOINTS_DIR = DATA_DIR / "checkpoints"
SETTINGS_FILE = DATA_DIR / "user_settings.json"

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
    # Stage 1: Transient & Peak detection (Mức Tiêu Chuẩn Cân Bằng)
    energy_threshold: float = 0.025   # Ngưỡng năng lượng tiêu chuẩn (loại bỏ tiếng ồn nền, tiếng nói nhỏ)
    crest_factor_min: float = 2.2     # Tỉ lệ đỉnh / RMS (yêu cầu xung nhọn của tiếng vỗ tay)
    hf_energy_ratio_min: float = 0.20 # Tỉ lệ năng lượng tần số cao (>1200Hz)
    min_silence_before_ms: float = 15.0 # Khoảng lặng trước khi có xung

class MLConfig(BaseModel):
    # Stage 2: AI Classifier (Ngưỡng tự tin tiêu chuẩn chống báo giả)
    confidence_threshold: float = 0.65 # Ngưỡng xác nhận AI (0.65 = 65%)
    model_type: str = "hybrid_ensemble"  # "cnn" | "random_forest" | "hybrid_ensemble"
    active_profile: str = "default"

class SensitivityPresets:
    PRESETS = {
        "balanced": {
            "name": "Tiêu Chuẩn (Khuyên Dùng - Phòng 1.5-3m)",
            "energy_threshold": 0.025,
            "crest_factor_min": 2.2,
            "confidence_threshold": 0.65,
            "hf_energy_ratio_min": 0.20
        },
        "high_sensitivity": {
            "name": "Độ Nhạy Cao (Vỗ nhẹ / Ở xa 3-5m)",
            "energy_threshold": 0.015,
            "crest_factor_min": 1.7,
            "confidence_threshold": 0.50,
            "hf_energy_ratio_min": 0.15
        },
        "strict_anti_noise": {
            "name": "Chống Nhiễu Tuyệt Đối (Phòng rất ồn)",
            "energy_threshold": 0.045,
            "crest_factor_min": 2.8,
            "confidence_threshold": 0.75,
            "hf_energy_ratio_min": 0.28
        }
    }

class PatternConfig(BaseModel):
    # Nhận diện chuỗi 2 tiếng vỗ tay tức thời (Instant Double Clap)
    min_inter_clap_ms: int = 120       # Khoảng cách tối thiểu giữa 2 cú vỗ
    max_inter_clap_ms: int = 700       # Cửa sổ tối đa giữa 2 cú vỗ (700ms chuẩn sinh học)
    cooldown_ms: int = 400             # Thời gian nghỉ sau khi thực thi hành động

class SmartLightConfig(BaseModel):
    power: bool = True
    brightness: int = 80               # 0 - 100
    color: str = "#00e5ff"             # Hex color (Cyan neon default)
    mode: str = "solid"                # "solid" | "rainbow" | "pulse" | "party"
    double_clap_action: str = "toggle_power"   # 2 tiếng vỗ liên tiếp (Double Clap) -> Bật/Tắt Đèn
    # Mặc định cấu hình sẵn Webhook Home Assistant của bạn
    webhook_url: str = os.getenv("WEBHOOK_URL", "http://192.168.2.171:8123/api/webhook/vo_tay_toggle_den")

class AdaptiveNoiseConfig(BaseModel):
    enabled: bool = True                  # Bật/tắt tự động căn chỉnh độ ồn nền liên tục
    adaptation_speed: float = 0.05        # Tốc độ cập nhật EMA (alpha)
    margin_factor: float = 1.40           # Hệ số an toàn
    min_energy_threshold: float = 0.020   # Ngưỡng tối thiểu khi phòng yên tĩnh
    max_energy_threshold: float = 0.080   # Ngưỡng tối đa khi phòng ồn
    transient_rejection_ratio: float = 2.5 # Tỉ lệ peak/noise_floor để loại bỏ

class AppSettings(BaseModel):
    audio: AudioConfig = AudioConfig()
    dsp: DSPConfig = DSPConfig()
    adaptive_noise: AdaptiveNoiseConfig = AdaptiveNoiseConfig()
    ml: MLConfig = MLConfig()
    pattern: PatternConfig = PatternConfig()
    light: SmartLightConfig = SmartLightConfig()
    windows_studio_url: str = os.getenv("WINDOWS_STUDIO_URL", "http://127.0.0.1:8001")
    linux_server_url: str = os.getenv("LINUX_SERVER_URL", "http://127.0.0.1:8000")
    auto_collect_true_claps: bool = os.getenv("AUTO_COLLECT_TRUE_CLAPS", "true").lower() in ("true", "1", "yes")
    studio_api_token: str = os.getenv("STUDIO_API_TOKEN", "")
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")

settings = AppSettings()

def load_persistent_settings():
    """Tải cấu hình đã lưu trên đĩa (nếu có) để duy trì cấu hình qua các lần khởi động lại"""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if "webhook_url" in data and data["webhook_url"]:
                settings.light.webhook_url = data["webhook_url"]
            if "double_clap_action" in data and data["double_clap_action"]:
                settings.light.double_clap_action = data["double_clap_action"]
            if "energy_threshold" in data:
                settings.dsp.energy_threshold = float(data["energy_threshold"])
            if "confidence_threshold" in data:
                settings.ml.confidence_threshold = float(data["confidence_threshold"])
            if "min_inter_clap_ms" in data:
                settings.pattern.min_inter_clap_ms = int(data["min_inter_clap_ms"])
            if "max_inter_clap_ms" in data:
                settings.pattern.max_inter_clap_ms = int(data["max_inter_clap_ms"])
            if "windows_studio_url" in data and data["windows_studio_url"]:
                settings.windows_studio_url = data["windows_studio_url"]
            if "linux_server_url" in data and data["linux_server_url"]:
                settings.linux_server_url = data["linux_server_url"]
            logger.info(f"Loaded persistent user settings from {SETTINGS_FILE} (Webhook: {settings.light.webhook_url})")
        except Exception as e:
            logger.warning(f"Error loading persistent settings: {e}")

def save_persistent_settings():
    """Lưu cấu hình hiện tại ra file JSON trên đĩa để không bao giờ bị mất"""
    try:
        data = {
            "webhook_url": settings.light.webhook_url,
            "double_clap_action": settings.light.double_clap_action,
            "energy_threshold": settings.dsp.energy_threshold,
            "confidence_threshold": settings.ml.confidence_threshold,
            "min_inter_clap_ms": settings.pattern.min_inter_clap_ms,
            "max_inter_clap_ms": settings.pattern.max_inter_clap_ms,
            "windows_studio_url": settings.windows_studio_url,
            "linux_server_url": settings.linux_server_url,
            "auto_collect_true_claps": settings.auto_collect_true_claps,
            "adaptive_noise_enabled": settings.adaptive_noise.enabled
        }
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved persistent user settings to {SETTINGS_FILE}")
    except Exception as e:
        logger.error(f"Error saving persistent settings: {e}")

# Tải cấu hình khi import module
load_persistent_settings()
