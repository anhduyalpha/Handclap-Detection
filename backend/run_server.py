import uvicorn
import sys
import os
from pathlib import Path

# Thêm thư mục hiện tại vào PYTHONPATH
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

if __name__ == "__main__":
    # Tắt uvicorn auto-reload để tránh restart vòng lặp vô tận khi lưu audio/checkpoints trên server Linux
    use_reload = os.getenv("UVICORN_RELOAD", "false").lower() in ("true", "1", "yes")

    print("=========================================================")
    print("  🚀 HandClap Detection & Smart Light Server Starting   ")
    print("  📡 WebSocket: ws://0.0.0.0:8000/ws/audio              ")
    print("  🌐 REST API:  http://0.0.0.0:8000/docs                ")
    print(f"  ⚡ Live Model Hot-Reload: ACTIVE | Uvicorn Reload: {use_reload}")
    print("=========================================================")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=use_reload,
        log_level="info",
        timeout_keep_alive=30
    )
