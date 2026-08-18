import sys
from pathlib import Path

# Thêm backend vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import torch
from app.api.routes_training import get_system_info
from app.training.trainer import PersonalModelTrainer
from app.config import CHECKPOINTS_DIR, settings

def test_system_info_endpoint():
    """Kiểm tra endpoint system-info trả về thông tin GPU/CPU"""
    data = get_system_info()
    assert "gpu_available" in data
    assert "gpu_name" in data
    assert "device" in data
    print(f"[PASS] System info: Device={data['device']}, GPU={data['gpu_name']}")

def test_gpu_or_cpu_trainer_execution():
    """Kiểm tra quy trình PersonalModelTrainer huấn luyện & xuất checkpoint CPU compatible"""
    trainer = PersonalModelTrainer(sample_rate=settings.audio.sample_rate)
    meta = trainer.train_profile(profile_name="default", augment_factor=3, cnn_epochs=3)
    
    assert "accuracy" in meta
    assert meta["accuracy"] > 50.0
    
    ckpt_dir = CHECKPOINTS_DIR / "default"
    assert (ckpt_dir / "model_cnn.pt").exists()
    assert (ckpt_dir / "model_sklearn.joblib").exists()
    assert (ckpt_dir / "scaler.joblib").exists()
    
    # Kiểm tra model PyTorch nạp được bằng CPU
    state_dict = torch.load(ckpt_dir / "model_cnn.pt", map_location="cpu")
    assert state_dict is not None
    print(f"[PASS] Trainer execution passed! Accuracy={meta['accuracy']}%")

if __name__ == "__main__":
    test_system_info_endpoint()
    test_gpu_or_cpu_trainer_execution()
    print("\n[SUCCESS] ALL REMOTE RECORDING & GPU TESTS PASSED!")
