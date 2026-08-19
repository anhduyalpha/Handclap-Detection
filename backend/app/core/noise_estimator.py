import numpy as np
import logging
from typing import Dict, Any
from ..config import settings

logger = logging.getLogger("handclap.noise_estimator")

class AdaptiveNoiseFloorEstimator:
    """
    Bộ ước lượng ồn nền phân vị (Percentile Noise Floor Estimator).
    Tự động căn chỉnh ngưỡng nhạy theo môi trường thực tế (Yên tĩnh vs Ồn ào).
    
    Phân loại mức ồn phòng:
    - 'quiet': RMS < 0.009 (Phòng đêm yên tĩnh -> Tăng cường độ nhạy bắt xa 3-5m)
    - 'normal': 0.009 <= RMS < 0.025 (Phòng sinh hoạt bình thường)
    - 'noisy': 0.025 <= RMS < 0.055 (Phòng mở quạt gió to, tivi, có người nói chuyện)
    - 'very_noisy': RMS >= 0.055 (Môi trường rất ồn -> Nâng cao ngưỡng chống báo giả)
    """
    def __init__(self, history_len: int = 120):
        self.history_len = history_len
        self.rms_history = np.full(history_len, 0.005, dtype=np.float32)
        self.history_idx = 0
        self.initialized_samples = 0

        # Ước lượng EMA
        self.noise_floor_rms = 0.005
        self.noise_floor_peak = 0.010
        
        # Thống kê phân vị
        self.p10_rms = 0.003
        self.p50_rms = 0.005
        self.p90_rms = 0.008

        # Ngưỡng động thả nổi (Dynamic Floating Thresholds)
        self.dynamic_energy_thresh = 0.010
        self.dynamic_crest_thresh = 1.5
        self.dynamic_hf_thresh = 0.12
        self.dynamic_confidence_thresh = 0.45

        self.ambient_status = "normal"
        self.ambient_label = "Phòng Bình Thường"
        self.snr_db = 0.0

    def update(
        self, 
        chunk_rms: float, 
        chunk_peak: float, 
        chunk_crest: float, 
        chunk_hf: float,
        is_transient: bool = False
    ) -> Dict[str, Any]:
        """Cập nhật thống kê môi trường thời gian thực cho từng chunk âm thanh"""
        cfg = settings.adaptive_noise
        if not cfg.enabled:
            return self.get_state()

        # Không đưa các xung năng lượng cao vào làm sai lệch mức ồn nền
        if is_transient or chunk_crest > cfg.transient_rejection_ratio:
            is_valid_background = False
        else:
            is_valid_background = True

        if is_valid_background:
            self.rms_history[self.history_idx] = chunk_rms
            self.history_idx = (self.history_idx + 1) % self.history_len
            
            if self.initialized_samples < 10:
                alpha = 0.40
                self.initialized_samples += 1
            else:
                if chunk_rms > self.noise_floor_rms:
                    alpha = cfg.adaptation_speed * 1.2
                else:
                    alpha = cfg.adaptation_speed * 0.6

            self.noise_floor_rms = (1.0 - alpha) * self.noise_floor_rms + alpha * chunk_rms
            self.noise_floor_peak = (1.0 - alpha) * self.noise_floor_peak + alpha * chunk_peak

            self.p10_rms = float(np.percentile(self.rms_history, 10))
            self.p50_rms = float(np.percentile(self.rms_history, 50))
            self.p90_rms = float(np.percentile(self.rms_history, 90))

            if self.noise_floor_rms < 0.009:
                self.ambient_status = "quiet"
                self.ambient_label = "🌙 Phòng Yên Tĩnh (Bắt xa 3-5m)"
            elif self.noise_floor_rms < 0.025:
                self.ambient_status = "normal"
                self.ambient_label = "🏡 Phòng Bình Thường (Bắt 2-3m)"
            elif self.noise_floor_rms < 0.055:
                self.ambient_status = "noisy"
                self.ambient_label = "📢 Phòng Ồn / Bật Quạt"
            else:
                self.ambient_status = "very_noisy"
                self.ambient_label = "⚠️ Rất Ồn (Tự Động Nâng Ngưỡng)"

        # 1. Tính ngưỡng năng lượng động (Dynamic Energy Threshold)
        effective_peak_base = max(self.noise_floor_peak, self.p90_rms * 1.5)
        raw_energy = effective_peak_base * cfg.margin_factor + 0.001
        self.dynamic_energy_thresh = float(np.clip(
            raw_energy,
            cfg.min_energy_threshold,
            cfg.max_energy_threshold
        ))

        # 2. Ngưỡng Crest & Confidence động
        if self.ambient_status == "quiet":
            self.dynamic_crest_thresh = 1.4
            self.dynamic_hf_thresh = 0.10
            self.dynamic_confidence_thresh = 0.40
        elif self.ambient_status == "normal":
            self.dynamic_crest_thresh = 1.5
            self.dynamic_hf_thresh = 0.12
            self.dynamic_confidence_thresh = 0.45
        elif self.ambient_status == "noisy":
            self.dynamic_crest_thresh = 2.0
            self.dynamic_hf_thresh = 0.18
            self.dynamic_confidence_thresh = 0.55
        else: # very_noisy
            self.dynamic_crest_thresh = 2.4
            self.dynamic_hf_thresh = 0.22
            self.dynamic_confidence_thresh = 0.65

        # 3. Tính SNR
        if self.noise_floor_rms > 1e-6:
            self.snr_db = round(float(20.0 * np.log10(max(chunk_peak, 1e-5) / self.noise_floor_rms)), 1)
        else:
            self.snr_db = 0.0

        return self.get_state()

    def get_state(self) -> Dict[str, Any]:
        return {
            "ambient_status": self.ambient_status,
            "ambient_label": self.ambient_label,
            "noise_floor_rms": round(float(self.noise_floor_rms), 4),
            "noise_floor_peak": round(float(self.noise_floor_peak), 4),
            "p10_rms": round(float(self.p10_rms), 4),
            "p50_rms": round(float(self.p50_rms), 4),
            "p90_rms": round(float(self.p90_rms), 4),
            "dynamic_energy_thresh": round(float(self.dynamic_energy_thresh), 4),
            "dynamic_crest_thresh": round(float(self.dynamic_crest_thresh), 2),
            "dynamic_hf_thresh": round(float(self.dynamic_hf_thresh), 2),
            "dynamic_confidence_thresh": round(float(self.dynamic_confidence_thresh), 2),
            "snr_db": self.snr_db
        }
