#!/bin/bash
# ==============================================================================
# Script khởi động lại dịch vụ HandClap Detection (Đảm bảo Web Server sẵn sàng 100%)
# ==============================================================================

SERVICE_NAME="handclap"
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$SERVER_IP" ] && SERVER_IP="127.0.0.1"

echo "[*] Đang gửi lệnh khởi động lại dịch vụ ${SERVICE_NAME}..."
sudo systemctl restart "${SERVICE_NAME}"

echo -n "[*] Đang đợi Web Server và API khởi động hoàn tất"
MAX_RETRIES=40
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
    echo -e " \033[33m[ĐANG KHỞI ĐỘNG]\033[0m"
    echo "[*] Kiểm tra trạng thái dịch vụ:"
    sudo systemctl status ${SERVICE_NAME} --no-pager
    echo "=================================================================="
    echo "  🌐 Web Dashboard: http://${SERVER_IP}:8000"
    echo "=================================================================="
fi
