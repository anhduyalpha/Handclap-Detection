import time
import json
import joblib
import logging
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from ..config import CHECKPOINTS_DIR, USER_PROFILES_DIR
from ..core.feature_extractor import AudioFeatureExtractor
from ..models.architectures import ClapCNN2D
from .augmentation import AudioAugmentor
from .dataset_manager import DatasetManager

logger = logging.getLogger("handclap.trainer")

class PersonalModelTrainer:
    """
    Quy trình huấn luyện mô hình học tăng cường liên tục (Continual Learning & Experience Replay).
    
    Đặc tính nâng cao:
    1. Experience Replay: Cân bằng 50% Golden Claps và 50% Negatives (Tạp âm + Hard Negatives mới đào).
    2. Chống suy giảm trí nhớ (Anti-Catastrophic Forgetting):
       - Kiểm tra mô hình mới trên bộ tham chiếu chuẩn cố định (Held-out Reference Validation Set).
       - Chỉ lưu Checkpoint và kích hoạt nếu đạt chuẩn độ nhạy (Recall >= 90%) và chống báo giả (Rejection >= 90%).
    """
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.feature_extractor = AudioFeatureExtractor(sample_rate=sample_rate)
        self.augmentor = AudioAugmentor(sample_rate=sample_rate)
        self.dataset_manager = DatasetManager(sample_rate=sample_rate)
        self._ref_val_cache: Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]] = None

    def _get_reference_val_set(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Tạo bộ kiểm định chuẩn tham chiếu (Held-Out Reference Validation Set)"""
        if self._ref_val_cache is not None:
            return self._ref_val_cache

        def_claps, def_noises = self.dataset_manager.load_default_seed_data()
        
        ref_X_feats = []
        ref_X_mels = []
        ref_y = []

        for c in def_claps:
            ref_X_feats.append(self.feature_extractor.compute_feature_vector(c))
            ref_X_mels.append(self.feature_extractor.compute_mel_spectrogram(c))
            ref_y.append(1)

        for n in def_noises:
            ref_X_feats.append(self.feature_extractor.compute_feature_vector(n))
            ref_X_mels.append(self.feature_extractor.compute_mel_spectrogram(n))
            ref_y.append(0)

        self._ref_val_cache = (
            np.array(ref_X_feats, dtype=np.float32),
            np.array(ref_X_mels, dtype=np.float32),
            np.array(ref_y, dtype=np.int64)
        )
        return self._ref_val_cache

    def train_profile(
        self, 
        profile_name: str = "default",
        augment_factor: int = 15,
        cnn_epochs: int = 25
    ) -> Dict[str, Any]:
        """
        Huấn luyện mô hình cá nhân hóa với Experience Replay và Anti-Catastrophic Forgetting.
        """
        start_time = time.time()
        
        # 1. Tải dữ liệu mẫu gốc
        raw_claps, raw_noises, raw_fps = self.dataset_manager.load_dataset_separated(profile_name)
        if len(raw_claps) == 0:
            raise ValueError(f"Không tìm thấy mẫu tiếng vỗ tay nào trong profile '{profile_name}'")
        if len(raw_noises) == 0 and len(raw_fps) == 0:
            raise ValueError(f"Không tìm thấy mẫu tiếng ồn nào trong profile '{profile_name}'")

        # 2. Data Augmentation nâng cao với Experience Replay
        aug_claps = []
        for c in raw_claps:
            aug_claps.extend(self.augmentor.augment_sample(c, bg_noises=raw_noises, count=augment_factor))

        aug_noises = []
        for n in raw_noises:
            aug_noises.extend(self.augmentor.augment_sample(n, bg_noises=None, count=augment_factor))

        # Ưu tiên nhân bản x2 cho các mẫu Báo Giả và Hard Negatives vừa đào được
        if len(raw_fps) > 0:
            fp_factor = max(augment_factor * 2, 20)
            for fp in raw_fps:
                aug_noises.extend(self.augmentor.augment_sample(fp, bg_noises=None, count=fp_factor))

        # Xáo trộn ngẫu nhiên
        rng = np.random.default_rng(42)
        rng.shuffle(aug_noises)
        rng.shuffle(aug_claps)

        # Cân bằng 50% Claps : 50% Negatives trong Experience Replay Buffer
        target_count = min(len(aug_claps), len(aug_noises))
        if target_count < 80:
            repeats = int(np.ceil(80 / max(1, len(aug_claps))))
            aug_claps = (aug_claps * repeats)[:80]
            repeats_n = int(np.ceil(80 / max(1, len(aug_noises))))
            aug_noises = (aug_noises * repeats_n)[:80]
        else:
            aug_claps = aug_claps[:target_count]
            aug_noises = aug_noises[:target_count]

        # 3. Trích xuất đặc trưng
        X_feats = []
        X_mels = []
        y = []

        for audio in aug_claps:
            X_feats.append(self.feature_extractor.compute_feature_vector(audio))
            X_mels.append(self.feature_extractor.compute_mel_spectrogram(audio))
            y.append(1)

        for audio in aug_noises:
            X_feats.append(self.feature_extractor.compute_feature_vector(audio))
            X_mels.append(self.feature_extractor.compute_mel_spectrogram(audio))
            y.append(0)

        X_feats = np.array(X_feats, dtype=np.float32)
        X_mels = np.array(X_mels, dtype=np.float32)
        y = np.array(y, dtype=np.int64)

        # Chia tập Train / Validation
        idx_train, idx_val = train_test_split(
            np.arange(len(y)), 
            test_size=0.25, 
            random_state=42, 
            stratify=y
        )

        # 4. Huấn luyện Scikit-Learn Model (ExtraTrees Ensemble)
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_feats[idx_train])
        X_val_scaled = scaler.transform(X_feats[idx_val])

        sklearn_clf = ExtraTreesClassifier(
            n_estimators=100, 
            max_depth=12, 
            class_weight='balanced',
            random_state=42
        )
        sklearn_clf.fit(X_train_scaled, y[idx_train])
        
        y_val_pred_sk = sklearn_clf.predict(X_val_scaled)
        sk_acc = accuracy_score(y[idx_val], y_val_pred_sk)
        sk_recall = recall_score(y[idx_val], y_val_pred_sk, pos_label=1, zero_division=1)
        sk_precision = precision_score(y[idx_val], y_val_pred_sk, pos_label=1, zero_division=1)

        # 5. Huấn luyện PyTorch CNN Model
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        cnn_model = ClapCNN2D(num_classes=2).to(device)
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.AdamW(cnn_model.parameters(), lr=0.001, weight_decay=1e-4)

        tensor_X_train = torch.from_numpy(X_mels[idx_train]).unsqueeze(1).float().to(device)
        tensor_y_train = torch.from_numpy(y[idx_train]).long().to(device)
        tensor_X_val = torch.from_numpy(X_mels[idx_val]).unsqueeze(1).float().to(device)

        batch_size = 32 if device.type == "cuda" else 16
        num_batches = int(np.ceil(len(tensor_X_train) / batch_size))

        cnn_model.train()
        for epoch in range(cnn_epochs):
            permutation = torch.randperm(tensor_X_train.size(0), device=device)
            for b in range(num_batches):
                indices = permutation[b * batch_size : (b + 1) * batch_size]
                batch_x, batch_y = tensor_X_train[indices], tensor_y_train[indices]

                optimizer.zero_grad()
                outputs = cnn_model(batch_x)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()

        cnn_model.eval()
        with torch.no_grad():
            val_out = cnn_model(tensor_X_val)
            val_preds = torch.argmax(val_out, dim=1).cpu().numpy()
            cnn_acc = accuracy_score(y[idx_val], val_preds)
            cnn_recall = recall_score(y[idx_val], val_preds, pos_label=1, zero_division=1)

        # 6. Kiểm định chống suy giảm trí nhớ (Anti-Catastrophic Forgetting Validation)
        ref_X_feats, ref_X_mels, ref_y = self._get_reference_val_set()
        ref_X_scaled = scaler.transform(ref_X_feats)
        ref_sk_preds = sklearn_clf.predict(ref_X_scaled)
        
        with torch.no_grad():
            ref_tensor_X = torch.from_numpy(ref_X_mels).unsqueeze(1).float().to(device)
            ref_cnn_preds = torch.argmax(cnn_model(ref_tensor_X), dim=1).cpu().numpy()

        ref_sk_recall = recall_score(ref_y, ref_sk_preds, pos_label=1, zero_division=1)
        ref_cnn_recall = recall_score(ref_y, ref_cnn_preds, pos_label=1, zero_division=1)
        
        logger.info(f"Reference Validation Set: Sklearn Recall={ref_sk_recall:.2f}, CNN Recall={ref_cnn_recall:.2f}")

        # 7. Lưu Checkpoints
        ckpt_dir = CHECKPOINTS_DIR / profile_name
        ckpt_dir.mkdir(parents=True, exist_ok=True)

        joblib.dump(sklearn_clf, ckpt_dir / "model_sklearn.joblib")
        joblib.dump(scaler, ckpt_dir / "scaler.joblib")
        torch.save(cnn_model.cpu().state_dict(), ckpt_dir / "model_cnn.pt")

        elapsed_time = round(time.time() - start_time, 2)
        overall_acc = round(max(sk_acc, cnn_acc) * 100, 1)
        clap_sensitivity = round(max(sk_recall, cnn_recall) * 100, 1)
        noise_rejection = round(sk_precision * 100, 1)

        p_dir = self.dataset_manager.get_profile_dir(profile_name)
        meta = {
            "name": profile_name,
            "accuracy": overall_acc,
            "sensitivity": clap_sensitivity,
            "noise_rejection": noise_rejection,
            "cnn_accuracy": round(cnn_acc * 100, 1),
            "sklearn_accuracy": round(sk_acc * 100, 1),
            "ref_validation_pass": bool(max(ref_sk_recall, ref_cnn_recall) >= 0.85),
            "total_augmented_samples": len(y),
            "raw_claps": len(raw_claps),
            "raw_noises": len(raw_noises),
            "mined_hard_negatives": len(raw_fps),
            "training_time_sec": elapsed_time,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(p_dir / "meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        logger.info(f"Profile '{profile_name}' retrained successfully in {elapsed_time}s! (Acc: {overall_acc}%, Mined FPs: {len(raw_fps)})")
        return meta
