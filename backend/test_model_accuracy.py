import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from app.config import settings
from app.training.dataset_manager import DatasetManager
from app.training.augmentation import AudioAugmentor
from app.core.feature_extractor import AudioFeatureExtractor

class ImprovedClapCNN(nn.Module):
    def __init__(self, num_classes=2):
        super().__init__()
        # Input: [B, 1, 40, 22]
        self.conv1 = nn.Conv2d(1, 16, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(16)
        self.pool1 = nn.MaxPool2d((2, 2)) # -> [16, 20, 11]

        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(32)
        self.pool2 = nn.MaxPool2d((2, 2)) # -> [32, 10, 5]

        self.conv3 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.bn3 = nn.BatchNorm2d(64)
        self.pool3 = nn.AdaptiveAvgPool2d((4, 4)) # -> [64, 4, 4] = 1024 features

        self.dropout = nn.Dropout(0.3)
        self.fc1 = nn.Linear(64 * 4 * 4, 64)
        self.fc2 = nn.Linear(64, num_classes)

    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = self.pool1(x)
        x = F.relu(self.bn2(self.conv2(x)))
        x = self.pool2(x)
        x = F.relu(self.bn3(self.conv3(x)))
        x = self.pool3(x)
        x = torch.flatten(x, 1)
        x = self.dropout(x)
        x = F.relu(self.fc1(x))
        return self.fc2(x)

def run_test():
    dm = DatasetManager()
    fe = AudioFeatureExtractor()
    aug = AudioAugmentor()

    raw_claps, raw_noises = dm.load_dataset("default")
    print(f"[*] Raw Claps: {len(raw_claps)}, Raw Noises: {len(raw_noises)}")

    aug_claps = []
    for c in raw_claps:
        aug_claps.extend(aug.augment_sample(c, bg_noises=raw_noises, count=10))

    aug_noises = []
    for n in raw_noises:
        aug_noises.extend(aug.augment_sample(n, bg_noises=None, count=10))

    # Cân bằng
    target_count = min(len(aug_claps), len(aug_noises))
    aug_claps = aug_claps[:target_count]
    aug_noises = aug_noises[:target_count]
    print(f"[*] Balanced Samples: {len(aug_claps)} claps, {len(aug_noises)} noises (Total: {target_count*2})")

    X_feats, X_mels, y = [], [], []
    for audio in aug_claps:
        X_feats.append(fe.compute_feature_vector(audio))
        X_mels.append(fe.compute_mel_spectrogram(audio))
        y.append(1)

    for audio in aug_noises:
        X_feats.append(fe.compute_feature_vector(audio))
        X_mels.append(fe.compute_mel_spectrogram(audio))
        y.append(0)

    X_feats = np.array(X_feats, dtype=np.float32)
    X_mels = np.array(X_mels, dtype=np.float32)
    y = np.array(y, dtype=np.int64)

    idx_tr, idx_val = train_test_split(np.arange(len(y)), test_size=0.25, random_state=42, stratify=y)

    # 1. Test Sklearn
    scaler = StandardScaler()
    X_tr_sc = scaler.fit_transform(X_feats[idx_tr])
    X_val_sc = scaler.transform(X_feats[idx_val])
    sk_clf = ExtraTreesClassifier(n_estimators=100, max_depth=12, random_state=42)
    sk_clf.fit(X_tr_sc, y[idx_tr])
    sk_preds = sk_clf.predict(X_val_sc)
    print(f"[*] Sklearn Accuracy: {accuracy_score(y[idx_val], sk_preds):.2%}, Precision: {precision_score(y[idx_val], sk_preds):.2%}, Recall: {recall_score(y[idx_val], sk_preds):.2%}")

    # 2. Test Improved CNN
    device = torch.device("cpu")
    model = ImprovedClapCNN().to(device)
    crit = nn.CrossEntropyLoss()
    opt = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)

    t_X_tr = torch.from_numpy(X_mels[idx_tr]).unsqueeze(1).float()
    t_y_tr = torch.from_numpy(y[idx_tr]).long()
    t_X_val = torch.from_numpy(X_mels[idx_val]).unsqueeze(1).float()
    t_y_val = torch.from_numpy(y[idx_val]).long()

    bs = 32
    for ep in range(25):
        perm = torch.randperm(t_X_tr.size(0))
        for b in range(int(np.ceil(len(t_X_tr)/bs))):
            idx = perm[b*bs:(b+1)*bs]
            opt.zero_grad()
            out = model(t_X_tr[idx])
            loss = crit(out, t_y_tr[idx])
            loss.backward()
            opt.step()

    model.eval()
    with torch.no_grad():
        val_preds = torch.argmax(model(t_X_val), dim=1).numpy()
        print(f"[*] Improved CNN Accuracy: {accuracy_score(y[idx_val], val_preds):.2%}, Precision: {precision_score(y[idx_val], val_preds):.2%}, Recall: {recall_score(y[idx_val], val_preds):.2%}")

if __name__ == "__main__":
    run_test()
