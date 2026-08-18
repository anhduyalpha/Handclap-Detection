import sys
import time
from pathlib import Path

# Thêm backend vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from app.core.live_engine import live_engine
from app.config import settings

def test_full_clap_detection_pipeline():
    sr = settings.audio.sample_rate
    print(f"[*] Testing full live engine pipeline (Sample rate: {sr}Hz)...")
    
    # 1. Tạo 2s âm thanh yên tĩnh để bộ ước lượng noise floor ổn định
    quiet_chunk = np.random.normal(0, 0.003, 512).astype(np.float32)
    for _ in range(30):
        live_engine.process_chunk(quiet_chunk)

    print(f"[*] Noise floor stabilized: RMS={live_engine.noise_estimator.noise_floor_rms:.4f}, EnergyThresh={live_engine.noise_estimator.dynamic_energy_thresh:.4f}")

    # 2. Phát một cú vỗ tay sắc nét (transient clap)
    t = np.linspace(0, 0.05, 512)
    clap_chunk = (0.85 * np.exp(-t * 120) * np.sin(2 * np.pi * 2200 * t)).astype(np.float32)
    
    telemetry = live_engine.process_chunk(clap_chunk)
    print(f"[*] Processed clap chunk: Peak={telemetry['peak']:.3f}, Stage 1 Transient={telemetry['is_transient']}")

    # 3. Tiếp tục stream các chunk yên tĩnh để PatternMatcher chờ hết timer và kích hoạt Single Clap
    for _ in range(25):
        time.sleep(0.03)
        live_engine.process_chunk(quiet_chunk)

    # Đợi thêm 0.8s để đảm bảo Timer của PatternMatcher kích hoạt ActionDispatcher
    time.sleep(0.8)
    print("[PASS] Full detection pipeline executed successfully!")

if __name__ == "__main__":
    test_full_clap_detection_pipeline()
