import numpy as np
from typing import Dict, Any, Tuple
from ..config import settings

class AdaptiveNoiseFloorEstimator:
    """
    Bộ theo dõi và tự động căn chỉnh mức ồn nền phòng thời gian thực (Continuous Noise Floor Tracker).
    
    Cơ chế hoạt động:
    1. Đo lường liên tục RMS và Peak của tín hiệu âm thanh môi trường.
    2. Bộ lọc loại trừ xung (Transient Rejection): Khi có âm thanh tăng đột ngột (tiếng vỗ tay, gõ bàn),
       hệ thống đóng băng cập nhật để tiếng vỗ tay không làm tăng ngưỡng ồn nền.
    3. Cập nhật bất đối xứng (Asymmetric EMA):
       - Tăng nhanh vừa phải khi phòng có nguồn ồn liên tục mới (bật quạt, máy lạnh).
       - Giảm chậm rãi, ổn định khi phòng yên tĩnh trở lại.
    4. Tính toán Ngưỡng Động (Dynamic Thresholds):
       - Dynamic Energy Threshold: Tự động dịch chuyển theo biên độ đỉnh của tiếng ồn phòng.
       - Dynamic Crest Factor & AI Confidence: Tự động nới lỏng khi phòng yên tĩnh (bắt vỗ nhẹ xa 3-4m)
         và siết chặt khi phòng ồn (chống báo giả).
    """
    def __init__(self):
        # Giá trị khởi tạo mặc định (môi trường phòng tiêu chuẩn)
        self.noise_floor_rms: float = 0.008
        self.noise_floor_peak: float = 0.015
        self.hf_noise_ratio: float = 0.25
        
        # Trạng thái hiện tại
        self.ambient_status: str = "normal"  # "quiet" | "normal" | "noisy"
        self.dynamic_energy_thresh: float = settings.dsp.energy_threshold
        self.dynamic_crest_thresh: float = settings.dsp.crest_factor_min
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

        # Phân biệt xung đột ngột (Clap Transient) vs Tiếng ồn nền liên tục (Ambient Noise):
        # Tiếng vỗ tay: Dạng xung nhọn (Crest Factor >= 2.8), tăng vọt trong 1-2 chunks ngắn.
        # Tiếng ồn nền (quạt gió, máy lạnh, xe cộ): Dạng sóng đều (Crest Factor < 2.8) hoặc kéo dài liên tục.
        is_impulsive_spike = (
            is_transient or 
            (chunk_crest >= 2.8 and chunk_peak > max(0.040, self.noise_floor_peak * cfg.transient_rejection_ratio))
        )
        
        if is_impulsive_spike:
            self.sustained_frames = 0
        else:
            self.sustained_frames += 1

        # Cập nhật mức ồn nền khi là âm thanh nền ổn định, hoặc âm thanh lớn kéo dài liên tục > 5 chunks
        if not is_impulsive_spike or self.sustained_frames > 5:
            # Giai đoạn khởi động nhanh (10 chunks đầu tiên)
            if self.initialized_samples < 10:
                alpha = 0.35
                self.initialized_samples += 1
            else:
                # Cập nhật bất đối xứng
                if chunk_rms > self.noise_floor_rms:
                    alpha = cfg.adaptation_speed  # Tăng vừa phải khi ồn tăng
                else:
                    alpha = cfg.adaptation_speed * 0.4  # Giảm chậm khi ồn hạ

            self.noise_floor_rms = (1.0 - alpha) * self.noise_floor_rms + alpha * chunk_rms
            self.noise_floor_peak = (1.0 - alpha) * self.noise_floor_peak + alpha * chunk_peak
            self.hf_noise_ratio = (1.0 - alpha) * self.hf_noise_ratio + alpha * chunk_hf

        # Đảm bảo noise floor không bị tràn hoặc quá bé
        self.noise_floor_rms = max(0.001, min(0.20, self.noise_floor_rms))
        self.noise_floor_peak = max(0.003, min(0.30, self.noise_floor_peak))

        # Phân loại trạng thái âm học phòng
        if self.noise_floor_rms < 0.009:
            self.ambient_status = "quiet"     # Phòng rất yên tĩnh
        elif self.noise_floor_rms > 0.032:
            self.ambient_status = "noisy"     # Phòng nhiều tạp âm
        else:
            self.ambient_status = "normal"    # Phòng tiêu chuẩn

        # Tính toán các ngưỡng động
        if cfg.enabled:
            # 1. Dynamic Energy Threshold:
            raw_energy = self.noise_floor_peak * cfg.margin_factor + 0.005
            self.dynamic_energy_thresh = max(
                cfg.min_energy_threshold, 
                min(cfg.max_energy_threshold, raw_energy)
            )

            # 2. Dynamic Crest Factor & AI Confidence:
            if self.ambient_status == "quiet":
                # Nới lỏng nhẹ để bắt tiếng vỗ xa nhưng vẫn giữ độ tin cậy AI cao
                self.dynamic_crest_thresh = max(2.2, settings.dsp.crest_factor_min - 0.3)
                self.dynamic_confidence_thresh = max(0.70, settings.ml.confidence_threshold - 0.05)
            elif self.ambient_status == "noisy":
                # Siết chặt để chống báo giả từ tiếng ồn môi trường
                self.dynamic_crest_thresh = min(3.5, settings.dsp.crest_factor_min + 0.6)
                self.dynamic_confidence_thresh = min(0.85, settings.ml.confidence_threshold + 0.08)
            else:
                self.dynamic_crest_thresh = settings.dsp.crest_factor_min
                self.dynamic_confidence_thresh = settings.ml.confidence_threshold
        else:
            # Khi tắt adaptive, dùng ngưỡng tĩnh trong config
            self.dynamic_energy_thresh = settings.dsp.energy_threshold
            self.dynamic_crest_thresh = settings.dsp.crest_factor_min
            self.dynamic_confidence_thresh = settings.ml.confidence_threshold

        return self.get_state()

    def get_state(self) -> Dict[str, Any]:
        """Trả về toàn bộ trạng thái căn chỉnh ồn nền"""
        return {
            "noise_floor_rms": round(float(self.noise_floor_rms), 4),
            "noise_floor_peak": round(float(self.noise_floor_peak), 4),
            "hf_noise_ratio": round(float(self.hf_noise_ratio), 3),
            "ambient_status": self.ambient_status,
            "dynamic_energy_thresh": round(float(self.dynamic_energy_thresh), 4),
            "dynamic_crest_thresh": round(float(self.dynamic_crest_thresh), 2),
            "dynamic_confidence_thresh": round(float(self.dynamic_confidence_thresh), 2),
            "auto_adaptive_enabled": settings.adaptive_noise.enabled
        }
