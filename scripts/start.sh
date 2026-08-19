#!/bin/bash
# ==============================================================================
# Script khởi động dịch vụ HandClap Detection
# ==============================================================================

SERVICE_NAME="handclap"

if systemctl is-active --quiet "${SERVICE_NAME}"; then
    echo "[!] Dịch vụ ${SERVICE_NAME} đã đang chạy!"
else
    echo "[*] Đang khởi động dịch vụ ${SERVICE_NAME}..."
    sudo systemctl start "${SERVICE_NAME}"
    sleep 1
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        echo "[+] Dịch vụ ${SERVICE_NAME} đã khởi động thành công!"
        echo "🌐 Web Dashboard: http://$(hostname -I | awk '{print $1}'):8000"
    else
        echo "[!] Không thể khởi động. Xem log: journalctl -u ${SERVICE_NAME} -n 20"
    fi
fi
