import time
import threading
from typing import Callable, Optional, Dict, Any, List

class ClapPatternMatcher:
    """
    Bộ nhận diện chuỗi vỗ tay (Clap Pattern Engine).
    Phân biệt chính xác:
    - 1 Clap (Single): Vỗ 1 lần -> Đợi hết cửa sổ (vd 450ms) nếu không có vỗ tiếp theo thì phát sinh sự kiện SINGLE_CLAP.
    - 2 Claps (Double): Vỗ 2 lần liên tiếp trong khoảng 90ms - 420ms.
    - 3 Claps (Triple): Vỗ 3 lần liên tiếp trong khoảng 90ms - 420ms.
    """
    def __init__(
        self,
        min_interval_ms: int = 90,
        max_interval_ms: int = 420,
        cooldown_ms: int = 450,
        on_pattern_callback: Optional[Callable[[str, int, List[Dict[str, Any]]], None]] = None
    ):
        self.min_interval_ms = min_interval_ms
        self.max_interval_ms = max_interval_ms
        self.cooldown_ms = cooldown_ms
        self.on_pattern = on_pattern_callback
        
        self.clap_timestamps: List[float] = []
        self.clap_events_meta: List[Dict[str, Any]] = []
        self.last_action_time: float = 0.0
        self.timer: Optional[threading.Timer] = None
        self.lock = threading.Lock()

    def update_config(self, min_interval_ms: int, max_interval_ms: int, cooldown_ms: int):
        with self.lock:
            self.min_interval_ms = min_interval_ms
            self.max_interval_ms = max_interval_ms
            self.cooldown_ms = cooldown_ms

    def register_clap(self, confidence: float, meta: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Ghi nhận một tiếng vỗ tay vừa được xác thực bởi Stage 2 Classifier.
        Returns tên pattern nếu kích hoạt tức thời (vd triple clap), hoặc None nếu đang chờ cửa sổ.
        """
        now = time.time()
        
        with self.lock:
            # Kiểm tra Cooldown sau khi vừa thực hiện hành động
            if (now - self.last_action_time) * 1000.0 < self.cooldown_ms:
                return None
                
            # Nếu đã có tiếng vỗ trước đó trong hàng đợi
            if self.clap_timestamps:
                delta_ms = (now - self.clap_timestamps[-1]) * 1000.0
                
                # Quá nhanh (< min_interval): có thể là tiếng vang (echo/reverb), bỏ qua
                if delta_ms < self.min_interval_ms:
                    return None
                    
                # Quá lâu (> max_interval): chuỗi cũ đã hết hạn, bắt đầu chuỗi mới
                if delta_ms > self.max_interval_ms:
                    self._cancel_timer()
                    self.clap_timestamps.clear()
                    self.clap_events_meta.clear()

            # Thêm timestamp và metadata
            self.clap_timestamps.append(now)
            self.clap_events_meta.append(meta or {"confidence": confidence, "time": now})
            
            count = len(self.clap_timestamps)
            
            # Nếu đã đạt 3 tiếng vỗ -> Kích hoạt ngay Triple Clap không cần chờ timer
            if count >= 3:
                self._cancel_timer()
                pattern = "triple"
                self._dispatch_pattern(pattern, count)
                return pattern
            else:
                # Nếu là tiếng vỗ thứ 1 hoặc 2: đặt Timer chờ xem có tiếng vỗ tiếp theo không
                self._cancel_timer()
                wait_seconds = (self.max_interval_ms + 50) / 1000.0
                self.timer = threading.Timer(wait_seconds, self._on_timeout)
                self.timer.daemon = True
                self.timer.start()
                return None

    def _cancel_timer(self):
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None

    def _on_timeout(self):
        """Hết thời gian chờ, xác định pattern dựa trên số lượng tiếng vỗ đã ghi nhận"""
        with self.lock:
            count = len(self.clap_timestamps)
            if count == 1:
                pattern = "single"
            elif count == 2:
                pattern = "double"
            elif count >= 3:
                pattern = "triple"
            else:
                pattern = "none"
                
            if count > 0:
                self._dispatch_pattern(pattern, count)

    def _dispatch_pattern(self, pattern: str, count: int):
        self.last_action_time = time.time()
        events = list(self.clap_events_meta)
        self.clap_timestamps.clear()
        self.clap_events_meta.clear()
        
        if self.on_pattern and pattern != "none":
            try:
                self.on_pattern(pattern, count, events)
            except Exception as e:
                print(f"[PatternMatcher] Error in callback: {e}")
