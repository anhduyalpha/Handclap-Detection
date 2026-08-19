#!/bin/bash
# ==============================================================================
# Script khởi động lại dịch vụ HandClap Detection
# ==============================================================================

SERVICE_NAME="handclap"

echo "[*] Đang khởi động lại dịch vụ ${SERVICE_NAME}..."
sudo systemctl restart "${SERVICE_NAME}"
sleep 1
if systemctl is-active --quiet "${SERVICE_NAME}"; then
    echo "[+] Dịch vụ ${SERVICE_NAME} đã khởi động lại thành công!"
    echo "🌐 Web Dashboard: http://$(hostname -I | awk '{print $1}'):8000"
else
    echo "[!] Có lỗi xảy ra. Kiểm tra log bằng lệnh: journalctl -u ${SERVICE_NAME} -n 20"
fi
