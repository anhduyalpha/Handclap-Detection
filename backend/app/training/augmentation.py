import logging
import numpy as np
from scipy import signal
from typing import List, Tuple

logger = logging.getLogger("handclap.augmentation")

class AudioAugmentor:
    """
    Bộ tăng cường dữ liệu âm thanh nâng cao (Data Augmentation Pro).
    Tạo ra các biến thể phong phú:
    1. Dynamic Amplitude Scaling (0.18x đến 1.6x): Giúp model nhận diện được cả tiếng vỗ siêu nhẹ lẫn cực mạnh.
    2. Time Shifting (-30ms đến +30ms).
    3. Room Noise Mixing: Trộn các tạp âm thực tế mà người dùng đã thu.
    4. Frequency Tilt / EQ Filtering: Mô phỏng các loại micro và góc thu khác nhau.
    5. Gaussian & Pink Noise Injection.
    """
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

    def time_shift(self, audio: np.ndarray, max_shift_samples: int = 480) -> np.ndarray:
        """Dịch chuyển thời gian ngẫu nhiên (-30ms đến +30ms)"""
        shift = np.random.randint(-max_shift_samples, max_shift_samples)
        return np.roll(audio, shift)

    def scale_amplitude(self, audio: np.ndarray, scale_range: Tuple[float, float] = (0.18, 1.6)) -> np.ndarray:
        """Thay đổi biên độ âm lượng rộng để model nhận diện được cả tiếng vỗ từ xa / cực nhẹ"""
        scale = np.random.uniform(scale_range[0], scale_range[1])
        scaled = audio * scale
        return np.clip(scaled, -1.0, 1.0).astype(np.float32)

    def add_noise(self, audio: np.ndarray, snr_db_range: Tuple[float, float] = (12, 35)) -> np.ndarray:
        """Thêm nhiễu trắng ngẫu nhiên với SNR thực tế"""
        snr_db = np.random.uniform(snr_db_range[0], snr_db_range[1])
        signal_power = np.mean(audio ** 2) + 1e-10
        noise_power = signal_power / (10 ** (snr_db / 10.0))
        noise = np.random.normal(0, np.sqrt(noise_power), len(audio))
        return (audio + noise).astype(np.float32)

    def frequency_tilt(self, audio: np.ndarray) -> np.ndarray:
        """Mô phỏng đáp ứng tần số micro khác nhau (EQ tilt)"""
        if len(audio) < 16:
            return audio
        try:
            tilt_type = np.random.choice(["hp", "lp", "none"])
            if tilt_type == "hp":
                b, a = signal.butter(1, 400.0 / (self.sample_rate / 2.0), btype='highpass')
                filtered = signal.lfilter(b, a, audio)
                return (0.7 * audio + 0.3 * filtered).astype(np.float32)
            elif tilt_type == "lp":
                b, a = signal.butter(1, 5500.0 / (self.sample_rate / 2.0), btype='lowpass')
                filtered = signal.lfilter(b, a, audio)
                return (0.7 * audio + 0.3 * filtered).astype(np.float32)
        except Exception as e:
            logger.debug(f"frequency_tilt calculation note: {e}")
        return audio

    def mix_background(self, audio: np.ndarray, bg_noise: np.ndarray, mix_ratio: float = 0.2) -> np.ndarray:
        """Trộn tiếng vỗ tay vào tiếng ồn phòng thực tế"""
        if len(bg_noise) == 0:
            return audio
            
        if len(bg_noise) < len(audio):
            repeats = int(np.ceil(len(audio) / len(bg_noise)))
            bg_noise = np.tile(bg_noise, repeats)
            
        start = np.random.randint(0, len(bg_noise) - len(audio) + 1)
        bg_slice = bg_noise[start:start + len(audio)]
        
        mixed = (1.0 - mix_ratio) * audio + mix_ratio * bg_slice
        return np.clip(mixed, -1.0, 1.0).astype(np.float32)

    def augment_sample(
        self, 
        audio: np.ndarray, 
        bg_noises: List[np.ndarray] = None, 
        count: int = 15
    ) -> List[np.ndarray]:
        """Tạo ra `count` phiên bản biến thể chất lượng cao từ 1 mẫu âm thanh gốc"""
        augmented = [audio.copy()]
        for _ in range(count - 1):
            aug = audio.copy()
            aug = self.time_shift(aug)
            aug = self.scale_amplitude(aug)
            aug = self.frequency_tilt(aug)
            aug = self.add_noise(aug)
            if bg_noises and len(bg_noises) > 0:
                bg = bg_noises[np.random.randint(0, len(bg_noises))]
                aug = self.mix_background(aug, bg, mix_ratio=np.random.uniform(0.05, 0.30))
            augmented.append(aug)
        return augmented
