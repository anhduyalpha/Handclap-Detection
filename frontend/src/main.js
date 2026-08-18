/**
 * HandClap AI - Main Application Entry Point
 */
import './styles/main.css';
import './styles/bulb.css';
import './styles/visualizer.css';

import { wsClient } from './services/websocket_client.js';
import { audioStreamManager } from './services/audio_recorder.js';
import { SmartLightBulb } from './components/SmartLightBulb.js';
import { AudioVisualizer } from './components/AudioVisualizer.js';
import { TrainingStudio } from './components/TrainingStudio.js';
import { SettingsModal } from './components/SettingsModal.js';
import { TriggerHistoryWidget } from './components/TriggerHistoryWidget.js';

class App {
  constructor() {
    this.bulb = null;
    this.visualizer = null;
    this.trainingStudio = null;
    this.settingsModal = null;
    this.triggerHistory = null;
    this.init();
  }

  init() {
    // 1. Khởi tạo các Components
    if (document.getElementById('smart-light-slot')) {
      this.bulb = new SmartLightBulb('smart-light-slot');
    }
    if (document.getElementById('audio-visualizer-slot')) {
      this.visualizer = new AudioVisualizer('audio-visualizer-slot');
    }
    if (document.getElementById('training-studio-slot')) {
      this.trainingStudio = new TrainingStudio('training-studio-slot');
    }
    if (document.getElementById('settings-modal-slot')) {
      this.settingsModal = new SettingsModal('settings-modal-slot');
    }
    if (document.getElementById('trigger-history-slot')) {
      this.triggerHistory = new TriggerHistoryWidget('trigger-history-slot');
    }

    // 2. Kết nối WebSocket
    wsClient.connect();

    // 3. Thiết lập Event Listeners
    this.setupTabNavigation();
    this.setupMicToggle();
    this.setupConnectionStatus();
    this.setupSettingsTrigger();
  }

  setupTabNavigation() {
    const tabButtons = document.querySelectorAll('.nav-tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabButtons.forEach((btn) => {
      btn.addEventListener('click', () => {
        const targetTabId = btn.getAttribute('data-tab');

        tabButtons.forEach((b) => b.classList.remove('active'));
        tabPanes.forEach((p) => p.classList.remove('active'));

        btn.classList.add('active');
        document.getElementById(targetTabId)?.classList.add('active');
      });
    });
  }

  setupMicToggle() {
    const micBtn = document.getElementById('btn-toggle-mic');
    const label = document.getElementById('mic-btn-label');

    micBtn?.addEventListener('click', async () => {
      if (audioStreamManager.isStreaming) {
        audioStreamManager.stopStream();
        micBtn.classList.remove('active');
        if (label) label.textContent = 'Bật Microphone';
      } else {
        try {
          await audioStreamManager.startStream();
          micBtn.classList.add('active');
          if (label) label.textContent = 'Đang Thu Micro';
        } catch (err) {
          alert('Không thể truy cập Microphone: ' + err.message + '\nVui lòng cấp quyền Microphone trong trình duyệt.');
        }
      }
    });
  }

  setupConnectionStatus() {
    const dot = document.getElementById('ws-status-dot');
    const text = document.getElementById('ws-status-text');

    wsClient.on('connection_change', ({ connected }) => {
      if (connected) {
        dot?.classList.add('connected');
        if (text) text.textContent = 'Backend: Sẵn sàng';
      } else {
        dot?.classList.remove('connected');
        if (text) text.textContent = 'Backend: Mất kết nối';
      }
    });
  }

  setupSettingsTrigger() {
    const btn = document.getElementById('btn-open-settings');
    btn?.addEventListener('click', () => {
      this.settingsModal?.open();
    });
  }
}

// Khởi chạy App khi DOM sẵn sàng
document.addEventListener('DOMContentLoaded', () => {
  window.__app = new App();
});
