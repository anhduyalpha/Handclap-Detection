import numpy as np
import threading
from typing import Optional, Tuple

class AudioRingBuffer:
    """
    Bộ đệm vòng (Ring Buffer) luồng âm thanh thời gian thực.
    Lưu trữ lịch sử âm thanh float32 liên tục (ví dụ 1.5 - 2.0 giây)
    để khi phát hiện xung (transient), có thể trích xuất chính xác
    cửa sổ âm thanh [trước xung 50ms, sau xung 200ms].
    """
    def __init__(self, capacity_samples: int = 24000, sample_rate: int = 16000):
        self.capacity = capacity_samples
        self.sample_rate = sample_rate
        self.buffer = np.zeros(capacity_samples, dtype=np.float32)
        self.write_idx = 0
        self.total_samples_written = 0
        self.lock = threading.Lock()

    def write(self, samples: np.ndarray) -> None:
        """Ghi mảng mẫu âm thanh (float32, range [-1.0, 1.0]) vào buffer"""
        if len(samples) == 0:
            return

        with self.lock:
            n = len(samples)
            if n >= self.capacity:
                # Nếu mảng mới dài hơn cả buffer, chỉ lấy phần đuôi
                self.buffer[:] = samples[-self.capacity:]
                self.write_idx = 0
            else:
                end_idx = self.write_idx + n
                if end_idx <= self.capacity:
                    self.buffer[self.write_idx:end_idx] = samples
                else:
                    first_part = self.capacity - self.write_idx
                    self.buffer[self.write_idx:] = samples[:first_part]
                    self.buffer[:n - first_part] = samples[first_part:]
                self.write_idx = end_idx % self.capacity
            self.total_samples_written += n

    def get_recent(self, num_samples: int) -> np.ndarray:
        """Lấy `num_samples` mẫu âm thanh mới nhất"""
        with self.lock:
            num_samples = min(num_samples, self.capacity)
            if self.write_idx >= num_samples:
                return self.buffer[self.write_idx - num_samples:self.write_idx].copy()
            else:
                part2 = self.buffer[:self.write_idx]
                part1 = self.buffer[self.capacity - (num_samples - self.write_idx):]
                return np.concatenate((part1, part2))

    def get_window_around_offset(self, offset_from_now_samples: int, pre_samples: int, post_samples: int) -> Optional[np.ndarray]:
        """
        Trích xuất cửa sổ âm thanh quanh một vị trí thời gian đã xảy ra trong quá khứ.
        `offset_from_now_samples`: số mẫu cách thời điểm hiện tại về trước (offset > 0).
        """
        with self.lock:
            total_needed = pre_samples + post_samples
            if total_needed > self.capacity:
                return None
            
            recent = self.get_recent(self.capacity)
            center_idx = len(recent) - offset_from_now_samples
            start_idx = center_idx - pre_samples
            end_idx = center_idx + post_samples

            if start_idx < 0 or end_idx > len(recent):
                return None
            return recent[start_idx:end_idx].copy()

    def clear(self) -> None:
        with self.lock:
            self.buffer.fill(0)
            self.write_idx = 0
            self.total_samples_written = 0
