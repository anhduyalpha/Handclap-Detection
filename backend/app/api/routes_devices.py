from fastapi import APIRouter, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any

from ..smart_home.virtual_bulb import virtual_bulb
from ..smart_home.action_dispatcher import action_dispatcher
from ..core.live_engine import live_engine
from ..config import settings, save_persistent_settings
from ..core.security import validate_outbound_url

router = APIRouter(prefix="/api", tags=["devices_and_settings"])

class BulbControlRequest(BaseModel):
    power: Optional[bool] = None
    brightness: Optional[int] = None
    color: Optional[str] = None
    mode: Optional[str] = None

class ActionTriggerRequest(BaseModel):
    action: str # "toggle_power" | "next_color" | "party_mode"

class SettingsUpdateRequest(BaseModel):
    energy_threshold: Optional[float] = None
    confidence_threshold: Optional[float] = None
    min_inter_clap_ms: Optional[int] = None
    max_inter_clap_ms: Optional[int] = None
    double_clap_action: Optional[str] = None
    webhook_url: Optional[str] = None
    windows_studio_url: Optional[str] = None
    linux_server_url: Optional[str] = None
    auto_collect_true_claps: Optional[bool] = None
    # Cấu hình Căn chỉnh độ ồn phòng liên tục
    adaptive_noise_enabled: Optional[bool] = None
    adaptation_speed: Optional[float] = None
    margin_factor: Optional[float] = None

@router.get("/bulb/state")
def get_bulb_state():
    return virtual_bulb.get_state()

@router.post("/bulb/state")
def update_bulb_state(req: BulbControlRequest):
    if req.power is not None:
        virtual_bulb.set_power(req.power)
    if req.brightness is not None:
        virtual_bulb.set_brightness(req.brightness)
    if req.color is not None:
        virtual_bulb.set_color(req.color)
    if req.mode is not None:
        virtual_bulb.mode = req.mode

    state = virtual_bulb.get_state()
    # Broadcast cập nhật
    action_dispatcher.dispatch_pattern("manual_update", 0, [])
    return state

@router.post("/bulb/action")
def trigger_bulb_action(req: ActionTriggerRequest):
    if req.action == "toggle_power":
        state = virtual_bulb.toggle_power(source="api_manual")
    elif req.action == "next_color":
        state = virtual_bulb.next_color(source="api_manual")
    elif req.action == "party_mode":
        state = virtual_bulb.party_mode(source="api_manual")
    else:
        state = virtual_bulb.get_state()
        
    return state

@router.get("/settings")
def get_settings():
    return {
        "dsp": settings.dsp.model_dump(),
        "adaptive_noise": settings.adaptive_noise.model_dump(),
        "noise_estimator": live_engine.noise_estimator.get_state(),
        "ml": settings.ml.model_dump(),
        "pattern": settings.pattern.model_dump(),
        "light": settings.light.model_dump(),
        "windows_studio_url": getattr(settings, "windows_studio_url", "http://127.0.0.1:8001"),
        "linux_server_url": getattr(settings, "linux_server_url", "http://127.0.0.1:8000"),
        "auto_collect_true_claps": getattr(settings, "auto_collect_true_claps", True)
    }

@router.post("/settings")
def update_settings(req: SettingsUpdateRequest):
    if req.energy_threshold is not None:
        settings.dsp.energy_threshold = req.energy_threshold
    if req.confidence_threshold is not None:
        settings.ml.confidence_threshold = req.confidence_threshold
        live_engine.classifier.confidence_threshold = req.confidence_threshold
        
    if req.adaptive_noise_enabled is not None:
        settings.adaptive_noise.enabled = req.adaptive_noise_enabled
    if req.adaptation_speed is not None:
        settings.adaptive_noise.adaptation_speed = req.adaptation_speed
    if req.margin_factor is not None:
        settings.adaptive_noise.margin_factor = req.margin_factor

    if req.min_inter_clap_ms is not None:
        settings.pattern.min_inter_clap_ms = req.min_inter_clap_ms
    if req.max_inter_clap_ms is not None:
        settings.pattern.max_inter_clap_ms = req.max_inter_clap_ms
        
    live_engine.pattern_matcher.update_config(
        min_interval_ms=settings.pattern.min_inter_clap_ms,
        max_interval_ms=settings.pattern.max_inter_clap_ms,
        cooldown_ms=settings.pattern.cooldown_ms
    )

    if req.double_clap_action is not None:
        settings.light.double_clap_action = req.double_clap_action
    if req.webhook_url is not None:
        validated_webhook = validate_outbound_url(req.webhook_url)
        settings.light.webhook_url = validated_webhook
    if req.windows_studio_url is not None:
        validated_windows_url = validate_outbound_url(req.windows_studio_url)
        settings.windows_studio_url = validated_windows_url
    if req.linux_server_url is not None:
        validated_linux_url = validate_outbound_url(req.linux_server_url)
        settings.linux_server_url = validated_linux_url
    if req.auto_collect_true_claps is not None:
        settings.auto_collect_true_claps = req.auto_collect_true_claps

    save_persistent_settings()
    return {"status": "success", "settings": get_settings()}
