/**
 * Web Audio API Recorder & Streamer (v2 Pro with Smart Auto-Capture)
 * Thu âm microphone ở chuẩn 16kHz Mono, hỗ trợ Real-time Streaming & Auto-Capture Onset Slicer
 */
import { wsClient } from './websocket_client.js';

export class AudioStreamManager {
  constructor() {
    this.audioContext = null;
    this.mediaStream = null;
    this.sourceNode = null;
    this.processorNode = null;
    this.analyserNode = null;
    this.isStreaming = false;
    this.targetSampleRate = 16000;

    // Manual Recording buffer cho Training Studio
    this.isRecordingSnippet = false;
    this.snippetBuffer = [];

    // Auto-Capture Slicer Mode
    this.isAutoCaptureEnabled = false;
    this.onAutoCapturedSample = null;
    this.autoCaptureThreshold = 0.030;
    this.lastAutoCaptureTime = 0;
    this.rollingPreBuffer = new Float32Array(1600); // 100ms pre-buffer
  }

  async startStream() {
    if (this.isStreaming) return;

    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
          channelCount: 1
        }
      });

      this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: 16000
      });

      const actualSampleRate = this.audioContext.sampleRate;

      this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream);
      this.analyserNode = this.audioContext.createAnalyser();
      this.analyserNode.fftSize = 512;
      this.analyserNode.smoothingTimeConstant = 0.5;

      const bufferSize = 512;
      this.processorNode = this.audioContext.createScriptProcessor(bufferSize, 1, 1);

      this.processorNode.onaudioprocess = (e) => {
        if (!this.isStreaming) return;

        const inputChannelData = e.inputBuffer.getChannelData(0);
        let pcmData;

        if (actualSampleRate !== this.targetSampleRate) {
          pcmData = this._resample(inputChannelData, actualSampleRate, this.targetSampleRate);
        } else {
          pcmData = new Float32Array(inputChannelData);
        }

        // 1. Gửi qua WebSocket cho live engine
        wsClient.sendAudioChunk(pcmData);

        // 2. Chế độ thu âm thủ công 1-shot snippet
        if (this.isRecordingSnippet) {
          this.snippetBuffer.push(new Float32Array(pcmData));
        }

        // 3. Chế độ Smart Auto-Capture Onset Slicer
        if (this.isAutoCaptureEnabled && this.onAutoCapturedSample) {
          this._processAutoCapture(pcmData);
        }
      };

      this.sourceNode.connect(this.analyserNode);
      this.analyserNode.connect(this.processorNode);
      this.processorNode.connect(this.audioContext.destination);

      this.isStreaming = true;
      console.log(`[Audio] Streaming started (${actualSampleRate}Hz -> ${this.targetSampleRate}Hz)`);
      return true;
    } catch (err) {
      console.error('[Audio] Error starting mic stream:', err);
      throw err;
    }
  }

  stopStream() {
    this.isStreaming = false;
    this.isAutoCaptureEnabled = false;
    if (this.processorNode) {
      this.processorNode.disconnect();
      this.processorNode = null;
    }
    if (this.sourceNode) {
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((t) => t.stop());
      this.mediaStream = null;
    }
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
    console.log('[Audio] Streaming stopped');
  }

  enableAutoCapture(callback, threshold = 0.030) {
    this.isAutoCaptureEnabled = true;
    this.onAutoCapturedSample = callback;
    this.autoCaptureThreshold = threshold;
    this.lastAutoCaptureTime = 0;
  }

  disableAutoCapture() {
    this.isAutoCaptureEnabled = false;
    this.onAutoCapturedSample = null;
  }

  _processAutoCapture(chunk) {
    // Cập nhật rolling pre-buffer
    const combined = new Float32Array(this.rollingPreBuffer.length + chunk.length);
    combined.set(this.rollingPreBuffer, 0);
    combined.set(chunk, this.rollingPreBuffer.length);
    this.rollingPreBuffer = combined.slice(chunk.length);

    // Tính peak của chunk
    let peak = 0;
    for (let i = 0; i < chunk.length; i++) {
      const abs = Math.abs(chunk[i]);
      if (abs > peak) peak = abs;
    }

    const now = performance.now();
    // Điều kiện onset và debounce 350ms
    if (peak >= this.autoCaptureThreshold && (now - this.lastAutoCaptureTime > 350)) {
      this.lastAutoCaptureTime = now;

      // Cắt cửa sổ 250ms (4000 samples) kết hợp pre-buffer và chunk
      const targetLength = 4000;
      const snippet = new Float32Array(targetLength);
      const preLen = Math.min(this.rollingPreBuffer.length, 1200);
      snippet.set(this.rollingPreBuffer.slice(this.rollingPreBuffer.length - preLen), 0);
      snippet.set(chunk, preLen);

      // Gọi callback tải mẫu lên
      try {
        this.onAutoCapturedSample(snippet, peak);
      } catch (e) {
        console.error('[AutoCapture] Error in callback:', e);
      }
    }
  }

  getFrequencyData(array) {
    if (this.analyserNode) {
      this.analyserNode.getByteFrequencyData(array);
    }
  }

  getTimeDomainData(array) {
    if (this.analyserNode) {
      this.analyserNode.getByteTimeDomainData(array);
    }
  }

  startSnippetRecording(durationMs = 1200) {
    this.snippetBuffer = [];
    this.isRecordingSnippet = true;

    return new Promise((resolve) => {
      setTimeout(() => {
        this.isRecordingSnippet = false;
        const totalSamples = this.snippetBuffer.reduce((acc, b) => acc + b.length, 0);
        const result = new Float32Array(totalSamples);
        let offset = 0;
        for (const chunk of this.snippetBuffer) {
          result.set(chunk, offset);
          offset += chunk.length;
        }
        this.snippetBuffer = [];
        resolve(result);
      }, durationMs);
    });
  }

  _resample(source, fromRate, toRate) {
    const ratio = fromRate / toRate;
    const targetLength = Math.round(source.length / ratio);
    const result = new Float32Array(targetLength);
    for (let i = 0; i < targetLength; i++) {
      const srcIdx = Math.min(Math.round(i * ratio), source.length - 1);
      result[i] = source[srcIdx];
    }
    return result;
  }
}

export const audioStreamManager = new AudioStreamManager();
