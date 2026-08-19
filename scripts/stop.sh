#!/bin/bash
# ==============================================================================
# Script dừng dịch vụ HandClap Detection
# ==============================================================================

SERVICE_NAME="handclap"

echo "[*] Đang dừng dịch vụ ${SERVICE_NAME}..."
sudo systemctl stop "${SERVICE_NAME}"
echo "[+] Đã dừng dịch vụ thành công."
