import io
import time
import uuid
import threading
import numpy as np
from typing import List, Dict, Any, Optional
from scipy.io import wavfile

class TriggerHistoryBuffer:
    """
    Quản lý hàng đợi vòng lưu trữ các sự kiện kích hoạt gần nhất (tối đa 15 sự kiện).
    Mỗi sự kiện lưu kèm mảng âm thanh 500ms xung quanh cú vỗ để người dùng:
    1. Nghe lại âm thanh trực tiếp trên Web.
    2. Đánh dấu 'Báo Giả' (False Positive) để tự động trích xuất mẫu nhiễu và học lại.
    """
    def __init__(self, max_history: int = 15, sample_rate: int = 16000):
        self.max_history = max_history
        self.sample_rate = sample_rate
        self.history: List[Dict[str, Any]] = []
        self.lock = threading.Lock()

    def add_event(
        self,
        pattern: str,
        count: int,
        confidence: float,
        audio_clip: np.ndarray,
        dsp_metrics: Optional[Dict[str, Any]] = None,
        events_meta: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Thêm một sự kiện kích hoạt mới vào đầu danh sách lịch sử.
        """
        now = time.time()
        time_struct = time.localtime(now)
        datetime_str = time.strftime("%H:%M:%S (%d/%m)", time_struct)
        event_id = f"trig_{int(now * 1000)}_{uuid.uuid4().hex[:6]}"

        # Chuẩn hóa audio_clip về mảng float32 1D
        if audio_clip is None or len(audio_clip) == 0:
            audio_data = np.zeros(int(self.sample_rate * 0.5), dtype=np.float32)
        else:
            audio_data = np.asarray(audio_clip, dtype=np.float32)

        record = {
            "id": event_id,
            "timestamp": now,
            "datetime_str": datetime_str,
            "pattern": pattern,
            "count": count,
            "confidence": round(float(confidence), 3),
            "dsp_metrics": dsp_metrics or {},
            "events_meta": events_meta or [],
            "audio_data": audio_data,
            "is_false_positive": False,
            "marked_category": None,
            "has_retrained": False
        }

        with self.lock:
            self.history.insert(0, record)
            # Giới hạn kích thước bộ đệm
            if len(self.history) > self.max_history:
                self.history = self.history[:self.max_history]

        return self._to_public_dict(record)

    def get_recent_events(self) -> List[Dict[str, Any]]:
        """Lấy danh sách các sự kiện kích hoạt gần nhất (không kèm mảng âm thanh thô)"""
        with self.lock:
            return [self._to_public_dict(r) for r in self.history]

    def get_event_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Lấy chi tiết một sự kiện theo ID"""
        with self.lock:
            for r in self.history:
                if r["id"] == event_id:
                    return r
        return None

    def mark_false_positive(self, event_id: str, category: str, has_retrained: bool = False) -> Optional[Dict[str, Any]]:
        """Đánh dấu sự kiện là Báo Giả"""
        with self.lock:
            for r in self.history:
                if r["id"] == event_id:
                    r["is_false_positive"] = True
                    r["marked_category"] = category
                    r["has_retrained"] = has_retrained
                    return self._to_public_dict(r)
        return None

    def clear(self):
        """Xóa toàn bộ lịch sử"""
        with self.lock:
            self.history.clear()

    def get_event_wav_bytes(self, event_id: str) -> Optional[bytes]:
        """Tạo file WAV in-memory từ mảng âm thanh của sự kiện"""
        record = self.get_event_by_id(event_id)
        if not record or "audio_data" not in record:
            return None

        audio_float = record["audio_data"]
        # Chuẩn hóa về int16 để tương thích mọi trình duyệt
        audio_int16 = (np.clip(audio_float, -1.0, 1.0) * 32767).astype(np.int16)

        bio = io.BytesIO()
        wavfile.write(bio, self.sample_rate, audio_int16)
        bio.seek(0)
        return bio.read()

    def _to_public_dict(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Chuyển đổi bản ghi sự kiện sang dict JSON an toàn không chứa mảng numpy lớn"""
        return {
            "id": record["id"],
            "timestamp": record["timestamp"],
            "datetime_str": record["datetime_str"],
            "pattern": record["pattern"],
            "count": record["count"],
            "confidence": record["confidence"],
            "dsp_metrics": record.get("dsp_metrics", {}),
            "is_false_positive": record.get("is_false_positive", False),
            "marked_category": record.get("marked_category"),
            "has_retrained": record.get("has_retrained", False),
            "audio_url": f"/api/events/audio/{record['id']}"
        }

# Global singleton
trigger_history = TriggerHistoryBuffer(max_history=15, sample_rate=16000)
