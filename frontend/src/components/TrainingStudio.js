/**
 * Component: TrainingStudio (v2 Pro - Auto-Capture & Deep Learning Studio)
 */
import { audioStreamManager } from '../services/audio_recorder.js';
import { ApiClient } from '../services/api_client.js';
import confetti from 'canvas-confetti';

const CATEGORIES_LIST = [
  { id: 'claps', label: '👏 Tiếng Vỗ Tay', hint: 'Vỗ tay tự do: vỗ nhẹ, vỗ mạnh, ở xa 2-3m, vỗ nhanh' },
  { id: 'typing', label: '⌨️ Gõ Bàn & Bàn Phím', hint: 'Gõ ngón tay lên bàn, gõ bàn phím cơ, click chuột' },
  { id: 'speech', label: '🗣️ Tiếng Nói & Ho', hint: 'Nói chuyện bình thường, ho, hắt hơi, thở dài gần mic' },
  { id: 'snaps', label: '💥 Búng Tay & Va Chạm', hint: 'Búng ngón tay, tiếng chìa khóa, va chạm cốc nước' },
  { id: 'ambient', label: '💨 Tiếng Ồn Nền Phòng', hint: 'Tiếng quạt gió, điều hòa, tiếng xe cộ ngoài cửa sổ' }
];

export class TrainingStudio {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.activeProfile = 'my_custom_model';
    this.activeCategory = 'claps';
    this.isAutoCapturing = false;
    this.isCalibrating = false;
    this.isTraining = false;
    this.currentPreset = 'balanced';

    this.profiles = [];
    this.samples = [];
    this.categoryCounts = {};
    this.trainResult = null;
    this.currentAudio = null;

