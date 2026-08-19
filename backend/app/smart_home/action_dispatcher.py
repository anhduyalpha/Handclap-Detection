import time
import logging
import requests
import threading
from typing import Dict, Any, Callable, Optional, List
from .virtual_bulb import virtual_bulb
from ..config import settings
from ..core.executor import io_executor

logger = logging.getLogger("handclap.action_dispatcher")

class ActionDispatcher:
    """
    Bộ điều phối hành động (Action Dispatcher).
    Khi phát hiện pattern (1 vỗ, 2 vỗ, 3 vỗ):
    - Cập nhật trạng thái bóng đèn ảo (Virtual Bulb)
    - Kích hoạt Webhook ra thiết bị IoT bên ngoài qua Bounded ThreadPoolExecutor
    - Gửi sự kiện phản hồi đến WebSocket clients
    - Tích hợp Debounce Lock chống gửi trùng lặp (tránh bật rồi tắt liền)
    """
    def __init__(self, broadcast_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.broadcast_callback = broadcast_callback
        self.last_webhook_time = 0.0
        self.debounce_lock = threading.Lock()
        self.min_action_interval_sec = 0.85  # Tối thiểu 850ms giữa 2 lần gửi webhook

    def set_broadcast_callback(self, callback: Callable[[Dict[str, Any]], None]):
        self.broadcast_callback = callback

    def dispatch_pattern(self, pattern: str, count: int, events_meta: List[Dict[str, Any]]):
        """Thực thi hành động tương ứng với 2 tiếng vỗ tay (Double Clap)"""
        action_name = ""
        bulb_state = None

        if pattern == "double":
            action_name = settings.light.double_clap_action
            if action_name == "toggle_power":
                bulb_state = virtual_bulb.toggle_power(source="clap_double")
            elif action_name == "next_color":
                bulb_state = virtual_bulb.next_color(source="clap_double")
            elif action_name == "party_mode":
                bulb_state = virtual_bulb.party_mode(source="clap_double")
            else:
                action_name = "toggle_power"
                bulb_state = virtual_bulb.toggle_power(source="clap_double")
        else:
            action_name = "none"

        if bulb_state is None:
            bulb_state = virtual_bulb.get_state()

        event_payload = {
            "type": "ACTION_TRIGGERED",
            "pattern": pattern,
            "count": count,
            "action": action_name,
            "timestamp": time.time(),
            "bulb_state": bulb_state,
            "events_meta": events_meta
        }

        # 1. Gửi WebSocket về UI
        if self.broadcast_callback:
            try:
                self.broadcast_callback(event_payload)
            except Exception as e:
                logger.warning(f"Broadcast callback error: {e}")

        # 2. Gửi Webhook không đồng bộ ra ngoài (Home Assistant / ESP32) qua Bounded ThreadPool
        if settings.light.webhook_url and action_name not in ("none", "", None):
            io_executor.submit(
                self._send_external_webhook,
                settings.light.webhook_url,
                event_payload
            )
        elif action_name in ("none", "", None):
            logger.debug(f"Pattern '{pattern}' ({count} clap(s)) mapped to 'none' -> Skipped webhook.")

    def _send_external_webhook(self, url: str, payload: Dict[str, Any]):
        pattern = payload.get("pattern", "double")
        count = payload.get("count", 2)
        action_name = payload.get("action", "")

        if not action_name or action_name == "none":
            return

        # Chống dội / chống gửi lặp lệnh webhook (Debounce Lock)
        with self.debounce_lock:
            now = time.time()
            if now - self.last_webhook_time < self.min_action_interval_sec:
                logger.info(f"Debounce skipped duplicate webhook call ({now - self.last_webhook_time:.2f}s < {self.min_action_interval_sec}s)")
                return
            self.last_webhook_time = now

        try:
            logger.info(f"[{count} Clap(s) ({pattern})] Sending POST Webhook to: {url}")
            res = requests.post(url, json=payload, timeout=2.5)
            logger.info(f"[{count} Clap(s)] Webhook response: HTTP {res.status_code} ({url})")
        except Exception as e:
            logger.error(f"[{count} Clap(s)] Webhook failed ({url}): {e}")

action_dispatcher = ActionDispatcher()
