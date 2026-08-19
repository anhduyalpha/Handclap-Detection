import os
import time
import logging
import threading
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List

from ..config import USER_PROFILES_DIR, settings
from ..core.security import safe_path_resolve, sanitize_identifier
from ..core.executor import io_executor

logger = logging.getLogger("handclap.hard_negatives")

class HardNegativeMiner:
    """
    Module tự động thu thập và lưu trữ mẫu Báo Giả / Mẫu Khó (Hard Negative Mining Engine).
    1. Tự động ghi lại các mẫu âm thanh rơi vào dải bất định (Uncertainty Band: 0.40 <= confidence <= 0.70).
    2. Lưu trữ theo cơ chế On-Disk Rolling Buffer (Giới hạn tối đa 500 mẫu trên ổ đĩa).
    3. Hỗ trợ Continual Learning mà không làm tràn dung lượng bộ nhớ.
    """
    def __init__(self, max_samples: int = 500, sample_rate: int = 16000):
        self.max_samples = max_samples
        self.sample_rate = sample_rate
        self.lock = threading.Lock()
        self.last_mine_time: float = 0.0
        self.min_mine_interval: float = 3.0  # Tối đa 1 mẫu mỗi 3s

    def get_hard_negatives_dir(self, profile_name: str) -> Path:
        clean_prof = sanitize_identifier(profile_name, "profile_name")
        p_dir = safe_path_resolve(USER_PROFILES_DIR, clean_prof)
        hn_dir = safe_path_resolve(p_dir, "hard_negatives")
        hn_dir.mkdir(parents=True, exist_ok=True)
        return hn_dir

    def mine_uncertain_sample(
        self, 
        profile_name: str, 
        audio_clip: np.ndarray, 
        confidence: float, 
        clf_details: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Tự động ghi lại mẫu âm thanh rơi vào vùng bất định (0.40 <= conf <= 0.70)
        """
        now = time.time()
        with self.lock:
            if now - self.last_mine_time < self.min_mine_interval:
                return None
            self.last_mine_time = now

        # Chạy I/O lưu file bất đồng bộ qua thread pool
        clean_prof = sanitize_identifier(profile_name, "profile_name")
        audio_copy = audio_clip.copy()
        
        io_executor.submit(self._save_and_prune, clean_prof, audio_copy, confidence, "uncertainty_miner")
        return f"mined_conf_{confidence:.2f}"

    def save_explicit_false_positive(
        self, 
        profile_name: str, 
        audio_clip: np.ndarray, 
        category: str = "false_positives"
    ) -> str:
        """
        Lưu mẫu khi người dùng chủ động bấm 'Báo Giả' trên giao diện Web.
        """
        clean_prof = sanitize_identifier(profile_name, "profile_name")
        audio_copy = audio_clip.copy()
        return self._save_and_prune(clean_prof, audio_copy, 0.0, category)

    def _save_and_prune(
        self, 
        profile_name: str, 
        audio: np.ndarray, 
        confidence: float, 
        source: str
    ) -> str:
        with self.lock:
            try:
                hn_dir = self.get_hard_negatives_dir(profile_name)
                timestamp_str = time.strftime("%Y%m%d_%H%M%S")
                sample_id = f"hn_{timestamp_str}_{int(time.time() * 1000000) % 1000000:06d}"
                
                npy_path = safe_path_resolve(hn_dir, f"{sample_id}.npy")
                np.save(npy_path, audio.astype(np.float32))
                
                logger.info(f"Mined hard negative sample [{sample_id}] for profile '{profile_name}' (Source: {source}, Conf: {confidence:.2f})")

                # Kiểm tra và dọn dẹp (Prune) nếu vượt quá max_samples
                all_files = sorted(hn_dir.glob("*.npy"), key=lambda p: (p.stat().st_mtime_ns, p.name))
                if len(all_files) > self.max_samples:
                    excess_count = len(all_files) - self.max_samples
                    for old_file in all_files[:excess_count]:
                        try:
                            if old_file.exists():
                                old_file.unlink()
                        except Exception as ex:
                            logger.debug(f"File unlink note: {ex}")
                    logger.info(f"Evicted {excess_count} oldest hard negative samples from on-disk buffer.")

                # Thông báo cho AutoLearner để tích lũy mẫu huấn luyện
                try:
                    from ..training.auto_learner import auto_learner
                    auto_learner.notify_new_sample(profile_name=profile_name, category="false_positives")
                except Exception as e:
                    logger.debug(f"AutoLearner notification note: {e}")

                return sample_id
            except Exception as e:
                logger.error(f"Error saving hard negative sample: {e}")
                return ""

    def load_hard_negatives(self, profile_name: str) -> List[np.ndarray]:
        """Tải toàn bộ các mẫu Hard Negatives đã lưu của profile"""
        hn_dir = self.get_hard_negatives_dir(profile_name)
        samples = []
        for f in hn_dir.glob("*.npy"):
            try:
                samples.append(np.load(f))
            except Exception:
                pass
        return samples

hard_negative_miner = HardNegativeMiner(max_samples=500, sample_rate=settings.audio.sample_rate)
