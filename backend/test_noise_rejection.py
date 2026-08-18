import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.live_engine import live_engine

def test_noise_sample():
    print("[*] Testing noise samples against trained model to ensure NO FALSE POSITIVES...")
    typing_files = list(Path("backend/data/user_profiles/default/typing").glob("*.npy"))
    if not typing_files:
        print("[!] No typing noise files found.")
        return

    sample = np.load(typing_files[0])
    print(f"[*] Loaded typing noise sample: {typing_files[0].name}")

    mel = live_engine.feature_extractor.compute_mel_spectrogram(sample)
    feat = live_engine.feature_extractor.compute_feature_vector(sample)
    dsp_m = {"peak_amp": float(np.max(np.abs(sample))), "crest_factor": 2.2, "hf_ratio": 0.25}

    is_clap, conf, details = live_engine.classifier.predict(
        mel_spectrogram=mel,
        feature_vector=feat,
        dsp_metrics=dsp_m,
        confidence_thresh=0.65
    )

    print(f"\n[RESULT] Typing Noise Classification:")
    print(f" - is_clap:           {is_clap} (Expected: False)")
    print(f" - AI Confidence:     {conf:.2%}")
    print(f" - CNN Prob:          {details.get('cnn_prob', 'N/A')}")
    print(f" - Sklearn Prob:      {details.get('sklearn_prob', 'N/A')}")

    assert is_clap == False, "Noise should be rejected by the model!"
    print("\n[SUCCESS] Noise successfully rejected by AI model without triggering webhook!")

if __name__ == "__main__":
    test_noise_sample()
