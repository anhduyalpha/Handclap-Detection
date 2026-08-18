import base64
import numpy as np
from fastapi import APIRouter, HTTPException, Body, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path

from ..training.dataset_manager import DatasetManager, CATEGORIES
from ..training.trainer import PersonalModelTrainer
from ..training.segmenter import segmenter
from ..core.live_engine import live_engine
from ..config import settings, SensitivityPresets, USER_PROFILES_DIR

router = APIRouter(prefix="/api/training", tags=["training"])

dataset_mgr = DatasetManager(sample_rate=settings.audio.sample_rate)
trainer = PersonalModelTrainer(sample_rate=settings.audio.sample_rate)

class SampleUploadRequest(BaseModel):
    profile_name: str = "default"
    category: str # "claps" | "typing" | "speech" | "snaps" | "ambient" | "noises"
    audio_base64: str # Mảng Float32 hoặc int16 base64
    format: str = "float32" # "float32" | "int16"

class SampleDeleteRequest(BaseModel):
    profile_name: str = "default"
    category: str
    sample_id: str

class ClearCategoryRequest(BaseModel):
    profile_name: str = "default"
    category: str

class CalibrateRequest(BaseModel):
    audio_base64: str

class PresetRequest(BaseModel):
    preset_name: str

class TrainRequest(BaseModel):
    profile_name: str = "default"
    augment_factor: int = 15
    cnn_epochs: int = 25

class ProfileCreateRequest(BaseModel):
    name: str

@router.get("/profiles")
def get_profiles():
    """Danh sách các profile mô hình đã thu thập"""
    profiles = dataset_mgr.list_profiles()
    return {
        "active_profile": settings.ml.active_profile,
        "categories": CATEGORIES,
        "current_preset": getattr(settings, "current_preset", "balanced"),
        "profiles": profiles
    }

@router.post("/profiles")
def create_profile(req: ProfileCreateRequest):
    clean_name = "".join(c for c in req.name if c.isalnum() or c in ("-", "_")).lower()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Tên profile không hợp lệ")
        
    dataset_mgr.get_profile_dir(clean_name)
    return {"status": "success", "profile_name": clean_name}

@router.get("/samples")
def list_samples(profile_name: str = "default", category: Optional[str] = None):
    """Lấy danh sách các mẫu âm thanh chi tiết kèm URL wav để nghe lại"""
    samples = dataset_mgr.list_samples_detailed(profile_name, category)
    return {
        "profile_name": profile_name,
        "category": category,
        "total": len(samples),
        "samples": samples
    }

