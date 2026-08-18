#!/usr/bin/env python3
"""
Diagnostic Script for Dell Linux Server (192.168.2.171)
Kiểm tra toàn diện: Micro phần cứng ALC3246, API Routes và Segmenter.
"""
import sys
import subprocess
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

def main():
    print("=" * 65)
    print("  🐧 KIỂM TRA HỆ THỐNG SERVER DELL (MICRO & TRAINING API)")
    print("=" * 65)

    # 1. Kiểm tra Segmenter
    try:
        from app.training.segmenter import segmenter
        print("[+] 1. Segmenter Module:       OK (Đã nạp thành công)")
    except Exception as e:
        print(f"[-] 1. Segmenter Module LỖI:  {e}")

    # 2. Kiểm tra API Routes
    try:
        from app.api import routes_training
        paths = [getattr(r, "path", "") for r in routes_training.router.routes]
        if "/api/training/record-continuous-session" in paths:
            print("[+] 2. Route record-continuous: OK (Đã có route)")
        else:
            print("[-] 2. Route record-continuous: THIẾU (File routes_training.py chưa cập nhật!)")
    except Exception as e:
        print(f"[-] 2. API Routes LỖI:        {e}")

    # 3. Kiểm tra Micro ALSA (arecord)
    print("[*] 3. Đang thử thu âm 1.0s từ Micro Server ALC3246...")
    try:
        cmd = ["arecord", "-d", "1", "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "raw", "-q"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        raw_bytes, _ = proc.communicate(timeout=3.0)
        if raw_bytes and len(raw_bytes) >= 16000 * 2:
            print(f"[+] 3. Micro Server ALC3246:   OK ({len(raw_bytes)} bytes thu được)")
        else:
            print("[-] 3. Micro Server ALC3246:   Không thu được dữ liệu (Kiểm tra alsamixer/mute)")
    except Exception as e:
        print(f"[-] 3. arecord Test LỖI:      {e}")

    print("=" * 65)
    print("Nếu tất cả đều [OK], bạn chỉ cần chạy: ./run.sh")
    print("=" * 65)

if __name__ == "__main__":
    main()
