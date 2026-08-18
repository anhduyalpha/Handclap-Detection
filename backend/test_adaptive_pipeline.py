import numpy as np
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.noise_estimator import AdaptiveNoiseFloorEstimator
from app.core.live_engine import LiveDetectionEngine
from app.config import settings

def test_adaptive_noise_estimator():
    print("[TEST 1] Testing AdaptiveNoiseFloorEstimator...")
    estimator = AdaptiveNoiseFloorEstimator()

    # 1. Simulate quiet room (RMS ~ 0.005, peak ~ 0.010)
    for _ in range(30):
        estimator.update(
            chunk_rms=0.005,
            chunk_peak=0.010,
            chunk_crest=2.0,
            chunk_hf=0.25,
            is_transient=False
        )
    state = estimator.get_state()
    print(" -> Quiet room state:", state)
    assert state["ambient_status"] == "quiet", f"Expected quiet, got {state['ambient_status']}"
    assert state["dynamic_energy_thresh"] <= 0.025, f"Expected low thresh, got {state['dynamic_energy_thresh']}"

    # 2. Simulate sudden transient clap (peak 0.40, crest 5.0) -> Should NOT blow up noise floor
    prev_noise_floor = state["noise_floor_rms"]
    estimator.update(
        chunk_rms=0.08,
        chunk_peak=0.40,
        chunk_crest=5.0,
        chunk_hf=0.55,
        is_transient=True
    )
    post_clap_state = estimator.get_state()
    print(" -> State after clap pulse:", post_clap_state)
    assert abs(post_clap_state["noise_floor_rms"] - prev_noise_floor) < 0.01, "Clap caused noise floor to spike!"

    # 3. Simulate noisy environment (RMS ~ 0.040, peak ~ 0.075)
    for _ in range(40):
        estimator.update(
            chunk_rms=0.040,
            chunk_peak=0.075,
            chunk_crest=1.875,
            chunk_hf=0.28,
            is_transient=False
        )
    noisy_state = estimator.get_state()
    print(" -> Noisy room state:", noisy_state)
    assert noisy_state["ambient_status"] == "noisy", f"Expected noisy, got {noisy_state['ambient_status']}"
    assert noisy_state["dynamic_energy_thresh"] > 0.04, f"Expected higher threshold, got {noisy_state['dynamic_energy_thresh']}"
    print("[PASS] AdaptiveNoiseFloorEstimator test passed successfully!\n")

def test_live_engine_telemetry():
    print("[TEST 2] Testing LiveDetectionEngine telemetry integration...")
    engine = LiveDetectionEngine()
    
    # Send quiet chunk (512 samples)
    sample_chunk = np.random.normal(0, 0.005, 512).astype(np.float32)
    telemetry = engine.process_chunk(sample_chunk)
    
    print(" -> Process chunk telemetry output:", telemetry)
    assert "noise_floor_rms" in telemetry
    assert "dynamic_energy_thresh" in telemetry
    assert "ambient_status" in telemetry
    assert "auto_adaptive" in telemetry
    print("[PASS] LiveDetectionEngine telemetry test passed successfully!\n")

if __name__ == "__main__":
    test_adaptive_noise_estimator()
    test_live_engine_telemetry()
    print("[SUCCESS] ALL TESTS PASSED SUCCESSFULLY!")
