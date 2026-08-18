import sys
from pathlib import Path

# Thêm backend vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings
from app.smart_home.action_dispatcher import action_dispatcher

def test_webhook_config():
    print(f"[*] Default Webhook URL configured: {settings.light.webhook_url}")
    assert settings.light.webhook_url == "http://192.168.2.171:8123/api/webhook/vo_tay_toggle_den"

    # Test dispatching pattern without blocking
    action_dispatcher.dispatch_pattern("single", 1, [])
    print("[PASS] dispatch_pattern('single', 1, []) called successfully with external webhook thread launched!")

if __name__ == "__main__":
    test_webhook_config()
    print("[SUCCESS] Webhook test completed!")
