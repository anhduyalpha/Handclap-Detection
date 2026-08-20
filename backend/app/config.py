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

for directory in [DATA_DIR, DEFAULT_SAMPLES_DIR, USER_PROFILES_DIR, CHECKPOINTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

class AudioConfig(BaseModel):
    sample_rate: int = 16000
    chunk_size: int = 512
    buffer_duration_sec: float = 1.5
    clip_duration_sec: float = 0.25
    n_mels: int = 40
    n_fft: int = 512
    hop_length: int = 160
    n_mfcc: int = 20

class DSPConfig(BaseModel):
    # Stage 1: Transient & Peak detection
    energy_threshold: float = 0.018   # Ngưỡng năng lượng linh hoạt
    crest_factor_min: float = 1.8     # Tỉ lệ đỉnh / RMS
    hf_energy_ratio_min: float = 0.15 # Tỉ lệ năng lượng tần số cao (>1200Hz)
    min_silence_before_ms: float = 15.0

class MLConfig(BaseModel):
    # Stage 2: AI Classifier
    confidence_threshold: float = 0.50 # Ngưỡng xác nhận AI (50% mặc định rất nhạy)
    model_type: str = "hybrid_ensemble"
    active_profile: str = "default"

class SensitivityPresets:
    PRESETS = {
        "high_sensitivity": {
            "name": "⚡ Siêu Nhạy (Ở xa 3-5m / Vỗ nhẹ)",
            "energy_threshold": 0.012,
            "crest_factor_min": 1.5,
            "confidence_threshold": 0.40,
            "hf_energy_ratio_min": 0.12,
            "margin_factor": 1.15,
            "max_inter_clap_ms": 800
        },
        "balanced": {
            "name": "⚖️ Cân Bằng (Phòng 1.5-3m / Tiêu chuẩn)",
            "energy_threshold": 0.020,
            "crest_factor_min": 1.8,
            "confidence_threshold": 0.50,
            "hf_energy_ratio_min": 0.16,
            "margin_factor": 1.30,
            "max_inter_clap_ms": 750
        },
        "strict_anti_noise": {
            "name": "🛡️ Chống Nhiễu Cao (Phòng nhiều tạp âm)",
            "energy_threshold": 0.040,
            "crest_factor_min": 2.5,
            "confidence_threshold": 0.70,
            "hf_energy_ratio_min": 0.25,
            "margin_factor": 1.60,
            "max_inter_clap_ms": 650
        }
    }

class PatternConfig(BaseModel):
    min_inter_clap_ms: int = 100
    max_inter_clap_ms: int = 750
    cooldown_ms: int = 350

class SmartLightConfig(BaseModel):
    power: bool = True
    brightness: int = 80
    color: str = "#00e5ff"
    mode: str = "solid"
    double_clap_action: str = "toggle_power"
    webhook_url: str = os.getenv("WEBHOOK_URL", "http://192.168.2.171:8123/api/webhook/vo_tay_toggle_den")

class AdaptiveNoiseConfig(BaseModel):
    enabled: bool = True
    adaptation_speed: float = 0.05
    margin_factor: float = 1.30
    min_energy_threshold: float = 0.010
    max_energy_threshold: float = 0.075
    transient_rejection_ratio: float = 2.4

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
    """Tải cấu hình đã lưu trên đĩa để duy trì qua các lần khởi động lại"""
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
            if "crest_factor_min" in data:
                settings.dsp.crest_factor_min = float(data["crest_factor_min"])
            if "confidence_threshold" in data:
                settings.ml.confidence_threshold = float(data["confidence_threshold"])
            if "min_inter_clap_ms" in data:
                settings.pattern.min_inter_clap_ms = int(data["min_inter_clap_ms"])
            if "max_inter_clap_ms" in data:
                settings.pattern.max_inter_clap_ms = int(data["max_inter_clap_ms"])
            if "margin_factor" in data:
                settings.adaptive_noise.margin_factor = float(data["margin_factor"])
            if "adaptive_noise_enabled" in data:
                settings.adaptive_noise.enabled = bool(data["adaptive_noise_enabled"])
            if "windows_studio_url" in data and data["windows_studio_url"]:
                settings.windows_studio_url = data["windows_studio_url"]
            if "linux_server_url" in data and data["linux_server_url"]:
                settings.linux_server_url = data["linux_server_url"]
            logger.info(f"Loaded persistent user settings from {SETTINGS_FILE} (Webhook: {settings.light.webhook_url})")
        except Exception as e:
            logger.warning(f"Error loading persistent settings: {e}")

def save_persistent_settings():
    """Lưu cấu hình hiện tại ra file JSON trên đĩa"""
    try:
        data = {
            "webhook_url": settings.light.webhook_url,
            "double_clap_action": settings.light.double_clap_action,
            "energy_threshold": settings.dsp.energy_threshold,
            "crest_factor_min": settings.dsp.crest_factor_min,
            "confidence_threshold": settings.ml.confidence_threshold,
            "min_inter_clap_ms": settings.pattern.min_inter_clap_ms,
            "max_inter_clap_ms": settings.pattern.max_inter_clap_ms,
            "margin_factor": settings.adaptive_noise.margin_factor,
            "adaptive_noise_enabled": settings.adaptive_noise.enabled,
            "windows_studio_url": settings.windows_studio_url,
            "linux_server_url": settings.linux_server_url,
            "auto_collect_true_claps": settings.auto_collect_true_claps
        }
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved persistent user settings to {SETTINGS_FILE}")
    except Exception as e:
        logger.error(f"Error saving persistent settings: {e}")

# Tải cấu hình khi import module
load_persistent_settings()