    this.init();
  }

  async init() {
    this.render();
    await this.loadProfiles();
    await this.loadSamples();
  }

  async loadProfiles() {
    try {
      const data = await ApiClient.getProfiles();
      this.profiles = data.profiles || [];
      this.activeProfile = data.active_profile || this.activeProfile;

      // Update category counts from profile meta
      const currentProf = this.profiles.find((p) => p.name === this.activeProfile);
      if (currentProf && currentProf.category_counts) {
        this.categoryCounts = currentProf.category_counts;
      }

      this.updateProfileDropdown();
    } catch (e) {
      console.warn('Could not load profiles:', e);
    }
  }

  async loadSamples() {
    try {
      const data = await ApiClient.getSamples(this.activeProfile, this.activeCategory);
      this.samples = data.samples || [];
      this.renderSampleCards();
      this.updateCategoryTabs();
    } catch (e) {
      console.warn('Could not load samples:', e);
    }
  }

  render() {
    const activeCatObj = CATEGORIES_LIST.find((c) => c.id === this.activeCategory) || CATEGORIES_LIST[0];

    this.container.innerHTML = `
      <div class="glass-card">
        <!-- Header & Profile Selector -->
        <div class="card-header">
          <div class="card-title">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
            </svg>
            Training Studio Pro (Huấn Luyện & Tối Ưu Nhạy)
          </div>
          
          <div style="display: flex; gap: 0.5rem; align-items: center;">
            <select class="form-select" id="studio-profile-select" style="padding: 6px 12px; font-size: 0.85rem; width: auto; font-weight: 600;">
              <option value="${this.activeProfile}">${this.activeProfile}</option>
            </select>
          </div>
        </div>

        <!-- Top Calibration & Sensitivity Presets Bar -->
        <div class="studio-top-bar">
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <button class="btn btn-secondary" id="btn-auto-calibrate" style="font-size: 0.8rem; padding: 6px 14px;">
              <span>⚡</span>
              <span id="label-calibrate-btn">${this.isCalibrating ? 'Đang đo độ ồn (3s)...' : 'Cân Chỉnh Độ Ồn Phòng (3s)'}</span>
            </button>
            <span style="font-size: 0.75rem; color: var(--text-muted);" id="calib-status-text">Đo độ ồn để tối ưu độ nhạy mic</span>
          </div>

          <div class="presets-group">
            <span style="font-size: 0.75rem; color: var(--text-secondary); font-weight: 600;">Preset độ nhạy:</span>
            <button class="preset-chip ${this.currentPreset === 'high_sensitivity' ? 'active' : ''}" data-preset="high_sensitivity">
              🚀 Nhạy Cao (Ở xa / Vỗ nhẹ)
            </button>
            <button class="preset-chip ${this.currentPreset === 'balanced' ? 'active' : ''}" data-preset="balanced">
              ⚖️ Cân Bằng
            </button>
            <button class="preset-chip ${this.currentPreset === 'strict_anti_noise' ? 'active' : ''}" data-preset="strict_anti_noise">
              🛡️ Chống Nhiễu Cao
            </button>
          </div>
        </div>

        <!-- Category Filter Tabs -->
        <div class="category-tabs-bar" id="category-tabs-bar">
          ${CATEGORIES_LIST.map((cat) => `
            <button class="category-tab-btn ${cat.id === this.activeCategory ? 'active' : ''}" data-cat="${cat.id}">
              <span>${cat.label}</span>
              <span class="category-count-badge" id="badge-${cat.id}">${this.categoryCounts[cat.id] || 0}</span>
            </button>
          `).join('')}
        </div>

        <!-- Capture Control Banner -->
        <div class="capture-banner">
          <div>
            <h4 style="color: var(--accent-cyan); font-size: 1rem; margin-bottom: 0.25rem;">
              ${activeCatObj.label}
            </h4>
            <p style="font-size: 0.85rem; color: var(--text-secondary);">
              💡 <em>${activeCatObj.hint}</em>
            </p>
          </div>

          <div style="display: flex; gap: 0.75rem; align-items: center;">
            <button class="auto-capture-toggle-btn ${this.isAutoCapturing ? 'recording' : ''}" id="btn-toggle-auto-capture">
              <span>${this.isAutoCapturing ? '🟢' : '🔴'}</span>
              <span id="label-auto-capture">
                ${this.isAutoCapturing ? 'Đang Auto-Capture (Hãy vỗ/tạo tiếng động tự do)' : 'BẬT AUTO-CAPTURE TỰ ĐỘNG BẮT MẪU'}
              </span>
            </button>

            <button class="btn btn-secondary" id="btn-record-single-sample" title="Thu 1 mẫu thủ công">
              🎙️ Thu 1 Mẫu (1-Shot)
            </button>

            <button class="btn btn-secondary" id="btn-clear-category" style="color: var(--color-danger);" title="Xóa hết mẫu trong mục này">
              🗑️ Xoá Mục Này
            </button>
          </div>
        </div>

        <!-- Sample Cards Grid -->
        <div class="sample-cards-grid" id="sample-cards-grid">
          <!-- Rendered via renderSampleCards() -->
        </div>

        <!-- Train Model Actions Banner -->
        <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border-card); border-radius: var(--radius-lg); padding: 1.5rem; display: flex; flex-direction: column; gap: 1rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
            <div>
              <div style="font-weight: 700; font-size: 1rem;">Huấn Luyện & Hot-Reload Mô Hình Cá Nhân</div>
              <div style="font-size: 0.85rem; color: var(--text-secondary);">
                Tự động tăng cường dữ liệu x15 lần với dải biên độ rộng (0.2x – 1.6x) và nạp ngay mô hình mới vào luồng nhận diện.
              </div>
            </div>

            <button class="btn btn-primary" id="btn-train-model" style="padding: 0.85rem 1.8rem; font-size: 1rem;" ${this.isTraining ? 'disabled' : ''}>
              ${this.isTraining ? '⚙️ Đang huấn luyện AI...' : '🚀 BẮT ĐẦU HUẤN LUYỆN NGAY (INSTANT TRAIN)'}
            </button>
          </div>

          <!-- Training Report Area -->
          <div id="training-report-container">
            ${this.renderTrainingReport()}
          </div>
        </div>
      </div>
    `;

    this.setupListeners();
  }

  renderSampleCards() {
    const grid = this.container.querySelector('#sample-cards-grid');
    if (!grid) return;

    if (this.samples.length === 0) {
      grid.innerHTML = `
        <div class="empty-samples-box">
          <div style="font-size: 2rem; margin-bottom: 0.5rem;">🎙️</div>
          <div style="font-weight: 700; font-size: 1rem; color: var(--text-primary);">Chưa có mẫu nào trong danh mục này</div>
          <div style="font-size: 0.85rem; margin-top: 0.25rem;">
            Bật nút <strong>"BẬT AUTO-CAPTURE"</strong> ở trên rồi vỗ tay hoặc tạo tiếng động tự do, hệ thống sẽ tự động bắt mẫu!
          </div>
        </div>
      `;
      return;
    }

    grid.innerHTML = this.samples.map((s) => `
      <div class="sample-card-item" id="card-${s.sample_id}">
        <div class="sample-card-top">
          <span class="sample-card-id" title="${s.sample_id}">${s.sample_id}</span>
          <button class="sample-play-btn" data-wav="${s.wav_url}" title="Bấm để nghe lại">
            ▶
          </button>
        </div>

        <div class="sample-card-meta">
          <span>Peak: <strong>${s.peak_amp}</strong></span>
          <span>RMS: <strong>${s.rms_amp}</strong></span>
          <span>${s.created_at || ''}</span>
        </div>

        <div style="display: flex; justify-content: flex-end; margin-top: 0.2rem;">
          <button class="sample-delete-btn" data-id="${s.sample_id}" data-cat="${s.category}" title="Xoá mẫu này">
            🗑️ Xoá
          </button>
        </div>
      </div>
    `).join('');

    // Attach play & delete listeners
    grid.querySelectorAll('.sample-play-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const url = btn.getAttribute('data-wav');
        this.playAudioSample(url);
      });
    });

    grid.querySelectorAll('.sample-delete-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        const cat = btn.getAttribute('data-cat');
        await this.handleDeleteSample(cat, id);
      });
    });
  }

  renderTrainingReport() {
    if (!this.trainResult) return '';

    return `
      <div class="training-report-box">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="font-weight: 700; color: var(--color-success); font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem;">
            <span>✨</span> ĐÃ HUẤN LUYỆN & KÍCH HOẠT THÀNH CÔNG!
          </div>
          <span style="font-size: 0.8rem; color: var(--text-muted);">${this.trainResult.updated_at || ''}</span>
        </div>

        <div class="report-stats-grid">
          <div class="report-stat-card">
            <div class="report-stat-val highlight">${this.trainResult.accuracy}%</div>
            <div class="report-stat-label">Độ Chính Xác Tổng Thể</div>
          </div>

          <div class="report-stat-card">
            <div class="report-stat-val" style="color: var(--accent-cyan);">${this.trainResult.sensitivity || 98}%</div>
            <div class="report-stat-label">Độ Nhạy Bắt Tiếng Vỗ</div>
          </div>

          <div class="report-stat-card">
            <div class="report-stat-val" style="color: var(--accent-lime);">${this.trainResult.noise_rejection || 99}%</div>
            <div class="report-stat-label">Chống Báo Động Giả</div>
          </div>

          <div class="report-stat-card">
            <div class="report-stat-val" style="color: var(--text-primary);">${this.trainResult.training_time_sec}s</div>
            <div class="report-stat-label">Thời Gian Train (CPU)</div>
          </div>
        </div>
      </div>
    `;
  }

  setupListeners() {
    // Category Tabs click
    this.container.querySelectorAll('.category-tab-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const cat = btn.getAttribute('data-cat');
        this.activeCategory = cat;
        this.updateCategoryTabs();
        await this.loadSamples();
      });
    });

    // Profile select change
    const profSelect = this.container.querySelector('#studio-profile-select');
    profSelect?.addEventListener('change', async (e) => {
      const val = e.target.value;
      if (val === '__new__') {
        const name = prompt('Nhập tên Profile mới (viết liền không dấu):', 'my_custom_model');
        if (name) {
          await ApiClient.createProfile(name);
          this.activeProfile = name;
          await this.loadProfiles();
          await this.loadSamples();
        }
      } else {
        this.activeProfile = val;
        await ApiClient.activateProfile(val);
        await this.loadProfiles();
        await this.loadSamples();
      }
    });

    // Auto-Capture Toggle
    this.container.querySelector('#btn-toggle-auto-capture')?.addEventListener('click', async () => {
      await this.toggleAutoCapture();
    });

    // Record 1-Shot Sample
    this.container.querySelector('#btn-record-single-sample')?.addEventListener('click', async () => {
      await this.recordSingleSample();
    });

    // Clear Category
    this.container.querySelector('#btn-clear-category')?.addEventListener('click', async () => {
      if (confirm(`Bạn có chắc muốn xoá toàn bộ mẫu trong mục "${this.activeCategory}"?`)) {
        await ApiClient.clearCategorySamples(this.activeProfile, this.activeCategory);
        await this.loadProfiles();
        await this.loadSamples();
      }
    });

    // Auto-Calibrate 3s
    this.container.querySelector('#btn-auto-calibrate')?.addEventListener('click', async () => {
      await this.runAutoCalibration();
    });

    // Preset Chips
    this.container.querySelectorAll('.preset-chip').forEach((chip) => {
      chip.addEventListener('click', async () => {
        const presetName = chip.getAttribute('data-preset');
        this.currentPreset = presetName;
        this.container.querySelectorAll('.preset-chip').forEach((c) => c.classList.remove('active'));
        chip.classList.add('active');
        await ApiClient.applyPreset(presetName);
      });
    });

    // Train Model Button
    this.container.querySelector('#btn-train-model')?.addEventListener('click', async () => {
      await this.runTraining();
    });
  }

  updateProfileDropdown() {
    const select = this.container.querySelector('#studio-profile-select');
    if (!select) return;

    select.innerHTML = this.profiles.map((p) => `
      <option value="${p.name}" ${p.name === this.activeProfile ? 'selected' : ''}>
        ${p.name} (${p.claps_count} claps, ${p.noises_count} noise)
      </option>
    `).join('') + `<option value="__new__">+ Tạo Profile Mới...</option>`;
  }

  updateCategoryTabs() {
    this.container.querySelectorAll('.category-tab-btn').forEach((btn) => {
      const cat = btn.getAttribute('data-cat');
      if (cat === this.activeCategory) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
      const badge = this.container.querySelector(`#badge-${cat}`);
      if (badge && this.categoryCounts[cat] !== undefined) {
        badge.textContent = this.categoryCounts[cat];
      }
    });
  }

  async toggleAutoCapture() {
    if (this.isAutoCapturing) {
      this.isAutoCapturing = false;
      audioStreamManager.disableAutoCapture();
      this.render();
    } else {
      if (!audioStreamManager.isStreaming) {
        await audioStreamManager.startStream();
      }
      this.isAutoCapturing = true;

      // Kích hoạt auto capture với ngưỡng tự động phù hợp
      audioStreamManager.enableAutoCapture(async (chunk, peak) => {
        try {
          const res = await ApiClient.uploadSample(this.activeProfile, this.activeCategory, chunk);
          if (res.sample) {
            // Thêm mẫu vào danh sách ngay lập tức
            this.samples.unshift(res.sample);
            this.categoryCounts[this.activeCategory] = (this.categoryCounts[this.activeCategory] || 0) + 1;
            this.renderSampleCards();
            this.updateCategoryTabs();
          }
        } catch (err) {
          console.warn('[AutoCapture] Upload error:', err);
        }
      }, 0.025);

      this.render();
    }
  }

  async recordSingleSample() {
    if (!audioStreamManager.isStreaming) {
      await audioStreamManager.startStream();
    }
    const btn = this.container.querySelector('#btn-record-single-sample');
    if (btn) btn.textContent = '🔴 Đang lắng nghe 1 giây...';

    try {
      const snippet = await audioStreamManager.startSnippetRecording(1200);
      const res = await ApiClient.uploadSample(this.activeProfile, this.activeCategory, snippet);
      if (res.sample) {
        this.samples.unshift(res.sample);
        this.categoryCounts[this.activeCategory] = (this.categoryCounts[this.activeCategory] || 0) + 1;
        this.renderSampleCards();
        this.updateCategoryTabs();
      }
    } catch (err) {
      alert('Lỗi thu âm: ' + err.message);
    } finally {
      if (btn) btn.textContent = '🎙️ Thu 1 Mẫu (1-Shot)';
    }
  }

  async handleDeleteSample(cat, id) {
    try {
      await ApiClient.deleteSample(this.activeProfile, cat, id);
      this.samples = this.samples.filter((s) => s.sample_id !== id);
      this.categoryCounts[cat] = Math.max(0, (this.categoryCounts[cat] || 1) - 1);
      this.renderSampleCards();
      this.updateCategoryTabs();
    } catch (err) {
      alert('Lỗi xoá mẫu: ' + err.message);
    }
  }

  playAudioSample(wavUrl) {
    if (this.currentAudio) {
      this.currentAudio.pause();
    }
    this.currentAudio = new Audio(wavUrl);
    this.currentAudio.play().catch((e) => console.warn('Play error:', e));
  }

  async runAutoCalibration() {
    if (this.isCalibrating) return;

    if (!audioStreamManager.isStreaming) {
      await audioStreamManager.startStream();
    }

    this.isCalibrating = true;
    const label = this.container.querySelector('#label-calibrate-btn');
    const statusText = this.container.querySelector('#calib-status-text');
    if (label) label.textContent = 'Đang đo độ ồn phòng (3s)...';
    if (statusText) statusText.textContent = 'Vui lòng giữ im lặng trong 3 giây để hệ thống đo tiếng ồn...';

    try {
      const snippet = await audioStreamManager.startSnippetRecording(3000);
      const res = await ApiClient.calibrateNoise(snippet);
      if (res.status === 'success') {
        if (statusText) {
          statusText.textContent = `✅ Độ ồn: Peak ${res.noise_floor_peak} -> Ngưỡng tối ưu: ${res.recommended_energy_threshold}`;
        }
        confetti({ particleCount: 40, spread: 60, origin: { y: 0.3 } });
      }
    } catch (err) {
      alert('Lỗi cân chỉnh: ' + err.message);
    } finally {
      this.isCalibrating = false;
      if (label) label.textContent = 'Cân Chỉnh Độ Ồn Phòng (3s)';
    }
  }

  async runTraining() {
    if (this.isTraining) return;

    this.isTraining = true;
    const btn = this.container.querySelector('#btn-train-model');
    if (btn) btn.innerHTML = '⚙️ Đang tăng cường dữ liệu và huấn luyện mô hình...';

    try {
      const res = await ApiClient.trainModel(this.activeProfile, 25);
      if (res.status === 'success') {
        this.trainResult = res.metrics;
        confetti({ particleCount: 120, spread: 90, origin: { y: 0.6 } });
        const reportArea = this.container.querySelector('#training-report-container');
        if (reportArea) reportArea.innerHTML = this.renderTrainingReport();
      }
    } catch (err) {
      alert('Lỗi huấn luyện: ' + err.message);
    } finally {
      this.isTraining = false;
      if (btn) btn.innerHTML = '🚀 BẮT ĐẦU HUẤN LUYỆN NGAY (INSTANT TRAIN)';
    }
  }
}
