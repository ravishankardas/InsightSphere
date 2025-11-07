// src/components/EmptyState.js
import React from 'react';

// Simple utility component to avoid repetition in DocumentsPanel and ChatMessages
export default function EmptyState({ icon, text }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon}</div>
      <div className="empty-text">{text}</div>
    </div>
  );
}