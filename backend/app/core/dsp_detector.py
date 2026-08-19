import logging
import numpy as np
from scipy import signal
from typing import Dict, Any, Tuple

logger = logging.getLogger("handclap.dsp")

class DSPTransientDetector:
    """
    Stage 1: Bộ phát hiện xung âm thanh năng lượng cao & Transient Trigger thời gian thực.
    Thiết kế High-Recall Ultra-Responsive: Bắt trọn vẹn mọi tiếng vỗ tay dù nhẹ hay xa (3-5m) và chuyển cho Stage 2 ML phân loại chính xác.
    """
    def __init__(self, sample_rate: int = 16000, chunk_size: int = 512):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.nyquist = sample_rate / 2.0
        
        # Thiết kế bộ lọc dải cao (Highpass Filter > 1000Hz)
        self.b_hp, self.a_hp = signal.butter(
            N=2, 
            Wn=1000.0 / self.nyquist, 
            btype='highpass'
        )
        self.hp_zi = signal.lfilter_zi(self.b_hp, self.a_hp)
        
        # Tiền tính toán cửa sổ Hanning
        self.hanning_window = np.hanning(chunk_size).astype(np.float32)

    def analyze_chunk(
        self, 
        chunk: np.ndarray, 
        recent_history: np.ndarray,
        energy_thresh: float = 0.010,
        crest_thresh: float = 1.5,
        hf_ratio_thresh: float = 0.12
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Phân tích chunk hiện tại để xác định có xung âm thanh đột biến hay không.
        
        Returns:
            (is_transient_detected, metrics_dict)
        """
        if len(chunk) == 0:
            return False, {}

        # 1. Đo lường biên độ đỉnh và RMS
        abs_chunk = np.abs(chunk)
        peak_amp = float(np.max(abs_chunk)) if len(chunk) > 0 else 0.0
        rms_amp = float(np.sqrt(np.mean(chunk ** 2) + 1e-10))
        crest_factor = float(np.clip(peak_amp / (rms_amp + 1e-8), 1.0, 50.0))

        # 2. Tính tỷ lệ năng lượng dải cao (High-Frequency Energy Ratio)
        try:
            hp_filtered, _ = signal.lfilter(self.b_hp, self.a_hp, chunk, zi=self.hp_zi * 0)
            hp_rms = float(np.sqrt(np.mean(hp_filtered ** 2) + 1e-10))
            hf_ratio = float(np.clip(hp_rms / (rms_amp + 1e-8), 0.0, 1.0))
        except Exception as e:
            logger.debug(f"Highpass filter fallback: {e}")
            hf_ratio = 0.5

        # 3. Tính Zero-Crossing Rate (ZCR)
        zero_crossings = np.sum(np.diff(chunk > 0) != 0)
        zcr = float(np.clip(zero_crossings / (len(chunk) + 1e-8), 0.0, 1.0))

        # 4. Kiểm tra Onset Attack Ratio so với nền trước đó
        onset_ratio = 1.0
        if len(recent_history) >= len(chunk) * 2:
            prev_samples = recent_history[:-len(chunk)]
            prev_rms = float(np.sqrt(np.mean(prev_samples ** 2) + 1e-10))
            onset_ratio = float(np.clip(rms_amp / (prev_rms + 1e-8), 0.0, 100.0))

        # 5. Phân tích Rise-Time và Decay-Ratio
        peak_idx = int(np.argmax(abs_chunk))
        ten_pct = 0.10 * peak_amp
        t10_idx = 0
        for i in range(peak_idx, -1, -1):
            if abs_chunk[i] <= ten_pct:
                t10_idx = i
                break
        rise_samples = max(1, peak_idx - t10_idx)
        rise_time_ms = float(rise_samples * 1000.0 / self.sample_rate)

        half_len = len(chunk) // 2
        first_half_rms = float(np.sqrt(np.mean(chunk[:half_len] ** 2) + 1e-10))
        second_half_rms = float(np.sqrt(np.mean(chunk[half_len:] ** 2) + 1e-10))
        decay_ratio = float(np.clip(first_half_rms / (second_half_rms + 1e-8), 0.0, 100.0))

        # 6. Spectral Flatness
        win = self.hanning_window if len(chunk) == len(self.hanning_window) else np.hanning(len(chunk))
        windowed = chunk * win
        power_spec = np.abs(np.fft.rfft(windowed)) ** 2
        power_spec = np.maximum(power_spec, 1e-12)
        log_power = np.log(power_spec)
        geom_mean = float(np.exp(np.mean(log_power)))
        arith_mean = float(np.mean(power_spec))
        spectral_flatness = float(np.clip(geom_mean / (arith_mean + 1e-12), 0.0, 1.0))
        if np.isnan(spectral_flatness) or np.isinf(spectral_flatness):
            spectral_flatness = 0.5

        metrics = {
            "peak_amp": round(peak_amp, 4),
            "rms_amp": round(rms_amp, 4),
            "crest_factor": round(crest_factor, 2),
            "hf_ratio": round(hf_ratio, 3),
            "zcr": round(zcr, 3),
            "onset_ratio": round(onset_ratio, 2),
            "rise_time_ms": round(rise_time_ms, 2),
            "decay_ratio": round(decay_ratio, 2),
            "spectral_flatness": round(spectral_flatness, 3)
        }

        # 7. Điều kiện Stage 1 Transient Trigger:
        # Nếu biên độ đỉnh vượt ngưỡng năng lượng VÀ (có độ nhọn xung HOẶC bùng nổ onset HOẶC biên độ rõ rệt)
        is_candidate = bool(
            (peak_amp >= energy_thresh) and 
            (crest_factor >= crest_thresh or onset_ratio >= 1.2 or peak_amp >= 0.020)
        )

        return is_candidate, metrics
