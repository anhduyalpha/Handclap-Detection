import unittest
import threading
import time
import numpy as np
from app.api.ws_audio import ThreadSafeConnectionManager
from app.models.classifier import ClapClassifier
from app.smart_home.action_dispatcher import ActionDispatcher
from app.core.executor import io_executor

class MockWebSocket:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.sent_messages = []

    async def accept(self):
        pass

    async def send_json(self, data: dict):
        if self.should_fail:
            raise RuntimeError("Connection broken")
        self.sent_messages.append(data)

class TestConcurrencyRemediation(unittest.TestCase):
    def test_websocket_manager_thread_safety(self):
        manager = ThreadSafeConnectionManager()
        ws_good = MockWebSocket(should_fail=False)
        ws_bad = MockWebSocket(should_fail=True)

        with manager.lock:
            manager.active_connections.add(ws_good)
            manager.active_connections.add(ws_bad)

        # Broadcast from 10 threads concurrently
        def worker(idx):
            for m in range(20):
                manager.broadcast_json_sync({"thread": idx, "seq": m})

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Ensure active_connections was safely managed and no deadlocks occurred
        with manager.lock:
            self.assertIn(ws_good, manager.active_connections)

    def test_classifier_double_buffered_reload_concurrency(self):
        classifier = ClapClassifier()
        # Mock feature vector & spectrogram
        dummy_mel = np.random.randn(40, 25).astype(np.float32)
        dummy_feat = np.random.randn(54).astype(np.float32)

        stop_event = threading.Event()
        inference_errors = []

        # Thread 1: Continuous Inference loop
        def inference_worker():
            try:
                for _ in range(100):
                    is_clap, conf, details = classifier.predict(
                        mel_spectrogram=dummy_mel,
                        feature_vector=dummy_feat
                    )
                    self.assertIsInstance(is_clap, bool)
                    self.assertIsInstance(conf, float)
                    time.sleep(0.001)
            except Exception as e:
                inference_errors.append(e)

        # Thread 2: Concurrent model reload
        def reload_worker():
            try:
                for _ in range(5):
                    classifier.load_profile_model("default")
                    time.sleep(0.01)
            except Exception as e:
                inference_errors.append(e)

        t1 = threading.Thread(target=inference_worker)
        t2 = threading.Thread(target=reload_worker)

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        self.assertEqual(len(inference_errors), 0, f"Errors during concurrent inference/reload: {inference_errors}")

    def test_action_dispatcher_debounce_lock(self):
        callback_called = []
        dispatcher = ActionDispatcher(broadcast_callback=lambda msg: callback_called.append(msg))

        # Rapid fire 5 patterns
        for _ in range(5):
            dispatcher.dispatch_pattern("double", 2, [])

        # Broadcast callbacks should all fire (5 times)
        self.assertEqual(len(callback_called), 5)
        # But external webhooks are debounced by min_action_interval_sec

if __name__ == "__main__":
    unittest.main()
