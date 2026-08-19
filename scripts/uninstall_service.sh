#!/bin/bash
# ==============================================================================
# Script gỡ bỏ dịch vụ Systemd HandClap Detection
# ==============================================================================

SERVICE_NAME="handclap"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "[*] Đang dừng và gỡ bỏ dịch vụ ${SERVICE_NAME}..."
sudo systemctl stop "${SERVICE_NAME}" || true
sudo systemctl disable "${SERVICE_NAME}" || true

if [ -f "${SERVICE_FILE}" ]; then
    sudo rm -f "${SERVICE_FILE}"
    sudo systemctl daemon-reload
    echo "[+] Đã xóa file dịch vụ ${SERVICE_FILE} thành công."
fi

echo "[+] Đã gỡ bỏ dịch vụ khỏi hệ thống."