@router.post("/sample")
def upload_sample(req: SampleUploadRequest):
    """Lưu một mẫu âm thanh thu từ trình duyệt vào profile"""
    try:
        raw_bytes = base64.b64decode(req.audio_base64)
        if req.format == "float32":
            audio = np.frombuffer(raw_bytes, dtype=np.float32)
        elif req.format == "int16":
            audio = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            raise HTTPException(status_code=400, detail="Định dạng âm thanh không hỗ trợ")

        if len(audio) == 0:
            raise HTTPException(status_code=400, detail="Dữ liệu âm thanh rỗng")

        sample_info = dataset_mgr.save_sample(
            profile_name=req.profile_name,
            category=req.category,
            audio=audio
        )

        # Thông báo cho AutoLearner trên Windows để gom batch tự động huấn luyện
        try:
            from ..training.auto_learner import auto_learner
            auto_learner.notify_new_sample(req.profile_name, req.category)
        except Exception as err:
            print(f"[RoutesTraining] AutoLearner note: {err}")

        claps, noises = dataset_mgr.load_dataset(req.profile_name)
        return {
            "status": "success",
            "sample": sample_info,
            "claps_count": len(claps),
            "noises_count": len(noises)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sample")
def delete_sample(req: SampleDeleteRequest):
    """Xoá 1 mẫu âm thanh bị lỗi"""
    success = dataset_mgr.delete_sample(req.profile_name, req.category, req.sample_id)
    if not success:
        raise HTTPException(status_code=404, detail="Mẫu âm thanh không tồn tại")
    return {"status": "success", "message": f"Đã xoá mẫu {req.sample_id}"}

@router.delete("/samples/clear")
def clear_samples(req: ClearCategoryRequest):
    """Xoá toàn bộ mẫu của 1 danh mục"""
    count = dataset_mgr.clear_category(req.profile_name, req.category)
    return {"status": "success", "deleted_count": count}

@router.post("/calibrate")
def calibrate_room_noise(req: CalibrateRequest):
    """
    Tự động cân chỉnh độ nhạy dựa trên 2-3s tiếng ồn phòng thực tế.
    """
    try:
        raw_bytes = base64.b64decode(req.audio_base64)
        audio = np.frombuffer(raw_bytes, dtype=np.float32)
        if len(audio) == 0:
            raise HTTPException(status_code=400, detail="Không có dữ liệu âm thanh")

        # Tính toán mức ồn phòng
        rms = float(np.sqrt(np.mean(audio ** 2) + 1e-10))
        peak = float(np.max(np.abs(audio)))

        # Tính toán ngưỡng tối ưu:
        # Ngưỡng năng lượng đặt cao hơn đỉnh tiếng ồn phòng ~ 1.8 lần, tối thiểu 0.015
        recommended_energy = max(0.015, min(0.12, peak * 1.8))
        recommended_crest = 2.2 if rms < 0.01 else 2.6
        recommended_conf = 0.65 if rms < 0.01 else 0.75

        # Áp dụng ngay vào Live Engine
        settings.dsp.energy_threshold = round(recommended_energy, 4)
        settings.dsp.crest_factor_min = round(recommended_crest, 2)
        settings.ml.confidence_threshold = round(recommended_conf, 2)
        live_engine.classifier.confidence_threshold = settings.ml.confidence_threshold

        return {
            "status": "success",
            "noise_floor_rms": round(rms, 4),
            "noise_floor_peak": round(peak, 4),
            "recommended_energy_threshold": round(recommended_energy, 4),
            "recommended_crest_factor": round(recommended_crest, 2),
            "recommended_confidence": round(recommended_conf, 2),
            "message": "Đã tự động cân chỉnh độ nhạy tối ưu cho phòng của bạn!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/preset")
def apply_preset(req: PresetRequest):
    """Áp dụng preset độ nhạy nhanh (high_sensitivity | balanced | strict_anti_noise)"""
    preset = SensitivityPresets.PRESETS.get(req.preset_name)
    if not preset:
        raise HTTPException(status_code=400, detail="Preset không tồn tại")

    settings.dsp.energy_threshold = preset["energy_threshold"]
    settings.dsp.crest_factor_min = preset["crest_factor_min"]
    settings.dsp.hf_energy_ratio_min = preset["hf_energy_ratio_min"]
    settings.ml.confidence_threshold = preset["confidence_threshold"]
    live_engine.classifier.confidence_threshold = preset["confidence_threshold"]

    return {
        "status": "success",
        "preset_name": req.preset_name,
        "preset_info": preset
    }

@router.post("/train")
def train_model(req: TrainRequest):
    """Kích hoạt quá trình huấn luyện mô hình cá nhân hóa và hot-reload"""
    try:
        meta = trainer.train_profile(
            profile_name=req.profile_name,
            augment_factor=req.augment_factor,
            cnn_epochs=req.cnn_epochs
        )

        settings.ml.active_profile = req.profile_name
        live_engine.reload_model(req.profile_name)

        return {
            "status": "success",
            "message": f"Đã huấn luyện và kích hoạt thành công mô hình '{req.profile_name}'",
            "metrics": meta
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Huấn luyện thất bại: {str(e)}")

@router.post("/activate")
def activate_profile(profile_name: str = Body(..., embed=True)):
    settings.ml.active_profile = profile_name
    live_engine.reload_model(profile_name)
    return {"status": "success", "active_profile": profile_name}

@router.get("/system-info")
def get_system_info():
    """Trả về thông tin phần cứng, GPU CUDA và nền tảng máy chủ"""
    import sys
    import torch
    
    cuda_avail = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if cuda_avail else "CPU (Standard)"
    cuda_ver = torch.version.cuda if cuda_avail else None
    
    return {
        "platform": sys.platform,
        "gpu_available": cuda_avail,
        "gpu_name": gpu_name,
        "device": "cuda" if cuda_avail else "cpu",
        "cuda_version": cuda_ver,
        "sample_rate": settings.audio.sample_rate
    }

class HardwareRecordRequest(BaseModel):
    profile_name: str = "default"
    category: str = "claps" # "claps" | "noise"
    duration_sec: float = 2.0

@router.post("/record-hardware-sample")
def record_hardware_sample(req: HardwareRecordRequest):
    """
    Thu âm trực tiếp từ Microphone phần cứng của Server (Realtek ALC3246 trên Dell).
    Ghi 2.0s và lưu thẳng vào thư mục user_profiles.
    """
    import subprocess
    import time
    
    duration = max(0.5, min(5.0, req.duration_sec))
    sample_rate = settings.audio.sample_rate
    total_samples = int(duration * sample_rate)
    audio_float = None

    # 1. Thử thu âm bằng sounddevice
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_id = None
        for i, dev in enumerate(devices):
            if dev.get('max_input_channels', 0) > 0:
                input_id = i
                break
        
        recording = sd.rec(
            total_samples,
            samplerate=sample_rate,
            channels=1,
            dtype='float32',
            device=input_id
        )
        sd.wait()
        audio_float = recording[:, 0]
    except Exception as e:
        print(f"[RecordHardware] sounddevice fallback: {e}")

    # 2. Thử arecord (Linux native ALSA)
    if audio_float is None:
        try:
            cmd = [
                "arecord",
                "-d", str(int(np.ceil(duration))),
                "-f", "S16_LE",
                "-r", str(sample_rate),
                "-c", "1",
                "-t", "raw",
                "-q"
            ]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            raw_bytes, _ = proc.communicate(timeout=duration + 2.0)
            if raw_bytes and len(raw_bytes) >= total_samples * 2:
                audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
                audio_float = audio_int16.astype(np.float32) / 32768.0
                audio_float = audio_float[:total_samples]
        except Exception as e:
            print(f"[RecordHardware] arecord fallback: {e}")

    if audio_float is None or len(audio_float) == 0:
        raise HTTPException(
            status_code=500, 
            detail="Không thể thu âm từ Microphone phần cứng của Server. Hãy đảm bảo Micro ALC3246 đã bật!"
        )

    # Lưu mẫu vào dataset profile
    sample_info = dataset_mgr.save_sample(
        profile_name=req.profile_name,
        category=req.category,
        audio=audio_float
    )

    claps, noises = dataset_mgr.load_dataset(req.profile_name)

    return {
        "status": "success",
        "message": f"Đã thu âm 2.0s từ Micro phần cứng Server và lưu vào danh mục '{req.category}'",
        "sample": sample_info,
        "category": req.category,
        "claps_count": len(claps),
        "noises_count": len(noises)
    }

class ContinuousSessionRequest(BaseModel):
    profile_name: str = "default"
    category: str = "claps" # "claps" | "typing" | "speech" | "snaps" | "ambient"
    duration_sec: float = 15.0
    source: str = "server" # "server" | "upload"
    audio_base64: Optional[str] = None
    format: str = "float32"

@router.post("/record-continuous-session")
def record_continuous_session(req: ContinuousSessionRequest):
    """
    Thu âm một phiên dài (10-30s) và tự động phân tách thông minh:
    - Nếu danh mục là 'claps': Tự động phát hiện từng cú vỗ tay và cắt thành từng mẫu 250ms riêng lẻ.
    - Nếu danh mục là tiếng ồn (typing, speech, snaps, ambient): Tự động băm nhỏ thành các mẫu 250ms chuẩn.
    Hỗ trợ thu trực tiếp từ Micro phần cứng Server (Dell ALC3246) hoặc từ Client tải lên.
    """
    import subprocess
    import time

    duration = max(3.0, min(60.0, req.duration_sec))
    sample_rate = settings.audio.sample_rate
    total_samples = int(duration * sample_rate)
    audio_float = None

    if req.source == "upload" and req.audio_base64:
        raw_bytes = base64.b64decode(req.audio_base64)
        if req.format == "float32":
            audio_float = np.frombuffer(raw_bytes, dtype=np.float32)
        elif req.format == "int16":
            audio_float = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    else:
        # Thu âm từ Micro Server Dell
        # 1. Thử sounddevice
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_id = None
            for i, dev in enumerate(devices):
                if dev.get('max_input_channels', 0) > 0:
                    dev_name = dev.get('name', '')
                    if any(k in dev_name.lower() for k in ['default', 'sysdefault', 'pulse']):
                        input_id = i
                        break
                    elif input_id is None:
                        input_id = i
            
            recording = sd.rec(
                total_samples,
                samplerate=sample_rate,
                channels=1,
                dtype='float32',
                device=input_id
            )
            sd.wait()
            audio_float = recording[:, 0]
        except Exception as e:
            print(f"[ContinuousSession] sounddevice fallback: {e}")

        # 2. Thử arecord
        if audio_float is None:
            try:
                cmd = [
                    "arecord",
                    "-d", str(int(np.ceil(duration))),
                    "-f", "S16_LE",
                    "-r", str(sample_rate),
                    "-c", "1",
                    "-t", "raw",
                    "-q"
                ]
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                raw_bytes, _ = proc.communicate(timeout=duration + 3.0)
                if raw_bytes and len(raw_bytes) >= total_samples * 2:
                    audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
                    audio_float = audio_int16.astype(np.float32) / 32768.0
                    audio_float = audio_float[:total_samples]
            except Exception as e:
                print(f"[ContinuousSession] arecord fallback: {e}")

    if audio_float is None or len(audio_float) == 0:
        raise HTTPException(
            status_code=500,
            detail="Không thể thu âm phiên liên tục từ Micro. Hãy kiểm tra lại kết nối micro!"
        )

    # 3. Tự động phân tách (Auto-Split)
    if req.category == "claps":
        extracted_clips = segmenter.segment_claps(audio_float, clip_duration_sec=0.25)
    else:
        extracted_clips = segmenter.segment_noise(audio_float, clip_duration_sec=0.25)

    if len(extracted_clips) == 0:
        # Nếu là claps mà không tìm thấy cú vỗ rõ rệt, lưu 1 đoạn đầu tiên làm fallback
        if req.category == "claps":
            return {
                "status": "warning",
                "extracted_count": 0,
                "category": req.category,
                "message": "Không phát hiện thấy cú vỗ tay rõ ràng nào trong phiên thu âm. Hãy thử vỗ to hơn hoặc đứng gần micro hơn!"
            }
        else:
            extracted_clips = [audio_float[:int(sample_rate * 0.25)]]

    # 4. Lưu toàn bộ các mẫu vừa trích xuất
    saved_samples = []
    for clip in extracted_clips:
        info = dataset_mgr.save_sample(
            profile_name=req.profile_name,
            category=req.category,
            audio=clip
        )
        saved_samples.append(info)

    claps, noises = dataset_mgr.load_dataset(req.profile_name)

    cat_label = CATEGORIES.get(req.category, req.category)
    return {
        "status": "success",
        "extracted_count": len(saved_samples),
        "category": req.category,
        "claps_count": len(claps),
        "noises_count": len(noises),
        "message": f"🎉 Tuyệt vời! Đã thu và tự động cắt thành công {len(saved_samples)} mẫu {cat_label}!"
    }

@router.get("/audio/{profile_name}/{category}/{filename}")
def stream_sample_wav(profile_name: str, category: str, filename: str):
    """Phục vụ file âm thanh WAV để phát trực tiếp trên trình duyệt"""
    wav_path = USER_PROFILES_DIR / profile_name / category / filename
    if not wav_path.exists():
        raise HTTPException(status_code=404, detail="File audio không tồn tại")
    return FileResponse(str(wav_path), media_type="audio/wav")

class CheckpointUploadRequest(BaseModel):
    profile_name: str = "default"
    files: Dict[str, str] # filename -> base64 string
    metrics: Optional[Dict[str, Any]] = None

@router.post("/upload-checkpoint")
def upload_checkpoint(req: CheckpointUploadRequest):
    """Nhận gói checkpoint mô hình AI vừa huấn luyện xong từ máy Windows và Hot-Reload trên Linux"""
    from ..config import CHECKPOINTS_DIR
    ckpt_dir = CHECKPOINTS_DIR / req.profile_name
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    for fname, b64_content in req.files.items():
        target_path = ckpt_dir / fname
        content_bytes = base64.b64decode(b64_content)
        with open(target_path, "wb") as f:
            f.write(content_bytes)

    # Hot reload model trên Live Engine
    try:
        live_engine.reload_model(req.profile_name)
    except Exception as e:
        print(f"[RoutesTraining] Hot-reload note: {e}")

    # Gửi thông báo WebSocket tới toàn bộ giao diện Web
    if live_engine.broadcast_callback:
        try:
            live_engine.broadcast_callback({
                "type": "AI_MODEL_UPGRADED",
                "profile_name": req.profile_name,
                "metrics": req.metrics or {},
                "message": f"🚀 AI Model profile '{req.profile_name}' vừa được tự động nâng cấp thành công!"
            })
        except Exception as e:
            print(f"[RoutesTraining] Broadcast upgrade error: {e}")

    return {
        "status": "success",
        "message": f"Đã nạp và kích hoạt mô hình AI mới cho profile '{req.profile_name}'",
        "metrics": req.metrics
    }

@router.get("/auto-learn-status")
def get_auto_learn_status():
    """Kiểm tra trạng thái hàng đợi tự động học trên Windows"""
    try:
        from ..training.auto_learner import auto_learner
        return auto_learner.get_status()
    except Exception as e:
        return {"enabled": False, "error": str(e)}



