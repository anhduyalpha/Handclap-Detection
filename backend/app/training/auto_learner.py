import io
import os
import json
import time
import base64
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional

from .trainer import PersonalModelTrainer
from ..config import CHECKPOINTS_DIR, settings
from ..core.executor import io_executor
from ..core.network import post_with_retry
from ..core.security import sanitize_identifier

logger = logging.getLogger("handclap.auto_learner")

class AutoRetrainManager:
    """
    Quản lý Tự động Học & Tự động Huấn luyện (Continuous Active Learning Pipeline).
    
    Cơ chế:
    1. Lắng nghe các mẫu âm thanh mới được nạp vào máy tính Windows (Claps hoặc False Positives).
    2. Gom nhóm thông minh (Debounce Batching):
       - Tự động kích hoạt GPU huấn luyện khi tích lũy đủ 3 mẫu Báo Giả hoặc 10 mẫu Vỗ Thật mới.
       - HOẶC tự động kích hoạt sau 15 giây kể từ mẫu âm thanh cuối cùng nếu không có thêm mẫu mới.
    3. Tự động đóng gói và chuyển giao mô hình (Checkpoints) sang Server Linux qua REST API có Token Auth & Exponential Retry.
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

        clean_prof = sanitize_identifier(profile_name, "profile_name")
        with self.lock:
            self.last_sample_time = time.time()
            if category == "false_positives":
                self.pending_fps += 1
            elif category in ("claps", "hard_claps", "soft_claps"):
                self.pending_claps += 1

            logger.info(f"New sample '{category}' received for '{clean_prof}'. Pending: FPs={self.pending_fps}, Claps={self.pending_claps}")

            # 1. Nếu đã đủ ngưỡng batch (3 mẫu báo giả hoặc 10 mẫu vỗ tay) -> Train ngay
            if self.pending_fps >= 3 or self.pending_claps >= 10:
                self._cancel_timer()
                if not self.is_training:
                    io_executor.submit(self._execute_training_and_sync, clean_prof)
                return

            # 2. Ngược lại: Đặt Debounce Timer 15 giây
            self._cancel_timer()
            self.debounce_timer = threading.Timer(15.0, self._on_debounce_timeout, args=(clean_prof,))
            self.debounce_timer.daemon = True
            self.debounce_timer.start()

    def _cancel_timer(self):
        if self.debounce_timer is not None:
            self.debounce_timer.cancel()
            self.debounce_timer = None

    def _on_debounce_timeout(self, profile_name: str):
        with self.lock:
            if (self.pending_fps > 0 or self.pending_claps > 0) and not self.is_training:
                logger.info("Debounce timeout (15s) reached -> Triggering Auto-Retrain...")
                io_executor.submit(self._execute_training_and_sync, profile_name)

    def _execute_training_and_sync(self, profile_name: str = "default"):
        with self.lock:
            if self.is_training:
                return
            self.is_training = True
            self.pending_fps = 0
            self.pending_claps = 0

        logger.info(f"STARTING GPU AUTO-TRAINING FOR PROFILE: {profile_name}")
        try:
            metrics = self.trainer.train_profile(
                profile_name=profile_name,
                augment_factor=12,
                cnn_epochs=20
            )
            logger.info(f"Training completed! Acc={metrics.get('accuracy', 0)}%, Sens={metrics.get('sensitivity', 0)}%")

            # Tự động xuất và upload sang Server Linux với Exponential Backoff Retry & Token
            linux_url = getattr(settings, "linux_server_url", "http://127.0.0.1:8000")
            self._sync_checkpoint_to_linux(profile_name, linux_url, metrics)

        except Exception as e:
            logger.error(f"Auto-training error: {e}")
        finally:
            with self.lock:
                self.is_training = False

    def _sync_checkpoint_to_linux(self, profile_name: str, linux_url: str, metrics: Dict[str, Any]):
        """Gửi gói checkpoint đã huấn luyện sang Server Linux qua REST API an toàn"""
        ckpt_dir = CHECKPOINTS_DIR / profile_name
        files_to_send = ["model_sklearn.joblib", "scaler.joblib", "model_cnn.pt"]

        payload_files = {}
        for fname in files_to_send:
            fpath = ckpt_dir / fname
            if fpath.exists():
                with open(fpath, "rb") as f:
                    payload_files[fname] = base64.b64encode(f.read()).decode("ascii")

        if not payload_files:
            logger.warning("No checkpoint files found to sync.")
            return

        target_url = linux_url.rstrip("/") + "/api/training/upload-checkpoint"
        body = {
            "profile_name": profile_name,
            "files": payload_files,
            "metrics": metrics
        }

        logger.info(f"Uploading new AI Checkpoints to Linux Server ({target_url})...")
        success = post_with_retry(
            url=target_url,
            json_data=body,
            max_retries=3,
            base_delay=0.5,
            timeout=5.0,
            auth_token=getattr(settings, "studio_api_token", None)
        )
        if success:
            logger.info(f"AI Model checkpoint successfully synchronized to {target_url}!")
        else:
            logger.warning(f"Could not reach Linux Server ({target_url}) after retries.")

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
