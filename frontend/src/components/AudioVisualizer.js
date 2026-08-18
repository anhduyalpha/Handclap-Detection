/**
 * Component: AudioVisualizer (Oscilloscope Sóng Âm Thanh, Dải Năng Lượng, Ngưỡng Động & AI Confidence)
 */
import { audioStreamManager } from '../services/audio_recorder.js';
import { wsClient } from '../services/websocket_client.js';

export class AudioVisualizer {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.canvas = null;
    this.ctx = null;
    this.animationFrameId = null;
    
    this.telemetryData = {
      peak: 0.0,
      rms: 0.0,
      crest: 0.0,
      hfRatio: 0.0,
      confidence: 0.0,
      noiseFloorRms: 0.008,
      noiseFloorPeak: 0.015,
      dynamicEnergyThresh: 0.028,
      dynamicCrestThresh: 2.4,
      ambientStatus: 'normal',
      autoAdaptive: true
    };

    this.init();
  }

  init() {
    this.render();
    this.setupCanvas();
    this.setupListeners();
    this.startRenderLoop();
  }

  render() {
    this.container.innerHTML = `
      <div class="glass-card visualizer-card">
        <div class="card-header">
          <div class="card-title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M2 10v3M6 6v11M10 3v18M14 8v7M18 5v13M22 10v3"></path>
            </svg>
            Biểu Đồ Sóng Âm & AI Detector
          </div>
          <div class="header-status-badges" style="display: flex; gap: 0.5rem; align-items: center;">
            <div id="ambient-status-badge" class="status-pill room-status normal" title="Trạng thái tự căn chỉnh độ ồn nền">
              <span class="room-status-dot"></span>
              <span id="ambient-status-text">🌿 Phòng chuẩn</span>
            </div>
            <div id="ai-status-badge" class="status-pill">
              <span class="status-dot"></span>
              <span id="ai-status-text">Đang lắng nghe...</span>
            </div>
          </div>
        </div>

        <!-- Oscilloscope Waveform Canvas -->
        <div class="canvas-container" id="canvas-container">
          <canvas class="oscilloscope-canvas" id="oscilloscope-canvas"></canvas>
          <div class="canvas-legend">
            <span class="legend-item"><span class="legend-dot cyan"></span> Sóng âm</span>
            <span class="legend-item"><span class="legend-dot amber"></span> Ngưỡng kích hoạt động</span>
          </div>
        </div>

        <!-- Energy, Noise Floor & AI Gauges -->
        <div class="gauges-grid four-cols">
          <div class="gauge-item">
            <div class="gauge-label">
              <span>Độ lớn âm thanh (Peak)</span>
              <span id="val-peak">0.000</span>
            </div>
            <div class="gauge-bar-bg">
              <div class="gauge-bar-fill" id="bar-peak"></div>
            </div>
          </div>

          <div class="gauge-item">
            <div class="gauge-label">
              <span>Mức ồn phòng (Floor RMS)</span>
              <span id="val-floor">0.008</span>
            </div>
            <div class="gauge-bar-bg">
              <div class="gauge-bar-fill warning" id="bar-floor"></div>
            </div>
          </div>

          <div class="gauge-item">
            <div class="gauge-label">
              <span>Dải cao HF Ratio (>2kHz)</span>
              <span id="val-hf">0.00</span>
            </div>
            <div class="gauge-bar-bg">
              <div class="gauge-bar-fill success" id="bar-hf"></div>
            </div>
          </div>

          <div class="gauge-item">
            <div class="gauge-label">
              <span>Độ tin cậy AI (Confidence)</span>
              <span id="val-conf">0%</span>
            </div>
            <div class="gauge-bar-bg">
              <div class="gauge-bar-fill danger" id="bar-conf"></div>
            </div>
          </div>
        </div>

        <!-- History Timeline -->
        <div class="timeline-section">
          <div class="timeline-header">
            <span>Nhật ký phát hiện gần đây</span>
            <button class="btn btn-secondary" id="btn-clear-log" style="padding: 2px 8px; font-size: 0.7rem;">Xoá</button>
          </div>
          <div class="timeline-list" id="timeline-list">
            <div style="color: var(--text-muted); font-size: 0.8rem; text-align: center; padding: 1rem;">
              Chưa có sự kiện vỗ tay nào. Hãy thử vỗ tay vào micro!
            </div>
          </div>
        </div>
      </div>
    `;
  }

  setupCanvas() {
    this.canvas = this.container.querySelector('#oscilloscope-canvas');
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.resizeCanvas();
    window.addEventListener('resize', () => this.resizeCanvas());
  }

  resizeCanvas() {
    if (!this.canvas) return;
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width * (window.devicePixelRatio || 1);
    this.canvas.height = rect.height * (window.devicePixelRatio || 1);
    this.ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
  }

  setupListeners() {
    this.container.querySelector('#btn-clear-log')?.addEventListener('click', () => {
      const list = this.container.querySelector('#timeline-list');
      if (list) {
        list.innerHTML = `<div style="color: var(--text-muted); font-size: 0.8rem; text-align: center; padding: 1rem;">Đã làm mới nhật ký.</div>`;
      }
    });

    // Lắng nghe Telemetry từ WebSocket
    wsClient.on('TELEMETRY', (data) => {
      this.telemetryData = {
        peak: data.peak || 0.0,
        rms: data.rms || 0.0,
        crest: data.crest_factor || 0.0,
        hfRatio: data.hf_ratio || 0.0,
        confidence: data.confidence || 0.0,
        noiseFloorRms: data.noise_floor_rms || 0.008,
        noiseFloorPeak: data.noise_floor_peak || 0.015,
        dynamicEnergyThresh: data.dynamic_energy_thresh || 0.028,
        dynamicCrestThresh: data.dynamic_crest_thresh || 2.4,
        ambientStatus: data.ambient_status || 'normal',
        ambientLabel: data.ambient_label || '☀️ Phòng Tiêu Chuẩn',
        snrDb: data.snr_db || 0.0,
        autoAdaptive: data.auto_adaptive !== false
      };
      this.updateGauges();
      this.updateAmbientBadge();
    });

    // Lắng nghe Clap Hit (Hiệu ứng chớp sáng tức thì)
    wsClient.on('CLAP_HIT', (data) => {
      this.triggerFlash();
    });

    // Lắng nghe Action Triggered
    wsClient.on('ACTION_TRIGGERED', (data) => {
      this.addTimelineEvent(data);
    });
  }

  triggerFlash() {
    const container = this.container.querySelector('#canvas-container');
    if (container) {
      container.classList.remove('clap-flash');
      void container.offsetWidth; // Trigger reflow
      container.classList.add('clap-flash');
    }
  }

  updateAmbientBadge() {
    const badge = this.container.querySelector('#ambient-status-badge');
    const text = this.container.querySelector('#ambient-status-text');
    if (!badge || !text) return;

    badge.className = 'status-pill room-status';
    const snrText = this.telemetryData.snrDb ? ` | SNR ${this.telemetryData.snrDb}dB` : '';

    if (this.telemetryData.ambientStatus === 'quiet') {
      badge.classList.add('quiet');
      text.textContent = `🌙 Phòng Yên Tĩnh (Bắt xa 3-5m${snrText})`;
    } else if (this.telemetryData.ambientStatus === 'noisy') {
      badge.classList.add('noisy');
      text.textContent = `🌪️ Phòng Ồn (Chống báo giả${snrText})`;
    } else {
      badge.classList.add('normal');
      text.textContent = `☀️ Phòng Chuẩn (${snrText || 'Cân bằng'})`;
    }
  }

  updateGauges() {
    const valPeak = this.container.querySelector('#val-peak');
    const barPeak = this.container.querySelector('#bar-peak');
    const valFloor = this.container.querySelector('#val-floor');
    const barFloor = this.container.querySelector('#bar-floor');
    const valHf = this.container.querySelector('#val-hf');
    const barHf = this.container.querySelector('#bar-hf');
    const valConf = this.container.querySelector('#val-conf');
    const barConf = this.container.querySelector('#bar-conf');

    if (valPeak && barPeak) {
      valPeak.textContent = this.telemetryData.peak.toFixed(3);
      barPeak.style.width = `${Math.min(100, this.telemetryData.peak * 350)}%`;
    }

    if (valFloor && barFloor) {
      valFloor.textContent = `${this.telemetryData.noiseFloorRms.toFixed(3)} (Ngưỡng: ${this.telemetryData.dynamicEnergyThresh.toFixed(3)})`;
      barFloor.style.width = `${Math.min(100, this.telemetryData.noiseFloorRms * 1200)}%`;
    }

    if (valHf && barHf) {
      valHf.textContent = this.telemetryData.hfRatio.toFixed(2);
      barHf.style.width = `${Math.min(100, this.telemetryData.hfRatio * 100)}%`;
    }

    if (valConf && barConf) {
      const pct = Math.round(this.telemetryData.confidence * 100);
      valConf.textContent = `${pct}%`;
      barConf.style.width = `${pct}%`;
    }
  }

  addTimelineEvent(event) {
    const list = this.container.querySelector('#timeline-list');
    if (!list) return;

    if (list.children.length === 1 && list.children[0].textContent.includes('Chưa có sự kiện')) {
      list.innerHTML = '';
    }

    const timeStr = new Date(event.timestamp * 1000).toLocaleTimeString();
    const patternLabels = {
      single: '👏 1 Vỗ (Single)',
      double: '👏👏 2 Vỗ (Double)',
      triple: '👏👏👏 3 Vỗ (Triple)',
      manual_update: '⚙️ Thủ công'
    };

    const actionLabels = {
      toggle_power: 'Bật/Tắt đèn',
      next_color: 'Đổi màu RGB',
      party_mode: 'Party Strobe',
      '': 'Phát hiện vỗ tay'
    };

    const item = document.createElement('div');
    item.className = 'timeline-item';
    item.innerHTML = `
      <div style="display: flex; align-items: center; gap: 0.5rem;">
        <span class="timeline-item-badge ${event.pattern || 'single'}">
          ${patternLabels[event.pattern] || event.pattern}
        </span>
        <span style="color: var(--text-primary); font-weight: 600;">
          ${actionLabels[event.action] || event.action}
        </span>
      </div>
      <span style="color: var(--text-muted); font-size: 0.75rem;">${timeStr}</span>
    `;

    list.insertBefore(item, list.firstChild);

    while (list.children.length > 15) {
      list.removeChild(list.lastChild);
    }
  }

  startRenderLoop() {
    const bufferLength = 256;
    const timeData = new Uint8Array(bufferLength);
    const freqData = new Uint8Array(bufferLength);

    const render = () => {
      this.animationFrameId = requestAnimationFrame(render);

      if (!this.ctx || !this.canvas) return;

      const rect = this.canvas.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;

      this.ctx.clearRect(0, 0, width, height);

      // Background grid lines
      this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
      this.ctx.lineWidth = 1;
      this.ctx.beginPath();
      this.ctx.moveTo(0, height / 2);
      this.ctx.lineTo(width, height / 2);
      this.ctx.stroke();

      if (audioStreamManager.isStreaming) {
        audioStreamManager.getTimeDomainData(timeData);
        audioStreamManager.getFrequencyData(freqData);

        // 1. Vẽ Frequency Spectrogram Bars ở nửa mờ phía sau
        const barWidth = width / (bufferLength / 2);
        for (let i = 0; i < bufferLength / 2; i++) {
          const barHeight = (freqData[i] / 255) * (height * 0.65);
          const x = i * barWidth;
          const y = height - barHeight;

          const grad = this.ctx.createLinearGradient(0, height, 0, y);
          grad.addColorStop(0, 'rgba(0, 229, 255, 0.05)');
          grad.addColorStop(1, 'rgba(138, 43, 226, 0.25)');

          this.ctx.fillStyle = grad;
          this.ctx.fillRect(x, y, barWidth - 1, barHeight);
        }

        // 2. Vẽ Vạch Ngưỡng Động (Dynamic Threshold Lines: Trên & Dưới)
        const threshScale = Math.min(height * 0.45, this.telemetryData.dynamicEnergyThresh * height * 3.2);
        const topThreshY = height / 2 - threshScale;
        const bottomThreshY = height / 2 + threshScale;

        this.ctx.save();
        this.ctx.strokeStyle = 'rgba(255, 179, 0, 0.6)';
        this.ctx.lineWidth = 1.2;
        this.ctx.setLineDash([4, 4]);

        // Đường trên
        this.ctx.beginPath();
        this.ctx.moveTo(0, topThreshY);
        this.ctx.lineTo(width, topThreshY);
        this.ctx.stroke();

        // Đường dưới
        this.ctx.beginPath();
        this.ctx.moveTo(0, bottomThreshY);
        this.ctx.lineTo(width, bottomThreshY);
        this.ctx.stroke();

        // Nhãn ngưỡng động nhỏ góc phải
        this.ctx.fillStyle = 'rgba(255, 179, 0, 0.85)';
        this.ctx.font = '10px "Plus Jakarta Sans", sans-serif';
        this.ctx.textAlign = 'right';
        this.ctx.fillText(`Ngưỡng: ${this.telemetryData.dynamicEnergyThresh.toFixed(3)}`, width - 8, topThreshY - 4);
        this.ctx.restore();

        // 3. Vẽ Neon Oscilloscope Waveform Line
        this.ctx.lineWidth = 2.5;
        this.ctx.strokeStyle = '#00e5ff';
        this.ctx.shadowColor = '#00e5ff';
        this.ctx.shadowBlur = 8;

        this.ctx.beginPath();
        const sliceWidth = width / bufferLength;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
          const v = timeData[i] / 128.0; // [0, 2] -> 1 is center
          const y = (v * height) / 2;

          if (i === 0) {
            this.ctx.moveTo(x, y);
          } else {
            this.ctx.lineTo(x, y);
          }
          x += sliceWidth;
        }

        this.ctx.stroke();
        this.ctx.shadowBlur = 0; // Reset shadow
      } else {
        // Idle straight line
        this.ctx.lineWidth = 1.5;
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
        this.ctx.beginPath();
        this.ctx.moveTo(0, height / 2);
        this.ctx.lineTo(width, height / 2);
        this.ctx.stroke();

        this.ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
        this.ctx.font = '12px "Plus Jakarta Sans", sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.fillText('Bật Micro ở góc trên để bắt đầu lắng nghe sóng âm', width / 2, height / 2 - 12);
      }
    };

    render();
  }
}

