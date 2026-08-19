import unittest
import numpy as np
from unittest.mock import patch, MagicMock
from app.core.network import post_with_retry
from app.core.feature_extractor import AudioFeatureExtractor
from app.core.dsp_detector import DSPTransientDetector
from app.training.segmenter import AudioSegmenter

class TestResilienceRemediation(unittest.TestCase):
    def test_post_with_retry_success_first_try(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            result = post_with_retry("http://localhost:8000/api/test", {"data": 123}, max_retries=3)
            self.assertTrue(result)
            self.assertEqual(mock_post.call_count, 1)

    def test_post_with_retry_recover_after_failure(self):
        with patch("requests.post") as mock_post:
            # 1st attempt fails with 500, 2nd attempt succeeds with 200
            mock_fail = MagicMock()
            mock_fail.status_code = 500
            mock_ok = MagicMock()
            mock_ok.status_code = 200
            mock_post.side_effect = [mock_fail, mock_ok]

            result = post_with_retry(
                "http://localhost:8000/api/test", 
                {"data": 123}, 
                max_retries=3, 
                base_delay=0.01
            )
            self.assertTrue(result)
            self.assertEqual(mock_post.call_count, 2)

    def test_post_with_retry_exhaustion(self):
        with patch("requests.post") as mock_post:
            mock_fail = MagicMock()
            mock_fail.status_code = 503
            mock_post.return_value = mock_fail

            result = post_with_retry(
                "http://localhost:8000/api/test", 
                {"data": 123}, 
                max_retries=2, 
                base_delay=0.01
            )
            self.assertFalse(result)
            self.assertEqual(mock_post.call_count, 2)

    def test_feature_extractor_nan_safety(self):
        extractor = AudioFeatureExtractor(sample_rate=16000)
        
        # Test 1: Complete silence
        silent_audio = np.zeros(4000, dtype=np.float32)
        mel = extractor.compute_mel_spectrogram(silent_audio)
        feat = extractor.compute_feature_vector(silent_audio)

        self.assertFalse(np.isnan(mel).any())
        self.assertFalse(np.isinf(mel).any())
        self.assertFalse(np.isnan(feat).any())
        self.assertFalse(np.isinf(feat).any())
        self.assertEqual(feat.shape, (50,))

        # Test 2: Extreme noise
        extreme_audio = np.random.uniform(-10.0, 10.0, 4000).astype(np.float32)
        mel_ext = extractor.compute_mel_spectrogram(extreme_audio)
        feat_ext = extractor.compute_feature_vector(extreme_audio)

        self.assertFalse(np.isnan(mel_ext).any())
        self.assertFalse(np.isinf(mel_ext).any())
        self.assertFalse(np.isnan(feat_ext).any())
        self.assertFalse(np.isinf(feat_ext).any())

    def test_dsp_detector_nan_safety(self):
        detector = DSPTransientDetector(sample_rate=16000)
        
        # Test on silence
        silent_chunk = np.zeros(512, dtype=np.float32)
        history = np.zeros(1024, dtype=np.float32)
        is_cand, metrics = detector.analyze_chunk(silent_chunk, history)

        self.assertFalse(is_cand)
        self.assertFalse(np.isnan(metrics["spectral_flatness"]))
        self.assertFalse(np.isnan(metrics["crest_factor"]))
        self.assertFalse(np.isnan(metrics["hf_ratio"]))

        # Test on impulse
        impulse_chunk = np.zeros(512, dtype=np.float32)
        impulse_chunk[50] = 0.8
        is_cand_impulse, metrics_impulse = detector.analyze_chunk(impulse_chunk, history)
        self.assertIsInstance(is_cand_impulse, bool)
        self.assertFalse(np.isnan(metrics_impulse["decay_ratio"]))

    def test_segmenter_robustness(self):
        segmenter = AudioSegmenter(sample_rate=16000)
        
        # Test on short/empty
        empty_audio = np.array([], dtype=np.float32)
        self.assertEqual(segmenter.segment_claps(empty_audio), [])
        self.assertEqual(segmenter.segment_noise(empty_audio), [])

        # Test on synthetic audio with multiple peaks
        audio = np.zeros(16000 * 2, dtype=np.float32)  # 2 seconds
        audio[8000:8100] = np.random.uniform(0.5, 0.9, 100) # Peak 1
        audio[18000:18100] = np.random.uniform(0.5, 0.9, 100) # Peak 2

        clips = segmenter.segment_claps(audio, energy_thresh=0.02)
        self.assertIsInstance(clips, list)
        for c in clips:
            self.assertEqual(len(c), 4000)
            self.assertFalse(np.isnan(c).any())

if __name__ == "__main__":
    unittest.main()
