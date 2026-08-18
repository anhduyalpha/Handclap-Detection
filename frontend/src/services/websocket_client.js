/**
 * WebSocket Client hai chiều kết nối với Backend Live Detection Engine
 */

export class WebSocketClient {
  constructor() {
    this.ws = null;
    this.url = this._getWebSocketUrl();
    this.listeners = new Map();
    this.isConnected = false;
    this.reconnectTimer = null;
  }

  _getWebSocketUrl() {
    const loc = window.location;
    const proto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
    // Nếu chạy qua Vite dev server trên port 5173, kết nối tới proxy /ws/audio hoặc trực tiếp 8000
    if (loc.port === '5173') {
      return `ws://${loc.hostname}:8000/ws/audio`;
    }
    return `${proto}//${loc.host}/ws/audio`;
  }

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      this.ws = new WebSocket(this.url);
      this.ws.binaryType = 'arraybuffer';

      this.ws.onopen = () => {
        this.isConnected = true;
        console.log('[WebSocket] Connected to Audio Engine');
        this.emit('connection_change', { connected: true });
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.ws.onmessage = (event) => {
        try {
          if (typeof event.data === 'string') {
            const data = JSON.parse(event.data);
            this.emit(data.type || 'message', data);
            this.emit('*', data);
          }
        } catch (e) {
          console.error('[WebSocket] Parse error:', e);
        }
      };

      this.ws.onclose = () => {
        this.isConnected = false;
        console.log('[WebSocket] Disconnected. Retrying in 2s...');
        this.emit('connection_change', { connected: false });
        this._scheduleReconnect();
      };

      this.ws.onerror = (err) => {
        console.warn('[WebSocket] Connection error:', err);
        this.ws?.close();
      };
    } catch (e) {
      console.error('[WebSocket] Init error:', e);
      this._scheduleReconnect();
    }
  }

  _scheduleReconnect() {
    if (!this.reconnectTimer) {
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.connect();
      }, 2000);
    }
  }

  sendAudioChunk(float32Array) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(float32Array.buffer);
    }
  }

  sendCommand(commandObj) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(commandObj));
    }
  }

  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event).add(callback);
    return () => this.off(event, callback);
  }

  off(event, callback) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).delete(callback);
    }
  }

  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach((cb) => {
        try {
          cb(data);
        } catch (e) {
          console.error(`[WebSocket] Error in listener for ${event}:`, e);
        }
      });
    }
  }
}

export const wsClient = new WebSocketClient();
