import threading
import time
import logging
import subprocess
import numpy as np
from typing import Optional
from .live_engine import live_engine
from ..config import settings

logger = logging.getLogger("handclap.server_mic")

class ServerMicrophoneStreamer:
    """
    Thu âm trực tiếp từ Microphone tích hợp của Server Laptop (Dell ALC3246 / ALSA).
    Tối ưu hóa âm lượng thu âm phần cứng & Kỹ thuật số (Digital Gain Boost 1.35x).
    Bổ sung Heartbeat Watchdog 24/7: Tự động khởi động lại luồng nếu mất tín hiệu audio > 3s.
    """
    def __init__(self, sample_rate: int = 16000, chunk_size: int = 512):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.is_running = False
        self.last_chunk_time: float = 0.0
        self.thread: Optional[threading.Thread] = None
        self.watchdog_thread: Optional[threading.Thread] = None
        self.proc: Optional[subprocess.Popen] = None
        self._backend = "none"

    def _optimize_linux_alsa_gain(self):
        """Tự động nâng mức âm lượng thu âm phần cứng của Micro Laptop lên mức tối đa"""
        commands = [
            ["amixer", "set", "Capture", "100%"],
            ["amixer", "set", "Capture Volume", "100%"],
            ["amixer", "set", "Internal Mic Boost", "2"],
            ["amixer", "set", "Mic Boost", "2"],
            ["amixer", "set", "Digital", "100%"],
            ["amixer", "sset", "Capture", "cap"]
        ]
        for cmd in commands:
            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=0.5)
            except Exception:
                pass

    def start(self):
        if self.is_running:
            return
        
        self._optimize_linux_alsa_gain()
        self.is_running = True
        self.last_chunk_time = time.time()
        
        self.thread = threading.Thread(target=self._supervise_capture_loop, daemon=True, name="ServerMicThread")
        self.thread.start()

        # Khởi động Watchdog thread giám sát tín hiệu âm thanh
        self.watchdog_thread = threading.Thread(target=self._run_watchdog, daemon=True, name="ServerMicWatchdog")
        self.watchdog_thread.start()

    def stop(self):
        self.is_running = False
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=1.5)
            except Exception:
                try:
                    self.proc.kill()
                    self.proc.wait(timeout=0.5)
                except Exception:
                    pass
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)

    def _run_watchdog(self):
        """Watchdog: Kiểm tra luồng PCM mỗi giây. Nếu đóng băng > 3s -> ép restart tiến trình"""
        while self.is_running:
            time.sleep(1.0)
            if not self.is_running:
                break
            
            now = time.time()
            if self.last_chunk_time > 0 and (now - self.last_chunk_time > 3.0):
                logger.warning(f"Audio stream stall detected (no PCM for {now - self.last_chunk_time:.1f}s)! Watchdog restarting mic capture...")
                if self.proc and self.proc.poll() is None:
                    try:
                        self.proc.terminate()
                        self.proc.wait(timeout=0.5)
                    except Exception:
                        try:
                            self.proc.kill()
                        except Exception:
                            pass
                self.last_chunk_time = now

    def _supervise_capture_loop(self):
        """Vòng lặp giám sát: Tự động kết nối lại nếu micro ALSA tạm thời bận"""
        while self.is_running:
            try:
                success = self._run_capture_loop()
                if not success and self.is_running:
                    time.sleep(2.0)
            except Exception as e:
                logger.warning(f"Server mic supervisor caught error: {e}. Reconnecting in 2s...")
                time.sleep(2.0)

    def _run_capture_loop(self) -> bool:
        # 1. Thử qua ALSA arecord trước (Tương thích tốt nhất trên Dell Linux)
        alsa_devices = ["default", "sysdefault", "pulse", "plughw:0,0"]
        bytes_per_chunk = self.chunk_size * 2  # 16-bit PCM = 2 bytes/sample
        
        for dev in alsa_devices:
            if not self.is_running:
                return False
            try:
                cmd = [
                    "arecord",
                    "-D", dev,
                    "-f", "S16_LE",
                    "-r", str(self.sample_rate),
                    "-c", "1",
                    "-t", "raw",
                    "-q"
                ]
                self.proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL
                )
                
                # Đọc thử chunk đầu tiên để xác nhận device hoạt động
                first_chunk = self.proc.stdout.read(bytes_per_chunk)
                if not first_chunk or len(first_chunk) < bytes_per_chunk:
                    self.proc.terminate()
                    self.proc.wait(timeout=0.5)
                    continue

                self._backend = f"arecord:{dev}"
                self.last_chunk_time = time.time()
                logger.info(f"Laptop Hardware Mic LISTENING live via Linux 'arecord -D {dev}' ({self.sample_rate}Hz)!")

                # Xử lý chunk đầu tiên
                audio_int16 = np.frombuffer(first_chunk, dtype=np.int16)
                audio_float = audio_int16.astype(np.float32) / 32768.0
                audio_boosted = np.clip(audio_float * 1.35, -1.0, 1.0)
                try:
                    telemetry = live_engine.process_chunk(audio_boosted)
                    if live_engine.broadcast_callback:
                        live_engine.broadcast_callback(telemetry)
                except Exception:
                    pass

                chunk_count = 0
                while self.is_running:
                    raw_bytes = self.proc.stdout.read(bytes_per_chunk)
                    if not raw_bytes or len(raw_bytes) < bytes_per_chunk:
                        logger.warning(f"arecord -D {dev} stream ended. Retrying...")
                        break

                    self.last_chunk_time = time.time()
                    audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
                    audio_float = audio_int16.astype(np.float32) / 32768.0
                    audio_boosted = np.clip(audio_float * 1.35, -1.0, 1.0)

                    chunk_count += 1
                    if chunk_count % 150 == 0:
                        rms = float(np.sqrt(np.mean(audio_boosted ** 2) + 1e-10))
                        peak = float(np.max(np.abs(audio_boosted)))
                        logger.info(f"[ServerMic Heartbeat] ALC3246 Active ({dev}): Signal RMS={rms:.4f}, Peak={peak:.4f}, NoiseFloor={live_engine.noise_estimator.noise_floor_rms:.4f}")

                    try:
                        telemetry = live_engine.process_chunk(audio_boosted)
                        if live_engine.broadcast_callback:
                            live_engine.broadcast_callback(telemetry)
                    except Exception as e:
                        logger.error(f"process_chunk error: {e}")

                return True
            except FileNotFoundError:
                break
            except Exception as e:
                logger.debug(f"arecord -D {dev} failed: {e}")
                if self.proc:
                    try:
                        self.proc.terminate()
                        self.proc.wait(timeout=0.5)
                    except Exception:
                        pass

        # 2. Fallback sang sounddevice nếu arecord không nhận
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_device_id = None

            for i, dev in enumerate(devices):
                if dev.get('max_input_channels', 0) > 0:
                    dev_name = dev.get('name', f'Device {i}')
                    if any(k in dev_name.lower() for k in ['default', 'sysdefault', 'pulse', 'realtek', 'alc']):
                        input_device_id = i
                        break
                    elif input_device_id is None:
                        input_device_id = i

            if input_device_id is not None:
                dev_info = sd.query_devices(input_device_id)
                logger.info(f"Selected Laptop Hardware Mic via sounddevice: [{input_device_id}] {dev_info.get('name')}")
                self._backend = "sounddevice"
                self.last_chunk_time = time.time()

                def audio_callback(indata, frames, time_info, status):
                    if not self.is_running:
                        return
                    self.last_chunk_time = time.time()
                    audio_mono = indata[:, 0].astype(np.float32)
                    audio_boosted = np.clip(audio_mono * 1.35, -1.0, 1.0)
                    try:
                        telemetry = live_engine.process_chunk(audio_boosted)
                        if live_engine.broadcast_callback:
                            live_engine.broadcast_callback(telemetry)
                    except Exception as err:
                        logger.debug(f"sounddevice callback processing error: {err}")

                with sd.InputStream(
                    device=input_device_id,
                    samplerate=self.sample_rate,
                    blocksize=self.chunk_size,
                    channels=1,
                    dtype='float32',
                    callback=audio_callback
                ):
                    logger.info(f"Laptop Hardware Mic LISTENING live via sounddevice at {self.sample_rate}Hz!")
                    while self.is_running:
                        time.sleep(0.1)
                return True
        except Exception as e:
            logger.warning(f"sounddevice fallback error: {e}")

        return False

server_mic = ServerMicrophoneStreamer(
    sample_rate=settings.audio.sample_rate,
    chunk_size=settings.audio.chunk_size
)
