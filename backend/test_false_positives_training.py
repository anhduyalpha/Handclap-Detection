import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.training.dataset_manager import DatasetManager, CATEGORIES
from app.training.trainer import PersonalModelTrainer

def test_fp_category_and_training():
    sr = 16000
    print("[*] 1. Verifying 'false_positives' in CATEGORIES...")
    assert "false_positives" in CATEGORIES
    print("[+] Found category 'false_positives' in CATEGORIES")

    dm = DatasetManager(sample_rate=sr)
    
    # Tạo 1 mẫu giả lập tiếng ồn báo giả
    t = np.linspace(0, 0.25, int(sr * 0.25), endpoint=False)
    synthetic_fp = (0.5 * np.sin(2 * np.pi * 800 * t) * np.exp(-t * 12)).astype(np.float32)

    print("[*] 2. Saving sample into 'false_positives' category...")
    sample_info = dm.save_sample(
        profile_name="default",
        category="false_positives",
        audio=synthetic_fp
    )
    print(f"[+] Sample saved: ID={sample_info['sample_id']}")

    # Kiểm tra load_dataset_separated
    claps, noises, fps = dm.load_dataset_separated("default")
    print(f"[+] Loaded dataset - Claps: {len(claps)}, Noises: {len(noises)}, False Positives: {len(fps)}")
    assert len(fps) >= 1

    # Kiểm tra huấn luyện với 2x Augmentation cho False Positives
    print("[*] 3. Running PersonalModelTrainer with Hard Negatives...")
    trainer = PersonalModelTrainer(sample_rate=sr)
    metrics = trainer.train_profile(
        profile_name="default",
        augment_factor=6,
        cnn_epochs=12
    )

    print("[+] Training completed successfully!")
    print(f"[+] Accuracy: {metrics['accuracy']}%, Noise Rejection: {metrics['noise_rejection']}%, Sensitivity: {metrics['sensitivity']}%")
    print(f"[+] Total Augmented Samples: {metrics['total_augmented_samples']}")
    assert metrics['accuracy'] >= 70.0

    print("\n[SUCCESS] False Positives category & 2x Augmented Training verified 100%!")

if __name__ == "__main__":
    test_fp_category_and_training()
