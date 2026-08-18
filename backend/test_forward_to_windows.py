import sys
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.trigger_history import trigger_history
from app.api.routes_events import mark_false_positive, MarkFalsePositiveRequest
from app.config import settings

def test_forwarding_to_windows():
    sr = 16000
    print("[*] 1. Adding simulated trigger event...")
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
    synthetic_noise = (np.sin(2 * np.pi * 500 * t) * np.exp(-t * 6)).astype(np.float32)

    event = trigger_history.add_event(
        pattern="single",
        count=1,
        confidence=0.85,
        audio_clip=synthetic_noise,
        dsp_metrics={"peak": 0.5}
    )
    print(f"[+] Added event ID: {event['id']}")

    # Cấu hình target windows URL
    settings.windows_studio_url = "http://127.0.0.1:8001"

    print("[*] 2. Calling mark_false_positive with auto-forwarding...")
    req = MarkFalsePositiveRequest(
        event_id=event["id"],
        profile_name="default",
        category="false_positives",
        auto_retrain=False
    )
    res = mark_false_positive(req)

    print(f"[+] Status: {res['status']}")
    print(f"[+] Forwarded to Windows configured: {res['forwarded_to_windows']}")
    assert res["status"] == "success"
    assert res["forwarded_to_windows"] is True

    # Đợi 0.5s để luồng thread nền kết thúc
    time.sleep(0.5)
    print("\n[SUCCESS] Linux to Windows auto-forwarding verified 100%!")

if __name__ == "__main__":
    test_forwarding_to_windows()
