#!/bin/bash
# ==============================================================================
# Script theo dõi trạng thái và log thời gian thực của HandClap Detection
# ==============================================================================

SERVICE_NAME="handclap"

echo "=================================================================="
echo "  📊 TRẠNG THÁI DỊCH VỤ: ${SERVICE_NAME}"
echo "=================================================================="
sudo systemctl status "${SERVICE_NAME}" --no-pager

echo ""
echo "=================================================================="
echo "  📜 ĐANG THEO DÕI LOG THỜI GIAN THỰC (Bấm Ctrl+C để thoát)      "
echo "=================================================================="
journalctl -u "${SERVICE_NAME}" -f
