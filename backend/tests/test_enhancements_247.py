import unittest
import numpy as np
import time
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.core.noise_estimator import AdaptiveNoiseFloorEstimator
from app.core.dsp_detector import DSPTransientDetector
from app.core.hard_negative_miner import HardNegativeMiner
from app.core.audio_stream import AudioRingBuffer
from app.core.telemetry import SystemTelemetryTracker
from app.training.trainer import PersonalModelTrainer
from app.config import USER_PROFILES_DIR

class TestEnhancements247(unittest.TestCase):
    def test_noise_estimator_percentiles_and_adaptation(self):
        estimator = AdaptiveNoiseFloorEstimator(history_len=30)
        
        # 1. Feed 30 chunks of normal/high noise (rms=0.030, peak=0.060)
        for _ in range(30):
            estimator.update(
                chunk_rms=0.030,
                chunk_peak=0.060,
                chunk_crest=2.0,
                chunk_hf=0.25,
                is_transient=False
            )
        
        state_high = estimator.get_state()
        self.assertIn(state_high["ambient_status"], ["noisy", "very_noisy", "normal"])
        self.assertGreater(state_high["p90_rms"], 0.0)

        # 2. Feed 80 chunks of quiet noise (rms=0.002, peak=0.005)
        for _ in range(80):
            estimator.update(
                chunk_rms=0.002,
                chunk_peak=0.005,
                chunk_crest=2.0,
                chunk_hf=0.20,
                is_transient=False
            )
        
        state_quiet = estimator.get_state()
        self.assertEqual(state_quiet["ambient_status"], "quiet")
        self.assertLess(state_quiet["dynamic_energy_thresh"], state_high["dynamic_energy_thresh"])

    def test_dsp_detector_rise_decay_validator(self):
        detector = DSPTransientDetector(sample_rate=16000)
        recent_history = np.zeros(1600, dtype=np.float32)

        # 1. Realistic handclap: High frequency resonance + noise + fast exponential envelope
        t = np.linspace(0, 0.032, 512, endpoint=False)
        np.random.seed(42)
        noise = np.random.normal(0, 0.75, 512)
        res = np.sin(2 * np.pi * 3400 * t)
        env = np.exp(-t * 90.0) # fast 11ms decay
        clap_chunk = (0.75 * noise + 0.25 * res) * env
        clap_chunk = (clap_chunk / np.max(np.abs(clap_chunk)) * 0.75).astype(np.float32)

        is_cand, metrics = detector.analyze_chunk(
            chunk=clap_chunk,
            recent_history=recent_history,
            energy_thresh=0.03,
            crest_thresh=2.4,
            hf_ratio_thresh=0.25
        )
        self.assertTrue(is_cand)
        self.assertLessEqual(metrics["rise_time_ms"], 8.0)
        self.assertGreaterEqual(metrics["decay_ratio"], 1.05)

        # 2. Slow rising low-frequency voice/typing hum (300Hz sinusoidal)
        voice_chunk = (np.sin(2 * np.pi * 300 * t) * 0.5).astype(np.float32)
        is_cand_v, metrics_v = detector.analyze_chunk(
            chunk=voice_chunk,
            recent_history=recent_history,
            energy_thresh=0.03,
            crest_thresh=2.4,
            hf_ratio_thresh=0.25
        )
        self.assertFalse(is_cand_v)

    def test_audio_ring_buffer_zero_allocation(self):
        buf = AudioRingBuffer(capacity_samples=48000, sample_rate=16000)
        
        # Write chunks
        chunk1 = np.random.uniform(-0.5, 0.5, 512).astype(np.float32)
        chunk2 = np.random.uniform(-0.5, 0.5, 512).astype(np.float32)
        buf.write(chunk1)
        buf.write(chunk2)

        out_arr = np.empty(1024, dtype=np.float32)
        copied = buf.get_recent_into(out_arr)
        self.assertEqual(copied, 1024)

        recent_copy = buf.get_recent(1024)
        np.testing.assert_array_almost_equal(out_arr, recent_copy)

    def test_hard_negative_miner_bounded_buffer(self):
        test_prof = "test_hn_miner_profile"
        miner = HardNegativeMiner(max_samples=5, sample_rate=16000)
        miner.min_mine_interval = 0.0
        
        hn_dir = miner.get_hard_negatives_dir(test_prof)
        try:
            dummy_audio = np.random.uniform(-0.2, 0.2, 4000).astype(np.float32)
            # Write 8 samples with distinct timestamps
            for i in range(8):
                time.sleep(0.01)
                miner._save_and_prune(test_prof, dummy_audio, confidence=0.55, source="test")

            # Check that on-disk files are strictly bounded to max_samples (5)
            files = list(hn_dir.glob("*.npy"))
            self.assertLessEqual(len(files), 5)
        finally:
            p_dir = USER_PROFILES_DIR / test_prof
            if p_dir.exists():
                shutil.rmtree(p_dir, ignore_errors=True)

    def test_system_telemetry_tracker(self):
        tracker = SystemTelemetryTracker()
        tracker.record_chunk(0.4)
        tracker.record_chunk(0.6)
        tracker.record_stage2_inference(ml_duration_ms=1.8, is_clap=False, confidence=0.52)
        tracker.record_stage2_inference(ml_duration_ms=2.2, is_clap=True, confidence=0.88)
        tracker.record_trigger_event()
        tracker.record_mined_negative()

        metrics = tracker.get_metrics()
        self.assertEqual(metrics["total_chunks_processed"], 2)
        self.assertEqual(metrics["total_transients_detected"], 2)
        self.assertEqual(metrics["total_claps_confirmed"], 1)
        self.assertEqual(metrics["total_mined_hard_negatives"], 1)
        self.assertEqual(metrics["triggers_last_1h"], 1)
        self.assertEqual(metrics["ml_noise_rejection_rate_pct"], 50.0)
        self.assertGreater(metrics["avg_dsp_latency_ms"], 0.0)

if __name__ == "__main__":
    unittest.main()
