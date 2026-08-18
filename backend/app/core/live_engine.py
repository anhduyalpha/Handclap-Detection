import numpy as np
import time
import threading
import requests
from typing import Dict, Any, Optional, Callable
from .audio_stream import AudioRingBuffer
from .dsp_detector import DSPTransientDetector
from .feature_extractor import AudioFeatureExtractor
from .pattern_matcher import ClapPatternMatcher
from .noise_estimator import AdaptiveNoiseFloorEstimator
from .trigger_history import trigger_history
from ..models.classifier import ClapClassifier
from ..smart_home.action_dispatcher import action_dispatcher
from ..config import settings

class LiveDetectionEngine:
    """
    Cỗ máy nhận diện âm thanh thời gian thực (Dual-Stage Live Engine).
    Kết nối đồng bộ toàn bộ luồng xử lý:
    Stream Audio (WebSocket) -> Ring Buffer -> Adaptive Noise Tracking -> Stage 1 DSP -> Stage 2 ML -> Pattern Matcher -> Action Dispatcher -> Trigger History
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

    def set_broadcast_callback(self, callback: Callable[[Dict[str, Any]], None]):
        self.broadcast_callback = callback
        action_dispatcher.set_broadcast_callback(callback)

    def reload_model(self, profile_name: str = "default"):
        """Tải lại mô hình (Hot-reload) sau khi train profile mới"""
        self.classifier.load_profile_model(profile_name)

    def _on_pattern_detected(self, pattern: str, count: int, events_meta: list):
        """Xử lý khi PatternMatcher phát hiện chuỗi vỗ tay hoàn chỉnh"""
        print(f"[LiveEngine] [Pattern Matched] Pattern='{pattern}', Count={count} clap(s) -> Dispatching action & Webhook...")
        action_dispatcher.dispatch_pattern(pattern, count, events_meta)

        # Trích xuất 500ms âm thanh quanh cú kích hoạt lưu vào TriggerHistory
        clip_samples = int(self.sample_rate * 0.5)
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

    def process_chunk(self, audio_chunk: np.ndarray) -> Dict[str, Any]:
        """
        Xử lý từng chunk âm thanh float32 nhận được từ client hoặc server mic.
        Trả về metrics thời gian thực để hiển thị visualizer trên UI.
        """
        if len(audio_chunk) == 0:
            return {"rms": 0.0, "peak": 0.0, "stage1": False, "stage2": False}

        # 1. Ghi vào Ring Buffer
        self.ring_buffer.write(audio_chunk)

        # Kiểm tra tự động Hot-Reload nếu có model mới từ Windows sync sang (mỗi ~3s)
        self._check_counter = getattr(self, "_check_counter", 0) + 1
        if self._check_counter % 100 == 0:
            self.classifier.check_and_reload_if_updated()

        # Lấy đoạn lịch sử gần đây (150ms trước) để so sánh năng lượng onset
        history_samples = int(self.sample_rate * 0.15)
        recent_history = self.ring_buffer.get_recent(history_samples)

        # 2. Stage 1: DSP Transient Detector với Ngưỡng Động
        energy_thresh = self.noise_estimator.dynamic_energy_thresh if settings.adaptive_noise.enabled else settings.dsp.energy_threshold
        crest_thresh = self.noise_estimator.dynamic_crest_thresh if settings.adaptive_noise.enabled else settings.dsp.crest_factor_min
        confidence_thresh = self.noise_estimator.dynamic_confidence_thresh if settings.adaptive_noise.enabled else settings.ml.confidence_threshold

        is_transient, dsp_metrics = self.dsp_detector.analyze_chunk(
            chunk=audio_chunk,
            recent_history=recent_history,
            energy_thresh=energy_thresh,
            crest_thresh=crest_thresh,
            hf_ratio_thresh=settings.dsp.hf_energy_ratio_min
        )

        # 3. Cập nhật Bộ ước lượng ồn nền liên tục (Adaptive Noise Floor Tracker)
        peak_amp = dsp_metrics.get("peak_amp", 0.0)
        rms_amp = dsp_metrics.get("rms_amp", 0.0)
        crest_factor = dsp_metrics.get("crest_factor", 0.0)
        hf_ratio = dsp_metrics.get("hf_ratio", 0.0)

        self.noise_estimator.update(
            chunk_rms=rms_amp,
            chunk_peak=peak_amp,
            chunk_crest=crest_factor,
            chunk_hf=hf_ratio,
            is_transient=is_transient
        )

        telemetry = {
            "type": "TELEMETRY",
            "peak": peak_amp,
            "rms": rms_amp,
            "crest_factor": crest_factor,
            "hf_ratio": hf_ratio,
            "is_transient": is_transient,
            "clap_detected": False,
            "confidence": 0.0,
            # Các trường Căn chỉnh ồn nền liên tục
            "noise_floor_rms": round(float(self.noise_estimator.noise_floor_rms), 4),
            "noise_floor_peak": round(float(self.noise_estimator.noise_floor_peak), 4),
            "dynamic_energy_thresh": round(float(self.noise_estimator.dynamic_energy_thresh), 4),
            "dynamic_crest_thresh": round(float(self.noise_estimator.dynamic_crest_thresh), 2),
            "ambient_status": self.noise_estimator.ambient_status,
            "auto_adaptive": settings.adaptive_noise.enabled
        }

        # 4. Stage 2: Nếu Stage 1 nghi ngờ có xung vỗ tay -> Chạy Deep Learning Classifier
        now = time.time()
        if is_transient:
            print(f"[LiveEngine] [Stage 1 Transient] Peak={peak_amp:.3f}, Crest={crest_factor:.2f}, EnergyThresh={energy_thresh:.3f}")
            
            if (now - self.last_detection_time > 0.30): # Tối thiểu 300ms giữa 2 lần nhận diện để triệt tiêu hoàn toàn tiếng vọng (reverb/echo)
                # Trích xuất cửa sổ 250ms (4000 samples) xung quanh thời điểm phát hiện
                clip_samples = int(self.sample_rate * settings.audio.clip_duration_sec)
                clip = self.ring_buffer.get_recent(clip_samples)
                
                if len(clip) >= clip_samples // 2:
                    # Trích xuất đặc trưng
                    mel_spec = self.feature_extractor.compute_mel_spectrogram(clip)
                    feat_vec = self.feature_extractor.compute_feature_vector(clip)

                    # Dự đoán xác suất từ ML Classifier kèm ngưỡng động
                    is_clap, confidence, clf_details = self.classifier.predict(
                        mel_spectrogram=mel_spec,
                        feature_vector=feat_vec,
                        dsp_metrics=dsp_metrics,
                        confidence_thresh=confidence_thresh
                    )

                    telemetry["confidence"] = round(confidence, 3)
                    telemetry["clf_details"] = clf_details

                    reason = clf_details.get("decision_reason", "")
                    print(f"[LiveEngine] [Stage 2 Classifier] is_clap={is_clap}, Confidence={confidence:.2f} (Thresh={confidence_thresh:.2f}) -> {reason}")

                    if is_clap:
                        self.last_detection_time = now
                        telemetry["clap_detected"] = True
                        print(f"[LiveEngine] [CLAP CONFIRMED] Confidence={confidence:.2f} -> Registering with PatternMatcher...")

                        # Ghi nhận vào bộ đếm nhịp vỗ tay (PatternMatcher sẽ gọi ActionDispatcher gửi Webhook duy nhất)
                        self.pattern_matcher.register_clap(
                            confidence=confidence,
                            meta={
                                "timestamp": now,
                                "confidence": confidence,
                                "peak": peak_amp,
                                "hf_ratio": hf_ratio
                            }
                        )

                        # Bắn sự kiện tức thì CLAP_HIT để UI chớp sáng
                        if self.broadcast_callback:
                            self.broadcast_callback({
                                "type": "CLAP_HIT",
                                "confidence": round(confidence, 3),
                                "timestamp": now,
                                "metrics": dsp_metrics
                            })

        return telemetry

# Global singleton live engine
live_engine = LiveDetectionEngine()
