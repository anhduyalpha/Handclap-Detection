import torch
import joblib
import json
import threading
import logging
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from ..config import CHECKPOINTS_DIR, MLConfig
from .architectures import ClapCNN2D

logger = logging.getLogger("handclap.classifier")

class ClapClassifier:
    """
    Wrapper quản lý mô hình phân loại âm thanh vỗ tay (Stage 2).
    Hỗ trợ cả PyTorch CNN và Scikit-Learn Ensemble, hỗ trợ Double-Buffered Hot-Reload
    tức thì (<1ms stall) ngay khi train xong mà không chặn luồng âm thanh thời gian thực.
    """
    def __init__(self, config: Optional[MLConfig] = None):
        self.config = config or MLConfig()
        self.active_profile = self.config.active_profile
        self.confidence_threshold = self.config.confidence_threshold
        
        self.cnn_model: Optional[ClapCNN2D] = None
        self.sklearn_model = None
        self.scaler = None
        self.model_type = "hybrid"  # "cnn" | "sklearn" | "hybrid"
        self.lock = threading.Lock()
        self._last_loaded_mtimes: Dict[str, float] = {}
        
        # Nạp mô hình ban đầu
        self.load_profile_model(self.active_profile)

    def load_profile_model(self, profile_name: str = "default") -> bool:
        """
        Nạp model từ checkpoints/ của profile tương ứng theo cơ chế Double-Buffering:
        Đọc file I/O hoàn toàn ngoài Lock, chỉ giữ Lock trong < 1ms để swap con trỏ model.
        """
        profile_ckpt_dir = CHECKPOINTS_DIR / profile_name
        default_ckpt_dir = CHECKPOINTS_DIR / "default"
        target_dir = profile_ckpt_dir if profile_ckpt_dir.exists() else default_ckpt_dir

        new_cnn = None
        new_sklearn = None
        new_scaler = None
        new_mtimes: Dict[str, float] = {}

        # 1. Tải Sklearn Model (Đọc ngoài lock)
        sklearn_path = target_dir / "model_sklearn.joblib"
        scaler_path = target_dir / "scaler.joblib"
        if sklearn_path.exists() and scaler_path.exists():
            try:
                new_sklearn = joblib.load(sklearn_path)
                new_scaler = joblib.load(scaler_path)
                new_mtimes[str(sklearn_path)] = sklearn_path.stat().st_mtime
                new_mtimes[str(scaler_path)] = scaler_path.stat().st_mtime
            except Exception as e:
                logger.warning(f"Error loading sklearn model: {e}")

        # 2. Tải PyTorch CNN Model (Đọc ngoài lock với weights_only=True)
        cnn_path = target_dir / "model_cnn.pt"
        if cnn_path.exists():
            try:
                model = ClapCNN2D(num_classes=2)
                state_dict = torch.load(cnn_path, map_location="cpu", weights_only=True)
                model.load_state_dict(state_dict)
                model.eval()
                new_cnn = model
                new_mtimes[str(cnn_path)] = cnn_path.stat().st_mtime
            except Exception as e:
                logger.warning(f"Error loading CNN model: {e}")

        meta_path = target_dir / "meta.json"
        if meta_path.exists():
            new_mtimes[str(meta_path)] = meta_path.stat().st_mtime

        # Xác định model type mới
        if new_cnn is not None and new_sklearn is not None:
            new_model_type = "hybrid"
        elif new_cnn is not None:
            new_model_type = "cnn"
        elif new_sklearn is not None:
            new_model_type = "sklearn"
        else:
            new_model_type = "rule_based_fallback"

        # 3. Swap con trỏ nguyên tử dưới Lock (< 1ms)
        with self.lock:
            self.cnn_model = new_cnn
            self.sklearn_model = new_sklearn
            self.scaler = new_scaler
            self.active_profile = profile_name
            self.model_type = new_model_type
            self._last_loaded_mtimes = new_mtimes

        logger.info(f"Loaded model for profile '{profile_name}' (Type: {self.model_type})")
        return True

    def check_and_reload_if_updated(self) -> bool:
        """Kiểm tra xem file model trên ổ đĩa có thay đổi (do vừa train từ Windows đẩy sang) hay không"""
        target_dir = CHECKPOINTS_DIR / self.active_profile
        if not target_dir.exists():
            target_dir = CHECKPOINTS_DIR / "default"
            
        has_update = False
        for f in [target_dir / "model_cnn.pt", target_dir / "model_sklearn.joblib", target_dir / "meta.json"]:
            if f.exists():
                curr_mtime = f.stat().st_mtime
                old_mtime = self._last_loaded_mtimes.get(str(f), 0)
                if curr_mtime > old_mtime + 0.5:  # File mới hơn ít nhất 0.5s
                    has_update = True
                    break
        
        if has_update:
            logger.info("Hot-Reload: New AI model checkpoint detected on disk, performing atomic reload...")
            return self.load_profile_model(self.active_profile)
        return False

    def predict(
        self, 
        mel_spectrogram: Optional[np.ndarray] = None, 
        feature_vector: Optional[np.ndarray] = None,
        dsp_metrics: Optional[Dict[str, Any]] = None,
        mel_spec: Optional[np.ndarray] = None,
        feat_vec: Optional[np.ndarray] = None,
        confidence_thresh: Optional[float] = None
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Dự đoán xem âm thanh có phải là tiếng vỗ tay hay không.
        
        Returns:
            (is_clap, confidence_score, details_dict)
        """
        if mel_spectrogram is None and mel_spec is not None:
            mel_spectrogram = mel_spec
        if feature_vector is None and feat_vec is not None:
            feature_vector = feat_vec

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

        # 3. Tổng hợp điểm tự tin (Weighted Ensemble)
        if cnn_ref is not None and sk_ref is not None and len(conf_scores) == 2:
            final_confidence = float(0.75 * conf_scores[0] + 0.25 * conf_scores[1])
        elif conf_scores:
            final_confidence = float(np.mean(conf_scores))
        else:
            # Fallback rule-based nếu chưa có file weights
            final_confidence = self._fallback_rule_score(dsp_metrics)
            details["rule_fallback"] = True

        effective_thresh = confidence_thresh if confidence_thresh is not None else self.confidence_threshold
        details["final_confidence"] = round(final_confidence, 4)
        details["threshold_used"] = round(effective_thresh, 4)
        is_clap = final_confidence >= effective_thresh

        return is_clap, final_confidence, details

    def _fallback_rule_score(self, dsp_metrics: Optional[Dict[str, Any]]) -> float:
        """Đánh giá xác suất dựa trên DSP metrics khi khởi động lần đầu chưa train model"""
        if not dsp_metrics:
            return 0.5
            
        score = 0.0
        if dsp_metrics.get("crest_factor", 0) > 4.0:
            score += 0.3
        if dsp_metrics.get("hf_ratio", 0) > 0.40:
            score += 0.35
        if dsp_metrics.get("onset_ratio", 0) > 2.5:
            score += 0.25
        if dsp_metrics.get("peak_amp", 0) > 0.08:
            score += 0.1
        return min(1.0, score)
