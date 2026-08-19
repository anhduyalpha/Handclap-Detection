import numpy as np
from typing import Dict, Any, Tuple
from ..config import settings

class AdaptiveNoiseFloorEstimator:
    """
    Bộ theo dõi và tự động căn chỉnh mức ồn nền phòng thời gian thực (Adaptive Percentile Noise Estimator).
    Hoạt động 24/7 với bộ đệm cố định (Zero-Leak Bounded Buffer) và Exponential Moving Average (EMA).
    
    Cơ chế:
    1. Đo lường liên tục RMS và Peak của tín hiệu môi trường.
    2. Theo dõi phân vị (Percentile Tracking p10, p50, p90) trên cửa sổ trượt 100 khung hình gần nhất.
    3. Cập nhật bất đối xứng (Asymmetric EMA):
       - Tăng nhanh khi có nguồn ồn liên tục mới (quạt gió, máy lạnh bật).
       - Giảm chậm rãi, ổn định khi phòng yên tĩnh trở lại.
    4. Tự động tính toán các ngưỡng động:
       - Dynamic Energy Threshold (nổi trên nền đỉnh ồn).
       - Dynamic Crest Factor.
       - Dynamic High-Frequency Ratio Threshold.
       - Dynamic AI Confidence Threshold.
    """
    def __init__(self, history_len: int = 120):
        self.history_len = history_len
        # Bộ đệm cố định lưu RMS lịch sử để tính phân vị (Percentiles)
        self.rms_history = np.full(history_len, 0.008, dtype=np.float32)
        self.history_idx = 0
        self.history_count = 0
        
        # Mức ồn nền khởi tạo
        self.noise_floor_rms: float = 0.008
        self.noise_floor_peak: float = 0.015
        self.hf_noise_ratio: float = 0.25
        
        # Phân vị năng lượng ồn
        self.p10_rms: float = 0.006
        self.p50_rms: float = 0.008
        self.p90_rms: float = 0.012
        
        # Trạng thái âm học phòng
        self.ambient_status: str = "normal"  # "quiet" | "normal" | "noisy" | "very_noisy"
        self.ambient_label: str = "☀️ Phòng Tiêu Chuẩn"
        self.current_snr_db: float = 0.0
        
        # Các ngưỡng động
        self.dynamic_energy_thresh: float = settings.dsp.energy_threshold
        self.dynamic_crest_thresh: float = settings.dsp.crest_factor_min
        self.dynamic_hf_thresh: float = settings.dsp.hf_energy_ratio_min
        self.dynamic_confidence_thresh: float = settings.ml.confidence_threshold
        
        self.initialized_samples: int = 0
        self.sustained_frames: int = 0

    def update(
        self, 
        chunk_rms: float, 
        chunk_peak: float, 
        chunk_crest: float, 
        chunk_hf: float, 
        is_transient: bool = False
    ) -> Dict[str, Any]:
        """
        Cập nhật ước lượng mức ồn nền từ chunk hiện tại và tính toán ngưỡng động.
        """
        cfg = settings.adaptive_noise

        # 1. Phân biệt xung đột ngột (Clap Transient) vs Tiếng ồn nền liên tục (Ambient Noise)
        is_impulsive_spike = (
            is_transient or 
            (chunk_crest >= 2.8 and chunk_peak > max(0.035, self.noise_floor_peak * cfg.transient_rejection_ratio))
        )
        
        if is_impulsive_spike:
            self.sustained_frames = 0
        else:
            self.sustained_frames += 1

        # 2. Cập nhật mức ồn nền khi là âm thanh nền ổn định hoặc âm thanh lớn kéo dài liên tục > 5 chunks
        if not is_impulsive_spike or self.sustained_frames > 5:
            # Ghi vào bộ đệm vòng RMS lịch sử
            self.rms_history[self.history_idx] = chunk_rms
            self.history_idx = (self.history_idx + 1) % self.history_len
            if self.history_count < self.history_len:
                self.history_count += 1

            # Giai đoạn khởi động nhanh (10 chunks đầu tiên)
            if self.initialized_samples < 10:
                alpha = 0.40
                self.initialized_samples += 1
            else:
                # Cập nhật bất đối xứng: tăng nhanh khi ồn, giảm chậm vừa phải khi yên tĩnh
                if chunk_rms > self.noise_floor_rms:
                    alpha = cfg.adaptation_speed * 1.2
                else:
                    alpha = cfg.adaptation_speed * 0.6

            self.noise_floor_rms = (1.0 - alpha) * self.noise_floor_rms + alpha * chunk_rms
            self.noise_floor_peak = (1.0 - alpha) * self.noise_floor_peak + alpha * chunk_peak
            self.hf_noise_ratio = (1.0 - alpha) * self.hf_noise_ratio + alpha * chunk_hf

        # Đảm bảo noise floor nằm trong dải vật lý hợp lệ
        self.noise_floor_rms = float(np.clip(self.noise_floor_rms, 0.001, 0.25))
        self.noise_floor_peak = float(np.clip(self.noise_floor_peak, 0.003, 0.35))

        # 3. Tính phân vị năng lượng (Percentiles) trên dữ liệu thực tế đã tích lũy
        if self.history_count >= 10:
            valid_hist = self.rms_history[:self.history_count]
            self.p10_rms = float(np.percentile(valid_hist, 10))
            self.p50_rms = float(np.percentile(valid_hist, 50))
            self.p90_rms = float(np.percentile(valid_hist, 90))

        # 4. Phân loại trạng thái âm học môi trường
        if self.noise_floor_rms < 0.009:
            self.ambient_status = "quiet"
            self.ambient_label = "🌙 Phòng Yên Tĩnh (Bắt xa 3-5m)"
        elif self.noise_floor_rms > 0.045:
            self.ambient_status = "very_noisy"
            self.ambient_label = "🚨 Phòng Cực Ồn (Siết chặt ngưỡng)"
        elif self.noise_floor_rms > 0.025:
            self.ambient_status = "noisy"
            self.ambient_label = "🌪️ Phòng Nhiều Tạp Âm"
        else:
            self.ambient_status = "normal"
            self.ambient_label = "☀️ Phòng Tiêu Chuẩn"

        # 5. Tính toán tỷ lệ SNR thời gian thực (dB)
        snr_ratio = max(0.0001, chunk_rms) / max(0.0001, self.noise_floor_rms)
        self.current_snr_db = round(float(20.0 * np.log10(snr_ratio)), 1)

        # 6. Tính toán Ngưỡng Động (Dynamic Floating Thresholds)
        if cfg.enabled:
            # A. Dynamic Energy Threshold:
            # Ngưỡng năng lượng nổi trên nền đỉnh ồn (p90 hoặc noise_floor_peak)
            effective_peak_base = max(self.noise_floor_peak, self.p90_rms * 2.2)
            raw_energy = effective_peak_base * cfg.margin_factor + 0.003
            self.dynamic_energy_thresh = float(np.clip(
                raw_energy, 
                cfg.min_energy_threshold, 
                cfg.max_energy_threshold
            ))

            # B. Dynamic Crest Factor & High Frequency Ratio & AI Confidence
            if self.ambient_status == "quiet":
                # Nới lỏng nhẹ để bắt tiếng vỗ tay nhẹ / ở khoảng cách xa 3-5m
                self.dynamic_crest_thresh = max(2.0, settings.dsp.crest_factor_min - 0.4)
                self.dynamic_hf_thresh = max(0.28, settings.dsp.hf_energy_ratio_min - 0.04)
                self.dynamic_confidence_thresh = max(0.65, settings.ml.confidence_threshold - 0.08)
            elif self.ambient_status == "very_noisy":
                # Siết chặt tối đa để chống mọi loại báo giả
                self.dynamic_crest_thresh = min(3.8, settings.dsp.crest_factor_min + 0.8)
                self.dynamic_hf_thresh = min(0.40, settings.dsp.hf_energy_ratio_min + 0.06)
                self.dynamic_confidence_thresh = min(0.88, settings.ml.confidence_threshold + 0.10)
            elif self.ambient_status == "noisy":
                self.dynamic_crest_thresh = min(3.4, settings.dsp.crest_factor_min + 0.5)
                self.dynamic_hf_thresh = min(0.36, settings.dsp.hf_energy_ratio_min + 0.03)
                self.dynamic_confidence_thresh = min(0.84, settings.ml.confidence_threshold + 0.06)
            else:
                self.dynamic_crest_thresh = settings.dsp.crest_factor_min
                self.dynamic_hf_thresh = settings.dsp.hf_energy_ratio_min
                self.dynamic_confidence_thresh = settings.ml.confidence_threshold
        else:
            self.dynamic_energy_thresh = settings.dsp.energy_threshold
            self.dynamic_crest_thresh = settings.dsp.crest_factor_min
            self.dynamic_hf_thresh = settings.dsp.hf_energy_ratio_min
            self.dynamic_confidence_thresh = settings.ml.confidence_threshold

        return self.get_state()

    def get_state(self) -> Dict[str, Any]:
        """Trả về toàn bộ trạng thái căn chỉnh ồn nền"""
        return {
            "noise_floor_rms": round(float(self.noise_floor_rms), 4),
            "noise_floor_peak": round(float(self.noise_floor_peak), 4),
            "p10_rms": round(float(self.p10_rms), 4),
            "p50_rms": round(float(self.p50_rms), 4),
            "p90_rms": round(float(self.p90_rms), 4),
            "hf_noise_ratio": round(float(self.hf_noise_ratio), 3),
            "ambient_status": self.ambient_status,
            "ambient_label": self.ambient_label,
            "snr_db": getattr(self, "current_snr_db", 0.0),
            "dynamic_energy_thresh": round(float(self.dynamic_energy_thresh), 4),
            "dynamic_crest_thresh": round(float(self.dynamic_crest_thresh), 2),
            "dynamic_hf_thresh": round(float(self.dynamic_hf_thresh), 3),
            "dynamic_confidence_thresh": round(float(self.dynamic_confidence_thresh), 2),
            "auto_adaptive_enabled": settings.adaptive_noise.enabled
        }
