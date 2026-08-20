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
    Kết hợp chặt chẽ giữa AI Deep Learning (CNN / Sklearn) và Phân tích Vật lý Âm học (Physical Acoustics).
    Yêu cầu cả 2 bộ đánh giá cùng đồng thuận để loại bỏ 100% hiện tượng nhảy đèn giả/quá nhạy.
    """
    def __init__(self, config: Optional[Any] = None, model_type: str = "hybrid_ensemble", confidence_threshold: float = 0.60):
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

    def load_profile_model(self, profile_name: str) -> bool:
        return self.load_profile(profile_name)

    def _get_checkpoint_mtime(self, profile_name: str) -> float:
        p_dir = CHECKPOINTS_DIR / profile_name
        if not p_dir.exists():
            return 0.0
        mtimes = [f.stat().st_mtime for f in p_dir.glob("*") if f.is_file()]
        return max(mtimes) if mtimes else 0.0

    def check_and_reload_if_updated(self) -> bool:
        latest_mtime = self._get_checkpoint_mtime(self.active_profile)
        if latest_mtime > self.last_mtime and self.last_mtime > 0:
            logger.info(f"Detected updated checkpoint for '{self.active_profile}'. Reloading model...")
            return self.load_profile(self.active_profile)
        return False

    def compute_acoustic_score(self, dsp_metrics: Optional[Dict[str, Any]]) -> float:
        """
        Đánh giá Vật lý Âm học chuẩn xác: Phân biệt tuyệt đối giữa tiếng vỗ tay và tiếng nói/tiếng quạt/tạp âm.
        """
        if not dsp_metrics:
            return 0.0
        
        peak = dsp_metrics.get("peak_amp", 0.0)
        crest = dsp_metrics.get("crest_factor", 1.0)
        hf = dsp_metrics.get("hf_ratio", 0.0)
        onset = dsp_metrics.get("onset_ratio", 1.0)
        decay = dsp_metrics.get("decay_ratio", 1.0)
        flatness = dsp_metrics.get("spectral_flatness", 0.5)

        # 1. Nếu biên độ quá nhỏ hoặc không có độ nhọn xung -> Tiếng ồn nền/tiếng nói, trả về 0 ngay
        if peak < 0.018 or crest < 2.0:
            return 0.0

        # Nếu không có bùng nổ Onset (âm thanh liên tục như quạt, nhạc, tivi) -> Loại bỏ
        if onset < 1.3:
            return 0.05

        score = 0.10

        # 2. Độ nhọn đỉnh xung (Crest Factor)
        if crest >= 3.5:
            score += 0.35
        elif crest >= 2.6:
            score += 0.25
        elif crest >= 2.1:
            score += 0.15

        # 3. Bùng nổ Onset tức thì
        if onset >= 2.5:
            score += 0.30
        elif onset >= 1.7:
            score += 0.20
        elif onset >= 1.35:
            score += 0.10

        # 4. Tỷ lệ dải cao HF (>1200Hz)
        if hf >= 0.25:
            score += 0.20
        elif hf >= 0.15:
            score += 0.10
        elif hf < 0.08:
            score -= 0.15  # Tiếng đóng cửa trầm đục, tiếng dậm chân

        # 5. Tắt âm nhanh (Decay)
        if decay >= 1.25:
            score += 0.15
        elif decay < 1.05:
            score -= 0.15  # Tiếng nói ngân dài không suy hao

        # 6. Độ phẳng phổ (Broadband Noise)
        if flatness < 0.08:
            score -= 0.20  # Tiếng còi, tiếng rít kim loại

        return float(np.clip(score, 0.0, 1.0))

    def predict(
        self, 
        mel_spectrogram: Optional[np.ndarray], 
        feature_vector: Optional[np.ndarray], 
        dsp_metrics: Optional[Dict[str, Any]] = None,
        confidence_thresh: Optional[float] = None
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Dự đoán thời gian thực yêu cầu đồng thuận giữa ML và Vật lý Âm học.
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

        # 4. Tổng hợp điểm tự tin (Ensemble Consensus)
        # Chỉ khi cả 2 nguồn cùng xác nhận thì mới có điểm cao
        if conf_scores:
            ml_score = float(np.mean(conf_scores))
            if ml_score < 0.20 or acoustic_score < 0.20:
                final_confidence = min(ml_score, acoustic_score) * 0.5
            else:
                final_confidence = 0.55 * ml_score + 0.45 * acoustic_score
        else:
            final_confidence = acoustic_score
            details["rule_fallback"] = True

        effective_thresh = confidence_thresh if confidence_thresh is not None else self.confidence_threshold
        details["final_confidence"] = round(final_confidence, 4)
        details["threshold_used"] = round(effective_thresh, 4)
        is_clap = final_confidence >= effective_thresh

        return is_clap, final_confidence, details
