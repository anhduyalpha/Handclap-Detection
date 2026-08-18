import numpy as np
from scipy.signal import butter, sosfilt
from typing import List, Tuple, Optional

class AudioSegmenter:
    """
    Module xử lý & tự động phân tách âm thanh thông minh (Audio Transient Auto-Segmenter).
    1. Tự động phát hiện và cắt từng cú vỗ tay (250ms) trong một đoạn thu âm dài (10-30s).
    2. Tự động băm nhỏ các đoạn tiếng ồn nền dài thành các clip mẫu 250ms chuẩn hóa.
    """
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        # Bộ lọc thông dải 800Hz - 6500Hz để làm nổi bật tiếng vỗ tay
        self.sos = butter(4, [800, 6500], btype='bandpass', fs=sample_rate, output='sos')

    def segment_claps(
        self, 
        audio: np.ndarray, 
        clip_duration_sec: float = 0.25,
        energy_thresh: float = 0.030,
        crest_thresh: float = 2.4,
        min_gap_sec: float = 0.18
    ) -> List[np.ndarray]:
        """
        Quét qua đoạn âm thanh dài và tự động cắt chính xác từng cú vỗ tay.
        
        Returns:
            Danh sách các mảng 1D float32 (mỗi đoạn đúng clip_duration_sec, vd: 250ms ~ 4000 samples)
        """
        if len(audio) < int(self.sample_rate * 0.1):
            return []

        clip_samples = int(self.sample_rate * clip_duration_sec)
        pre_onset_samples = int(self.sample_rate * 0.05) # 50ms trước đỉnh
        min_gap_samples = int(self.sample_rate * min_gap_sec)

        # 1. Lọc thông dải
        filtered = sosfilt(self.sos, audio)

        # 2. Tính toán năng lượng tức thời (Frame 10ms ~ 160 samples, Hop 5ms ~ 80 samples)
        frame_size = int(self.sample_rate * 0.010)
        hop_size = int(self.sample_rate * 0.005)
        num_frames = (len(filtered) - frame_size) // hop_size

        if num_frames <= 0:
            return []

        energies = []
        crest_factors = []
        frame_indices = []

        for i in range(num_frames):
            start = i * hop_size
            end = start + frame_size
            frame = filtered[start:end]
            
            rms = np.sqrt(np.mean(frame ** 2) + 1e-10)
            peak = np.max(np.abs(frame))
            crest = peak / (rms + 1e-10)
            
            energies.append(peak)
            crest_factors.append(crest)
            frame_indices.append(start + frame_size // 2)

        energies = np.array(energies)
        crest_factors = np.array(crest_factors)

        # 3. Tìm các đỉnh Onset thỏa mãn điều kiện xung tiếng vỗ tay
        detected_peak_indices = []
        last_peak_idx = -min_gap_samples

        for i in range(1, len(energies) - 1):
            sample_idx = frame_indices[i]
            # Là đỉnh cực đại cục bộ
            is_local_max = energies[i] > energies[i - 1] and energies[i] >= energies[i + 1]
            
            if is_local_max:
                if energies[i] >= energy_thresh and crest_factors[i] >= crest_thresh:
                    # Kiểm tra khoảng cách với cú vỗ trước đó
                    if sample_idx - last_peak_idx >= min_gap_samples:
                        # Tìm mẫu có biên độ cực đại tuyệt đối quanh vùng đỉnh (+-10ms)
                        search_start = max(0, sample_idx - frame_size)
                        search_end = min(len(audio), sample_idx + frame_size)
                        exact_peak = search_start + np.argmax(np.abs(audio[search_start:search_end]))
                        
                        detected_peak_indices.append(exact_peak)
                        last_peak_idx = exact_peak

        # 4. Trích xuất các cửa sổ 250ms quanh từng đỉnh
        extracted_clips = []
        for peak_idx in detected_peak_indices:
            start_pos = peak_idx - pre_onset_samples
            end_pos = start_pos + clip_samples

            clip = np.zeros(clip_samples, dtype=np.float32)
            
            # Xử lý an toàn các vị trí biên
            src_start = max(0, start_pos)
            src_end = min(len(audio), end_pos)
            dst_start = max(0, -start_pos)
            dst_end = dst_start + (src_end - src_start)

            clip[dst_start:dst_end] = audio[src_start:src_end]
            
            # Đảm bảo mẫu có âm lượng hợp lệ (không phải khoảng lặng)
            if np.max(np.abs(clip)) > 0.015:
                extracted_clips.append(clip)

        return extracted_clips

    def segment_noise(
        self, 
        audio: np.ndarray, 
        clip_duration_sec: float = 0.25,
        step_sec: float = 0.25
    ) -> List[np.ndarray]:
        """
        Băm nhỏ một đoạn tiếng ồn phòng/tạp âm dài thành các clip mẫu 250ms chuẩn hóa.
        
        Returns:
            Danh sách các mảng 1D float32 (mỗi đoạn đúng clip_duration_sec)
        """
        clip_samples = int(self.sample_rate * clip_duration_sec)
        step_samples = int(self.sample_rate * step_sec)

        if len(audio) < clip_samples:
            return []

        extracted_clips = []
        idx = 0
        while idx + clip_samples <= len(audio):
            clip = audio[idx : idx + clip_samples].astype(np.float32)
            
            # Loại trừ khoảng lặng hoàn toàn (RMS < 0.0005)
            rms = np.sqrt(np.mean(clip ** 2) + 1e-10)
            if rms >= 0.0005:
                extracted_clips.append(clip)
            
            idx += step_samples

        return extracted_clips

segmenter = AudioSegmenter()
