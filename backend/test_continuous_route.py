import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.main import app

def check_router_routes():
    print("[*] All routes in app.router.routes:")
    for r in app.router.routes:
        print(f" - {getattr(r, 'methods', 'WS')} {getattr(r, 'path', r)}")

if __name__ == "__main__":
    check_router_routes()
