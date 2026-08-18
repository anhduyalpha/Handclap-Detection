import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.trigger_history import trigger_history
from app.api.routes_events import get_recent_triggers, get_event_audio, mark_false_positive, MarkFalsePositiveRequest
from app.training.dataset_manager import DatasetManager

def test_trigger_history_and_mining():
    sr = 16000
    print("[*] 1. Creating synthetic trigger event...")
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
    synthetic_noise = (np.sin(2 * np.pi * 350 * t) * np.exp(-t * 8)).astype(np.float32)

    event_record = trigger_history.add_event(
        pattern="single",
        count=1,
        confidence=0.82,
        audio_clip=synthetic_noise,
        dsp_metrics={"peak": 0.45, "crest": 3.2, "sfm": 0.18}
    )
    event_id = event_record["id"]
    print(f"[+] Added Event ID: {event_id}, time={event_record['datetime_str']}")

    # 2. Test get_recent_triggers
    res_triggers = get_recent_triggers()
    print(f"[+] Total triggers in history: {res_triggers['total']}")
    assert res_triggers["total"] >= 1
    assert any(e["id"] == event_id for e in res_triggers["events"])

    # 3. Test get_event_audio
    res_audio = get_event_audio(event_id)
    wav_bytes = res_audio.body
    print(f"[+] Generated WAV bytes size: {len(wav_bytes)} bytes")
    assert len(wav_bytes) > 1000
    assert wav_bytes[:4] == b"RIFF"

    # 4. Test mark_false_positive
    print("[*] 4. Marking event as False Positive (Category: speech)...")
    req = MarkFalsePositiveRequest(
        event_id=event_id,
        profile_name="default",
        category="speech",
        auto_retrain=False
    )
    res_mining = mark_false_positive(req)
    print(f"[+] Mining Status: {res_mining['status']}")
    assert res_mining["status"] == "success"
    assert res_mining["event"]["is_false_positive"] is True
    assert res_mining["event"]["marked_category"] == "speech"

    # Verify sample exists in dataset manager
    dm = DatasetManager(sample_rate=sr)
    samples = dm.list_samples_detailed("default", category="speech")
    assert len(samples) > 0
    print(f"[+] Samples count in 'speech' category: {len(samples)}")

    print("\n[SUCCESS] Active False Positive Feedback & Mining verified 100%!")

if __name__ == "__main__":
    test_trigger_history_and_mining()
