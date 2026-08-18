/**
 * API Client giao tiếp REST endpoints với Backend (v2 Pro)
 */

const API_BASE = '/api';

async function safeJson(res) {
  if (!res || !res.ok) {
    throw new Error(`HTTP ${res ? res.status : 'ERR'}`);
  }
  return await res.json();
}

export const ApiClient = {
  async getHealth() {
    try {
      const res = await fetch(`${API_BASE}/health`);
      return await safeJson(res);
    } catch {
      return { status: 'offline' };
    }
  },

  async getBulbState() {
    try {
      const res = await fetch(`${API_BASE}/bulb/state`);
      return await safeJson(res);
    } catch {
      return { is_on: false, brightness: 100, color_rgb: [255, 220, 100], last_pattern: 'none' };
    }
  },

  async updateBulbState(state) {
    const res = await fetch(`${API_BASE}/bulb/state`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(state)
    });
    return await safeJson(res);
  },

  async triggerBulbAction(action) {
    const res = await fetch(`${API_BASE}/bulb/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action })
    });
    return await safeJson(res);
  },

  async getSettings() {
    const res = await fetch(`${API_BASE}/settings`);
    return await safeJson(res);
  },

  async updateSettings(settings) {
    const res = await fetch(`${API_BASE}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });
    return await safeJson(res);
  },

  async getProfiles() {
    const res = await fetch(`${API_BASE}/training/profiles`);
    return await res.json();
  },

  async createProfile(name) {
    const res = await fetch(`${API_BASE}/training/profiles`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    return await res.json();
  },

  async getSamples(profileName = 'default', category = null) {
    const url = category 
      ? `${API_BASE}/training/samples?profile_name=${encodeURIComponent(profileName)}&category=${encodeURIComponent(category)}`
      : `${API_BASE}/training/samples?profile_name=${encodeURIComponent(profileName)}`;
    const res = await fetch(url);
    return await res.json();
  },

  async deleteSample(profileName, category, sampleId) {
    const res = await fetch(`${API_BASE}/training/sample`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profile_name: profileName,
        category: category,
        sample_id: sampleId
      })
    });
    return await res.json();
  },

  async clearCategorySamples(profileName, category) {
    const res = await fetch(`${API_BASE}/training/samples/clear`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profile_name: profileName,
        category: category
      })
    });
    return await res.json();
  },

  async uploadSample(profileName, category, float32Array) {
    const buffer = float32Array.buffer;
    let binary = '';
    const bytes = new Uint8Array(buffer);
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    const base64Audio = btoa(binary);

    const res = await fetch(`${API_BASE}/training/sample`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profile_name: profileName,
        category: category,
        audio_base64: base64Audio,
        format: 'float32'
      })
    });
    return await res.json();
  },

  async calibrateNoise(float32Array) {
    const buffer = float32Array.buffer;
    let binary = '';
    const bytes = new Uint8Array(buffer);
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    const base64Audio = btoa(binary);

    const res = await fetch(`${API_BASE}/training/calibrate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ audio_base64: base64Audio })
    });
    return await res.json();
  },

  async applyPreset(presetName) {
    const res = await fetch(`${API_BASE}/training/preset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preset_name: presetName })
    });
    return await res.json();
  },

  async trainModel(profileName, cnnEpochs = 25) {
    const res = await fetch(`${API_BASE}/training/train`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profile_name: profileName,
        augment_factor: 15,
        cnn_epochs: cnnEpochs
      })
    });
    return await res.json();
  },

  async activateProfile(profileName) {
    const res = await fetch(`${API_BASE}/training/activate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profile_name: profileName })
    });
    return await safeJson(res);
  },

  // --- TRIGGER HISTORY & FALSE POSITIVE MINING ---
  async getRecentTriggers() {
    try {
      const res = await fetch(`${API_BASE}/events/recent-triggers`);
      return await safeJson(res);
    } catch {
      return { status: 'error', total: 0, events: [] };
    }
  },

  async markFalsePositive(eventId, profileName = 'default', category = 'noises', autoRetrain = true) {
    const res = await fetch(`${API_BASE}/events/mark-false-positive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_id: eventId,
        profile_name: profileName,
        category: category,
        auto_retrain: autoRetrain
      })
    });
    return await safeJson(res);
  },

  async clearTriggerHistory() {
    const res = await fetch(`${API_BASE}/events/clear`, {
      method: 'DELETE'
    });
    return await safeJson(res);
  }
};
