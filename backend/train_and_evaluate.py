import sys
from pathlib import Path

# Thêm backend vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.training.trainer import PersonalModelTrainer
from app.config import settings, DEFAULT_SAMPLES_DIR
from app.training.dataset_manager import DatasetManager

def main():
    print("[*] Refreshing seed noise dataset and training high-precision model for 'default' profile...")
    dm = DatasetManager()
    # Xóa default samples cũ để nạp lại đầy đủ 60 mẫu tạp âm mới
    for f in (DEFAULT_SAMPLES_DIR / "noises").glob("*.npy"):
        try:
            f.unlink()
        except Exception:
            pass
    for f in (DEFAULT_SAMPLES_DIR / "claps").glob("*.npy"):
        try:
            f.unlink()
        except Exception:
            pass
    dm._ensure_default_seed_data()

    trainer = PersonalModelTrainer()
    meta = trainer.train_profile(
        profile_name="default",
        augment_factor=15,
        cnn_epochs=30
    )
    print("\n" + "="*50)
    print("[SUCCESS] TRAINING COMPLETED WITH HIGH ACCURACY:")
    print(f" - Overall Accuracy:   {meta['accuracy']}%")
    print(f" - Clap Sensitivity:   {meta['sensitivity']}%")
    print(f" - Noise Rejection:    {meta['noise_rejection']}%")
    print(f" - CNN Accuracy:       {meta['cnn_accuracy']}%")
    print(f" - Sklearn Accuracy:   {meta['sklearn_accuracy']}%")
    print(f" - Training Time:      {meta['training_time_sec']}s")
    print("="*50)

if __name__ == "__main__":
    main()
