/**
 * Component: SmartLightBulb (Bóng đèn thông minh mô phỏng 3D Glowing)
 */
import { wsClient } from '../services/websocket_client.js';
import { ApiClient } from '../services/api_client.js';
import confetti from 'canvas-confetti';

const RGB_PRESETS = [
  '#00e5ff', // Cyan Neon
  '#ff007f', // Magenta Neon
  '#00ff66', // Electric Lime
  '#ffaa00', // Warm Amber
  '#7928ca', // Electric Violet
  '#ffffff', // Pure White
  '#ff3333', // Crimson Red
  '#0088ff'  // Royal Blue
];

export class SmartLightBulb {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.state = {
      power: true,
      brightness: 85,
      color: '#00e5ff',
      mode: 'solid',
      last_triggered_by: 'init'
    };
    this.init();
  }

  init() {
    this.render();
    this.setupListeners();
  }

  render() {
    this.container.innerHTML = `
      <div class="glass-card bulb-card ${this.state.power ? 'powered-on' : ''}">
        <div class="card-header" style="width: 100%;">
          <div class="card-title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 18h6M10 22h4M12 2v1M12 7a5 5 0 0 0-5 5c0 1.5.5 2.5 1.5 3.5.5.5 1 1.5 1 2.5h5c0-1 .5-2 1-2.5 1-1 1.5-2 1.5-3.5a5 5 0 0 0-5-5z"></path>
            </svg>
            Đèn Thông Minh (Virtual Bulb)
          </div>
          <span class="bulb-power-badge" id="bulb-power-badge">
            ${this.state.power ? 'ON' : 'OFF'}
          </span>
        </div>

        <div class="bulb-stage ${this.state.power ? 'powered-on' : ''} mode-${this.state.mode}" id="bulb-stage">
          <div class="bulb-ambient-glow" id="bulb-ambient-glow"></div>
          
          <div class="bulb-svg-container" id="bulb-svg-btn" title="Bấm để Bật/Tắt đèn">
            <svg viewBox="0 0 140 200" width="140" height="200">
              <!-- Bulb Glass Body -->
              <path class="bulb-glass" id="bulb-glass-path" d="M 70,10 C 35,10 20,45 20,75 C 20,105 45,120 48,145 L 92,145 C 95,120 120,105 120,75 C 120,45 105,10 70,10 Z"></path>
              
              <!-- Filament -->
              <path class="bulb-filament" d="M 52,145 L 56,80 L 64,100 L 70,75 L 76,100 L 84,80 L 88,145"></path>
              
              <!-- Bulb Base Screw Threads -->
              <rect class="bulb-base" x="48" y="145" width="44" height="28" rx="4"></rect>
              <line class="bulb-base-threads" x1="48" y1="152" x2="92" y2="152"></line>
              <line class="bulb-base-threads" x1="48" y1="160" x2="92" y2="160"></line>
              <line class="bulb-base-threads" x1="48" y1="168" x2="92" y2="168"></line>
              <!-- Contact point -->
              <path d="M 58,173 C 58,185 82,185 82,173 Z" fill="#161b22"></path>
            </svg>
          </div>
        </div>

        <!-- Controls Panel -->
        <div class="bulb-controls">
          <!-- Brightness Slider -->
          <div class="form-group">
            <div class="form-label" style="display: flex; justify-content: space-between;">
              <span>Độ sáng (Brightness)</span>
              <span id="brightness-val">${this.state.brightness}%</span>
            </div>
            <input type="range" class="form-range" id="brightness-slider" min="5" max="100" value="${this.state.brightness}">
          </div>

          <!-- Color Swatches -->
          <div class="form-group">
            <div class="form-label">Bảng màu sắc RGB</div>
            <div class="color-swatches" id="color-swatches">
              ${RGB_PRESETS.map((hex) => `
                <button class="color-swatch-btn ${this.state.color.toLowerCase() === hex.toLowerCase() ? 'active' : ''}" 
                  data-color="${hex}" 
                  style="background-color: ${hex}; color: ${hex};"></button>
              `).join('')}
            </div>
          </div>

          <!-- Mode / Quick Action Triggers -->
          <div class="quick-triggers">
            <button class="quick-trigger-btn" id="btn-trigger-double" style="flex: 1.2;">
              <span>👏👏 2 Vỗ Tay</span>
              <span>Bật / Tắt Đèn</span>
            </button>
            <button class="quick-trigger-btn" id="btn-trigger-color" style="flex: 1;">
              <span>🎨 Đổi Màu</span>
              <span>RGB Preset</span>
            </button>
            <button class="quick-trigger-btn" id="btn-trigger-party" style="flex: 1;">
              <span>🎉 Party Mode</span>
              <span>Chớp Màu</span>
            </button>
          </div>
        </div>
      </div>
    `;

    this.updateVisuals();
  }

  setupListeners() {
    // Click vào bóng đèn -> Toggle
    const bulbBtn = this.container.querySelector('#bulb-svg-btn');
    bulbBtn?.addEventListener('click', () => {
      this.togglePower();
    });

    // Slider độ sáng
    const slider = this.container.querySelector('#brightness-slider');
    slider?.addEventListener('input', (e) => {
      const val = parseInt(e.target.value, 10);
      this.setBrightness(val);
    });

    // Swatches màu
    const swatches = this.container.querySelectorAll('.color-swatch-btn');
    swatches.forEach((btn) => {
      btn.addEventListener('click', () => {
        const color = btn.getAttribute('data-color');
        this.setColor(color);
      });
    });

    // Quick trigger buttons
    this.container.querySelector('#btn-trigger-double')?.addEventListener('click', () => {
      ApiClient.triggerBulbAction('toggle_power').then((st) => this.updateState(st));
    });

    this.container.querySelector('#btn-trigger-color')?.addEventListener('click', () => {
      ApiClient.triggerBulbAction('next_color').then((st) => this.updateState(st));
    });

    this.container.querySelector('#btn-trigger-party')?.addEventListener('click', () => {
      ApiClient.triggerBulbAction('party_mode').then((st) => this.updateState(st));
    });

    // Lắng nghe sự kiện từ WebSocket
    wsClient.on('INITIAL_STATE', (data) => {
      if (data.bulb_state) this.updateState(data.bulb_state);
    });

    wsClient.on('BULB_STATE_CHANGED', (data) => {
      if (data.bulb_state) this.updateState(data.bulb_state);
    });

    wsClient.on('ACTION_TRIGGERED', (data) => {
      if (data.bulb_state) this.updateState(data.bulb_state);
      if (data.pattern === 'triple' || data.action === 'party_mode') {
        this.launchConfetti();
      }
    });
  }

  updateState(newState) {
    this.state = { ...this.state, ...newState };
    this.updateVisuals();
  }

  updateVisuals() {
    const stage = this.container.querySelector('#bulb-stage');
    const badge = this.container.querySelector('#bulb-power-badge');
    const card = this.container.querySelector('.bulb-card');
    const brightnessVal = this.container.querySelector('#brightness-val');
    const brightnessSlider = this.container.querySelector('#brightness-slider');

    if (stage) {
      stage.style.setProperty('--bulb-color', this.state.color);
      stage.style.setProperty('--bulb-brightness', this.state.brightness);
      
      stage.className = `bulb-stage ${this.state.power ? 'powered-on' : ''} mode-${this.state.mode}`;
    }

    if (card) {
      card.className = `glass-card bulb-card ${this.state.power ? 'powered-on' : ''}`;
    }

    if (badge) {
      badge.textContent = this.state.power ? 'ON' : 'OFF';
    }

    if (brightnessVal) {
      brightnessVal.textContent = `${this.state.brightness}%`;
    }

    if (brightnessSlider && parseInt(brightnessSlider.value, 10) !== this.state.brightness) {
      brightnessSlider.value = this.state.brightness;
    }

    // Cập nhật active swatch
    const swatches = this.container.querySelectorAll('.color-swatch-btn');
    swatches.forEach((btn) => {
      const c = btn.getAttribute('data-color');
      if (c && c.toLowerCase() === this.state.color.toLowerCase()) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
  }

  togglePower() {
    const newPower = !this.state.power;
    this.state.power = newPower;
    this.updateVisuals();
    wsClient.sendCommand({ type: 'SET_BULB', power: newPower });
  }

  setBrightness(val) {
    this.state.brightness = val;
    this.updateVisuals();
    wsClient.sendCommand({ type: 'SET_BULB', brightness: val });
  }

  setColor(color) {
    this.state.color = color;
    this.state.mode = 'solid';
    this.updateVisuals();
    wsClient.sendCommand({ type: 'SET_BULB', color: color, mode: 'solid' });
  }

  launchConfetti() {
    try {
      confetti({
        particleCount: 60,
        spread: 70,
        origin: { y: 0.6 }
      });
    } catch (e) {
      // Ignore if canvas confetti not supported
    }
  }
}
