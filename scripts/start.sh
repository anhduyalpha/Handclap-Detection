#!/bin/bash
# ==============================================================================
# Script khởi động dịch vụ HandClap Detection (Đảm bảo Web Server sẵn sàng 100%)
# ==============================================================================

SERVICE_NAME="handclap"
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$SERVER_IP" ] && SERVER_IP="127.0.0.1"

if systemctl is-active --quiet "${SERVICE_NAME}"; then
    echo "[!] Dịch vụ ${SERVICE_NAME} đã đang chạy!"
else
    echo "[*] Đang gửi lệnh khởi động dịch vụ ${SERVICE_NAME}..."
    sudo systemctl start "${SERVICE_NAME}"
fi

echo -n "[*] Đang đợi Web Server và API khởi động hoàn tất"
MAX_RETRIES=30
RETRY=0
READY=0

while [ $RETRY -lt $MAX_RETRIES ]; do
    if curl -s -m 1 http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
        READY=1
        break
    fi
    echo -n "."
    sleep 0.5
    RETRY=$((RETRY + 1))
done

if [ $READY -eq 1 ]; then
    echo -e " \033[32m[SẴN SÀNG]\033[0m"
    echo "=================================================================="
    echo "  🎉 HỆ THỐNG HANDCLAP DETECTION ĐÃ HOẠT ĐỘNG HOÀN TOÀN!"
    echo "  🌐 Web Dashboard: http://${SERVER_IP}:8000"
    echo "  📊 API Docs:      http://${SERVER_IP}:8000/docs"
    echo "=================================================================="
else
    echo -e " \033[31m[CHƯA PHẢN HỒI]\033[0m"
    echo "[!] Web Server chưa phản hồi sau 15s. Xem log chi tiết:"
    journalctl -u ${SERVICE_NAME} -n 20 --no-pager
fi
