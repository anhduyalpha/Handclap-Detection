import threading
import time
import logging
import subprocess
import numpy as np
from typing import Optional, List
from .live_engine import live_engine
from ..config import settings

logger = logging.getLogger("handclap.server_mic")

class ServerMicrophoneStreamer:
    """
    Thu âm trực tiếp từ Microphone tích hợp của Server Laptop (Dell ALC3246 / ALSA).
    Khử nhiễu DC Offset, giữ âm lượng ở mức tự nhiên tiêu chuẩn (không over-boost).
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
        """Cân chỉnh mức âm lượng phần cứng của Micro Laptop ở mức tiêu chuẩn 70% (tự nhiên, không vỡ tiếng)"""
        cards = ["0", "1", "2", "default"]
        for c in cards:
            card_args = ["-c", c] if c != "default" else []
            commands = [
                ["amixer"] + card_args + ["set", "Input Source", "Internal Mic"],
                ["amixer"] + card_args + ["set", "Capture", "cap"],
                ["amixer"] + card_args + ["set", "Capture", "70%", "unmute"],
                ["amixer"] + card_args + ["set", "Capture Volume", "70%", "unmute"],
                ["amixer"] + card_args + ["set", "Internal Mic", "70%", "unmute"],
                ["amixer"] + card_args + ["set", "Internal Mic Boost", "0"],
                ["amixer"] + card_args + ["set", "Mic Boost", "0"],
                ["amixer"] + card_args + ["set", "Digital", "70%", "unmute"],
                ["amixer"] + card_args + ["set", "Master", "100%", "unmute"]
            ]
            for cmd in commands:
                try:
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=0.3)
                except Exception:
                    pass

    def _discover_alsa_capture_devices(self) -> List[str]:
        """Quét danh sách thiết bị phần cứng thu âm (Capture Devices) từ arecord -l"""
        devices = ["default", "plughw:0,0", "plughw:1,0", "pulse", "sysdefault"]
        try:
            res = subprocess.run(["arecord", "-l"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=1.0)
            for line in res.stdout.splitlines():
                if "card " in line and "device " in line:
                    try:
                        card_num = line.split("card ")[1].split(":")[0].strip()
                        dev_num = line.split("device ")[1].split(":")[0].strip()
                        hw_dev = f"plughw:{card_num},{dev_num}"
                        if hw_dev not in devices:
                            devices.append(hw_dev)
                        hw_raw = f"hw:{card_num},{dev_num}"
                        if hw_raw not in devices:
                            devices.append(hw_raw)
                    except Exception:
                        pass
        except Exception:
            pass
        return devices

    def start(self):
        if self.is_running:
            return
        
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
                self._optimize_linux_alsa_gain()
                success = self._run_capture_loop()
                if not success and self.is_running:
                    time.sleep(2.0)
            except Exception as e:
                logger.warning(f"Server mic supervisor caught error: {e}. Reconnecting in 2s...")
                time.sleep(2.0)

    def _run_capture_loop(self) -> bool:
        alsa_devices = self._discover_alsa_capture_devices()
        logger.info(f"Scanning available Linux ALSA capture devices: {alsa_devices}")

        for dev in alsa_devices:
            for channels in [1, 2]:
                if not self.is_running:
                    return False
                try:
                    bytes_per_chunk = self.chunk_size * 2 * channels
                    cmd = [
                        "arecord",
                        "-D", dev,
                        "-f", "S16_LE",
                        "-r", str(self.sample_rate),
                        "-c", str(channels),
                        "-t", "raw",
                        "-q"
                    ]
                    self.proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL
                    )
                    
                    # Đọc thử 3 chunks đầu
                    first_chunks_valid = False
                    for _ in range(3):
                        raw = self.proc.stdout.read(bytes_per_chunk)
                        if raw and len(raw) == bytes_per_chunk:
                            first_chunks_valid = True
                            break
                    
                    if not first_chunks_valid:
                        self.proc.terminate()
                        self.proc.wait(timeout=0.5)
                        continue

                    self._backend = f"arecord:{dev}:{channels}ch"
                    self.last_chunk_time = time.time()
                    logger.info(f"✅ Laptop Hardware Mic CONNECTED via 'arecord -D {dev} -c {channels}' ({self.sample_rate}Hz)!")

                    chunk_count = 0
                    while self.is_running:
                        raw_bytes = self.proc.stdout.read(bytes_per_chunk)
                        if not raw_bytes or len(raw_bytes) < bytes_per_chunk:
                            logger.warning(f"arecord -D {dev} stream ended. Retrying...")
                            break

                        self.last_chunk_time = time.time()
                        if channels == 2:
                            raw_stereo = np.frombuffer(raw_bytes, dtype=np.int16).reshape(-1, 2)
                            audio_float = raw_stereo.mean(axis=1).astype(np.float32) / 32768.0
                        else:
                            audio_float = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0

                        # 1. Khử DC Offset (DC Bias Removal)
                        audio_clean = audio_float - float(np.mean(audio_float))
                        audio_clean = np.clip(audio_clean, -1.0, 1.0)

                        chunk_count += 1
                        if chunk_count % 150 == 0:
                            rms = float(np.sqrt(np.mean(audio_clean ** 2) + 1e-10))
                            peak = float(np.max(np.abs(audio_clean)))
                            logger.info(f"[ServerMic Heartbeat] ALC3246 Active ({dev} {channels}ch): Signal RMS={rms:.4f}, Peak={peak:.4f}, NoiseFloor={live_engine.noise_estimator.noise_floor_rms:.4f}")

                        try:
                            telemetry = live_engine.process_chunk(audio_clean)
                            if live_engine.broadcast_callback:
                                live_engine.broadcast_callback(telemetry)
                        except Exception as e:
                            logger.error(f"process_chunk error: {e}")

                    return True
                except FileNotFoundError:
                    break
                except Exception as e:
                    logger.debug(f"arecord -D {dev} -c {channels} failed: {e}")
                    if self.proc:
                        try:
                            self.proc.terminate()
                            self.proc.wait(timeout=0.5)
                        except Exception:
                            pass

        # 2. Fallback sang sounddevice
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
                    audio_clean = audio_mono - float(np.mean(audio_mono))
                    audio_clean = np.clip(audio_clean, -1.0, 1.0)
                    try:
                        telemetry = live_engine.process_chunk(audio_clean)
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
