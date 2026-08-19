import numpy as np
import threading
from typing import Optional, Tuple

class AudioRingBuffer:
    """
    Bộ đệm vòng (Zero-Copy Circular Ring Buffer) luồng âm thanh thời gian thực.
    Lưu trữ lịch sử âm thanh float32 liên tục (3.0 giây @ 16kHz = 48,000 mẫu).
    Hoạt động 24/7 với bộ nhớ cố định (Zero Memory Allocation trong hot path),
    triệt tiêu hoàn toàn hiện tượng Garbage Collection (GC) pauses.
    """
    def __init__(self, capacity_samples: int = 48000, sample_rate: int = 16000):
        self.capacity = capacity_samples
        self.sample_rate = sample_rate
        # Mảng bộ đệm cố định
        self.buffer = np.zeros(capacity_samples, dtype=np.float32)
        self.write_idx = 0
        self.total_samples_written = 0
        self.lock = threading.Lock()

    def write(self, samples: np.ndarray) -> None:
        """Ghi mảng mẫu âm thanh (float32) vào buffer mà không cấp phát thêm bộ nhớ"""
        n = len(samples)
        if n == 0:
            return

        with self.lock:
            if n >= self.capacity:
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

    def get_recent_into(self, out_array: np.ndarray) -> int:
        """
        Sao chép trực tiếp các mẫu mới nhất vào out_array có sẵn (Zero-Allocation read).
        Trả về số lượng mẫu thực tế đã chép.
        """
        num_samples = min(len(out_array), self.capacity)
        with self.lock:
            if self.write_idx >= num_samples:
                out_array[:num_samples] = self.buffer[self.write_idx - num_samples:self.write_idx]
            else:
                part1_len = num_samples - self.write_idx
                out_array[:part1_len] = self.buffer[self.capacity - part1_len:]
                out_array[part1_len:num_samples] = self.buffer[:self.write_idx]
        return num_samples

    def get_recent(self, num_samples: int) -> np.ndarray:
        """
        Lấy `num_samples` mẫu âm thanh mới nhất.
        """
        num_samples = min(num_samples, self.capacity)
        out = np.empty(num_samples, dtype=np.float32)
        self.get_recent_into(out)
        return out

    def get_window_around_offset(self, offset_from_now_samples: int, pre_samples: int, post_samples: int) -> Optional[np.ndarray]:
        """
        Trích xuất cửa sổ âm thanh quanh một vị trí thời gian đã xảy ra trong quá khứ.
        """
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
