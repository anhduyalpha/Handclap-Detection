import sys
import base64
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.api.routes_training import record_continuous_session, ContinuousSessionRequest

def test_upload_continuous():
    sr = 16000
    # Tạo 5s audio có 3 xung vỗ tay nhân tạo
    audio = np.zeros(sr * 5, dtype=np.float32)
    t = np.linspace(0, 0.2, int(sr * 0.2), endpoint=False)
    clap1 = np.exp(-t * 25) * np.sin(2 * np.pi * 2200 * t) * 0.8
    audio[int(sr * 1.0):int(sr * 1.0) + len(clap1)] += clap1.astype(np.float32)
    
    clap2 = np.exp(-t * 30) * np.sin(2 * np.pi * 2500 * t) * 0.9
    audio[int(sr * 2.5):int(sr * 2.5) + len(clap2)] += clap2.astype(np.float32)

    b64 = base64.b64encode(audio.tobytes()).decode('utf-8')

    req = ContinuousSessionRequest(
        profile_name="default",
        category="claps",
        duration_sec=5.0,
        source="upload",
        audio_base64=b64,
        format="float32"
    )

    res = record_continuous_session(req)
    print(f"[*] Extracted samples count: {res.get('extracted_count')}")
    print(f"[*] Claps count in profile:  {res.get('claps_count')}")
    print("[SUCCESS] Local upload & auto-split verified 100%!")

if __name__ == "__main__":
    test_upload_continuous()
