import json
import asyncio
import threading
import logging
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Set, List, Optional
from ..core.live_engine import live_engine
from ..smart_home.virtual_bulb import virtual_bulb

logger = logging.getLogger("handclap.websocket")
router = APIRouter()

class ThreadSafeConnectionManager:
    """
    Quản lý các kết nối WebSocket đang mở giữa Web Client và Backend
    Bảo đảm an toàn luồng (Thread-Safe) giữa Thread xử lý DSP và Asyncio Event Loop.
    """
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.lock = threading.Lock()
        self.main_loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """Gắn Event Loop chính của FastAPI khi khởi động server"""
        self.main_loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        with self.lock:
            self.active_connections.add(websocket)
        
        # Nếu chưa set loop, tự động bắt loop hiện tại
        if self.main_loop is None:
            try:
                self.main_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
        
        # Gửi trạng thái ban đầu của đèn và cài đặt cho client vừa kết nối
        try:
            await websocket.send_json({
                "type": "INITIAL_STATE",
                "bulb_state": virtual_bulb.get_state()
            })
        except Exception as e:
            logger.warning(f"Failed to send initial state to new connection: {e}")

    def disconnect(self, websocket: WebSocket):
        with self.lock:
            self.active_connections.discard(websocket)

    def broadcast_json_sync(self, message: dict):
        """
        Hàm đồng bộ an toàn luồng được gọi từ các thread xử lý DSP hoặc ActionDispatcher
        để gửi tin nhắn tới tất cả WebSocket client mà không làm crash event loop.
        """
        with self.lock:
            if not self.active_connections:
                return
            targets = list(self.active_connections)

        # Sử dụng main_loop đã đăng ký
        loop = self.main_loop
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

        if loop and loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self._broadcast_to(targets, message), loop)
            except Exception as e:
                logger.debug(f"Broadcast threadsafe scheduling error: {e}")
        else:
            # Fallback nếu không có loop chạy
            pass

    async def _broadcast_to(self, targets: List[WebSocket], message: dict):
        dead_connections = []
        for connection in targets:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
                
        if dead_connections:
            with self.lock:
                for dc in dead_connections:
                    self.active_connections.discard(dc)

manager = ThreadSafeConnectionManager()

# Đăng ký broadcast callback vào live engine
live_engine.set_broadcast_callback(manager.broadcast_json_sync)

@router.websocket("/ws/audio")
async def websocket_audio_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    telemetry_counter = 0
    
    try:
        while True:
            # Nhận dữ liệu (có thể là binary PCM Float32 hoặc JSON text)
            message = await websocket.receive()
            
            if "bytes" in message and message["bytes"] is not None:
                # Dữ liệu âm thanh thô Float32 (16kHz Mono)
                raw_bytes = message["bytes"]
                audio_array = np.frombuffer(raw_bytes, dtype=np.float32)
                
                # Xử lý qua cỗ máy nhận diện
                try:
                    telemetry = live_engine.process_chunk(audio_array)
                    
                    # Gửi telemetry về UI định kỳ (mỗi 3 chunks ~ 96ms để UI mượt mà)
                    telemetry_counter += 1
                    if telemetry_counter % 3 == 0:
                        await websocket.send_json(telemetry)
                except Exception as proc_err:
                    logger.error(f"Error processing audio chunk: {proc_err}")

            elif "text" in message and message["text"] is not None:
                # Xử lý các lệnh điều khiển từ UI (JSON)
                try:
                    data = json.loads(message["text"])
                    cmd_type = data.get("type")
                    
                    if cmd_type == "PING":
                        await websocket.send_json({"type": "PONG"})
                        
                    elif cmd_type == "SET_BULB":
                        power = data.get("power")
                        color = data.get("color")
                        brightness = data.get("brightness")
                        mode = data.get("mode")
                        
                        if power is not None:
                            virtual_bulb.set_power(power, source="web_ui")
                        if color is not None:
                            virtual_bulb.set_color(color, source="web_ui")
                        if brightness is not None:
                            virtual_bulb.set_brightness(brightness, source="web_ui")
                        if mode is not None:
                            virtual_bulb.mode = mode
                            
                        # Broadcast trạng thái mới
                        manager.broadcast_json_sync({
                            "type": "BULB_STATE_CHANGED",
                            "bulb_state": virtual_bulb.get_state()
                        })

                except Exception as e:
                    logger.warning(f"Error parsing text message: {e}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.debug(f"WebSocket client disconnected: {e}")
        manager.disconnect(websocket)
