// src/components/SettingsPanel.js
import React from 'react';

export default function SettingsPanel({ apiUrl, setApiUrl, testBackendConnection }) {
  return (
    <div className="settings-panel">
      <div className="settings-content">
        <h3>Backend Configuration</h3>
        <label className="settings-label">Backend API URL</label>
        <input
          type="text"
          value={apiUrl}
          onChange={(e) => setApiUrl(e.target.value)}
          className="settings-input"
          placeholder="https://api.example.com"
        />
        <p className="card-subtitle" style={{ marginTop: 8 }}>
          Current: {apiUrl}
        </p>
        <button 
          className="secondary-button small" 
          onClick={testBackendConnection}
          style={{ marginTop: '0.5rem' }}
        >
          Test Connection
        </button>
      </div>
    </div>
  );
}