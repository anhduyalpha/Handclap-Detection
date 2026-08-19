import os
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, CHECKPOINTS_DIR, settings
from .api import ws_audio, routes_training, routes_devices, routes_events
from .training.trainer import PersonalModelTrainer
from .core.live_engine import live_engine
from .core.server_mic import server_mic
from .core.executor import io_executor
from .core.telemetry import system_telemetry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("handclap.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern FastAPI lifespan context manager for startup and graceful shutdown"""
    # 1. Startup: Bind main running asyncio event loop to WebSocket connection manager
    loop = asyncio.get_running_loop()
    ws_audio.manager.set_loop(loop)
    logger.info("FastAPI Event Loop successfully bound to WebSocket Connection Manager.")

    # 2. Check and initialize default model if missing
    default_ckpt = CHECKPOINTS_DIR / "default"
    if not (default_ckpt / "model_sklearn.joblib").exists() and not (default_ckpt / "model_cnn.pt").exists():
        logger.info("Initializing default seed model checkpoint...")
        try:
            trainer = PersonalModelTrainer(sample_rate=settings.audio.sample_rate)
            meta = trainer.train_profile(profile_name="default", augment_factor=10, cnn_epochs=15)
            logger.info(f"Default model trained successfully (Accuracy: {meta.get('accuracy', 0)}%)")
            live_engine.reload_model("default")
        except Exception as e:
            logger.warning(f"Initial seed training note: {e}")

    # 3. Start hardware mic capture on Linux server
    if os.name != "nt":
        try:
            server_mic.start()
            logger.info("Server hardware microphone streamer started.")
        except Exception as e:
            logger.warning(f"Server mic startup note: {e}")

    yield

    # 4. Graceful Shutdown
    logger.info("Server shutting down: stopping microphone streamer and background executors...")
    try:
        server_mic.stop()
    except Exception as e:
        logger.debug(f"Server mic stop note: {e}")

    try:
        io_executor.shutdown(wait=False, cancel_futures=True)
    except Exception as e:
        logger.debug(f"IO executor shutdown note: {e}")

app = FastAPI(
    title="HandClap Detection & Smart Light API",
    description="Real-time Audio DSP & AI Handclap Classifier with Smart Light Integration",
    version="1.0.0",
    lifespan=lifespan
)

# Cấu hình CORS an toàn
raw_origins = getattr(settings, "cors_origins", "*")
if raw_origins == "*":
    origins = ["*"]
else:
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True if origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký Routers
app.include_router(ws_audio.router)
app.include_router(routes_training.router)
app.include_router(routes_devices.router)
app.include_router(routes_events.router)

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "HandClap Detection Engine",
        "active_profile": settings.ml.active_profile,
        "sample_rate": settings.audio.sample_rate,
        "telemetry": system_telemetry.get_metrics(),
        "noise_state": live_engine.noise_estimator.get_state()
    }

@app.get("/api/telemetry")
def get_telemetry():
    return {
        "status": "success",
        "metrics": system_telemetry.get_metrics(),
        "noise_state": live_engine.noise_estimator.get_state()
    }

# Phục vụ file tĩnh Frontend trong môi trường Production (nếu đã chạy npm run build)
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"
if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="static")
    logger.info(f"Mounted production Frontend static build from {FRONTEND_DIST}")
