#!/usr/bin/env python3
"""
==============================================================================
  👏 HANDCLAP DETECTION - WINDOWS OFFLINE TRAINING STUDIO
==============================================================================
  Huấn luyện mô hình AI phân loại vỗ tay trên máy Windows (tận dụng CPU/GPU mạnh)
  và tự động xuất Model sang thư mục Checkpoint.
  Khi WinSCP đang bật đồng bộ (Ctrl+U), Server Linux sẽ tự động nạp Model mới
  sau 0.1 giây mà KHÔNG CẦN khởi động lại Server!
==============================================================================
"""

import os
import sys
import time
import argparse
from pathlib import Path

# Đảm bảo in UTF-8 không bị lỗi mã hoá trên Windows Console (cp1252)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thêm đường dẫn backend vào sys.path
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.training.trainer import PersonalModelTrainer
from app.config import settings, CHECKPOINTS_DIR, DEFAULT_SAMPLES_DIR, USER_PROFILES_DIR

def print_banner():
    print("=" * 68)
    print("  🔥 WINDOWS OFFLINE MODEL TRAINING STUDIO - HANDCLAP DETECTION")
    print("=" * 68)
    print(f"[*] Thư mục mẫu gốc:      {DEFAULT_SAMPLES_DIR}")
    print(f"[*] Thư mục mẫu cá nhân:  {USER_PROFILES_DIR}")
    print(f"[*] Thư mục xuất Model:   {CHECKPOINTS_DIR}")
    print("=" * 68)

def main():
    parser = argparse.ArgumentParser(description="Huấn luyện mô hình vỗ tay trên máy Windows")
    parser.add_argument("--profile", type=str, default=None, help="Tên profile model")
    parser.add_argument("--epochs", type=int, default=None, help="Số epochs CNN")
    parser.add_argument("--augment", type=int, default=None, help="Hệ số Data Augmentation")
    args = parser.parse_args()

    print_banner()

    # Nhập thông tin hoặc lấy từ arguments
    if args.profile is not None:
        profile_name = args.profile
    else:
        try:
            profile_name = input("[?] Tên Profile mô hình (mặc định: 'default'): ").strip() or "default"
        except EOFError:
            profile_name = "default"
    
    if args.epochs is not None:
        cnn_epochs = args.epochs
    else:
        try:
            epochs_input = input("[?] Số Epochs huấn luyện CNN (mặc định: 25): ").strip()
            cnn_epochs = int(epochs_input) if epochs_input.isdigit() else 25
        except EOFError:
            cnn_epochs = 25

    if args.augment is not None:
        augment_factor = args.augment
    else:
        try:
            aug_input = input("[?] Hệ số nhân bản dữ liệu Data Augmentation (mặc định: 12): ").strip()
            augment_factor = int(aug_input) if aug_input.isdigit() else 12
        except EOFError:
            augment_factor = 12

    print("\n" + "-" * 68)
    print(f"[*] Bắt đầu huấn luyện Profile: '{profile_name}'...")
    print(f"[*] Cấu hình: Epochs={cnn_epochs}, AugmentFactor={augment_factor}x")
    print("-" * 68)

    start_time = time.time()
    try:
        trainer = PersonalModelTrainer(sample_rate=settings.audio.sample_rate)
        results = trainer.train_profile(
            profile_name=profile_name,
            augment_factor=augment_factor,
            cnn_epochs=cnn_epochs
        )
        elapsed = time.time() - start_time

        print("\n" + "=" * 68)
        print("  🎉 HUẤN LUYỆN THÀNH CÔNG RỰC RỠ!")
        print("=" * 68)
        print(f"  🏆 Độ chính xác (Accuracy): {results.get('accuracy', 100.0):.2f}%")
        print(f"  ⏱️  Thời gian huấn luyện:     {elapsed:.2f} giây")
        print(f"  📊 Tổng số mẫu sau Augment:  {results.get('total_augmented_samples', 0)}")
        print(f"  💾 Thư mục đã lưu:           {CHECKPOINTS_DIR / profile_name}")
        print("=" * 68)
        print("\n👉 NẾU WINSCP ĐANG BẬT ĐỒNG BỘ (Ctrl+U):")
        print("   File model (.pt & .joblib) đã được tự động đẩy sang Server Dell!")
        print("   Server Dell sẽ tự động Hot-Reload mô hình mới ngay trong RAM mà không cần khởi động lại!\n")

    except Exception as e:
        print(f"\n[X] LỖI trong quá trình huấn luyện: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
