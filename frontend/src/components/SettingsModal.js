/**
 * Component: SettingsModal (Cài đặt độ nhạy âm thanh, nhịp vỗ tay và Webhook IoT)
 */
import { ApiClient } from '../services/api_client.js';

export class SettingsModal {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.isOpen = false;
    this.settings = null;
    this.init();
  }

  init() {
    this.render();
    this.loadSettings();
  }

  async loadSettings() {
    try {
      this.settings = await ApiClient.getSettings();
      this.populateForm();
    } catch (e) {
      console.warn('Could not load settings:', e);
    }
  }

  render() {
    this.container.innerHTML = `
      <div class="modal-backdrop" id="settings-modal-backdrop">
        <div class="modal-dialog">
          <div class="card-header" style="margin-bottom: 1.5rem;">
            <div class="card-title">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3"></circle>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
              </svg>
              Cài Đặt Hệ Thống & Nhận Diện
            </div>
            <button class="btn btn-secondary" id="btn-close-settings" style="padding: 4px 8px;">✕</button>
          </div>

          <form id="settings-form">
            <!-- Adaptive Room Noise Continuous Calibration -->
            <div class="form-group" style="background: rgba(0, 229, 255, 0.05); border: 1px solid rgba(0, 229, 255, 0.2); border-radius: 8px; padding: 0.85rem;">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
                <span style="font-weight: 600; color: var(--accent-cyan);">⚡ Tự Căn Chỉnh Độ Ồn Phòng Liên Tục</span>
                <label class="switch-toggle">
                  <input type="checkbox" id="input-adaptive-enabled" checked>
                  <span class="slider-toggle"></span>
                </label>
              </div>
              <small style="color: var(--text-muted); font-size: 0.75rem; display: block; margin-bottom: 0.75rem;">
                Hệ thống tự động theo dõi mức ồn môi trường và liên tục hiệu chỉnh ngưỡng năng lượng, chống báo giả khi phòng ồn và tăng độ nhạy khi phòng yên tĩnh.
              </small>

              <div id="adaptive-params-group">
                <div class="form-label" style="display: flex; justify-content: space-between; font-size: 0.8rem;">
                  <span>Biên an toàn trên đỉnh nhiễu (Margin Factor)</span>
                  <span id="label-margin-factor">1.6x</span>
                </div>
                <input type="range" class="form-range" id="input-margin-factor" min="1.2" max="2.5" step="0.1" value="1.6">
              </div>
            </div>

            <!-- Stage 1 Energy Threshold (Manual Fallback) -->
            <div class="form-group">
              <div class="form-label" style="display: flex; justify-content: space-between;">
                <span>Ngưỡng năng lượng tĩnh Stage 1 (Fallback Peak)</span>
                <span id="label-energy-thresh">0.028</span>
              </div>
              <input type="range" class="form-range" id="input-energy-thresh" min="0.01" max="0.15" step="0.005" value="0.028">
              <small style="color: var(--text-muted); font-size: 0.75rem;">Sử dụng khi tắt chế độ Tự căn chỉnh liên tục.</small>
            </div>

            <!-- Stage 2 AI Confidence Threshold -->
            <div class="form-group">
              <div class="form-label" style="display: flex; justify-content: space-between;">
                <span>Độ tin cậy AI cơ bản (Base Confidence)</span>
                <span id="label-conf-thresh">70%</span>
              </div>
              <input type="range" class="form-range" id="input-conf-thresh" min="0.50" max="0.95" step="0.05" value="0.70">
            </div>

            <!-- Timing Window -->
            <div class="form-group">
              <div class="form-label" style="display: flex; justify-content: space-between;">
                <span>Cửa sổ thời gian vỗ kép nhanh (Max Clap Window)</span>
                <span id="label-window-thresh">420 ms</span>
              </div>
              <input type="range" class="form-range" id="input-window-thresh" min="200" max="800" step="20" value="420">
            </div>

            <!-- Action Mapping -->
            <div class="form-group">
              <div class="form-label">Ánh xạ hành động theo nhịp vỗ</div>
              <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                  <span style="font-size: 0.85rem;">👏 1 Vỗ (Single):</span>
                  <select class="form-select" id="select-act-single" style="width: 60%;">
                    <option value="none" selected>🚫 Bỏ qua (Chống nhận nhầm 100%)</option>
                    <option value="toggle_power">Bật / Tắt Đèn (Toggle Power)</option>
                    <option value="next_color">Đổi Màu (Next RGB Color)</option>
                    <option value="party_mode">Party Mode</option>
                  </select>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between;">
                  <span style="font-size: 0.85rem;">👏👏 2 Vỗ (Double):</span>
                  <select class="form-select" id="select-act-double" style="width: 60%;">
                    <option value="toggle_power" selected>Bật / Tắt Đèn (Toggle Power)</option>
                    <option value="next_color">Đổi Màu (Next RGB Color)</option>
                    <option value="party_mode">Party Mode</option>
                    <option value="none">🚫 Bỏ qua (Không làm gì)</option>
                  </select>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between;">
                  <span style="font-size: 0.85rem;">👏👏👏 3 Vỗ (Triple):</span>
                  <select class="form-select" id="select-act-triple" style="width: 60%;">
                    <option value="party_mode" selected>Party Strobe Mode</option>
                    <option value="next_color">Đổi Màu (Next RGB Color)</option>
                    <option value="toggle_power">Bật / Tắt Đèn (Toggle Power)</option>
                    <option value="none">🚫 Bỏ qua (Không làm gì)</option>
                  </select>
                </div>
              </div>
            </div>

            <!-- External Webhook URL -->
            <div class="form-group">
              <div class="form-label">Webhook URL điều khiển IoT bên ngoài (Tuỳ chọn)</div>
              <input type="text" class="form-input" id="input-webhook" placeholder="http://192.168.1.100/api/relay hoặc Home Assistant webhook">
            </div>

            <!-- Windows Studio URL (Real-time Forwarding) -->
            <div class="form-group" style="background: rgba(99, 102, 241, 0.05); border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 8px; padding: 0.85rem;">
              <div class="form-label" style="color: #a5b4fc; font-weight: 600;">💻 URL Máy Windows Studio (Tự động nhận mẫu Báo Giả)</div>
              <input type="text" class="form-input" id="input-windows-url" placeholder="http://192.168.2.134:8001">
              <small style="color: var(--text-muted); font-size: 0.75rem; display: block; margin-top: 0.35rem;">
                Khi bấm Báo Giả trên Linux, đoạn âm thanh sẽ tự động truyền trực tiếp sang máy tính Windows này để lưu vào tập huấn luyện.
              </small>
            </div>

            <div style="display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1.5rem;">
              <button type="button" class="btn btn-secondary" id="btn-cancel-settings">Huỷ</button>
              <button type="submit" class="btn btn-primary">Lưu Cài Đặt</button>
            </div>
          </form>
        </div>
      </div>
    `;

    this.setupListeners();
  }

  setupListeners() {
    const backdrop = this.container.querySelector('#settings-modal-backdrop');
    const btnClose = this.container.querySelector('#btn-close-settings');
    const btnCancel = this.container.querySelector('#btn-cancel-settings');
    const form = this.container.querySelector('#settings-form');

    const inputAdaptive = this.container.querySelector('#input-adaptive-enabled');
    const inputMargin = this.container.querySelector('#input-margin-factor');
    const labelMargin = this.container.querySelector('#label-margin-factor');
    inputMargin?.addEventListener('input', (e) => {
      if (labelMargin) labelMargin.textContent = `${e.target.value}x`;
    });

    const inputEnergy = this.container.querySelector('#input-energy-thresh');
    const labelEnergy = this.container.querySelector('#label-energy-thresh');
    inputEnergy?.addEventListener('input', (e) => {
      if (labelEnergy) labelEnergy.textContent = e.target.value;
    });

    const inputConf = this.container.querySelector('#input-conf-thresh');
    const labelConf = this.container.querySelector('#label-conf-thresh');
    inputConf?.addEventListener('input', (e) => {
      if (labelConf) labelConf.textContent = `${Math.round(e.target.value * 100)}%`;
    });

    const inputWindow = this.container.querySelector('#input-window-thresh');
    const labelWindow = this.container.querySelector('#label-window-thresh');
    inputWindow?.addEventListener('input', (e) => {
      if (labelWindow) labelWindow.textContent = `${e.target.value} ms`;
    });

    btnClose?.addEventListener('click', () => this.close());
    btnCancel?.addEventListener('click', () => this.close());

    form?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const updated = {
        adaptive_noise_enabled: inputAdaptive ? inputAdaptive.checked : true,
        margin_factor: inputMargin ? parseFloat(inputMargin.value) : 1.6,
        energy_threshold: parseFloat(inputEnergy.value),
        confidence_threshold: parseFloat(inputConf.value),
        max_inter_clap_ms: parseInt(inputWindow.value, 10),
        single_clap_action: this.container.querySelector('#select-act-single').value,
        double_clap_action: this.container.querySelector('#select-act-double').value,
        triple_clap_action: this.container.querySelector('#select-act-triple').value,
        webhook_url: this.container.querySelector('#input-webhook').value,
        windows_studio_url: this.container.querySelector('#input-windows-url')?.value || 'http://192.168.2.134:8001'
      };

      try {
        await ApiClient.updateSettings(updated);
        this.close();
      } catch (err) {
        alert('Lỗi lưu cài đặt: ' + err.message);
      }
    });
  }

  populateForm() {
    if (!this.settings) return;
    const { dsp, adaptive_noise, ml, pattern, light, windows_studio_url } = this.settings;

    const inputAdaptive = this.container.querySelector('#input-adaptive-enabled');
    const inputMargin = this.container.querySelector('#input-margin-factor');
    const labelMargin = this.container.querySelector('#label-margin-factor');
    if (adaptive_noise) {
      if (inputAdaptive) inputAdaptive.checked = adaptive_noise.enabled !== false;
      if (inputMargin) {
        inputMargin.value = adaptive_noise.margin_factor || 1.6;
        if (labelMargin) labelMargin.textContent = `${adaptive_noise.margin_factor || 1.6}x`;
      }
    }

    const inputEnergy = this.container.querySelector('#input-energy-thresh');
    const labelEnergy = this.container.querySelector('#label-energy-thresh');
    if (inputEnergy && dsp) {
      inputEnergy.value = dsp.energy_threshold;
      if (labelEnergy) labelEnergy.textContent = dsp.energy_threshold;
    }

    const inputConf = this.container.querySelector('#input-conf-thresh');
    const labelConf = this.container.querySelector('#label-conf-thresh');
    if (inputConf && ml) {
      inputConf.value = ml.confidence_threshold;
      if (labelConf) labelConf.textContent = `${Math.round(ml.confidence_threshold * 100)}%`;
    }

    const inputWindow = this.container.querySelector('#input-window-thresh');
    const labelWindow = this.container.querySelector('#label-window-thresh');
    if (inputWindow && pattern) {
      inputWindow.value = pattern.max_inter_clap_ms;
      if (labelWindow) labelWindow.textContent = `${pattern.max_inter_clap_ms} ms`;
    }

    if (light) {
      const sSingle = this.container.querySelector('#select-act-single');
      const sDouble = this.container.querySelector('#select-act-double');
      const sTriple = this.container.querySelector('#select-act-triple');
      const inWebhook = this.container.querySelector('#input-webhook');

      if (sSingle) sSingle.value = light.single_clap_action;
      if (sDouble) sDouble.value = light.double_clap_action;
      if (sTriple) sTriple.value = light.triple_clap_action;
      if (inWebhook) inWebhook.value = light.webhook_url || '';
    }

    const inWindowsUrl = this.container.querySelector('#input-windows-url');
    if (inWindowsUrl) {
      inWindowsUrl.value = windows_studio_url || 'http://192.168.2.134:8001';
    }
  }

  open() {
    this.isOpen = true;
    this.loadSettings();
    const backdrop = this.container.querySelector('#settings-modal-backdrop');
    backdrop?.classList.add('open');
  }

  close() {
    this.isOpen = false;
    const backdrop = this.container.querySelector('#settings-modal-backdrop');
    backdrop?.classList.remove('open');
  }
}
