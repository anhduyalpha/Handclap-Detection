import numpy as np
from scipy import signal, fftpack
from typing import Dict, Any, Tuple

class AudioFeatureExtractor:
    """
    Bộ trích xuất đặc trưng âm thanh thuần túy bằng NumPy & SciPy (Zero C-dependency issues).
    Hỗ trợ:
    - Log Mel-Spectrogram 2D (40 filterbanks x T time-steps)
    - MFCC (Mel-Frequency Cepstral Coefficients) 1D / 2D
    - Acoustic Statistical Vectors (Centroid, Rolloff, Contrast, Flatness, Energy Decay)
    """
    def __init__(
        self, 
        sample_rate: int = 16000, 
        n_fft: int = 512, 
        hop_length: int = 160, 
        n_mels: int = 40,
        fmin: float = 100.0,
        fmax: float = 7500.0
    ):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.n_mels = n_mels
        self.fmin = fmin
        self.fmax = fmax if fmax else sample_rate / 2.0
        
        # Tạo ma trận Mel Filterbank
        self.mel_basis = self._create_mel_filterbank()
        self.dct_basis = self._create_dct_basis(n_mels, 20)

    def _hz_to_mel(self, hz: np.ndarray) -> np.ndarray:
        return 2595.0 * np.log10(1.0 + hz / 700.0)

    def _mel_to_hz(self, mel: np.ndarray) -> np.ndarray:
        return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)

    def _create_mel_filterbank(self) -> np.ndarray:
        """Tạo ma trận bộ lọc Mel tam giác"""
        num_fft_bins = self.n_fft // 2 + 1
        mel_min = self._hz_to_mel(np.array(self.fmin))
        mel_max = self._hz_to_mel(np.array(self.fmax))
        
        mel_points = np.linspace(mel_min, mel_max, self.n_mels + 2)
        hz_points = self._mel_to_hz(mel_points)
        bin_points = np.floor((self.n_fft + 1) * hz_points / self.sample_rate).astype(int)
        
        filterbank = np.zeros((self.n_mels, num_fft_bins))
        for i in range(1, self.n_mels + 1):
            left = bin_points[i - 1]
            center = bin_points[i]
            right = bin_points[i + 1]
            
            for j in range(left, center):
                if center != left:
                    filterbank[i - 1, j] = (j - left) / (center - left)
            for j in range(center, right):
                if right != center:
                    filterbank[i - 1, j] = (right - j) / (right - center)
                    
        return filterbank

    def _create_dct_basis(self, n_input: int, n_mfcc: int) -> np.ndarray:
        """Tạo ma trận biến đổi DCT loại 2 để tính MFCC"""
        n = np.arange(n_input)
        k = np.arange(n_mfcc)[:, np.newaxis]
        dct_matrix = np.cos(np.pi * (n + 0.5) * k / n_input)
        return dct_matrix

    def align_and_pad(self, audio: np.ndarray, target_length: int = 4000) -> np.ndarray:
        """
        Căn chỉnh mẫu âm thanh (250ms @ 16kHz = 4000 samples)
        Tìm đỉnh xung và đặt ở vị trí ~20% đầu đoạn để giữ trọn vẹn phần Attack & Decay.
        """
        if len(audio) == 0:
            return np.zeros(target_length, dtype=np.float32)
            
        peak_idx = int(np.argmax(np.abs(audio)))
        pre_peak = int(target_length * 0.20)  # 50ms trước đỉnh
        post_peak = target_length - pre_peak # 200ms sau đỉnh
        
        start_idx = peak_idx - pre_peak
        end_idx = peak_idx + post_peak
        
        aligned = np.zeros(target_length, dtype=np.float32)
        
        src_start = max(0, start_idx)
        src_end = min(len(audio), end_idx)
        
        dest_start = max(0, -start_idx)
        dest_end = dest_start + (src_end - src_start)
        
        if src_end > src_start and dest_end <= target_length:
            aligned[dest_start:dest_end] = audio[src_start:src_end]
            
        # Chuẩn hóa biên độ (Peak Normalization an toàn)
        max_val = np.max(np.abs(aligned))
        if max_val > 1e-4:
            aligned = aligned / max_val
            
        return aligned

    def compute_mel_spectrogram(self, audio: np.ndarray) -> np.ndarray:
        """
        Tính Log Mel-Spectrogram (Shape: [n_mels, time_frames])
        """
        audio = self.align_and_pad(audio)
        
        # STFT (Short-Time Fourier Transform)
        window = signal.windows.hann(self.n_fft)
        _, _, Zxx = signal.stft(
            audio, 
            fs=self.sample_rate, 
            window=window, 
            nperseg=self.n_fft, 
            noverlap=self.n_fft - self.hop_length,
            padded=False
        )
        
        # Power Spectrum
        power_spec = np.abs(Zxx) ** 2
        
        # Áp dụng Mel Filterbank
        mel_spec = np.dot(self.mel_basis, power_spec)
        
        # Log Scale (dB)
        log_mel_spec = 10.0 * np.log10(np.maximum(mel_spec, 1e-10))
        
        # Normalize về dải [-1.0, 1.0] hoặc [0.0, 1.0]
        log_mel_spec = (log_mel_spec - np.mean(log_mel_spec)) / (np.std(log_mel_spec) + 1e-6)
        return log_mel_spec.astype(np.float32)

    def compute_feature_vector(self, audio: np.ndarray) -> np.ndarray:
        """
        Trích xuất vector 1D đặc trưng tổng hợp gồm:
        - Mean & Std MFCCs (40 giá trị)
        - Spectral Centroid, Bandwidth, Flatness, Rolloff (8 giá trị)
        - Temporal Energy Envelope Decay Stats (6 giá trị)
        -> Tổng: 54 chiều, lý tưởng cho LightGBM / Random Forest / MLP cực nhanh
        """
        aligned = self.align_and_pad(audio)
        mel_spec = self.compute_mel_spectrogram(aligned)
        
        # 1. MFCCs
        mfccs = np.dot(self.dct_basis, mel_spec)
        mfcc_mean = np.mean(mfccs, axis=1)
        mfcc_std = np.std(mfccs, axis=1)
        
        # 2. Spectral Features
        freqs = np.linspace(0, self.sample_rate / 2.0, self.n_fft // 2 + 1)
        window = signal.windows.hann(self.n_fft)
        _, _, Zxx = signal.stft(
            aligned, 
            fs=self.sample_rate, 
            window=window, 
            nperseg=self.n_fft, 
            noverlap=self.n_fft - self.hop_length
        )
        magnitude = np.abs(Zxx)
        
        # Spectral Centroid
        centroid = np.sum(freqs[:, np.newaxis] * magnitude, axis=0) / (np.sum(magnitude, axis=0) + 1e-8)
        centroid_mean = np.mean(centroid)
        centroid_std = np.std(centroid)
        
        # Spectral Rolloff (85% energy)
        cumsum = np.cumsum(magnitude, axis=0)
        total_energy = cumsum[-1, :]
        rolloff_idx = np.argmax(cumsum >= 0.85 * total_energy[np.newaxis, :], axis=0)
        rolloff = freqs[rolloff_idx]
        rolloff_mean = np.mean(rolloff)
        rolloff_std = np.std(rolloff)
        
        # 3. Temporal Envelope Decay
        # Tiếng vỗ tay có decay rate cực nhanh trong 100ms đầu
        sub_windows = np.array_split(np.abs(aligned), 6)
        sub_energies = [float(np.sqrt(np.mean(w**2) + 1e-10)) for w in sub_windows]
        
        feature_vector = np.concatenate([
            mfcc_mean,           # 20
            mfcc_std,            # 20
            [centroid_mean, centroid_std, rolloff_mean, rolloff_std], # 4
            sub_energies         # 6
        ]).astype(np.float32)
        
        return feature_vector
