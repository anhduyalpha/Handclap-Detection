#!/usr/bin/env python3
"""
==============================================================================
  🔥 HANDCLAP AI - TRAINING STUDIO PRO LAUNCHER (WINDOWS)
==============================================================================
  Khởi chạy trọn gói Studio Huấn Luyện mô hình AI trên máy tính Windows:
  - Backend Training API & Live Sandbox: http://localhost:8001
  - Frontend Studio Web App:             http://localhost:5174/training.html
==============================================================================
"""

import os
import sys
import time
import shutil
import subprocess
from pathlib import Path

# Đảm bảo UTF-8 trên console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"

def find_python_executable() -> str:
    candidate_paths = [
        ROOT_DIR / ".venv" / "Scripts" / "python.exe",
        ROOT_DIR / "venv" / "Scripts" / "python.exe",
        ROOT_DIR / ".venv" / "bin" / "python",
    ]
    for path in candidate_paths:
        if path.exists():
            return str(path)
    return sys.executable

def find_npm_executable() -> str:
    if os.name == "nt":
        return shutil.which("npm.cmd") or "npm.cmd"
    return shutil.which("npm") or "npm"

import socket

def wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 15.0) -> bool:
    """Chờ cổng backend mở kết nối TCP thành công trước khi mở trình duyệt"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            time.sleep(0.3)
    return False

def main():
    print("=" * 68)
    print("  🔥 HANDCLAP AI - TRAINING STUDIO PRO (WINDOWS EDITION)")
    print("=" * 68)
    print("  🌐 Studio URL:  http://localhost:5174/training.html")
    print("  📡 Backend API: http://localhost:8001 (Docs: /docs)")
    print("  🔄 Auto-Sync:   Tự động xuất Checkpoint khi Huấn Luyện Xong")
    print("=" * 68)

    python_exec = find_python_executable()
    npm_cmd = find_npm_executable()

    print(f"[*] Python Runtime: {python_exec}")
    print(f"[*] NPM Runtime:    {npm_cmd}")

    # Thiết lập biến môi trường cho Training Studio
    env = os.environ.copy()
    env["VITE_PORT"] = "5174"
    env["VITE_BACKEND_PORT"] = "8001"

    # 1. Khởi động Backend Studio (:8001) trước
    print("[*] Khởi động Training Studio Backend Server (:8001)...")
    backend_proc = subprocess.Popen(
        [python_exec, "run_training_server.py"],
        cwd=str(BACKEND_DIR),
        env=env
    )

    # Chờ Backend mở cổng :8001 hoàn toàn
    print("[*] Đang chờ Backend khởi tạo PyTorch & mở cổng :8001...")
    if wait_for_port(8001, timeout=15.0):
        print("[+] Backend :8001 đã sẵn sàng kết nối!")
    else:
        print("[!] Cảnh báo: Backend mất nhiều thời gian hơn dự kiến, đang tiếp tục khởi chạy Frontend...")

    # 2. Khởi động Frontend Studio (:5174)
    print("[*] Khởi động Training Studio Frontend (:5174)...")
    frontend_proc = subprocess.Popen(
        [npm_cmd, "run", "dev:training"],
        cwd=str(FRONTEND_DIR),
        env=env
    )

    print("\n🎉 Training Studio Pro đã sẵn sàng!")
    print("👉 Mở trình duyệt tại: http://localhost:5174/training.html")
    print("[+] Nhấn Ctrl+C trong terminal này để dừng Studio.\n")

    def cleanup(signum=None, frame=None):
        print("\n[*] Đang tắt Training Studio...")
        try:
            if backend_proc.poll() is None:
                backend_proc.terminate()
            if frontend_proc.poll() is None:
                frontend_proc.terminate()
            time.sleep(0.5)
        except Exception:
            pass
        print("[+] Đã dừng Training Studio thành công.")
        sys.exit(0)

    try:
        import signal
        signal.signal(signal.SIGINT, cleanup)
        signal.signal(signal.SIGTERM, cleanup)
    except Exception:
        pass

    try:
        while True:
            time.sleep(0.5)
            if backend_proc.poll() is not None:
                print(f"[!] Backend Studio đã dừng (Exit code: {backend_proc.returncode})")
                break
            if frontend_proc.poll() is not None:
                print(f"[!] Frontend Studio đã dừng (Exit code: {frontend_proc.returncode})")
                break
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()

if __name__ == "__main__":
    main()
