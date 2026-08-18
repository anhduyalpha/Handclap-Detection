import threading
import time
import numpy as np
from typing import Optional
from .live_engine import live_engine
from ..config import settings

class ServerMicrophoneStreamer:
    """
    Thu âm trực tiếp từ Microphone cắm vào Server (USB Mic, 3.5mm Mic, WebCam Mic...).
    Chạy ngầm liên tục và đẩy âm thanh vào LiveDetectionEngine.
    Không phụ thuộc vào trình duyệt Web.
    """
    def __init__(self, sample_rate: int = 16000, chunk_size: int = 512):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self._backend = "none"

    def start(self):
        if self.is_running:
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run_capture_loop, daemon=True, name="ServerMicThread")
        self.thread.start()

    def stop(self):
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)

    def _run_capture_loop(self):
        # 1. Thử sounddevice với cơ chế tự động tìm Micro tích hợp của Laptop
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_device_id = None

            # Ưu tiên thiết bị có plugin resample ALSA ('default', 'sysdefault', 'pulse')
            for i, dev in enumerate(devices):
                if dev.get('max_input_channels', 0) > 0:
                    dev_name = dev.get('name', f'Device {i}')
                    print(f"[ServerMic] Found audio input device [{i}]: {dev_name}")
                    if any(k in dev_name.lower() for k in ['default', 'sysdefault', 'pulse']):
                        input_device_id = i
                        break
                    elif input_device_id is None:
                        input_device_id = i

            if input_device_id is not None:
                dev_info = sd.query_devices(input_device_id)
                print(f"[ServerMic] Selected Laptop Hardware Mic: [{input_device_id}] {dev_info.get('name')}")
                self._backend = "sounddevice"

                def audio_callback(indata, frames, time_info, status):
                    if not self.is_running:
                        return
                    audio_mono = indata[:, 0].astype(np.float32)
                    try:
                        telemetry = live_engine.process_chunk(audio_mono)
                        if live_engine.broadcast_callback:
                            live_engine.broadcast_callback(telemetry)
                    except Exception:
                        pass

                with sd.InputStream(
                    device=input_device_id,
                    samplerate=self.sample_rate,
                    blocksize=self.chunk_size,
                    channels=1,
                    dtype='float32',
                    callback=audio_callback
                ):
                    print(f"[ServerMic] Laptop Hardware Mic is LISTENING live at {self.sample_rate}Hz!")
                    while self.is_running:
                        time.sleep(0.1)
                return
            else:
                print("[ServerMic] No sounddevice input device with channels > 0 found.")
        except Exception as e:
            print(f"[ServerMic] sounddevice init note ({e}), falling back to ALSA arecord...")

        # 2. Thử arecord (Linux native ALSA tool)
        try:
            import subprocess
            cmd = [
                "arecord",
                "-D", "default",
                "-f", "S16_LE",
                "-r", str(self.sample_rate),
                "-c", "1",
                "-t", "raw",
                "-q"
            ]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self._backend = "arecord"
            print(f"[ServerMic] Laptop Hardware Mic is LISTENING live via Linux 'arecord -D default' ({self.sample_rate}Hz)!")

            bytes_per_chunk = self.chunk_size * 2 # 16-bit PCM = 2 bytes per sample
            chunk_count = 0

            while self.is_running:
                raw_bytes = proc.stdout.read(bytes_per_chunk)
                if not raw_bytes:
                    err_out = proc.stderr.read().decode('utf-8', errors='ignore') if proc.stderr else ""
                    print(f"[ServerMic] arecord process stream ended! Exit code: {proc.poll()}, Stderr: {err_out}")
                    break
                audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
                audio_float = audio_int16.astype(np.float32) / 32768.0

                chunk_count += 1
                if chunk_count % 150 == 0:
                    # In log heartbeat mỗi ~5s để xác nhận mic đang nhận dữ liệu âm thanh thực tế
                    rms = float(np.sqrt(np.mean(audio_float ** 2) + 1e-10))
                    peak = float(np.max(np.abs(audio_float)))
                    print(f"[ServerMic Heartbeat] ALC3246 Active: Signal RMS={rms:.4f}, Peak={peak:.4f}, NoiseFloor={live_engine.noise_estimator.noise_floor_rms:.4f}")

                try:
                    telemetry = live_engine.process_chunk(audio_float)
                    if live_engine.broadcast_callback:
                        live_engine.broadcast_callback(telemetry)
                except Exception as e:
                    print(f"[ServerMic] process_chunk error: {e}")

            proc.terminate()
        except Exception as e:
            print(f"[ServerMic] Linux arecord error ({e}). Server mic capture inactive.")

server_mic = ServerMicrophoneStreamer(
    sample_rate=settings.audio.sample_rate,
    chunk_size=settings.audio.chunk_size
)
