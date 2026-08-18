import sys
from pathlib import Path

# Thêm backend vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from app.training.segmenter import AudioSegmenter
from app.api.routes_training import record_continuous_session, ContinuousSessionRequest
from app.config import settings

def test_audio_segmenter_claps():
    """Kiểm tra thuật toán phát hiện và tự động cắt cú vỗ tay"""
    sr = 16000
    duration_sec = 5.0
    total_samples = int(sr * duration_sec)
    audio = np.zeros(total_samples, dtype=np.float32)
    
    # Giả lập 4 cú vỗ tay tại các giây: 1.0s, 2.0s, 3.0s, 4.0s
    for t_sec in [1.0, 2.0, 3.0, 4.0]:
        idx = int(t_sec * sr)
        # Tạo xung sắc nhọn (transient pulse)
        pulse_len = 800
        t = np.linspace(0, 0.05, pulse_len)
        pulse = 0.8 * np.exp(-t * 120) * np.sin(2 * np.pi * 2200 * t)
        audio[idx : idx + pulse_len] += pulse.astype(np.float32)

    segmenter = AudioSegmenter(sample_rate=sr)
    clips = segmenter.segment_claps(audio, clip_duration_sec=0.25)
    
    print(f"[*] Detected and segmented {len(clips)} claps from audio.")
    assert len(clips) == 4, f"Expected 4 claps, found {len(clips)}"
    for c in clips:
        assert len(c) == int(sr * 0.25)
    print("[PASS] AudioSegmenter.segment_claps passed!")

def test_audio_segmenter_noise():
    """Kiểm tra thuật toán băm nhỏ tiếng ồn nền dài thành các clip 250ms"""
    sr = 16000
    duration_sec = 3.0
    total_samples = int(sr * duration_sec)
    # Tiếng ồn Gaussian
    audio = np.random.normal(0, 0.02, total_samples).astype(np.float32)

    segmenter = AudioSegmenter(sample_rate=sr)
    clips = segmenter.segment_noise(audio, clip_duration_sec=0.25)
    
    expected_clips = int(duration_sec / 0.25)
    print(f"[*] Sliced noise into {len(clips)} clips (expected: {expected_clips}).")
    assert len(clips) == expected_clips
    for c in clips:
        assert len(c) == int(sr * 0.25)
    print("[PASS] AudioSegmenter.segment_noise passed!")

def test_continuous_session_endpoint():
    """Kiểm tra endpoint record_continuous_session với audio upload"""
    sr = 16000
    audio = np.zeros(sr * 3, dtype=np.float32)
    # Thêm 2 cú vỗ
    for t_sec in [0.8, 1.8]:
        idx = int(t_sec * sr)
        pulse_len = 800
        t = np.linspace(0, 0.05, pulse_len)
        audio[idx : idx + pulse_len] = 0.8 * np.exp(-t * 120) * np.sin(2 * np.pi * 2200 * t)

    import base64
    b64 = base64.b64encode(audio.tobytes()).decode('ascii')

    req = ContinuousSessionRequest(
        profile_name="default",
        category="claps",
        duration_sec=3.0,
        source="upload",
        audio_base64=b64,
        format="float32"
    )

    res = record_continuous_session(req)
    assert res["status"] == "success"
    assert res["extracted_count"] == 2
    print(f"[PASS] record_continuous_session endpoint passed! Extracted: {res['extracted_count']}")

if __name__ == "__main__":
    test_audio_segmenter_claps()
    test_audio_segmenter_noise()
    test_continuous_session_endpoint()
    print("\n[SUCCESS] ALL AUDIO SEGMENTER & CONTINUOUS SESSION TESTS PASSED!")
