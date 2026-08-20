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
        <div class="modal-dialog" style="max-width: 580px; max-height: 90vh; overflow-y: auto;">
          <div class="card-header" style="margin-bottom: 1.2rem;">
            <div class="card-title">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3"></circle>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
              </svg>
              Cài Đặt Độ Nhạy & Hệ Thống
            </div>
            <button class="btn btn-secondary" id="btn-close-settings" style="padding: 4px 8px;">✕</button>
          </div>

          <form id="settings-form">
            <!-- Quick Sensitivity Presets -->
            <div class="form-group" style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 0.85rem;">
              <div class="form-label" style="font-weight: 600; color: var(--accent-cyan); margin-bottom: 0.5rem;">
                🎯 Chế Độ Độ Nhạy Nhanh (Sensitivity Presets)
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.5rem;">
                <button type="button" class="btn btn-secondary preset-btn" id="btn-preset-high" style="font-size: 0.75rem; padding: 6px 4px; text-align: center;">
                  ⚡ Siêu Nhạy<br><small style="color: #67e8f9; font-size: 0.65rem;">(3-5m / Vỗ nhẹ)</small>
                </button>
                <button type="button" class="btn btn-secondary preset-btn" id="btn-preset-balanced" style="font-size: 0.75rem; padding: 6px 4px; text-align: center;">
                  ⚖️ Cân Bằng<br><small style="color: #a5b4fc; font-size: 0.65rem;">(1.5-3m / Chuẩn)</small>
                </button>
                <button type="button" class="btn btn-secondary preset-btn" id="btn-preset-strict" style="font-size: 0.75rem; padding: 6px 4px; text-align: center;">
                  🛡️ Chống Nhiễu<br><small style="color: #fca5a5; font-size: 0.65rem;">(Phòng ồn ào)</small>
                </button>
              </div>
            </div>

            <!-- Adaptive Room Noise Continuous Calibration -->
            <div class="form-group" style="background: rgba(0, 229, 255, 0.05); border: 1px solid rgba(0, 229, 255, 0.2); border-radius: 8px; padding: 0.85rem;">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
                <span style="font-weight: 600; color: var(--accent-cyan); font-size: 0.85rem;">⚡ Tự Căn Chỉnh Độ Ồn Phòng Liên Tục</span>
                <label class="switch-toggle">
                  <input type="checkbox" id="input-adaptive-enabled" checked>
                  <span class="slider-toggle"></span>
                </label>
              </div>
              <small style="color: var(--text-muted); font-size: 0.75rem; display: block; margin-bottom: 0.75rem;">
                Tự động theo dõi độ ồn môi trường để hạ ngưỡng khi phòng yên tĩnh và tăng chống nhiễu khi phòng ồn.
              </small>

              <div id="adaptive-params-group">
                <div class="form-label" style="display: flex; justify-content: space-between; font-size: 0.8rem;">
                  <span>Biên an toàn trên đỉnh nhiễu (Margin Factor)</span>
                  <span id="label-margin-factor">1.30x</span>
                </div>
                <input type="range" class="form-range" id="input-margin-factor" min="1.0" max="2.5" step="0.05" value="1.30">
              </div>
            </div>

            <!-- Detailed Threshold Sliders -->
            <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.07); border-radius: 8px; padding: 0.85rem; margin-bottom: 1rem;">
              <div style="font-size: 0.8rem; font-weight: 600; color: #e2e8f0; margin-bottom: 0.75rem;">🛠️ Tinh Chỉnh Chi Tiết (Custom Parameters):</div>
              
              <!-- Stage 1 Energy Threshold -->
              <div class="form-group" style="margin-bottom: 0.85rem;">
                <div class="form-label" style="display: flex; justify-content: space-between; font-size: 0.78rem;">
                  <span>1. Ngưỡng năng lượng Stage 1 (Energy Threshold)</span>
                  <span id="label-energy-thresh" style="color: var(--accent-cyan); font-weight: 600;">0.018</span>
                </div>
                <input type="range" class="form-range" id="input-energy-thresh" min="0.005" max="0.080" step="0.001" value="0.018">
                <small style="color: var(--text-muted); font-size: 0.7rem;">Càng thấp thì càng bắt được tiếng vỗ nhẹ từ xa.</small>
              </div>

              <!-- Crest Factor Min -->
              <div class="form-group" style="margin-bottom: 0.85rem;">
                <div class="form-label" style="display: flex; justify-content: space-between; font-size: 0.78rem;">
                  <span>2. Độ nhọn xung âm thanh (Crest Factor Peak/RMS)</span>
                  <span id="label-crest-thresh" style="color: var(--accent-cyan); font-weight: 600;">1.8x</span>
                </div>
                <input type="range" class="form-range" id="input-crest-thresh" min="1.2" max="3.5" step="0.1" value="1.8">
                <small style="color: var(--text-muted); font-size: 0.7rem;">Tiếng vỗ tay có xung nhọn cao (>1.5), tiếng nói chuyện có xung thấp (~1.2).</small>
              </div>

              <!-- Stage 2 AI Confidence Threshold -->
              <div class="form-group" style="margin-bottom: 0.85rem;">
                <div class="form-label" style="display: flex; justify-content: space-between; font-size: 0.78rem;">
                  <span>3. Độ tin cậy Não AI Stage 2 (Confidence Threshold)</span>
                  <span id="label-conf-thresh" style="color: var(--accent-cyan); font-weight: 600;">50%</span>
                </div>
                <input type="range" class="form-range" id="input-conf-thresh" min="0.30" max="0.95" step="0.05" value="0.50">
                <small style="color: var(--text-muted); font-size: 0.7rem;">Mức 40%-50% bắt rất nhạy, mức 70%+ yêu cầu tiếng vỗ cực chuẩn.</small>
              </div>

              <!-- Timing Window -->
              <div class="form-group" style="margin-bottom: 0;">
                <div class="form-label" style="display: flex; justify-content: space-between; font-size: 0.78rem;">
                  <span>4. Cửa sổ chờ cú vỗ thứ 2 (Double Clap Window)</span>
                  <span id="label-window-thresh" style="color: var(--accent-cyan); font-weight: 600;">750 ms</span>
                </div>
                <input type="range" class="form-range" id="input-window-thresh" min="300" max="1000" step="25" value="750">
                <small style="color: var(--text-muted); font-size: 0.7rem;">Khoảng thời gian cho phép giữa 2 cú vỗ liên tiếp.</small>
              </div>
            </div>

            <!-- Action Mapping -->
            <div class="form-group">
              <div class="form-label">Hành động khi vỗ 2 tiếng liên tiếp (Double Clap)</div>
              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span style="font-size: 0.85rem; font-weight: 600; color: var(--accent-cyan);">👏👏 2 Vỗ (Double):</span>
                <select class="form-select" id="select-act-double" style="width: 65%;">
                  <option value="toggle_power" selected>💡 Bật / Tắt Đèn (Toggle Power)</option>
                  <option value="next_color">🎨 Đổi Màu (Next RGB Color)</option>
                  <option value="party_mode">🎉 Party Strobe Mode</option>
                </select>
              </div>
            </div>

            <!-- External Webhook URL -->
            <div class="form-group">
              <div class="form-label">Webhook URL Home Assistant / IoT</div>
              <input type="text" class="form-input" id="input-webhook" placeholder="http://192.168.2.171:8123/api/webhook/vo_tay_toggle_den">
            </div>

            <div style="display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1.2rem;">
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

    const inputCrest = this.container.querySelector('#input-crest-thresh');
    const labelCrest = this.container.querySelector('#label-crest-thresh');
    inputCrest?.addEventListener('input', (e) => {
      if (labelCrest) labelCrest.textContent = `${e.target.value}x`;
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

    // Preset Buttons
    const btnPresetHigh = this.container.querySelector('#btn-preset-high');
    const btnPresetBalanced = this.container.querySelector('#btn-preset-balanced');
    const btnPresetStrict = this.container.querySelector('#btn-preset-strict');

    btnPresetHigh?.addEventListener('click', () => {
      if (inputEnergy) { inputEnergy.value = 0.012; if (labelEnergy) labelEnergy.textContent = '0.012'; }
      if (inputCrest) { inputCrest.value = 1.5; if (labelCrest) labelCrest.textContent = '1.5x'; }
      if (inputConf) { inputConf.value = 0.40; if (labelConf) labelConf.textContent = '40%'; }
      if (inputWindow) { inputWindow.value = 800; if (labelWindow) labelWindow.textContent = '800 ms'; }
      if (inputMargin) { inputMargin.value = 1.15; if (labelMargin) labelMargin.textContent = '1.15x'; }
      this._highlightPresetBtn('btn-preset-high');
    });

    btnPresetBalanced?.addEventListener('click', () => {
      if (inputEnergy) { inputEnergy.value = 0.020; if (labelEnergy) labelEnergy.textContent = '0.020'; }
      if (inputCrest) { inputCrest.value = 1.8; if (labelCrest) labelCrest.textContent = '1.8x'; }
      if (inputConf) { inputConf.value = 0.50; if (labelConf) labelConf.textContent = '50%'; }
      if (inputWindow) { inputWindow.value = 750; if (labelWindow) labelWindow.textContent = '750 ms'; }
      if (inputMargin) { inputMargin.value = 1.30; if (labelMargin) labelMargin.textContent = '1.30x'; }
      this._highlightPresetBtn('btn-preset-balanced');
    });

    btnPresetStrict?.addEventListener('click', () => {
      if (inputEnergy) { inputEnergy.value = 0.040; if (labelEnergy) labelEnergy.textContent = '0.040'; }
      if (inputCrest) { inputCrest.value = 2.5; if (labelCrest) labelCrest.textContent = '2.5x'; }
      if (inputConf) { inputConf.value = 0.70; if (labelConf) labelConf.textContent = '70%'; }
      if (inputWindow) { inputWindow.value = 650; if (labelWindow) labelWindow.textContent = '650 ms'; }
      if (inputMargin) { inputMargin.value = 1.60; if (labelMargin) labelMargin.textContent = '1.60x'; }
      this._highlightPresetBtn('btn-preset-strict');
    });

    btnClose?.addEventListener('click', () => this.close());
    btnCancel?.addEventListener('click', () => this.close());

    form?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const updated = {
        adaptive_noise_enabled: inputAdaptive ? inputAdaptive.checked : true,
        margin_factor: inputMargin ? parseFloat(inputMargin.value) : 1.30,
        energy_threshold: parseFloat(inputEnergy.value),
        crest_factor_min: inputCrest ? parseFloat(inputCrest.value) : 1.8,
        confidence_threshold: parseFloat(inputConf.value),
        max_inter_clap_ms: parseInt(inputWindow.value, 10),
        double_clap_action: this.container.querySelector('#select-act-double')?.value || 'toggle_power',
        webhook_url: this.container.querySelector('#input-webhook').value
      };

      try {
        const res = await ApiClient.updateSettings(updated);
        this.settings = res.settings;
        this.close();
      } catch (err) {
        alert('Lỗi lưu cài đặt: ' + err.message);
      }
    });
  }

  _highlightPresetBtn(activeId) {
    const ids = ['btn-preset-high', 'btn-preset-balanced', 'btn-preset-strict'];
    ids.forEach(id => {
      const btn = this.container.querySelector(`#${id}`);
      if (btn) {
        if (id === activeId) {
          btn.style.borderColor = 'var(--accent-cyan)';
          btn.style.background = 'rgba(0, 229, 255, 0.15)';
        } else {
          btn.style.borderColor = '';
          btn.style.background = '';
        }
      }
    });
  }

  populateForm() {
    if (!this.settings) return;
    const { dsp, adaptive_noise, ml, pattern, light } = this.settings;

    const inputAdaptive = this.container.querySelector('#input-adaptive-enabled');
    const inputMargin = this.container.querySelector('#input-margin-factor');
    const labelMargin = this.container.querySelector('#label-margin-factor');
    if (adaptive_noise) {
      if (inputAdaptive) inputAdaptive.checked = adaptive_noise.enabled !== false;
      if (inputMargin) {
        inputMargin.value = adaptive_noise.margin_factor || 1.30;
        if (labelMargin) labelMargin.textContent = `${adaptive_noise.margin_factor || 1.30}x`;
      }
    }

    const inputEnergy = this.container.querySelector('#input-energy-thresh');
    const labelEnergy = this.container.querySelector('#label-energy-thresh');
    if (inputEnergy && dsp) {
      inputEnergy.value = dsp.energy_threshold;
      if (labelEnergy) labelEnergy.textContent = dsp.energy_threshold;
    }

    const inputCrest = this.container.querySelector('#input-crest-thresh');
    const labelCrest = this.container.querySelector('#label-crest-thresh');
    if (inputCrest && dsp) {
      inputCrest.value = dsp.crest_factor_min || 1.8;
      if (labelCrest) labelCrest.textContent = `${dsp.crest_factor_min || 1.8}x`;
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
      const sDouble = this.container.querySelector('#select-act-double');
      const inWebhook = this.container.querySelector('#input-webhook');

      if (sDouble) sDouble.value = light.double_clap_action || 'toggle_power';
      if (inWebhook) inWebhook.value = light.webhook_url || '';
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
