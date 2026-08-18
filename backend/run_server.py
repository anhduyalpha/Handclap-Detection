import uvicorn
import sys
from pathlib import Path

# Thêm thư mục hiện tại vào PYTHONPATH
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

if __name__ == "__main__":
    print("=========================================================")
    print("  🚀 HandClap Detection & Smart Light Server Starting   ")
    print("  📡 WebSocket: ws://localhost:8000/ws/audio            ")
    print("  🌐 REST API:  http://localhost:8000/docs              ")
    print("  ⚡ Auto Hot-Reload: ACTIVE (Tự động nạp code khi sửa) ")
    print("=========================================================")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(BACKEND_DIR / "app"), str(BACKEND_DIR / "data" / "checkpoints")],
        reload_includes=["*.py", "*.pt", "*.joblib", "*.json"],
        log_level="info"
    )
