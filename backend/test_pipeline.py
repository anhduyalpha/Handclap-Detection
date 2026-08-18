import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.training.trainer import PersonalModelTrainer
from app.core.live_engine import live_engine

def run_test():
    print("Testing PersonalModelTrainer...")
    trainer = PersonalModelTrainer()
    meta = trainer.train_profile("default", augment_factor=6, cnn_epochs=5)
    print(f"Training completed successfully! Metrics: {meta}")

    print("Testing LiveDetectionEngine...")
    import numpy as np
    dummy_chunk = np.zeros(512, dtype=np.float32)
    res = live_engine.process_chunk(dummy_chunk)
    print(f"Live engine processed chunk successfully! Result: {res}")
    print("All backend tests passed!")

if __name__ == "__main__":
    run_test()
