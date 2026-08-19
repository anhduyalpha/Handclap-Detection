#!/bin/bash
# ==============================================================================
# Script cài đặt và cấu hình HandClap Detection tự động khởi động cùng Server (Systemd)
# Tương thích: Ubuntu 20.04/22.04/24.04, Debian 11/12
# ==============================================================================

set -e

# Lấy đường dẫn thư mục gốc dự án
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CURRENT_USER="$(whoami)"
SERVICE_NAME="handclap"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"

echo "=================================================================="
echo "  👏 CÀI ĐẶT DỊCH VỤ CHẠY NGẦM & BOOT CÙNG SERVER (HANDCLAP AI)  "
echo "  📁 Thư mục dự án: ${PROJECT_DIR}"
echo "  👤 Người dùng:    ${CURRENT_USER}"
echo "  🐍 Python Venv:   ${PYTHON_BIN}"
echo "=================================================================="

# 1. Kiểm tra môi trường ảo Python
if [ ! -f "${PYTHON_BIN}" ]; then
    echo "[*] Chưa tìm thấy .venv. Đang tạo môi trường ảo Python..."
    python3 -m venv "${PROJECT_DIR}/.venv"
    source "${PROJECT_DIR}/.venv/bin/activate"
    pip install --upgrade pip
    pip install -r "${PROJECT_DIR}/backend/requirements.txt"
fi

# 2. Build Frontend tĩnh tối ưu cho Production (nếu có nodejs/npm)
if command -v npm &> /dev/null && [ -d "${PROJECT_DIR}/frontend" ]; then
    echo "[*] Đang đóng gói Frontend (Production Build)..."
    cd "${PROJECT_DIR}/frontend"
    if [ ! -d "node_modules" ]; then
        npm install
    fi
    npm run build
    cd "${PROJECT_DIR}"
    echo "[+] Đã build Frontend tĩnh vào: frontend/dist/"
fi

# 3. Đảm bảo người dùng thuộc nhóm audio để có quyền mở Micro phần cứng
if ! groups "${CURRENT_USER}" | grep -q '\baudio\b'; then
    echo "[*] Thêm user '${CURRENT_USER}' vào nhóm 'audio' để truy cập Micro..."
    sudo usermod -aG audio "${CURRENT_USER}"
fi

# 4. Tạo file cấu hình dịch vụ Systemd
echo "[*] Đang tạo cấu hình Systemd: ${SERVICE_FILE}..."

sudo bash -c "cat <<EOF > ${SERVICE_FILE}
[Unit]
Description=HandClap Detection & Smart Light 24/7 Service
After=network.target sound.target

[Service]
Type=simple
User=${CURRENT_USER}
Group=${CURRENT_USER}
WorkingDirectory=${PROJECT_DIR}/backend
ExecStart=${PYTHON_BIN} run_server.py
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=${PROJECT_DIR}/backend
StandardOutput=journal
StandardError=journal
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF"

# 5. Kích hoạt và bật tự khởi động cùng máy
echo "[*] Nạp cấu hình và kích hoạt tự động chạy khi khởi động server..."
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo ""
echo "=================================================================="
echo "  🎉 CÀI ĐẶT THÀNH CÔNG! DỊCH VỤ ĐÃ HOẠT ĐỘNG 24/7 TRÊN SERVER    "
echo "  🌐 Giao diện Web: http://$(hostname -I | awk '{print $1}'):8000"
echo "  📡 API Docs:      http://$(hostname -I | awk '{print $1}'):8000/docs"
echo "=================================================================="
echo ""
echo "Các lệnh quản trị tiện lợi:"
echo "  - Xem trạng thái:       sudo systemctl status ${SERVICE_NAME}"
echo "  - Xem log thời gian thực: journalctl -u ${SERVICE_NAME} -f"
echo "  - Khởi động lại:        sudo systemctl restart ${SERVICE_NAME}"
echo "  - Dừng dịch vụ:         sudo systemctl stop ${SERVICE_NAME}"
echo "=================================================================="
