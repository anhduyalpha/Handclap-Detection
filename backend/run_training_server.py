import uvicorn
import sys
from pathlib import Path

# Thêm thư mục hiện tại vào PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent))

if __name__ == "__main__":
    print("=========================================================")
    print("  🔥 HandClap Training Studio Backend Starting (Windows) ")
    print("  📡 WebSocket (Sandbox): ws://localhost:8001/ws/audio   ")
    print("  🌐 REST API:            http://localhost:8001/docs     ")
    print("=========================================================")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
