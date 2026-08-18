import base64
import json
import threading
import urllib.request
import numpy as np
from fastapi import APIRouter, HTTPException, Response, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from ..core.trigger_history import trigger_history
from ..core.live_engine import live_engine
from ..training.dataset_manager import DatasetManager, CATEGORIES
from ..training.trainer import PersonalModelTrainer
from ..config import settings

router = APIRouter(prefix="/api/events", tags=["events"])

dataset_mgr = DatasetManager(sample_rate=settings.audio.sample_rate)
trainer = PersonalModelTrainer(sample_rate=settings.audio.sample_rate)

def _forward_audio_to_windows_async(profile_name: str, category: str, audio_clip: np.ndarray, target_url: str):
    """Gửi bản sao âm thanh báo giả trực tiếp sang máy tính Windows (chạy nền ngầm không block)"""
    def _worker():
        try:
            url = target_url.rstrip("/") + "/api/training/sample"
            b64_audio = base64.b64encode(audio_clip.astype(np.float32).tobytes()).decode("ascii")
            payload = json.dumps({
                "profile_name": profile_name,
                "category": category,
                "audio_base64": b64_audio,
                "format": "float32"
            }).encode("utf-8")

            req = urllib.request.Request(
                url, 
                data=payload, 
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status in (200, 201):
                    print(f"[ForwardToWindows] [SUCCESS] Audio forwarded to Windows Studio: {url}")
                else:
                    print(f"[ForwardToWindows] Warning: Windows returned HTTP {resp.status}")
        except Exception as err:
            print(f"[ForwardToWindows] Info: Windows Studio ({target_url}) is offline/unreachable: {err}")

    threading.Thread(target=_worker, daemon=True).start()

class MarkFalsePositiveRequest(BaseModel):
    event_id: str
    profile_name: str = "default"
    category: str = "false_positives" # "false_positives" | "speech" | "typing" | "ambient" | "snaps" | "noises"
    auto_retrain: bool = True

@router.get("/recent-triggers")
def get_recent_triggers():
    """Lấy danh sách 15 sự kiện kích hoạt đèn gần nhất"""
    events = trigger_history.get_recent_events()
    return {
        "status": "success",
        "total": len(events),
        "events": events
    }

@router.get("/audio/{event_id}")
def get_event_audio(event_id: str):
    """Phục vụ file âm thanh WAV của sự kiện kích hoạt để nghe lại trực tiếp trên Web"""
    wav_bytes = trigger_history.get_event_wav_bytes(event_id)
    if not wav_bytes:
        raise HTTPException(status_code=404, detail="Không tìm thấy file âm thanh của sự kiện này")
    
    return Response(content=wav_bytes, media_type="audio/wav")

@router.post("/mark-false-positive")
def mark_false_positive(req: MarkFalsePositiveRequest):
    """
    Đánh dấu sự kiện là Báo Giả (False Positive / Hard-Negative Mining):
    1. Trích xuất đoạn âm thanh 250ms chuẩn hóa từ sự kiện kích hoạt.
    2. Lưu trực tiếp vào tập dữ liệu nhiễu của Profile trên Linux.
    3. Tự động chuyển tiếp (Forward) đoạn âm thanh sang máy tính Windows Training Studio.
    4. Tùy chọn: Tự động kích hoạt Huấn luyện lại và Hot-Reload mô hình ngay lập tức!
    """
    record = trigger_history.get_event_by_id(req.event_id)
    if not record:
        raise HTTPException(status_code=404, detail="Sự kiện không tồn tại trong bộ nhớ đệm")

    audio_raw = record.get("audio_data")
    if audio_raw is None or len(audio_raw) == 0:
        raise HTTPException(status_code=400, detail="Không có dữ liệu âm thanh để lưu")

    # 1. Trích xuất cửa sổ 250ms (4000 samples) quanh vùng có biên độ lớn nhất
    sr = settings.audio.sample_rate
    clip_samples = int(sr * 0.25)
    
    if len(audio_raw) > clip_samples:
        peak_idx = int(np.argmax(np.abs(audio_raw)))
        # Cắt với 50ms trước đỉnh
        start_idx = max(0, peak_idx - int(sr * 0.05))
        end_idx = start_idx + clip_samples
        if end_idx > len(audio_raw):
            end_idx = len(audio_raw)
            start_idx = max(0, end_idx - clip_samples)
        clip_audio = audio_raw[start_idx:end_idx]
    else:
        clip_audio = np.zeros(clip_samples, dtype=np.float32)
        clip_audio[:len(audio_raw)] = audio_raw

    # 2. Lưu vào thư mục dataset của profile trên Linux
    valid_category = req.category if req.category in CATEGORIES else "false_positives"
    sample_info = dataset_mgr.save_sample(
        profile_name=req.profile_name,
        category=valid_category,
        audio=clip_audio
    )

    # 3. Đánh dấu trạng thái trong TriggerHistoryBuffer
    updated_record = trigger_history.mark_false_positive(
        event_id=req.event_id,
        category=valid_category,
        has_retrained=req.auto_retrain
    )

    # 4. Tự động chuyển tiếp đoạn audio sang máy tính Windows Training Studio
    if getattr(settings, "windows_studio_url", None):
        _forward_audio_to_windows_async(
            profile_name=req.profile_name,
            category=valid_category,
            audio_clip=clip_audio,
            target_url=settings.windows_studio_url
        )

    # 5. Tùy chọn: Tự động Train lại & Hot-Reload trên Linux
    retrain_metrics = None
    if req.auto_retrain:
        try:
            retrain_metrics = trainer.train_profile(
                profile_name=req.profile_name,
                augment_factor=12,
                cnn_epochs=20
            )
            live_engine.reload_model(req.profile_name)
        except Exception as e:
            print(f"[MarkFalsePositive] Retrain note: {e}")

    cat_name = CATEGORIES.get(valid_category, valid_category)
    return {
        "status": "success",
        "message": f"🎉 Đã lưu đoạn âm thanh báo giả vào danh mục '{cat_name}' và tự động chuyển sang Windows Training Studio!",
        "event_id": req.event_id,
        "sample": sample_info,
        "retrained": req.auto_retrain,
        "forwarded_to_windows": bool(getattr(settings, "windows_studio_url", None)),
        "metrics": retrain_metrics,
        "event": updated_record
    }

@router.delete("/clear")
def clear_trigger_history():
    """Xóa sạch lịch sử kích hoạt"""
    trigger_history.clear()
    return {"status": "success", "message": "Đã xóa toàn bộ lịch sử kích hoạt"}
