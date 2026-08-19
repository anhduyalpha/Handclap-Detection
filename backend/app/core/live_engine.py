import numpy as np
import time
import logging
import threading
from typing import Dict, Any, Optional, Callable
from .audio_stream import AudioRingBuffer
from .dsp_detector import DSPTransientDetector
from .feature_extractor import AudioFeatureExtractor
from .pattern_matcher import ClapPatternMatcher
from .noise_estimator import AdaptiveNoiseFloorEstimator
from .trigger_history import trigger_history
from .hard_negative_miner import hard_negative_miner
from .telemetry import system_telemetry
from ..models.classifier import ClapClassifier
from ..smart_home.action_dispatcher import action_dispatcher
from ..config import settings

logger = logging.getLogger("handclap.live_engine")

class LiveDetectionEngine:
    """
    Cỗ máy nhận diện âm thanh thời gian thực (Dual-Stage Live Engine Pro).
    Kết nối đồng bộ toàn bộ luồng xử lý:
    Stream Audio -> Zero-Copy Ring Buffer -> Adaptive Percentile Noise Tracking ->
    Stage 1 DSP Envelope Validation -> Stage 2 Double-Buffered ML -> Active Hard Negative Miner ->
    Instant Pattern Matcher -> Action Dispatcher -> System Telemetry & History.
    """
    def __init__(self, broadcast_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.sample_rate = settings.audio.sample_rate
        self.ring_buffer = AudioRingBuffer(
            capacity_samples=int(self.sample_rate * settings.audio.buffer_duration_sec),
            sample_rate=self.sample_rate
        )
        self.dsp_detector = DSPTransientDetector(sample_rate=self.sample_rate)
        self.noise_estimator = AdaptiveNoiseFloorEstimator()
        self.feature_extractor = AudioFeatureExtractor(sample_rate=self.sample_rate)
        self.classifier = ClapClassifier(config=settings.ml)
        
        self.pattern_matcher = ClapPatternMatcher(
            min_interval_ms=settings.pattern.min_inter_clap_ms,
            max_interval_ms=settings.pattern.max_inter_clap_ms,
            cooldown_ms=settings.pattern.cooldown_ms,
            on_pattern_callback=self._on_pattern_detected
        )
        
        self.broadcast_callback = broadcast_callback
        if broadcast_callback:
            action_dispatcher.set_broadcast_callback(broadcast_callback)

        self.last_detection_time = 0.0
        self._check_counter = 0

    def set_broadcast_callback(self, callback: Callable[[Dict[str, Any]], None]):
        self.broadcast_callback = callback
        action_dispatcher.set_broadcast_callback(callback)

    def reload_model(self, profile_name: str = "default"):
        """Tải lại mô hình (Hot-reload) sau khi train profile mới"""
        self.classifier.load_profile_model(profile_name)

    def _on_pattern_detected(self, pattern: str, count: int, events_meta: list):
        """Xử lý khi PatternMatcher phát hiện chuỗi vỗ tay hoàn chỉnh"""
        logger.info(f"[Pattern Matched] Pattern='{pattern}', Count={count} clap(s) -> Dispatching action & Webhook...")
        system_telemetry.record_trigger_event()
        action_dispatcher.dispatch_pattern(pattern, count, events_meta)

        # Trích xuất 800ms âm thanh quanh 2 cú vỗ tay để lưu vào TriggerHistory
        clip_samples = int(self.sample_rate * 0.8)
        audio_clip = self.ring_buffer.get_recent(clip_samples)

        avg_conf = sum(e.get("confidence", 0.8) for e in events_meta) / max(1, len(events_meta)) if events_meta else 0.8
        dsp_metrics = events_meta[-1] if events_meta else {}

        record = trigger_history.add_event(
            pattern=pattern,
            count=count,
            confidence=avg_conf,
            audio_clip=audio_clip,
            dsp_metrics=dsp_metrics,
            events_meta=events_meta
        )

        # Phát sóng sự kiện TRIGGER_EVENT tới WebSocket clients
        if self.broadcast_callback:
            self.broadcast_callback({
                "type": "TRIGGER_EVENT",
                "event": record
            })

        # Tự động gửi mẫu True Clap sang Windows nếu được bật (rate-limited)
        if pattern == "double" and avg_conf >= 0.85:
            if getattr(settings, "windows_studio_url", None) and getattr(settings, "auto_collect_true_claps", True):
                now_t = time.time()
                if now_t - getattr(self, "_last_true_clap_sent", 0.0) > 15.0:
                    self._last_true_clap_sent = now_t
                    try:
                        from ..api.routes_events import _forward_audio_to_windows_async
                        _forward_audio_to_windows_async(
                            profile_name=settings.ml.active_profile,
                            category="claps",
                            audio_clip=audio_clip,
                            target_url=settings.windows_studio_url
                        )
                        logger.info("True Double-Clap sample automatically forwarded to Windows Studio!")
                    except Exception as err:
                        logger.debug(f"ActiveLearning note: {err}")

    def process_chunk(self, audio_chunk: np.ndarray) -> Dict[str, Any]:
        """
        Xử lý từng chunk âm thanh float32 nhận được từ client hoặc server mic.
        Đo lường độ trễ chính xác và tự động khai thác mẫu khó (Hard Negative Mining).
        """
        t0 = time.perf_counter()
        if len(audio_chunk) == 0:
            return {"rms": 0.0, "peak": 0.0, "stage1": False, "stage2": False}

        # 1. Ghi vào Ring Buffer
        self.ring_buffer.write(audio_chunk)

        # Kiểm tra tự động Hot-Reload nếu có model mới trên đĩa (mỗi ~3s)
        self._check_counter += 1
        if self._check_counter % 100 == 0:
            self.classifier.check_and_reload_if_updated()

        # Lấy đoạn lịch sử gần đây (150ms trước) để so sánh năng lượng onset
        history_samples = int(self.sample_rate * 0.15)
        recent_history = self.ring_buffer.get_recent(history_samples)

        # 2. Stage 1: DSP Transient Envelope Validator với Ngưỡng Động
        energy_thresh = self.noise_estimator.dynamic_energy_thresh if settings.adaptive_noise.enabled else settings.dsp.energy_threshold
        crest_thresh = self.noise_estimator.dynamic_crest_thresh if settings.adaptive_noise.enabled else settings.dsp.crest_factor_min
        confidence_thresh = self.noise_estimator.dynamic_confidence_thresh if settings.adaptive_noise.enabled else settings.ml.confidence_threshold

        is_transient, dsp_metrics = self.dsp_detector.analyze_chunk(
            chunk=audio_chunk,
            recent_history=recent_history,
            energy_thresh=energy_thresh,
            crest_thresh=crest_thresh,
            hf_ratio_thresh=self.noise_estimator.dynamic_hf_thresh if settings.adaptive_noise.enabled else settings.dsp.hf_energy_ratio_min
        )

        # 3. Cập nhật Bộ ước lượng ồn nền phân vị (Percentile Noise Tracker)
        peak_amp = dsp_metrics.get("peak_amp", 0.0)
        rms_amp = dsp_metrics.get("rms_amp", 0.0)
        crest_factor = dsp_metrics.get("crest_factor", 0.0)
        hf_ratio = dsp_metrics.get("hf_ratio", 0.0)

        noise_state = self.noise_estimator.update(
            chunk_rms=rms_amp,
            chunk_peak=peak_amp,
            chunk_crest=crest_factor,
            chunk_hf=hf_ratio,
            is_transient=is_transient
        )

        t_dsp = (time.perf_counter() - t0) * 1000.0
        system_telemetry.record_chunk(t_dsp)

        telemetry = {
            "type": "TELEMETRY",
            "peak": peak_amp,
            "rms": rms_amp,
            "crest_factor": crest_factor,
            "hf_ratio": hf_ratio,
            "is_transient": is_transient,
            "clap_detected": False,
            "confidence": 0.0,
            "dsp_latency_ms": round(t_dsp, 2),
            # Chỉ số căn chỉnh ồn nền
            "noise_floor_rms": noise_state["noise_floor_rms"],
            "noise_floor_peak": noise_state["noise_floor_peak"],
            "p10_rms": noise_state["p10_rms"],
            "p50_rms": noise_state["p50_rms"],
            "p90_rms": noise_state["p90_rms"],
            "dynamic_energy_thresh": noise_state["dynamic_energy_thresh"],
            "dynamic_crest_thresh": noise_state["dynamic_crest_thresh"],
            "ambient_status": noise_state["ambient_status"],
            "ambient_label": noise_state["ambient_label"],
            "snr_db": noise_state["snr_db"],
            "auto_adaptive": settings.adaptive_noise.enabled
        }

        # 4. Stage 2: Nếu Stage 1 xác nhận xung hợp lệ -> Chạy Double-Buffered ML Classifier
        now = time.time()
        if is_transient:
            logger.info(f"[Stage 1 Transient] Peak={peak_amp:.3f}, Crest={crest_factor:.2f} -> Running AI Classifier...")
            
            if (now - self.last_detection_time > 0.08):
                t_ml_start = time.perf_counter()
                
                # Trích xuất cửa sổ 250ms (4000 samples)
                clip_samples = int(self.sample_rate * settings.audio.clip_duration_sec)
                clip = self.ring_buffer.get_recent(clip_samples)
                
                if len(clip) >= clip_samples // 2:
                    # Auto-Gain Boost cho vỗ nhẹ trong phòng yên tĩnh
                    if self.noise_estimator.ambient_status == "quiet" and peak_amp < 0.08:
                        boost_factor = min(1.8, 0.08 / max(0.015, peak_amp))
                        clip_input = np.clip(clip * boost_factor, -1.0, 1.0)
                    else:
                        clip_input = clip

                    # Trích xuất đặc trưng (Zero NaN/Inf)
                    mel_spec = self.feature_extractor.compute_mel_spectrogram(clip_input)
                    feat_vec = self.feature_extractor.compute_feature_vector(clip_input)

                    # Dự đoán từ ML Classifier
                    is_clap, confidence, clf_details = self.classifier.predict(
                        mel_spectrogram=mel_spec,
                        feature_vector=feat_vec,
                        dsp_metrics=dsp_metrics,
                        confidence_thresh=confidence_thresh
                    )

                    t_ml = (time.perf_counter() - t_ml_start) * 1000.0
                    system_telemetry.record_stage2_inference(t_ml, is_clap, confidence)

                    telemetry["confidence"] = round(confidence, 3)
                    telemetry["clf_details"] = clf_details
                    telemetry["ml_latency_ms"] = round(t_ml, 2)

                    reason = clf_details.get("decision_reason", "")
                    logger.info(f"[Stage 2 Classifier] is_clap={is_clap}, Conf={confidence:.2f} (Thresh={confidence_thresh:.2f}, {t_ml:.1f}ms) -> {reason}")

                    if is_clap:
                        self.last_detection_time = now
                        telemetry["clap_detected"] = True
                        logger.info(f"[CLAP CONFIRMED] Confidence={confidence:.2f} -> Registering with InstantPatternMatcher...")

                        self.pattern_matcher.register_clap(
                            confidence=confidence,
                            meta={
                                "timestamp": now,
                                "confidence": confidence,
                                "peak": peak_amp,
                                "hf_ratio": hf_ratio
                            }
                        )

                        if self.broadcast_callback:
                            self.broadcast_callback({
                                "type": "CLAP_HIT",
                                "confidence": round(confidence, 3),
                                "timestamp": now,
                                "metrics": dsp_metrics
                            })
                    else:
                        # Stage 2 từ chối: Tự động khai thác mẫu khó nếu rơi vào vùng bất định [0.40, 0.70]
                        if 0.40 <= confidence <= 0.70:
                            mined_id = hard_negative_miner.mine_uncertain_sample(
                                profile_name=settings.ml.active_profile,
                                audio_clip=clip_input,
                                confidence=confidence,
                                clf_details=clf_details
                            )
                            if mined_id:
                                system_telemetry.record_mined_negative()

        # Bổ sung telemetry sức khỏe hệ thống định kỳ (mỗi ~30 chunks = ~1 giây)
        if self._check_counter % 30 == 0:
            telemetry["system_health"] = system_telemetry.get_metrics()

        return telemetry

# Global singleton live engine
live_engine = LiveDetectionEngine()
