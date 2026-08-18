#!/usr/bin/env bash
# ==============================================================================
#  HandClap Detection & Smart Light Web App - Linux/macOS Launcher
# ==============================================================================

set -e

# Chuyển về thư mục chứa script
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "=================================================================="
echo "  👏 HANDCLAP DETECTION & SMART LIGHT WEB APP (Linux Launcher)"
echo "=================================================================="

# 1. Kiểm tra môi trường ảo Python
VENV_PYTHON=""
if [ -f "$ROOT_DIR/.venv/bin/python" ]; then
    VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
elif [ -f "$ROOT_DIR/venv/bin/python" ]; then
    VENV_PYTHON="$ROOT_DIR/venv/bin/python"
fi

if [ -z "$VENV_PYTHON" ]; then
    echo "[!] Không tìm thấy môi trường ảo .venv!"
    echo "[*] Đang tự động chạy setup.sh để thiết lập môi trường..."
    chmod +x "$ROOT_DIR/setup.sh" 2>/dev/null || true
    bash "$ROOT_DIR/setup.sh"
    VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
fi

# 2. Kiểm tra Node.js & NPM
if ! command -v node &> /dev/null; then
    echo "[!] CẢNH BÁO: Không tìm thấy 'node'. Vui lòng cài đặt Node.js (v18+) để chạy Frontend."
fi

if ! command -v npm &> /dev/null; then
    echo "[!] CẢNH BÁO: Không tìm thấy 'npm'. Vui lòng cài đặt npm."
fi

# 3. Chạy Launcher cross-platform bằng Python trong .venv
echo "[*] Khởi động ứng dụng..."
exec "$VENV_PYTHON" "$ROOT_DIR/run.py" "$@"
