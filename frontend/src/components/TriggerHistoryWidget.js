/**
 * Component: TriggerHistoryWidget (Lịch sử Kích hoạt & Chống Báo Giả - Active Feedback)
 * Cho phép nghe lại âm thanh của các lần kích hoạt đèn gần nhất,
 * đánh dấu Báo Giả (False Positive) để tự động lưu mẫu nhiễu và Huấn luyện lại ngay lập tức!
 */
import { ApiClient } from '../services/api_client.js';
import { wsClient } from '../services/websocket_client.js';
import { escapeHtml } from '../utils/sanitize.js';

const CATEGORY_MAP = {
  false_positives: '🚫 Mẫu Báo Giả',
  speech: '🗣️ Tiếng Nói',
  typing: '⌨️ Gõ Bàn / Phím',
  ambient: '🌪️ Quạt / Tiếng Ồn',
  snaps: '🤏 Búng Tay / Va Chạm',
  noises: '🔇 Nhiễu Khác'
};

export class TriggerHistoryWidget {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    this.options = options;
    this.events = [];
    this.activeAudio = null;
    this.selectedEventForMining = null;
    this.activeProfile = options.profileName || 'default';
    this.init();
  }

  async init() {
    if (!this.container) return;
    this.render();
    this.bindEvents();
    await this.loadTriggers();

    // Lắng nghe sự kiện kích hoạt thời gian thực từ WebSocket
    wsClient.on('TRIGGER_EVENT', (data) => {
      if (data && data.event) {
        this.addRealtimeEvent(data.event);
      }
    });

    // Lắng nghe sự kiện xóa sau khi đã báo giả và đẩy sang Windows
    wsClient.on('TRIGGER_EVENT_REMOVED', (data) => {
      if (data && data.event_id) {
        this.events = this.events.filter(e => e.id !== data.event_id);
        this.renderEventList();
      }
    });

    // Lắng nghe sự kiện AI Model tự động nâng cấp từ Windows
    wsClient.on('AI_MODEL_UPGRADED', (data) => {
      this.showUpgradeToast(data);
    });
  }

  showUpgradeToast(data) {
    const existing = document.getElementById('ai-upgrade-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'ai-upgrade-toast';
    toast.style.cssText = `
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: linear-gradient(135deg, #1e1b4b, #312e81);
      border: 1px solid #6366f1;
      border-radius: 12px;
      padding: 14px 20px;
      color: #fff;
      font-size: 0.85rem;
      box-shadow: 0 10px 30px rgba(99, 102, 241, 0.4);
      z-index: 9999;
      display: flex;
      align-items: center;
      gap: 12px;
      animation: slideInUp 0.3s ease;
    `;
    const acc = data?.metrics?.accuracy ? ` (Độ chính xác: ${escapeHtml(data.metrics.accuracy)}%)` : '';
    toast.innerHTML = `
      <span style="font-size: 1.4rem;">🚀</span>
      <div>
        <div style="font-weight: 700; color: #a5b4fc;">Mô hình AI đã tự động nâng cấp!</div>
        <div style="font-size: 0.75rem; color: #c7d2fe;">Đã học các mẫu âm thanh mới và kích hoạt ngay${acc}</div>
      </div>
      <button style="background: transparent; border: none; color: #a5b4fc; font-size: 1rem; cursor: pointer; margin-left: 8px;" onclick="this.parentElement.remove()">✕</button>
    `;
    document.body.appendChild(toast);
    setTimeout(() => {
      if (toast.parentElement) toast.remove();
    }, 6000);
  }

  render() {
    this.container.innerHTML = `
      <div class="card trigger-history-card">
        <div class="card-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
          <div class="card-title" style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.95rem; font-weight: 700;">
            <span style="font-size: 1.15rem;">🕒</span>
            <span>Lịch Sử Kích Hoạt & Chống Báo Giả</span>
            <span class="history-badge" id="history-total-badge">0</span>
          </div>
          <button class="btn btn-secondary btn-sm" id="btn-clear-history" title="Xóa danh sách lịch sử" style="font-size: 0.75rem; padding: 0.25rem 0.6rem;">
            Xóa Lịch Sử
          </button>
        </div>

        <div class="history-description" style="font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 0.85rem; line-height: 1.4;">
          Khi thấy đèn bật/tắt nhầm, bấm <strong>🚫 Báo Giả</strong> để tự động trích xuất đoạn âm thanh đó, đẩy sang bộ Dataset máy tính Windows và xóa khỏi lịch sử Server.
        </div>

        <div class="trigger-events-list" id="trigger-events-list">
          <div class="empty-state" style="padding: 1.5rem; text-align: center; color: var(--text-secondary); font-size: 0.82rem;">
            Chưa có sự kiện kích hoạt nào. Hãy vỗ tay hoặc tạo âm thanh để kiểm tra!
          </div>
        </div>
      </div>

      <!-- Modal Chọn Loại Nhiễu Khi Báo Giả -->
      <div class="modal-backdrop" id="false-positive-modal" style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.75); z-index: 1000; align-items: center; justify-content: center; backdrop-filter: blur(4px);">
        <div class="modal-dialog" style="background: #111827; border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 12px; width: 90%; max-width: 440px; padding: 1.25rem; box-shadow: 0 10px 30px rgba(0,0,0,0.6);">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 0.5rem;">
            <div style="font-weight: 700; color: #ef4444; display: flex; align-items: center; gap: 0.4rem;">
              <span>🚫</span> Báo Giả $\rightarrow$ Đẩy Sang Dataset Windows
            </div>
            <button class="btn btn-secondary btn-sm" id="btn-close-fp-modal" style="padding: 2px 6px;">✕</button>
          </div>

          <p style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 1rem;">
            Đoạn âm thanh này sẽ được lưu và chuyển tiếp ngay lập tức sang máy tính Windows để làm mẫu huấn luyện:
          </p>

          <div class="form-group" style="margin-bottom: 1.25rem;">
            <label style="font-size: 0.78rem; color: var(--text-primary); font-weight: 600; margin-bottom: 0.35rem; display: block;">
              Chọn danh mục lưu mẫu trên Windows:
            </label>
            <select class="form-select" id="select-fp-category" style="width: 100%; background: #1f2937; border: 1px solid rgba(255,255,255,0.15); color: #fff; padding: 0.5rem; border-radius: 6px; font-size: 0.85rem;">
              <option value="false_positives" selected>🚫 Mẫu Báo Giả Chuyên Biệt (Hard Negatives - Khuyên dùng)</option>
              <option value="speech">🗣️ Tiếng Nói / Tiếng TV / Ca Hát</option>
              <option value="typing">⌨️ Gõ Phím / Va Chạm Đồ Vật</option>
              <option value="ambient">🌪️ Quạt Gió / Tiếng Ồn Nền</option>
              <option value="snaps">🤏 Búng Tay / Kim Loại Keng</option>
              <option value="noises">🔇 Tiếng Nhiễu Khác</option>
            </select>
          </div>

          <div style="display: flex; gap: 0.5rem; justify-content: flex-end;">
            <button class="btn btn-secondary btn-sm" id="btn-cancel-fp" style="padding: 0.45rem 0.85rem;">Hủy</button>
            <button class="btn btn-danger btn-sm" id="btn-confirm-fp" style="background: #ef4444; border-color: #ef4444; color: #fff; padding: 0.45rem 1rem; font-weight: 600; display: flex; align-items: center; gap: 0.35rem;">
              <span>🚀</span> Đẩy Sang Windows & Xóa Lịch Sử
            </button>
          </div>
        </div>
      </div>
    `;
  }

  bindEvents() {
    document.getElementById('btn-clear-history')?.addEventListener('click', async () => {
      if (confirm('Bạn có chắc muốn xóa sạch toàn bộ lịch sử kích hoạt gần đây?')) {
        await ApiClient.clearTriggerHistory();
        this.events = [];
        this.renderEventList();
      }
    });

    document.getElementById('btn-close-fp-modal')?.addEventListener('click', () => this.closeModal());
    document.getElementById('btn-cancel-fp')?.addEventListener('click', () => this.closeModal());

    document.getElementById('btn-confirm-fp')?.addEventListener('click', async () => {
      await this.executeFalsePositiveMining();
    });
  }

  async loadTriggers() {
    try {
      const data = await ApiClient.getRecentTriggers();
      if (data && data.events) {
        this.events = data.events;
        this.renderEventList();
      }
    } catch (e) {
      console.warn('Cannot load trigger history:', e);
    }
  }

  addRealtimeEvent(event) {
    // Thêm vào đầu danh sách
    this.events.unshift(event);
    if (this.events.length > 15) this.events.pop();
    this.renderEventList();

    // Hiệu ứng flash viền cho dòng đầu tiên
    const firstRow = document.querySelector('.trigger-event-row');
    if (firstRow) {
      firstRow.classList.add('event-row-flash');
      setTimeout(() => firstRow.classList.remove('event-row-flash'), 2000);
    }
  }

  renderEventList() {
    const list = document.getElementById('trigger-events-list');
    const badge = document.getElementById('history-total-badge');
    if (!list) return;

    if (badge) badge.textContent = this.events.length;

    if (this.events.length === 0) {
      list.innerHTML = `
        <div class="empty-state" style="padding: 1.5rem; text-align: center; color: var(--text-secondary); font-size: 0.82rem;">
          Chưa có sự kiện kích hoạt nào. Hãy vỗ tay hoặc tạo âm thanh để kiểm tra!
        </div>
      `;
      return;
    }

    list.innerHTML = '';
    this.events.forEach((ev) => {
      const row = document.createElement('div');
      row.className = `trigger-event-row ${ev.is_false_positive ? 'marked-fp' : ''}`;
      row.setAttribute('data-id', escapeHtml(ev.id));

      const patternLabel = ev.pattern === 'double' ? '👏👏 2 Vỗ (Double)' : '👏 Vỗ Tay';
      const confPct = Math.round((ev.confidence || 0.8) * 100);
      const safeTime = escapeHtml(ev.datetime_str || 'Vừa xong');
      const safePattern = escapeHtml(ev.pattern || 'double');
      const safeAudioUrl = escapeHtml(ev.audio_url || '#');
      const safeCategoryName = escapeHtml(CATEGORY_MAP[ev.marked_category] || ev.marked_category || 'Nhiễu');
      const safeId = escapeHtml(ev.id);

      row.innerHTML = `
        <div class="event-left">
          <div class="event-time">${safeTime}</div>
          <div class="event-meta">
            <span class="event-pill pill-${safePattern}">${patternLabel}</span>
            <span class="event-conf">Độ tin cậy: <strong>${confPct}%</strong></span>
          </div>
        </div>

        <div class="event-actions">
          <button class="btn btn-secondary btn-sm btn-play-trigger" data-url="${safeAudioUrl}" title="Nghe lại âm thanh gây kích hoạt">
            ▶ Nghe lại
          </button>

          ${ev.is_false_positive 
            ? `<span class="fp-status-badge">✅ Đã học: ${safeCategoryName}</span>`
            : `<button class="btn btn-danger-outline btn-sm btn-mark-fp" data-id="${safeId}">
                 🚫 Báo Giả
               </button>`
          }
        </div>
      `;

      list.appendChild(row);
    });

    // Gắn sự kiện nút Play
    list.querySelectorAll('.btn-play-trigger').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const url = btn.getAttribute('data-url');
        if (url && url !== '#') {
          if (this.activeAudio) {
            this.activeAudio.pause();
            this.activeAudio = null;
          }
          const audio = new Audio(url);
          this.activeAudio = audio;
          btn.textContent = '🔊 Đang phát...';
          audio.play().catch(() => {});
          audio.onended = () => {
            btn.textContent = '▶ Nghe lại';
            this.activeAudio = null;
          };
        }
      });
    });

    // Gắn sự kiện nút Báo Giả
    list.querySelectorAll('.btn-mark-fp').forEach((btn) => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-id');
        this.openModal(id);
      });
    });
  }

  openModal(eventId) {
    this.selectedEventForMining = eventId;
    const modal = document.getElementById('false-positive-modal');
    if (modal) modal.style.display = 'flex';
  }

  closeModal() {
    this.selectedEventForMining = null;
    const modal = document.getElementById('false-positive-modal');
    if (modal) modal.style.display = 'none';
  }

  showToast(message, isSuccess = true) {
    const toast = document.createElement('div');
    toast.style.cssText = `
      position: fixed;
      bottom: 24px;
      left: 24px;
      background: ${isSuccess ? 'linear-gradient(135deg, #064e3b, #047857)' : 'linear-gradient(135deg, #7f1d1d, #b91c1c)'};
      border: 1px solid ${isSuccess ? '#10b981' : '#ef4444'};
      border-radius: 10px;
      padding: 12px 18px;
      color: #fff;
      font-size: 0.85rem;
      font-weight: 500;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
      z-index: 9999;
      display: flex;
      align-items: center;
      gap: 10px;
      animation: slideInUp 0.3s ease;
    `;
    toast.innerHTML = `
      <span>${isSuccess ? '🚀' : '⚠️'}</span>
      <span>${message}</span>
    `;
    document.body.appendChild(toast);
    setTimeout(() => {
      if (toast.parentElement) toast.remove();
    }, 4000);
  }

  async executeFalsePositiveMining() {
    if (!this.selectedEventForMining) return;
    const eventId = this.selectedEventForMining;
    const category = document.getElementById('select-fp-category')?.value || 'false_positives';
    const confirmBtn = document.getElementById('btn-confirm-fp');

    if (confirmBtn) {
      confirmBtn.disabled = true;
      confirmBtn.innerHTML = `<span>⏳</span> Đang chuyển sang Windows...`;
    }

    try {
      const res = await ApiClient.markFalsePositive(eventId, this.activeProfile, category, false);
      if (res && res.status === 'success') {
        // Xóa sự kiện khỏi danh sách hiển thị trên Server
        this.events = this.events.filter(e => e.id !== eventId);
        this.renderEventList();
        this.closeModal();
        this.showToast(res.message || 'Đã chuyển đoạn âm thanh sang máy Windows và xóa khỏi danh sách trên Server!', true);
      } else {
        this.showToast('Lỗi: ' + (res?.message || 'Không thể chuyển mẫu'), false);
      }
    } catch (err) {
      this.showToast('Lỗi xử lý: ' + err.message, false);
    } finally {
      if (confirmBtn) {
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = `<span>🚀</span> Đẩy Sang Windows & Xóa Lịch Sử`;
      }
    }
  }
}
