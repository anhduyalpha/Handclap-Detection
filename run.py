"""
Cross-Platform Launcher for HandClap Detection & Smart Light Web App
Tương thích hoàn toàn Windows, Linux, macOS.
Khởi động đồng thời cả Backend (FastAPI :8000) và Frontend (Vite :5173).
"""
import subprocess
import sys
import time
import os
import signal
import shutil
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"

def find_python_executable() -> str:
    """Tự động tìm kiếm Python trong .venv tùy theo hệ điều hành (Windows vs Linux/macOS)"""
    candidate_paths = [
        ROOT_DIR / ".venv" / "bin" / "python",         # Linux/macOS venv
        ROOT_DIR / ".venv" / "bin" / "python3",        # Linux/macOS venv (alternative)
        ROOT_DIR / ".venv" / "Scripts" / "python.exe", # Windows venv
        ROOT_DIR / "venv" / "bin" / "python",          # Linux/macOS venv without dot
        ROOT_DIR / "venv" / "Scripts" / "python.exe",  # Windows venv without dot
    ]
    for path in candidate_paths:
        if path.exists() and os.access(path, os.X_OK if os.name != "nt" else os.F_OK):
            return str(path)
            
    # Fallback về Python hiện tại
    return sys.executable

def find_npm_executable() -> str:
    """Tìm lệnh npm phù hợp theo OS"""
    if os.name == "nt":
        return shutil.which("npm.cmd") or "npm.cmd"
    return shutil.which("npm") or "npm"

def wait_for_backend_ready(backend_proc, timeout_sec: float = 25.0) -> bool:
    """Chờ cho đến khi Backend FastAPI thực sự mở port 8000 và phản hồi /api/health"""
    print("[*] Đang chờ Backend khởi tạo mô hình AI & mở cổng 8000...")
    start_t = time.time()
    while time.time() - start_t < timeout_sec:
        if backend_proc.poll() is not None:
            print(f"\n[!] LỖI: Backend Server đã dừng đột ngột (Exit code: {backend_proc.returncode}).")
            return False
        try:
            req = urllib.request.Request("http://127.0.0.1:8000/api/health", headers={"User-Agent": "HandClapLauncher"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    print(f"[+] Backend đã sẵn sàng và đang lắng nghe tại http://127.0.0.1:8000 ({time.time() - start_t:.1f}s)")
                    return True
        except Exception:
            pass
        time.sleep(0.5)

    print(f"\n[!] CẢNH BÁO: Backend chưa phản hồi sau {timeout_sec}s, tiếp tục bật Frontend...")
    return True

def main():
    print("==================================================================")
    print("  👏 HANDCLAP DETECTION & SMART LIGHT WEB APP")
    print("  🖥️  Operating System:", "Windows" if os.name == "nt" else "Linux/POSIX")
    print("  🌐 Frontend URL: http://localhost:5173")
    print("  📡 Backend URL:  http://localhost:8000 (API Docs: /docs)")
    print("  ⚡ WebSocket:   ws://localhost:8000/ws/audio")
    print("==================================================================")

    python_exec = find_python_executable()
    npm_cmd = find_npm_executable()

    print(f"[*] Using Python: {python_exec}")
    print(f"[*] Using NPM:    {npm_cmd}")

    # 1. Khởi động Backend
    print("[*] Starting Backend Server...")
    backend_proc = subprocess.Popen(
        [python_exec, "run_server.py"],
        cwd=str(BACKEND_DIR)
    )

    # Chờ Backend mở cổng 8000 trước khi bật Frontend
    is_ready = wait_for_backend_ready(backend_proc, timeout_sec=25.0)
    if not is_ready:
        print("[!] Hãy thử chạy trực tiếp lệnh sau để kiểm tra lỗi thư viện:")
        print(f"    source .venv/bin/activate && python3 backend/run_server.py\n")
        sys.exit(1)

    # 2. Khởi động Frontend
    print("[*] Starting Frontend Vite Dev Server...")
    frontend_proc = subprocess.Popen(
        [npm_cmd, "run", "dev"],
        cwd=str(FRONTEND_DIR)
    )

    print("\n[+] Cả Backend và Frontend đã sẵn sàng!")
    print("[+] Nhấn Ctrl+C trong terminal để dừng ứng dụng.\n")

    def cleanup(signum=None, frame=None):
        print("\n[*] Đang tắt các tiến trình ứng dụng...")
        try:
            if backend_proc.poll() is None:
                backend_proc.terminate()
            if frontend_proc.poll() is None:
                frontend_proc.terminate()
                
            time.sleep(0.5)
            if backend_proc.poll() is None:
                backend_proc.kill()
            if frontend_proc.poll() is None:
                frontend_proc.kill()
        except Exception as e:
            print(f"[!] Warning during shutdown: {e}")
            
        print("[+] Đã dừng hệ thống thành công.")
        sys.exit(0)

    # Bắt tín hiệu dừng
    signal.signal(signal.SIGINT, cleanup)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, cleanup)

    try:
        while True:
            if backend_proc.poll() is not None:
                print("[!] Backend server đã dừng (Exit code:", backend_proc.returncode, ")")
                break
            if frontend_proc.poll() is not None:
                print("[!] Frontend server đã dừng (Exit code:", frontend_proc.returncode, ")")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()

if __name__ == "__main__":
    main()
