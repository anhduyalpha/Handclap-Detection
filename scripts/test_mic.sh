#!/bin/bash
# ==============================================================================
# Script kiểm tra trực tiếp Micro và thanh đo âm lượng (VU-meter) thời gian thực
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"

# Tạm dừng service ngầm nếu đang chạy để nhường quyền truy cập Micro
if systemctl is-active --quiet handclap; then
    echo "[*] Tạm dừng dịch vụ handclap ngầm để mở Micro độc quyền..."
    sudo systemctl stop handclap
    WAS_RUNNING=1
fi

echo "[*] Đang khởi động bộ kiểm tra Micro..."
PYTHONPATH="${PROJECT_DIR}/backend" ${PYTHON_BIN} "${PROJECT_DIR}/scripts/test_mic.py"

if [ "$WAS_RUNNING" = "1" ]; then
    echo "[*] Đang bật lại dịch vụ handclap ngầm..."
    sudo systemctl start handclap
fi
