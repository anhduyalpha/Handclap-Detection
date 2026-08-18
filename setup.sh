#!/usr/bin/env bash
# ==============================================================================
#  HandClap Detection - One-Click Linux/macOS Setup Script
#  Tự động khởi tạo .venv, cài đặt backend dependencies và frontend npm packages.
# ==============================================================================

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "=================================================================="
echo "  🚀 HANDCLAP DETECTION - SETUP ENVIRONMENT (Linux/macOS)"
echo "=================================================================="

# 1. Kiểm tra Python 3
if ! command -v python3 &> /dev/null; then
    echo "[X] LỖI: Không tìm thấy 'python3'. Vui lòng cài đặt Python 3.9+ (vd: sudo apt install python3 python3-venv python3-pip)"
    exit 1
fi

PYTHON_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[+] Tìm thấy Python version: $PYTHON_VER"

# 2. Kiểm tra Node.js & NPM
if ! command -v npm &> /dev/null; then
    echo "[!] CẢNH BÁO: Không tìm thấy 'npm'. Bạn có thể cần cài đặt Node.js để chạy Frontend (vd: sudo apt install nodejs npm)"
fi

# 3. Tạo môi trường ảo .venv chuẩn Linux nếu chưa có hoặc đang dính file Windows
if [ ! -f "$ROOT_DIR/.venv/bin/python" ]; then
    echo "[*] Đang tạo mới môi trường ảo Python .venv chuẩn Linux..."
    rm -rf "$ROOT_DIR/.venv"
    python3 -m venv "$ROOT_DIR/.venv" || {
        echo "[X] Lỗi khi tạo venv. Hãy đảm bảo đã cài python3-venv (vd: sudo apt install python3-venv python3-pip -y)"
        exit 1
    }
    echo "[+] Đã tạo .venv thành công."
else
    echo "[+] Đã tồn tại môi trường ảo .venv."
fi

# 4. Cài đặt Python Dependencies
echo "[*] Đang nâng cấp pip và cài đặt thư viện Backend..."
"$ROOT_DIR/.venv/bin/python" -m pip install --upgrade pip
"$ROOT_DIR/.venv/bin/python" -m pip install -r "$ROOT_DIR/backend/requirements.txt"
echo "[+] Cài đặt Backend dependencies hoàn tất!"

# 5. Cài đặt Frontend NPM Dependencies
if [ -d "$ROOT_DIR/frontend" ] && command -v npm &> /dev/null; then
    echo "[*] Đang cài đặt thư viện Frontend (npm install)..."
    cd "$ROOT_DIR/frontend"
    npm install
    chmod -R +x node_modules/.bin 2>/dev/null || true
    cd "$ROOT_DIR"
    echo "[+] Cài đặt Frontend packages hoàn tất!"
fi

# 6. Cấp quyền thực thi cho các scripts
chmod +x "$ROOT_DIR/run.sh" "$ROOT_DIR/setup.sh" 2>/dev/null || true
chmod -R +x "$ROOT_DIR/frontend/node_modules/.bin" 2>/dev/null || true

echo "=================================================================="
echo "  🎉 CÀI ĐẶT THÀNH CÔNG!"
echo "  👉 Để khởi chạy ứng dụng: ./run.sh hoặc python3 run.py"
echo "  👉 Truy cập Web UI:       http://localhost:5173"
echo "  👉 Backend API Docs:      http://localhost:8000/docs"
echo "=================================================================="
