import json
import asyncio
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Set
from ..core.live_engine import live_engine
from ..smart_home.virtual_bulb import virtual_bulb

router = APIRouter()

class ConnectionManager:
    """Quản lý các kết nối WebSocket đang mở giữa Web Client và Backend"""
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.loop = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.loop = asyncio.get_event_loop()
        
        # Gửi trạng thái ban đầu của đèn và cài đặt cho client vừa kết nối
        await websocket.send_json({
            "type": "INITIAL_STATE",
            "bulb_state": virtual_bulb.get_state()
        })

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    def broadcast_json_sync(self, message: dict):
        """Hàm đồng bộ được gọi từ các thread xử lý DSP để bắn tin nhắn tới tất cả WebSocket"""
        if not self.active_connections:
            return
            
        coro = self._broadcast(message)
        try:
            # Nếu đang có event loop đang chạy
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(coro, self.loop)
            else:
                asyncio.run(coro)
        except Exception as e:
            # Bỏ qua nếu loop đang tắt
            pass

    async def _broadcast(self, message: dict):
        dead_connections = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
                
        for dc in dead_connections:
            self.active_connections.discard(dc)

manager = ConnectionManager()

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
                    print(f"[WebSocket] Error processing audio chunk: {proc_err}")

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
                    print(f"[WebSocket] Error parsing text message: {e}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WebSocket] Disconnected with error: {e}")
        manager.disconnect(websocket)
