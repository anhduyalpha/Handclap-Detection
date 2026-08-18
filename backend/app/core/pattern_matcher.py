import time
import threading
from typing import Callable, Optional, Dict, Any, List

class ClapPatternMatcher:
    """
    Bộ nhận diện Nhịp Vỗ Kép Tức Thời (Instant Double-Clap Engine).
    
    Cơ chế hoạt động:
    1. Cú vỗ 1 (Step 1): Mở cổng chờ (Armed State). Phát sự kiện chớp sáng nhẹ trên Web (Nhịp 1/2).
       - Hoàn toàn KHÔNG dùng Timer, KHÔNG sinh sự kiện 1 vỗ (Single Clap), KHÔNG tạo log rác.
       - Tự động hết hạn trong im lặng nếu sau 550ms không có cú vỗ thứ 2.
    2. Cú vỗ 2 (Step 2): Khi có cú vỗ thứ 2 trong khoảng 70ms - 550ms:
       - KÍCH HOẠT TỨC THÌ (Zero Latency = 0ms).
       - Bật/tắt đèn và gửi Webhook Home Assistant ngay tại thời điểm dứt tiếng vỗ thứ 2!
       - Bắt trọn vẹn cả 2 tiếng vỗ trong đoạn ghi âm 800ms.
    3. Bộ lọc chống dội âm (Anti-Echo / Reverb Rejection):
       - Bỏ qua các xung < 70ms (tiếng vọng âm học trong phòng).
       - Đặt Cooldown 400ms sau khi thực hiện hành động để chống dội lệnh.
    """
    def __init__(
        self,
        min_interval_ms: int = 140,
        max_interval_ms: int = 500,
        cooldown_ms: int = 400,
        on_pattern_callback: Optional[Callable[[str, int, List[Dict[str, Any]]], None]] = None
    ):
        self.min_interval_ms = min_interval_ms
        self.max_interval_ms = max_interval_ms
        self.cooldown_ms = cooldown_ms
        self.on_pattern = on_pattern_callback
        
        self.first_clap_time: Optional[float] = None
        self.first_clap_meta: Optional[Dict[str, Any]] = None
        self.last_action_time: float = 0.0
        self.lock = threading.Lock()

    def update_config(self, min_interval_ms: int, max_interval_ms: int, cooldown_ms: int):
        with self.lock:
            self.min_interval_ms = min_interval_ms
            self.max_interval_ms = max_interval_ms
            self.cooldown_ms = cooldown_ms

    def register_clap(self, confidence: float, meta: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Ghi nhận một tiếng vỗ tay vừa được xác thực bởi Stage 2 AI Classifier.
        Returns:
        - "step_1": Ghi nhận cú vỗ thứ nhất (mở cổng chờ nhịp 2)
        - "double": Kích hoạt tức thì 2 tiếng vỗ tay liên tiếp
        - None: Bị chặn bởi Cooldown hoặc Anti-echo
        """
        now = time.time()
        clap_meta = meta or {"confidence": confidence, "timestamp": now}
        
        with self.lock:
            # 1. Kiểm tra Cooldown sau khi vừa thực thi hành động
            if (now - self.last_action_time) * 1000.0 < self.cooldown_ms:
                return None

            # 2. Nếu chưa có cú vỗ 1 hoặc cú vỗ 1 đã hết hạn (> max_interval)
            if self.first_clap_time is None or (now - self.first_clap_time) * 1000.0 > self.max_interval_ms:
                self.first_clap_time = now
                self.first_clap_meta = clap_meta
                return None

            # 3. Đã có cú vỗ 1 hợp lệ trong cửa sổ -> Kiểm tra cú vỗ 2
            delta_ms = (now - self.first_clap_time) * 1000.0

            # Quá nhanh (< min_interval): Tiếng dội âm phòng / echo, bỏ qua
            if delta_ms < self.min_interval_ms:
                print(f"[InstantPatternMatcher] [Anti-Echo] Dropped pulse too close ({delta_ms:.1f}ms < {self.min_interval_ms}ms)")
                return None

            # Khoảng cách chuẩn (70ms - 550ms): KÍCH HOẠT DOUBLE CLAP NGAY TỨC THÌ!
            if self.min_interval_ms <= delta_ms <= self.max_interval_ms:
                print(f"\n{'='*55}\n🎉 [InstantPatternMatcher] 👏👏 DOUBLE CLAP CONFIRMED! Delta = {delta_ms:.1f}ms (Zero Delay Trigger)\n{'='*55}")
                self.last_action_time = now
                events = [self.first_clap_meta, clap_meta]
                
                # Reset trạng thái
                self.first_clap_time = None
                self.first_clap_meta = None

                if self.on_pattern:
                    try:
                        self.on_pattern("double", 2, events)
                    except Exception as e:
                        print(f"[InstantPatternMatcher] Callback error: {e}")

                return "double"

            return None
