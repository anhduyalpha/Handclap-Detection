import time
from typing import Dict, Any, List

RGB_PALETTE = [
    "#00e5ff", # Cyan Neon
    "#ff007f", # Magenta Neon
    "#00ff66", # Electric Lime
    "#ffaa00", # Warm Amber
    "#7928ca", # Electric Violet
    "#ffffff", # Pure White
    "#ff3333", # Crimson Red
    "#0088ff"  # Royal Blue
]

class VirtualSmartBulb:
    """
    Quản lý trạng thái bóng đèn thông minh mô phỏng (Virtual Smart Bulb).
    Bao gồm: Power (Bật/Tắt), Độ sáng (0-100%), Màu sắc (RGB Hex), Chế độ hoạt động (Solid, Rainbow, Pulse, Party).
    """
    def __init__(self):
        self.power: bool = True
        self.brightness: int = 85
        self.color_index: int = 0
        self.color: str = RGB_PALETTE[0]
        self.mode: str = "solid"
        self.last_triggered_by: str = "init"
        self.last_updated: float = time.time()

    def get_state(self) -> Dict[str, Any]:
        return {
            "power": self.power,
            "brightness": self.brightness,
            "color": self.color,
            "mode": self.mode,
            "last_triggered_by": self.last_triggered_by,
            "last_updated": self.last_updated
        }

    def toggle_power(self, source: str = "clap_single") -> Dict[str, Any]:
        self.power = not self.power
        self.last_triggered_by = source
        self.last_updated = time.time()
        return self.get_state()

    def next_color(self, source: str = "clap_double") -> Dict[str, Any]:
        if not self.power:
            self.power = True
        self.color_index = (self.color_index + 1) % len(RGB_PALETTE)
        self.color = RGB_PALETTE[self.color_index]
        self.mode = "solid"
        self.last_triggered_by = source
        self.last_updated = time.time()
        return self.get_state()

    def party_mode(self, source: str = "clap_triple") -> Dict[str, Any]:
        if not self.power:
            self.power = True
        self.mode = "party" if self.mode != "party" else "solid"
        self.last_triggered_by = source
        self.last_updated = time.time()
        return self.get_state()

    def set_brightness(self, val: int, source: str = "manual") -> Dict[str, Any]:
        self.brightness = max(0, min(100, val))
        self.last_triggered_by = source
        self.last_updated = time.time()
        return self.get_state()

    def set_color(self, hex_color: str, source: str = "manual") -> Dict[str, Any]:
        self.color = hex_color
        self.mode = "solid"
        self.last_triggered_by = source
        self.last_updated = time.time()
        return self.get_state()

    def set_power(self, power: bool, source: str = "manual") -> Dict[str, Any]:
        self.power = power
        self.last_triggered_by = source
        self.last_updated = time.time()
        return self.get_state()

# Global singleton
virtual_bulb = VirtualSmartBulb()
