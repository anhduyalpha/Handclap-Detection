import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.live_engine import live_engine
from app.config import settings

def test_real_clap():
    print("[*] Testing real recorded clap sample against trained model...")
    real_clap_files = list(Path("backend/data/user_profiles/default/claps").glob("*.npy"))
    if not real_clap_files:
        print("[!] No recorded clap file found.")
        return

    sample = np.load(real_clap_files[0])
    print(f"[*] Loaded sample: {real_clap_files[0].name}, shape: {sample.shape}")

    # Chạy qua classifier
    mel = live_engine.feature_extractor.compute_mel_spectrogram(sample)
    feat = live_engine.feature_extractor.compute_feature_vector(sample)
    dsp_m = {"peak_amp": float(np.max(np.abs(sample))), "crest_factor": 4.5, "hf_ratio": 0.40}

    is_clap, conf, details = live_engine.classifier.predict(
        mel_spectrogram=mel,
        feature_vector=feat,
        dsp_metrics=dsp_m,
        confidence_thresh=0.65
    )

    print(f"\n[RESULT] Real Hand Clap Classification:")
    print(f" - is_clap:           {is_clap}")
    print(f" - AI Confidence:     {conf:.2%}")
    print(f" - CNN Prob:          {details.get('cnn_prob', 'N/A')}")
    print(f" - Sklearn Prob:      {details.get('sklearn_prob', 'N/A')}")
    print(f" - Threshold:         {details.get('threshold_used', 'N/A')}")

    assert is_clap == True, "Real clap should be detected!"
    print("\n[SUCCESS] Real clap verified with high confidence!")

if __name__ == "__main__":
    test_real_clap()
