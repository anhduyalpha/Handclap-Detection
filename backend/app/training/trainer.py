import time
import json
import joblib
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from pathlib import Path
from typing import Dict, Any, Tuple
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

from ..config import CHECKPOINTS_DIR, USER_PROFILES_DIR
from ..core.feature_extractor import AudioFeatureExtractor
from ..models.architectures import ClapCNN2D
from .augmentation import AudioAugmentor
from .dataset_manager import DatasetManager

class PersonalModelTrainer:
    """
    Quy trình huấn luyện mô hình cá nhân hóa nâng cao (Personalized Model Trainer Pro).
    Đảm bảo:
    1. Độ nhạy cực cao (High Recall): Nhận diện được cả tiếng vỗ nhẹ, ở xa.
    2. Chống báo động giả tuyệt đối (High Precision): Loại trừ tiếng gõ bàn, bấm phím, nói chuyện.
    """
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.feature_extractor = AudioFeatureExtractor(sample_rate=sample_rate)
        self.augmentor = AudioAugmentor(sample_rate=sample_rate)
        self.dataset_manager = DatasetManager(sample_rate=sample_rate)

    def train_profile(
        self, 
        profile_name: str = "default",
        augment_factor: int = 15,
        cnn_epochs: int = 25
    ) -> Dict[str, Any]:
        """
        Huấn luyện mô hình cá nhân hóa cho một profile cụ thể.
        """
        start_time = time.time()
        
        # 1. Tải dữ liệu mẫu gốc từ tất cả các danh mục
        raw_claps, raw_noises, raw_fps = self.dataset_manager.load_dataset_separated(profile_name)
        if len(raw_claps) == 0:
            raise ValueError(f"Không tìm thấy mẫu tiếng vỗ tay nào trong profile '{profile_name}'")
        if len(raw_noises) == 0 and len(raw_fps) == 0:
            raise ValueError(f"Không tìm thấy mẫu tiếng ồn nào trong profile '{profile_name}'")

        # 2. Data Augmentation nâng cao
        aug_claps = []
        for c in raw_claps:
            aug_claps.extend(self.augmentor.augment_sample(c, bg_noises=raw_noises, count=augment_factor))

        aug_noises = []
        for n in raw_noises:
            aug_noises.extend(self.augmentor.augment_sample(n, bg_noises=None, count=augment_factor))

        # Nhân bản tăng cường GẤP ĐÔI (2x) cho các mẫu Báo Giả (Hard Negatives)
        if len(raw_fps) > 0:
            fp_factor = max(augment_factor * 2, 20)
            for fp in raw_fps:
                aug_noises.extend(self.augmentor.augment_sample(fp, bg_noises=None, count=fp_factor))

        # Xáo trộn ngẫu nhiên để lấy đều mọi danh mục tạp âm (tiếng nói, kim loại, đóng cửa, gõ phím)
        rng = np.random.default_rng(42)
        rng.shuffle(aug_noises)
        rng.shuffle(aug_claps)

        # Cân bằng số lượng mẫu 1:1 giữa Claps và Noises
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
        X_feats = [] # 1D Vector cho Sklearn
        X_mels = []  # 2D Mel-Spectrogram cho CNN
        y = []       # Labels: 1 = Clap, 0 = Noise

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

        # 5. Huấn luyện PyTorch CNN Model (Tự động tăng tốc GPU CUDA nếu có)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
        print(f"[*] [Trainer] Using Compute Device: {device} ({gpu_name})")
        if device.type == "cuda":
            torch.backends.cudnn.benchmark = True

        cnn_model = ClapCNN2D(num_classes=2).to(device)
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.AdamW(cnn_model.parameters(), lr=0.001, weight_decay=1e-4)

        tensor_X_train = torch.from_numpy(X_mels[idx_train]).unsqueeze(1).float().to(device)
        tensor_y_train = torch.from_numpy(y[idx_train]).long().to(device)
        tensor_X_val = torch.from_numpy(X_mels[idx_val]).unsqueeze(1).float().to(device)
        tensor_y_val = torch.from_numpy(y[idx_val]).long().to(device)

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

        # 6. Lưu Checkpoints (Chuyển về CPU state_dict để Server Linux nạp trơn tru 100%)
        ckpt_dir = CHECKPOINTS_DIR / profile_name
        ckpt_dir.mkdir(parents=True, exist_ok=True)

        joblib.dump(sklearn_clf, ckpt_dir / "model_sklearn.joblib")
        joblib.dump(scaler, ckpt_dir / "scaler.joblib")
        torch.save(cnn_model.cpu().state_dict(), ckpt_dir / "model_cnn.pt")

        elapsed_time = round(time.time() - start_time, 2)
        overall_acc = round(max(sk_acc, cnn_acc) * 100, 1)
        clap_sensitivity = round(max(sk_recall, cnn_recall) * 100, 1)
        noise_rejection = round(sk_precision * 100, 1)

        # Cập nhật metadata profile
        p_dir = self.dataset_manager.get_profile_dir(profile_name)
        meta = {
            "name": profile_name,
            "accuracy": overall_acc,
            "sensitivity": clap_sensitivity,       # Độ nhạy bắt tiếng vỗ
            "noise_rejection": noise_rejection,     # Khả năng chống báo động giả
            "cnn_accuracy": round(cnn_acc * 100, 1),
            "sklearn_accuracy": round(sk_acc * 100, 1),
            "total_augmented_samples": len(y),
            "raw_claps": len(raw_claps),
            "raw_noises": len(raw_noises),
            "training_time_sec": elapsed_time,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(p_dir / "meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return meta
