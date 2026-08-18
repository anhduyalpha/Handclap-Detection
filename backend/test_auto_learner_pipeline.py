import sys
import base64
import numpy as np
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.training.auto_learner import auto_learner
from app.api.routes_training import upload_checkpoint, CheckpointUploadRequest
from app.core.noise_estimator import AdaptiveNoiseFloorEstimator
from app.config import CHECKPOINTS_DIR

def test_pipeline():
    print("[*] 1. Testing AdaptiveNoiseFloorEstimator dynamic calibration & SNR...")
    estimator = AdaptiveNoiseFloorEstimator()
    state = estimator.update(chunk_rms=0.005, chunk_peak=0.010, chunk_crest=2.0, chunk_hf=0.20)
    print(f"    [+] Ambient Status: {state['ambient_status']} ({state['ambient_label']})")
    print(f"    [+] Calculated SNR: {state['snr_db']} dB")
    print(f"    [+] Dynamic Energy Thresh: {state['dynamic_energy_thresh']}")
    assert state["ambient_status"] == "quiet"
    assert "🌙" in state["ambient_label"]

    print("\n[*] 2. Testing AutoLearner Batch Debounce Logic...")
    auto_learner.pending_fps = 0
    auto_learner.pending_claps = 0
    auto_learner.notify_new_sample("default", "false_positives")
    auto_learner.notify_new_sample("default", "false_positives")
    status = auto_learner.get_status()
    print(f"    [+] Pending False Positives: {status['pending_false_positives']}")
    assert status["pending_false_positives"] == 2
    auto_learner._cancel_timer()

    print("\n[*] 3. Testing Checkpoint Upload & Hot-Reload...")
    dummy_cnn_bytes = b"dummy_cnn_weights_binary"
    dummy_b64 = base64.b64encode(dummy_cnn_bytes).decode("ascii")

    req = CheckpointUploadRequest(
        profile_name="test_profile",
        files={"test_model.pt": dummy_b64},
        metrics={"accuracy": 99.5, "sensitivity": 98.0}
    )
    res = upload_checkpoint(req)
    print(f"    [+] Upload Checkpoint Response: {res['status']} - {res['message']}")
    assert res["status"] == "success"

    saved_file = CHECKPOINTS_DIR / "test_profile" / "test_model.pt"
    assert saved_file.exists()
    assert saved_file.read_bytes() == dummy_cnn_bytes
    # Cleanup test checkpoint
    import shutil
    shutil.rmtree(CHECKPOINTS_DIR / "test_profile", ignore_errors=True)

    print("\n[SUCCESS] All Auto-Learner & Adaptive Calibration tests passed 100%!")

if __name__ == "__main__":
    test_pipeline()
