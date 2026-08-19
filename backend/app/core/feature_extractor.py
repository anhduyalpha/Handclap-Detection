import numpy as np
from scipy import signal
from typing import Tuple, Dict, Any, Optional

class AudioFeatureExtractor:
    """
    Trích xuất đặc trưng âm thanh tốc độ cao cho mô hình học máy (Stage 2).
    - Log Mel-Spectrogram 2D (40 mels x 25 time steps) cho PyTorch CNN
    - 54-dimensional Feature Vector (MFCCs, Spectral Centroid, Rolloff, Temporal Decay) cho Scikit-Learn
    """
    def __init__(
        self,
        sample_rate: int = 16000,
        n_mels: int = 40,
        n_fft: int = 512,
        hop_length: int = 160,
        clip_duration_sec: float = 0.25,
        n_mfcc: int = 20
    ):
        self.sample_rate = sample_rate
        self.n_mels = n_mels
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.clip_duration_sec = clip_duration_sec
        self.target_samples = int(sample_rate * clip_duration_sec)  # 4000 samples @ 16kHz
        self.n_mfcc = n_mfcc
        
        # Tiền tính toán Mel Filterbank Matrix để tăng tốc tối đa
        self.mel_basis = self._create_mel_filterbank(
            sr=sample_rate, 
            n_fft=n_fft, 
            n_mels=n_mels, 
            fmin=200.0, 
            fmax=sample_rate / 2.0
        )
        
        # Tiền tính toán DCT matrix cho MFCCs
        self.dct_basis = self._create_dct_matrix(n_mfcc=self.n_mfcc, n_mels=self.n_mels)

    def _hz_to_mel(self, hz: float) -> float:
        return 2595.0 * np.log10(1.0 + hz / 700.0)

    def _mel_to_hz(self, mel: float) -> float:
        return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)

    def _create_mel_filterbank(self, sr: int, n_fft: int, n_mels: int, fmin: float, fmax: float) -> np.ndarray:
        """Tạo ma trận Mel filterbank chuẩn hoá không cần cài librosa"""
        min_mel = self._hz_to_mel(fmin)
        max_mel = self._hz_to_mel(fmax)
        mel_points = np.linspace(min_mel, max_mel, n_mels + 2)
        hz_points = self._mel_to_hz(mel_points)
        bin_points = np.floor((n_fft + 1) * hz_points / sr).astype(int)

        num_fft_bins = n_fft // 2 + 1
        filterbank = np.zeros((n_mels, num_fft_bins), dtype=np.float32)

        for i in range(1, n_mels + 1):
            left = bin_points[i - 1]
            center = bin_points[i]
            right = bin_points[i + 1]

            for j in range(left, center):
                if center > left and j < num_fft_bins:
                    filterbank[i - 1, j] = (j - left) / (center - left)
            for j in range(center, right):
                if right > center and j < num_fft_bins:
                    filterbank[i - 1, j] = (right - j) / (right - center)

        # Slaney-style area normalization
        enorm = 2.0 / (hz_points[2:n_mels + 2] - hz_points[:n_mels])
        filterbank *= enorm[:, np.newaxis]
        return filterbank

    def _create_dct_matrix(self, n_mfcc: int, n_mels: int) -> np.ndarray:
        """Tạo ma trận Discrete Cosine Transform (DCT Type-II)"""
        basis = np.empty((n_mfcc, n_mels), dtype=np.float32)
        basis[0, :] = 1.0 / np.sqrt(n_mels)
        samples = np.arange(1, 2 * n_mels, 2) * np.pi / (2.0 * n_mels)
        for i in range(1, n_mfcc):
            basis[i, :] = np.cos(i * samples) * np.sqrt(2.0 / n_mels)
        return basis

    def align_and_pad(self, audio: np.ndarray) -> np.ndarray:
        """
        Căn chỉnh đỉnh âm thanh (Transient Peak) vào vị trí 15% (khoảng 35ms-40ms đầu),
        pad hoặc cắt vừa đúng target_samples (250ms = 4000 samples).
        """
        target_length = self.target_samples
        if len(audio) == 0:
            return np.zeros(target_length, dtype=np.float32)

        # Tìm vị trí đỉnh năng lượng cao nhất
        peak_idx = int(np.argmax(np.abs(audio)))
        
        # Đặt đỉnh tại vị trí 15% của cửa sổ
        target_peak_pos = int(target_length * 0.15)
        start_idx = peak_idx - target_peak_pos
        end_idx = start_idx + target_length

        aligned = np.zeros(target_length, dtype=np.float32)
        
        src_start = max(0, start_idx)
        src_end = min(len(audio), end_idx)
        
        dest_start = max(0, -start_idx)
        dest_end = dest_start + (src_end - src_start)
        
        if src_end > src_start and dest_end <= target_length:
            aligned[dest_start:dest_end] = audio[src_start:src_end]
            
        # Chuẩn hóa biên độ (Peak Normalization an toàn)
        max_val = float(np.max(np.abs(aligned))) if len(aligned) > 0 else 0.0
        if max_val > 1e-4:
            aligned = aligned / max_val
            
        return aligned

    def compute_mel_spectrogram(self, audio: np.ndarray) -> np.ndarray:
        """
        Tính Log Mel-Spectrogram (Shape: [n_mels, time_frames]) với bảo vệ chống NaN/Inf.
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
        
        # Normalize về dải chuẩn hoá
        std_val = float(np.std(log_mel_spec))
        mean_val = float(np.mean(log_mel_spec))
        if std_val < 1e-5:
            log_mel_spec = log_mel_spec - mean_val
        else:
            log_mel_spec = (log_mel_spec - mean_val) / (std_val + 1e-6)

        log_mel_spec = np.nan_to_num(log_mel_spec, nan=0.0, posinf=1.0, neginf=-1.0)
        return log_mel_spec.astype(np.float32)

    def compute_feature_vector(self, audio: np.ndarray) -> np.ndarray:
        """
        Trích xuất vector 1D đặc trưng tổng hợp gồm:
        - Mean & Std MFCCs (40 giá trị)
        - Spectral Centroid, Bandwidth, Flatness, Rolloff (8 giá trị)
        - Temporal Energy Envelope Decay Stats (6 giá trị)
        -> Tổng: 54 chiều, bảo vệ chống NaN/Inf.
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
        centroid_mean = float(np.mean(centroid))
        centroid_std = float(np.std(centroid))
        
        # Spectral Rolloff (85% energy)
        cumsum = np.cumsum(magnitude, axis=0)
        total_energy = cumsum[-1, :]
        rolloff_idx = np.argmax(cumsum >= 0.85 * total_energy[np.newaxis, :], axis=0)
        rolloff = freqs[rolloff_idx]
        rolloff_mean = float(np.mean(rolloff))
        rolloff_std = float(np.std(rolloff))
        
        # 3. Temporal Envelope Decay
        sub_windows = np.array_split(np.abs(aligned), 6)
        sub_energies = [float(np.sqrt(np.mean(w**2) + 1e-10)) for w in sub_windows]
        
        feature_vector = np.concatenate([
            mfcc_mean,           # 20
            mfcc_std,            # 20
            [centroid_mean, centroid_std, rolloff_mean, rolloff_std],  # 4
            sub_energies         # 6
        ]).astype(np.float32)
        
        feature_vector = np.nan_to_num(feature_vector, nan=0.0, posinf=1.0, neginf=-1.0)
        return feature_vector
