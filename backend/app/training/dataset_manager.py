import os
import json
import wave
import time
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from ..config import DATA_DIR, USER_PROFILES_DIR, DEFAULT_SAMPLES_DIR

CATEGORIES = {
    "claps": "Tiếng Vỗ Tay",
    "false_positives": "Mẫu Báo Giả (Hard Negatives)",
    "speech": "Tiếng Nói & Hơi Thở",
    "typing": "Gõ Bàn & Bàn Phím",
    "snaps": "Va Chạm & Búng Tay",
    "ambient": "Tiếng Ồn Nền Phòng",
    "noises": "Tạp Âm Chung"
}

class DatasetManager:
    """
    Quản lý dữ liệu mẫu âm thanh thu thập cho từng User Profile theo danh mục chi tiết.
    Cấu trúc thư mục:
    data/user_profiles/<profile_name>/
      ├── meta.json
      ├── claps/
      ├── typing/
      ├── speech/
      ├── snaps/
      └── ambient/
    """
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._ensure_default_seed_data()

    def get_profile_dir(self, profile_name: str) -> Path:
        p_dir = USER_PROFILES_DIR / profile_name
        for cat in CATEGORIES.keys():
            (p_dir / cat).mkdir(parents=True, exist_ok=True)
        return p_dir

    def list_profiles(self) -> List[Dict[str, Any]]:
        profiles = []
        for p in USER_PROFILES_DIR.iterdir():
            if p.is_dir():
                cat_counts = {}
                total_claps = len(list((p / "claps").glob("*.npy")))
                total_noises = 0
                for cat in CATEGORIES.keys():
                    c_dir = p / cat
                    cnt = len(list(c_dir.glob("*.npy")))
                    cat_counts[cat] = cnt
                    if cat != "claps":
                        total_noises += cnt

                meta_file = p / "meta.json"
                meta = {}
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                    except Exception:
                        pass
                
                profiles.append({
                    "name": p.name,
                    "claps_count": total_claps,
                    "noises_count": total_noises,
                    "category_counts": cat_counts,
                    "accuracy": meta.get("accuracy", None),
                    "created_at": meta.get("created_at", None),
                    "is_active": meta.get("is_active", False)
                })
        return profiles

    def save_sample(
        self, 
        profile_name: str, 
        category: str, 
        audio: np.ndarray, 
        sample_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Lưu một mẫu âm thanh vào profile và category tương ứng.
        Tự động tính toán các chỉ số acoustic và lưu cả .npy lẫn .wav.
        """
        p_dir = self.get_profile_dir(profile_name)
        cat_dir = p_dir / category
        cat_dir.mkdir(parents=True, exist_ok=True)

        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        if not sample_id:
            existing = len(list(cat_dir.glob("*.npy")))
            sample_id = f"{category}_{timestamp_str}_{existing + 1:03d}"

        npy_path = cat_dir / f"{sample_id}.npy"
        wav_path = cat_dir / f"{sample_id}.wav"

        # Chuẩn hóa âm thanh
        peak_amp = float(np.max(np.abs(audio))) if len(audio) > 0 else 0.0
        rms_amp = float(np.sqrt(np.mean(audio ** 2) + 1e-10)) if len(audio) > 0 else 0.0
        duration_sec = round(len(audio) / self.sample_rate, 3)

        # Lưu file float32 và wav
        np.save(npy_path, audio.astype(np.float32))
        self._write_wav(wav_path, audio, self.sample_rate)

        return {
            "sample_id": sample_id,
            "category": category,
            "peak_amp": round(peak_amp, 4),
            "rms_amp": round(rms_amp, 4),
            "duration_sec": duration_sec,
            "wav_url": f"/api/training/audio/{profile_name}/{category}/{sample_id}.wav",
            "created_at": time.strftime("%H:%M:%S")
        }

    def list_samples_detailed(self, profile_name: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lấy danh sách chi tiết các mẫu đã thu để hiển thị player trên UI"""
        p_dir = self.get_profile_dir(profile_name)
        samples = []

        categories_to_scan = [category] if category else list(CATEGORIES.keys())

        for cat in categories_to_scan:
            cat_dir = p_dir / cat
            if not cat_dir.exists():
                continue

            for npy_file in sorted(cat_dir.glob("*.npy"), key=os.path.getmtime, reverse=True):
                sample_id = npy_file.stem
                wav_file = cat_dir / f"{sample_id}.wav"
                
                try:
                    audio = np.load(npy_file)
                    peak = float(np.max(np.abs(audio)))
                    rms = float(np.sqrt(np.mean(audio ** 2) + 1e-10))
                    duration = round(len(audio) / self.sample_rate, 3)
                except Exception:
                    peak, rms, duration = 0.0, 0.0, 0.0

                created_at = time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(npy_file)))

                samples.append({
                    "sample_id": sample_id,
                    "category": cat,
                    "category_name": CATEGORIES.get(cat, cat),
                    "peak_amp": round(peak, 3),
                    "rms_amp": round(rms, 3),
                    "duration_sec": duration,
                    "wav_url": f"/api/training/audio/{profile_name}/{cat}/{sample_id}.wav",
                    "created_at": created_at
                })

        return samples

    def delete_sample(self, profile_name: str, category: str, sample_id: str) -> bool:
        """Xoá 1 mẫu âm thanh theo id"""
        p_dir = self.get_profile_dir(profile_name)
        cat_dir = p_dir / category
        npy_path = cat_dir / f"{sample_id}.npy"
        wav_path = cat_dir / f"{sample_id}.wav"

        deleted = False
        if npy_path.exists():
            npy_path.unlink()
            deleted = True
        if wav_path.exists():
            wav_path.unlink()
            deleted = True
        return deleted

    def clear_category(self, profile_name: str, category: str) -> int:
        """Xoá toàn bộ mẫu của 1 danh mục"""
        p_dir = self.get_profile_dir(profile_name)
        cat_dir = p_dir / category
        if not cat_dir.exists():
            return 0

        count = 0
        for f in cat_dir.glob("*.*"):
            try:
                f.unlink()
                count += 1
            except Exception:
                pass
        return count // 2 # vì có cả .npy và .wav

    def load_dataset(self, profile_name: str) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """Tải toàn bộ mẫu claps và tất cả các loại tiếng ồn của profile kèm seed noises"""
        claps, noises, fps = self.load_dataset_separated(profile_name)
        return claps, noises + fps

    def load_dataset_separated(self, profile_name: str) -> Tuple[List[np.ndarray], List[np.ndarray], List[np.ndarray]]:
        """
        Tải toàn bộ dataset và phân tách rõ 3 nhóm:
        - claps: Các mẫu vỗ tay
        - noises: Các mẫu tiếng ồn thường
        - false_positives: Các mẫu báo giả (Hard Negatives) cần nhân bản x2
        """
        p_dir = self.get_profile_dir(profile_name)
        
        claps = []
        for f in (p_dir / "claps").glob("*.npy"):
            try:
                claps.append(np.load(f))
            except Exception:
                pass

        noises = []
        for cat in ["typing", "speech", "snaps", "ambient", "noises"]:
            cat_dir = p_dir / cat
            if cat_dir.exists():
                for f in cat_dir.glob("*.npy"):
                    try:
                        noises.append(np.load(f))
                    except Exception:
                        pass

        false_positives = []
        fp_dir = p_dir / "false_positives"
        if fp_dir.exists():
            for f in fp_dir.glob("*.npy"):
                try:
                    false_positives.append(np.load(f))
                except Exception:
                    pass

        # Luôn bổ sung kho mẫu hạt giống chuẩn đa dạng (tiếng nói, kim loại, đóng cửa)
        def_claps, def_noises = self.load_default_seed_data()
        if len(claps) < 5:
            claps = claps + def_claps
        noises = noises + def_noises

        return claps, noises, false_positives

    def _write_wav(self, path: Path, audio: np.ndarray, sample_rate: int):
        """Ghi file WAV 16-bit PCM tiêu chuẩn"""
        norm_audio = np.clip(audio, -1.0, 1.0)
        pcm_16 = (norm_audio * 32767).astype(np.int16)
        
        with wave.open(str(path), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_16.tobytes())

    def _ensure_default_seed_data(self):
        """Tạo kho mẫu hạt giống phong phú (Seed Dataset) chống mọi loại báo động giả"""
        DEFAULT_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        claps_dir = DEFAULT_SAMPLES_DIR / "claps"
        noises_dir = DEFAULT_SAMPLES_DIR / "noises"
        claps_dir.mkdir(parents=True, exist_ok=True)
        noises_dir.mkdir(parents=True, exist_ok=True)

        sr = self.sample_rate
        duration = 0.25 # 250ms = 4000 samples
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)

        np.random.seed(42)

        # 1. 20 Mẫu Vỗ Tay Mô Phỏng (Synthetic Claps)
        for i in range(20):
            center_freq = np.random.uniform(2000, 5000)
            decay_rate = np.random.uniform(25, 45) # ms - phân rã cực nhanh
            envelope = np.exp(-t * (1000.0 / decay_rate))
            noise = np.random.normal(0, 1, len(t))
            resonance = np.sin(2 * np.pi * center_freq * t) + 0.4 * np.sin(2 * np.pi * (center_freq * 1.5) * t)
            clap_sample = (noise * 0.75 + resonance * 0.25) * envelope
            clap_sample = clap_sample / (np.max(np.abs(clap_sample)) + 1e-6)
            np.save(claps_dir / f"seed_clap_{i+1:02d}.npy", clap_sample.astype(np.float32))

        # 2. 60 Mẫu Tạp Âm Đa Dạng (Tiếng nói, Kim loại, Đóng cửa, TV)
        for i in range(60):
            noise_type = i % 4
            if noise_type == 0:
                # Tiếng nói chuyện / Vowel Formants (F0 + harmonics) kéo dài >180ms
                f0 = np.random.uniform(140, 550)
                formant1 = 2 * f0
                formant2 = 3 * f0
                formant3 = 5 * f0
                sample = (
                    np.sin(2 * np.pi * f0 * t) + 
                    0.6 * np.sin(2 * np.pi * formant1 * t) + 
                    0.4 * np.sin(2 * np.pi * formant2 * t) +
                    0.2 * np.sin(2 * np.pi * formant3 * t)
                )
                sample *= (0.6 + 0.4 * np.sin(2 * np.pi * np.random.uniform(3, 8) * t))
            elif noise_type == 1:
                # Tiếng kim loại, chìa khóa, chén đĩa (Metallic High-Frequency Resonances 3.5kHz - 6.5kHz)
                metal_freq = np.random.uniform(3400, 6800)
                metal_freq2 = metal_freq * np.random.uniform(1.2, 1.6)
                env = np.exp(-t * np.random.uniform(8, 20)) # Phân rã chậm kéo dài
                sample = (
                    np.sin(2 * np.pi * metal_freq * t) + 
                    0.7 * np.sin(2 * np.pi * metal_freq2 * t) + 
                    0.15 * np.random.normal(0, 1, len(t))
                ) * env
            elif noise_type == 2:
                # Tiếng đóng cửa, gõ bàn, dậm chân (Low-Frequency Heavy Thumps 60Hz - 280Hz)
                thud_freq = np.random.uniform(60, 240)
                env = np.exp(-t * np.random.uniform(15, 35))
                sample = (
                    np.sin(2 * np.pi * thud_freq * t) + 
                    0.5 * np.sin(2 * np.pi * (thud_freq * 2) * t) + 
                    0.1 * np.random.normal(0, 1, len(t))
                ) * env
            else:
                # Tiếng huýt sáo, còi, tiếng rít quạt gió (Narrowband Whistling / Ambient Hiss)
                whistle_freq = np.random.uniform(1800, 3800)
                sample = np.sin(2 * np.pi * whistle_freq * t) + 0.25 * np.random.normal(0, 1, len(t))

            sample = sample / (np.max(np.abs(sample)) + 1e-6)
            np.save(noises_dir / f"seed_noise_{i+1:02d}.npy", sample.astype(np.float32))

    def load_default_seed_data(self) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        claps_dir = DEFAULT_SAMPLES_DIR / "claps"
        noises_dir = DEFAULT_SAMPLES_DIR / "noises"
        self._ensure_default_seed_data()
        claps = [np.load(f) for f in claps_dir.glob("*.npy")]
        noises = [np.load(f) for f in noises_dir.glob("*.npy")]
        return claps, noises
