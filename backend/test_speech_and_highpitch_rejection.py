import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.dsp_detector import DSPTransientDetector
from app.core.live_engine import live_engine

def test_all_false_positive_categories():
    print("="*60)
    print("[*] TESTING FALSE POSITIVE REJECTION ACROSS ALL CATEGORIES")
    print("="*60)

    dsp = DSPTransientDetector(sample_rate=16000)
    sr = 16000
    duration = 0.25 # 250ms
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    # 1. Test Speech / Laughter / High-pitch Voice Formants
    f0 = 350.0
    voice_audio = (
        np.sin(2 * np.pi * f0 * t) + 
        0.6 * np.sin(2 * np.pi * 2*f0 * t) + 
        0.4 * np.sin(2 * np.pi * 3*f0 * t)
    )
    voice_audio = voice_audio / (np.max(np.abs(voice_audio)) + 1e-6)
    
    is_transient_v, metrics_v = dsp.analyze_chunk(
        chunk=voice_audio[:512],
        recent_history=voice_audio,
        energy_thresh=0.025,
        crest_thresh=2.4,
        hf_ratio_thresh=0.25
    )
    print(f"\n1. Speech / High-pitch Voice Formants:")
    print(f" - Stage 1 DSP Transient: {is_transient_v} (Expected: False due to decay ratio)")
    print(f" - Metrics: Crest={metrics_v.get('crest_factor')}, DecayRatio={metrics_v.get('decay_ratio')}, Flatness={metrics_v.get('spectral_flatness')}")

    mel_v = live_engine.feature_extractor.compute_mel_spectrogram(voice_audio)
    feat_v = live_engine.feature_extractor.compute_feature_vector(voice_audio)
    is_clap_v, conf_v, _ = live_engine.classifier.predict(mel_v, feat_v, metrics_v, confidence_thresh=0.75)
    print(f" - Stage 2 AI Confidence:  {conf_v:.2%} -> is_clap={is_clap_v} (Expected: False)")
    assert is_clap_v == False, "Speech should NOT trigger!"

    # 2. Test Metallic Clinking / Key Jingles / Whistling
    metal_audio = np.sin(2 * np.pi * 4200 * t) + 0.5 * np.sin(2 * np.pi * 6100 * t)
    metal_audio = metal_audio / (np.max(np.abs(metal_audio)) + 1e-6)
    
    is_transient_m, metrics_m = dsp.analyze_chunk(
        chunk=metal_audio[:512],
        recent_history=metal_audio,
        energy_thresh=0.025,
        crest_thresh=2.4,
        hf_ratio_thresh=0.25
    )
    print(f"\n2. Metallic Resonances / Key Jingles / Whistling:")
    print(f" - Stage 1 DSP Transient: {is_transient_m} (Expected: False due to low Spectral Flatness)")
    print(f" - Metrics: Flatness={metrics_m.get('spectral_flatness')} (<0.13 is rejected)")
    
    mel_m = live_engine.feature_extractor.compute_mel_spectrogram(metal_audio)
    feat_m = live_engine.feature_extractor.compute_feature_vector(metal_audio)
    is_clap_m, conf_m, _ = live_engine.classifier.predict(mel_m, feat_m, metrics_m, confidence_thresh=0.75)
    print(f" - Stage 2 AI Confidence:  {conf_m:.2%} -> is_clap={is_clap_m} (Expected: False)")
    assert is_clap_m == False, "Metal clinking should NOT trigger!"

    # 3. Test Door Slams / Table Thumps / Footsteps
    thump_audio = (np.sin(2 * np.pi * 90 * t) + 0.4 * np.sin(2 * np.pi * 180 * t)) * np.exp(-t * 20)
    thump_audio = thump_audio / (np.max(np.abs(thump_audio)) + 1e-6)
    
    is_transient_t, metrics_t = dsp.analyze_chunk(
        chunk=thump_audio[:512],
        recent_history=thump_audio,
        energy_thresh=0.025,
        crest_thresh=2.4,
        hf_ratio_thresh=0.25
    )
    print(f"\n3. Door Slam / Heavy Thump (Sub-Bass Impact):")
    print(f" - Stage 1 DSP Transient: {is_transient_t} (Expected: False due to Sub-Bass dominance)")
    print(f" - Metrics: SubBassRatio={metrics_t.get('sub_bass_ratio')} (>0.65 is rejected)")

    mel_t = live_engine.feature_extractor.compute_mel_spectrogram(thump_audio)
    feat_t = live_engine.feature_extractor.compute_feature_vector(thump_audio)
    is_clap_t, conf_t, _ = live_engine.classifier.predict(mel_t, feat_t, metrics_t, confidence_thresh=0.75)
    print(f" - Stage 2 AI Confidence:  {conf_t:.2%} -> is_clap={is_clap_t} (Expected: False)")
    assert is_clap_t == False, "Door slam should NOT trigger!"

    print("\n" + "="*60)
    print("[SUCCESS] ALL 3 NOISE CATEGORIES 100% REJECTED BY DSP & AI MODEL!")
    print("="*60)

if __name__ == "__main__":
    test_all_false_positive_categories()
