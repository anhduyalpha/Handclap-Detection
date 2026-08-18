import numpy as np
from scipy import signal
from typing import Dict, Any, Tuple

class DSPTransientDetector:
    """
    Stage 1: Bộ phát hiện xung âm thanh năng lượng cao thời gian thực.
    Chạy trên từng chunk nhỏ (32ms - 64ms) với độ trễ < 5ms và tiêu tốn CPU cực thấp.
    
    Phân tích 4 đặc tính vật lý của tiếng vỗ tay:
    1. Fast Rise Time: Biên độ tăng đột ngột trong vài mili-giây.
    2. High Crest Factor (Độ nhọn xung): Peak / RMS cao.
    3. High-Frequency Energy Ratio: Năng lượng dải 1.5kHz - 7kHz chiếm tỷ lệ lớn so với dải trầm.
    4. Short Decay: Âm lượng suy giảm nhanh sau đỉnh.
    """
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.nyquist = sample_rate / 2.0
        
        # Thiết kế bộ lọc dải cao (Highpass Filter > 1500Hz)
        # Giúp lọc bỏ tiếng quạt, tiếng ồn đường phố, tiếng ù bass
        self.b_hp, self.a_hp = signal.butter(
            N=2, 
            Wn=1500.0 / self.nyquist, 
            btype='highpass'
        )
        self.hp_zi = signal.lfilter_zi(self.b_hp, self.a_hp)

    def analyze_chunk(
        self, 
        chunk: np.ndarray, 
        recent_history: np.ndarray,
        energy_thresh: float = 0.045,
        crest_thresh: float = 3.0,
        hf_ratio_thresh: float = 0.32
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Phân tích chunk hiện tại và đoạn âm thanh ngắn liền trước để xác định có xung vỗ tay hay không.
        
        Returns:
            (is_transient_detected, metrics_dict)
        """
        if len(chunk) == 0:
            return False, {}

        # 1. Đo lường biên độ đỉnh và RMS
        peak_amp = float(np.max(np.abs(chunk)))
        rms_amp = float(np.sqrt(np.mean(chunk ** 2) + 1e-10))
        crest_factor = peak_amp / (rms_amp + 1e-8)

        # 2. Tính tỷ lệ năng lượng dải cao (High-Frequency Energy Ratio)
        # So sánh năng lượng sau lọc Highpass với tổng năng lượng
        try:
            hp_filtered, _ = signal.lfilter(self.b_hp, self.a_hp, chunk, zi=self.hp_zi * 0)
            hp_rms = float(np.sqrt(np.mean(hp_filtered ** 2) + 1e-10))
            hf_ratio = hp_rms / (rms_amp + 1e-8)
        except Exception:
            hf_ratio = 0.5

        # 3. Tính Zero-Crossing Rate (ZCR) - Tiếng vỗ tay có ZCR cao do nhiễu dải rộng
        zero_crossings = np.sum(np.diff(chunk > 0) != 0)
        zcr = zero_crossings / (len(chunk) + 1e-8)

        # 4. Kiểm tra sự bùng nổ năng lượng so với nền trước đó (Onset Attack Ratio)
        onset_ratio = 1.0
        if len(recent_history) >= len(chunk) * 2:
            prev_samples = recent_history[:-len(chunk)]
            prev_rms = float(np.sqrt(np.mean(prev_samples ** 2) + 1e-10))
            onset_ratio = rms_amp / (prev_rms + 1e-8)

        # 5. Phân tích 3 Tầng Vật Lý Sóng Âm (3-Tier Acoustic Physics Check):

        # Tier 1: Phân rã năng lượng nhanh (Anti-Sustain Decay Ratio - Lọc tiếng nói, cười, ho, tivi)
        half_len = len(chunk) // 2
        first_half_rms = float(np.sqrt(np.mean(chunk[:half_len] ** 2) + 1e-10))
        second_half_rms = float(np.sqrt(np.mean(chunk[half_len:] ** 2) + 1e-10))
        # Tiếng vỗ tay: năng lượng nửa đầu cao gấp nhiều lần nửa sau (phân rã cực nhanh <40ms)
        decay_ratio = first_half_rms / (second_half_rms + 1e-8)

        # Tier 2: Độ phẳng phổ (Spectral Flatness Measure - Lọc tiếng kim loại, chìa khóa, huýt sáo, còi)
        windowed = chunk * np.hanning(len(chunk))
        power_spec = np.abs(np.fft.rfft(windowed)) ** 2 + 1e-12
        geom_mean = float(np.exp(np.mean(np.log(power_spec))))
        arith_mean = float(np.mean(power_spec))
        spectral_flatness = geom_mean / (arith_mean + 1e-12)

        # Tier 3: Năng lượng âm trầm (Sub-Bass Ratio - Lọc tiếng đóng cửa, gõ bàn, dậm chân)
        freq_bins = len(power_spec)
        cutoff_500hz_idx = max(1, int(freq_bins * 500.0 / self.nyquist))
        sub_bass_energy = float(np.sum(power_spec[:cutoff_500hz_idx]))
        total_spec_energy = float(np.sum(power_spec))
        sub_bass_ratio = sub_bass_energy / (total_spec_energy + 1e-8)

        metrics = {
            "peak_amp": round(peak_amp, 4),
            "rms_amp": round(rms_amp, 4),
            "crest_factor": round(crest_factor, 2),
            "hf_ratio": round(hf_ratio, 3),
            "zcr": round(zcr, 3),
            "onset_ratio": round(onset_ratio, 2),
            "decay_ratio": round(decay_ratio, 2),
            "spectral_flatness": round(spectral_flatness, 3),
            "sub_bass_ratio": round(sub_bass_ratio, 3)
        }

        # Điều kiện kích hoạt Stage 1 (Phải thỏa mãn cả 3 tầng âm học):
        # 1. Đạt ngưỡng năng lượng đỉnh và độ nhọn xung
        basic_transient = (peak_amp >= energy_thresh and crest_factor >= crest_thresh and hf_ratio >= hf_ratio_thresh)
        
        # 2. Tier 1: Không phải âm thanh kéo dài (tiếng nói/hát) -> decay_ratio >= 1.0 hoặc onset_ratio >= 2.0
        not_sustained_voice = (decay_ratio >= 1.05 or onset_ratio >= 2.2)
        
        # 3. Tier 2: Không phải tiếng kim loại đơn âm / huýt sáo (tiếng kim loại có spectral_flatness cực thấp < 0.12)
        not_pure_metal_tone = (spectral_flatness >= 0.13)
        
        # 4. Tier 3: Không bị thống trị bởi tiếng va đập bass trầm (<60% sub-bass)
        not_heavy_bass_thump = (sub_bass_ratio <= 0.65)

        is_candidate = bool(
            basic_transient and 
            not_sustained_voice and 
            not_pure_metal_tone and 
            not_heavy_bass_thump
        )

        return is_candidate, metrics
