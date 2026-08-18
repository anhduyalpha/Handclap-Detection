import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, CHECKPOINTS_DIR, settings
from .api import ws_audio, routes_training, routes_devices
from .training.trainer import PersonalModelTrainer
from .core.live_engine import live_engine
from .core.server_mic import server_mic

app = FastAPI(
    title="HandClap Detection & Smart Light API",
    description="Real-time Audio DSP & AI Handclap Classifier with Smart Light Integration",
    version="1.0.0"
)

# Cấu hình CORS mở cho giao diện Web Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký Routers
app.include_router(ws_audio.router)
app.include_router(routes_training.router)
app.include_router(routes_devices.router)

@app.on_event("startup")
def startup_event():
    """Khởi động và kiểm tra mô hình mặc định và bật mic server"""
    default_ckpt = CHECKPOINTS_DIR / "default"
    if not (default_ckpt / "model_sklearn.joblib").exists() and not (default_ckpt / "model_cnn.pt").exists():
        print("[Startup] Initializing default seed model checkpoint...")
        try:
            trainer = PersonalModelTrainer(sample_rate=settings.audio.sample_rate)
            meta = trainer.train_profile(profile_name="default", augment_factor=10, cnn_epochs=15)
            print(f"[Startup] Default model trained successfully (Accuracy: {meta['accuracy']}%)")
            live_engine.reload_model("default")
        except Exception as e:
            print(f"[Startup] Warning during initial seed training: {e}")

    # Bật thu âm trực tiếp từ microphone phần cứng trên Linux Server (Dell Laptop)
    if os.name != "nt":
        try:
            server_mic.start()
        except Exception as e:
            print(f"[Startup] Server mic note: {e}")

@app.on_event("shutdown")
def shutdown_event():
    server_mic.stop()

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "HandClap Detection Engine",
        "active_profile": settings.ml.active_profile,
        "sample_rate": settings.audio.sample_rate
    }
