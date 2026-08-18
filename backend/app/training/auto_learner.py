import io
import os
import json
import time
import base64
import threading
import urllib.request
from pathlib import Path
from typing import Dict, Any, Optional

from .trainer import PersonalModelTrainer
from ..config import CHECKPOINTS_DIR, settings

class AutoRetrainManager:
    """
    Quản lý Tự động Học & Tự động Huấn luyện (Continuous Active Learning Pipeline).
    
    Cơ chế:
    1. Lắng nghe các mẫu âm thanh mới được nạp vào máy tính Windows (Claps hoặc False Positives).
    2. Gom nhóm thông minh (Debounce Batching):
       - Tự động kích hoạt GPU huấn luyện khi tích lũy đủ 3 mẫu Báo Giả hoặc 10 mẫu Vỗ Thật mới.
       - HOẶC tự động kích hoạt sau 15 giây kể từ mẫu âm thanh cuối cùng nếu không có thêm mẫu mới.
    3. Tự động đóng gói và chuyển giao mô hình (Checkpoints) sang Server Linux qua REST API.
    4. Kích hoạt Server Linux Hot-Reload mô hình tức thì mà không gián đoạn hệ thống.
    """
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.trainer = PersonalModelTrainer(sample_rate=sample_rate)
        self.pending_fps: int = 0
        self.pending_claps: int = 0
        self.is_training: bool = False
        self.last_sample_time: float = 0.0
        self.debounce_timer: Optional[threading.Timer] = None
        self.lock = threading.Lock()
        self.auto_learn_enabled: bool = True

    def notify_new_sample(self, profile_name: str = "default", category: str = "false_positives"):
        """Ghi nhận một mẫu âm thanh mới vừa được nạp vào bộ Dataset"""
        if not self.auto_learn_enabled:
            return

        with self.lock:
            self.last_sample_time = time.time()
            if category == "false_positives":
                self.pending_fps += 1
            elif category in ("claps", "hard_claps", "soft_claps"):
                self.pending_claps += 1

            print(f"[AutoLearner] New sample '{category}' received. Pending: FPs={self.pending_fps}, Claps={self.pending_claps}")

            # 1. Nếu đã đủ ngưỡng batch (3 mẫu báo giả hoặc 10 mẫu vỗ tay) -> Train ngay
            if self.pending_fps >= 3 or self.pending_claps >= 10:
                self._cancel_timer()
                if not self.is_training:
                    threading.Thread(target=self._execute_training_and_sync, args=(profile_name,), daemon=True).start()
                return

            # 2. Ngược lại: Đặt Debounce Timer 15 giây
            self._cancel_timer()
            self.debounce_timer = threading.Timer(15.0, self._on_debounce_timeout, args=(profile_name,))
            self.debounce_timer.daemon = True
            self.debounce_timer.start()

    def _cancel_timer(self):
        if self.debounce_timer is not None:
            self.debounce_timer.cancel()
            self.debounce_timer = None

    def _on_debounce_timeout(self, profile_name: str):
        with self.lock:
            if (self.pending_fps > 0 or self.pending_claps > 0) and not self.is_training:
                print("[AutoLearner] Debounce timeout (15s) reached -> Triggering Auto-Retrain...")
                threading.Thread(target=self._execute_training_and_sync, args=(profile_name,), daemon=True).start()

    def _execute_training_and_sync(self, profile_name: str = "default"):
        with self.lock:
            self.is_training = True
            self.pending_fps = 0
            self.pending_claps = 0

        print(f"\n{'='*55}\n🚀 [AutoLearner] STARTING GPU AUTO-TRAINING FOR PROFILE: {profile_name}\n{'='*55}")
        try:
            metrics = self.trainer.train_profile(
                profile_name=profile_name,
                augment_factor=12,
                cnn_epochs=20
            )
            print(f"[AutoLearner] [SUCCESS] Training completed! Acc={metrics['accuracy']}%, Sens={metrics['sensitivity']}%, NoiseRejection={metrics['noise_rejection']}%")

            # Tự động xuất và upload sang Server Linux
            linux_url = getattr(settings, "linux_server_url", "http://192.168.2.171:8000")
            self._sync_checkpoint_to_linux(profile_name, linux_url, metrics)

        except Exception as e:
            print(f"[AutoLearner] [ERROR] Auto-training error: {e}")
        finally:
            with self.lock:
                self.is_training = False

    def _sync_checkpoint_to_linux(self, profile_name: str, linux_url: str, metrics: Dict[str, Any]):
        """Gửi gói checkpoint đã huấn luyện sang Server Linux qua REST API"""
        ckpt_dir = CHECKPOINTS_DIR / profile_name
        files_to_send = ["model_sklearn.joblib", "scaler.joblib", "model_cnn.pt"]

        payload_files = {}
        for fname in files_to_send:
            fpath = ckpt_dir / fname
            if fpath.exists():
                with open(fpath, "rb") as f:
                    payload_files[fname] = base64.b64encode(f.read()).decode("ascii")

        if not payload_files:
            print("[AutoLearner] Warning: No checkpoint files found to sync.")
            return

        target_url = linux_url.rstrip("/") + "/api/training/upload-checkpoint"
        body = json.dumps({
            "profile_name": profile_name,
            "files": payload_files,
            "metrics": metrics
        }).encode("utf-8")

        print(f"[AutoLearner] Uploading new AI Checkpoints to Linux Server ({target_url})...")
        try:
            req = urllib.request.Request(
                target_url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                if resp.status in (200, 201):
                    print(f"🎉 [AutoLearner] [SUCCESS] AI Model successfully upgraded and hot-reloaded on Linux Server!")
                else:
                    print(f"[AutoLearner] Warning: Linux Server returned HTTP {resp.status}")
        except Exception as err:
            print(f"[AutoLearner] Info: Linux Server ({target_url}) was unreachable during auto-sync: {err}")

    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "enabled": self.auto_learn_enabled,
                "is_training": self.is_training,
                "pending_false_positives": self.pending_fps,
                "pending_claps": self.pending_claps,
                "last_sample_time": self.last_sample_time
            }

auto_learner = AutoRetrainManager(sample_rate=settings.audio.sample_rate)
