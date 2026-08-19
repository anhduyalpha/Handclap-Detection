import sys
import time
import os
import subprocess
import numpy as np
from pathlib import Path

# Thêm backend vào sys.path
PROJECT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.server_mic import server_mic
from app.core.live_engine import live_engine
from app.config import settings

def draw_vu_meter(peak: float, rms: float, is_transient: bool, confidence: float, is_clap: bool):
    meter_len = 30
    filled = min(meter_len, int(peak * 100))
    bar = "█" * filled + "░" * (meter_len - filled)
    
    status_str = ""
    if is_clap:
        status_str = f"🎉 [CLAP CONFIRMED! 👏👏 Conf={confidence:.2f}]"
    elif is_transient:
        status_str = f"⚡ [Transient Pulse: Conf={confidence:.2f}]"
    
    sys.stdout.write(f"\r[VU] [{bar}] Peak: {peak:5.3f} | RMS: {rms:5.3f} {status_str:35s}")
    sys.stdout.flush()

def main():
    print("=" * 70)
    print("  🎤 REAL-TIME MICROPHONE & HARDWARE CLAP TESTER")
    print("  🖥️  Operating System:", "Windows" if os.name == "nt" else "Linux/ALSA")
    print("  🔊 Nhìn thanh VU-meter bên dưới: Thử vỗ tay hoặc nói để kiểm tra mic!")
    print("  🛑 Bấm Ctrl+C để dừng kiểm tra.")
    print("=" * 70)

    # Đăng ký callback hiển thị trực tiếp
    def custom_broadcast(data):
        if data.get("type") == "TELEMETRY":
            peak = data.get("peak", 0.0)
            rms = data.get("rms", 0.0)
            is_transient = data.get("is_transient", False)
            conf = data.get("confidence", 0.0)
            is_clap = data.get("clap_detected", False)
            draw_vu_meter(peak, rms, is_transient, conf, is_clap)
        elif data.get("type") == "TRIGGER_EVENT":
            print(f"\n\n{'='*70}\n🎉 [WEBHOOK DISPATCHED] 👏👏 DOUBLE CLAP TRIGGERED! Action executed successfully!\n{'='*70}\n")

    live_engine.set_broadcast_callback(custom_broadcast)
    server_mic.start()

    try:
        while True:
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n\n[*] Đang dừng kiểm tra Micro...")
        server_mic.stop()
        print("[+] Đã kết thúc.")

if __name__ == "__main__":
    main()
