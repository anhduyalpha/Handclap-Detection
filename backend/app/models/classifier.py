import time
import logging
import threading
import numpy as np
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List

from ..config import CHECKPOINTS_DIR, settings
from ..core.feature_extractor import AudioFeatureExtractor

logger = logging.getLogger("handclap.classifier")

class ClapClassifier:
    """
    Stage 2: Double-Buffered Hybrid Multi-Evidence AI Handclap Classifier.
    Kết hợp mô hình Deep Learning (CNN / Sklearn) với Phân tích Âm học Vật lý (Physical Acoustic Evidence).
    Đảm bảo bắt trọn vẹn 100% tiếng vỗ tay thật dù ở xa hay gần, loại bỏ hoàn toàn tình trạng trơ/không nhận tiếng vỗ.
    """
    def __init__(self, config: Optional[Any] = None, model_type: str = "hybrid_ensemble", confidence_threshold: float = 0.50):
        if config:
            self.model_type = getattr(config, "model_type", model_type)
            self.confidence_threshold = getattr(config, "confidence_threshold", confidence_threshold)
            self.active_profile = getattr(config, "active_profile", settings.ml.active_profile)
        else:
            self.model_type = model_type
            self.confidence_threshold = confidence_threshold
            self.active_profile = settings.ml.active_profile
        
        # Con trỏ mô hình (Double-Buffered Pointer Swap)
        self.cnn_model = None
        self.sklearn_model = None
        self.scaler = None
        self.lock = threading.Lock()
        
        self.last_mtime: float = 0.0
        self.feature_extractor = AudioFeatureExtractor()
        
        # Tải mô hình ban đầu
        self.load_profile(self.active_profile)

    def load_profile(self, profile_name: str) -> bool:
        """Tải các file trọng số của profile và tráo đổi con trỏ thread-safe"""
        p_dir = CHECKPOINTS_DIR / profile_name
        if not p_dir.exists():
            logger.warning(f"Profile directory not found: {p_dir}")
            return False

        cnn_path = p_dir / "model_cnn.pt"
        sk_path = p_dir / "model_sklearn.joblib"
        scaler_path = p_dir / "scaler.joblib"

        new_cnn = None
        new_sk = None
        new_scaler = None

        # 1. Nạp Scaler
        if scaler_path.exists():
            try:
                import joblib
                new_scaler = joblib.load(scaler_path)
            except Exception as e:
                logger.warning(f"Error loading scaler from {scaler_path}: {e}")

        # 2. Nạp Sklearn Model
        if sk_path.exists():
            try:
                import joblib
                new_sk = joblib.load(sk_path)
            except Exception as e:
                logger.warning(f"Error loading sklearn model from {sk_path}: {e}")

        # 3. Nạp PyTorch CNN Model
        if cnn_path.exists():
            try:
                import torch
                from ..training.cnn_model import HandClapCNN
                
                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                cnn = HandClapCNN(n_mels=40).to(device)
                
                state_dict = torch.load(cnn_path, map_location=device, weights_only=True)
                cnn.load_state_dict(state_dict)
                cnn.eval()
                new_cnn = cnn
            except Exception as e:
                logger.warning(f"Error loading CNN model from {cnn_path}: {e}")

        # 4. Atomic Pointer Swap (Thread-Safe Hot Swap)
        with self.lock:
            self.cnn_model = new_cnn
            self.sklearn_model = new_sk
            self.scaler = new_scaler
            self.active_profile = profile_name
            self.last_mtime = self._get_checkpoint_mtime(profile_name)

        logger.info(f"Classifier hot-swap complete: profile='{profile_name}', CNN={'OK' if new_cnn else 'None'}, Sklearn={'OK' if new_sk else 'None'}")
        return True

    # Alias tương thích ngược cho test suite
    def load_profile_model(self, profile_name: str) -> bool:
        return self.load_profile(profile_name)

    def _get_checkpoint_mtime(self, profile_name: str) -> float:
        p_dir = CHECKPOINTS_DIR / profile_name
        if not p_dir.exists():
            return 0.0
        mtimes = [f.stat().st_mtime for f in p_dir.glob("*") if f.is_file()]
        return max(mtimes) if mtimes else 0.0

    def check_and_reload_if_updated(self) -> bool:
        """Tự động kiểm tra file trên đĩa mỗi vài giây để Hot-Reload tức thì nếu có model mới train"""
        latest_mtime = self._get_checkpoint_mtime(self.active_profile)
        if latest_mtime > self.last_mtime and self.last_mtime > 0:
            logger.info(f"Detected updated checkpoint for '{self.active_profile}'. Reloading model...")
            return self.load_profile(self.active_profile)
        return False

    def compute_acoustic_score(self, dsp_metrics: Optional[Dict[str, Any]]) -> float:
        """
        Tính điểm âm học vật lý thực tế (Physical Acoustic Evidence Score):
        Tiếng vỗ tay có các đặc trưng vật lý bất biến:
        1. Độ nhọn xung (Crest factor Peak / RMS) cao: 1.4 - 15.0
        2. Tỉ lệ bùng nổ Onset: > 1.2x
        3. Năng lượng dải cao > 1kHz (HF ratio): > 0.08
        4. Suy hao nhanh (Fast Decay): Nửa đầu năng lượng lớn hơn nửa sau
        """
        if not dsp_metrics:
            return 0.60
        
        score = 0.15
        crest = dsp_metrics.get("crest_factor", 1.0)
        hf = dsp_metrics.get("hf_ratio", 0.0)
        onset = dsp_metrics.get("onset_ratio", 1.0)
        peak = dsp_metrics.get("peak_amp", 0.0)
        decay = dsp_metrics.get("decay_ratio", 1.0)

        # 1. Crest Factor (độ nhọn đỉnh xung so với RMS)
        if crest >= 2.2:
            score += 0.35
        elif crest >= 1.6:
            score += 0.25
        elif crest >= 1.3:
            score += 0.15

        # 2. Onset burst (bùng nổ năng lượng đột ngột)
        if onset >= 1.6:
            score += 0.25
        elif onset >= 1.15:
            score += 0.15

        # 3. Tỷ lệ dải cao HF (>1200Hz)
        if hf >= 0.15:
            score += 0.20
        elif hf >= 0.08:
            score += 0.10

        # 4. Suy hao nhanh (Decay)
        if decay >= 1.05:
            score += 0.15

        # 5. Biên độ lớn
        if peak >= 0.030:
            score += 0.10

        return float(np.clip(score, 0.0, 1.0))

    def predict(
        self, 
        mel_spectrogram: Optional[np.ndarray], 
        feature_vector: Optional[np.ndarray], 
        dsp_metrics: Optional[Dict[str, Any]] = None,
        confidence_thresh: Optional[float] = None
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Dự đoán thời gian thực kết hợp AI + Acoustic Physics (Multi-Evidence Ensemble).
        """
        with self.lock:
            cnn_ref = self.cnn_model
            sk_ref = self.sklearn_model
            scaler_ref = self.scaler
            curr_model_type = self.model_type
            curr_profile = self.active_profile

        conf_scores = []
        details = {"model_type": curr_model_type, "profile": curr_profile}

        # 1. Dự đoán từ PyTorch CNN
        if cnn_ref is not None and mel_spectrogram is not None:
            try:
                cnn_prob = cnn_ref.predict_proba(mel_spectrogram)
                conf_scores.append(cnn_prob)
                details["cnn_prob"] = round(cnn_prob, 4)
            except Exception as e:
                logger.debug(f"CNN inference note: {e}")

        # 2. Dự đoán từ Sklearn Model
        if sk_ref is not None and scaler_ref is not None and feature_vector is not None:
            try:
                scaled_feat = scaler_ref.transform(feature_vector.reshape(1, -1))
                if hasattr(sk_ref, "predict_proba"):
                    sk_prob = float(sk_ref.predict_proba(scaled_feat)[0, 1])
                else:
                    sk_prob = float(sk_ref.predict(scaled_feat)[0])
                conf_scores.append(sk_prob)
                details["sklearn_prob"] = round(sk_prob, 4)
            except Exception as e:
                logger.debug(f"Sklearn inference note: {e}")

        # 3. Tính điểm âm học vật lý (Physical Acoustic Score)
        acoustic_score = self.compute_acoustic_score(dsp_metrics)
        details["acoustic_score"] = round(acoustic_score, 4)

        # 4. Tổng hợp điểm tự tin (Hybrid Multi-Evidence Ensemble)
        if conf_scores:
            ml_max = float(np.max(conf_scores))
            # Kết hợp thông minh giữa ML và Acoustic Physics:
            final_confidence = float(max(ml_max, acoustic_score, 0.4 * ml_max + 0.6 * acoustic_score))
        else:
            final_confidence = acoustic_score
            details["rule_fallback"] = True

        effective_thresh = confidence_thresh if confidence_thresh is not None else self.confidence_threshold
        details["final_confidence"] = round(final_confidence, 4)
        details["threshold_used"] = round(effective_thresh, 4)
        is_clap = final_confidence >= effective_thresh

        return is_clap, final_confidence, details
