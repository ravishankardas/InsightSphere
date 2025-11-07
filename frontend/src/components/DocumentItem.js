// src/components/DocumentItem.js
import React from 'react';

export default function DocumentItem({ doc, isSelected, isDeleting, handleDocumentClick, handleDeleteClick }) {
  const docName = typeof doc === "string" ? doc : (doc.source || doc.name || doc.file || "");
  const displayName = docName.length > 30 ? docName.substring(0, 30) + "..." : docName;
  const isDocDeleting = isDeleting === docName;

  return (
    <div
      className={`document-item ${isSelected ? 'selected' : ''}`}
      onClick={() => handleDocumentClick(docName)}
      title={docName}
    >
      <div className="document-content">
        <div className="document-icon">📄</div>
        <div className="document-info">
          <div className="document-name">
            {displayName}
          </div>
        </div>
      </div>
      <button
        className="delete-button"
        onClick={(e) => {
          e.stopPropagation();
          handleDeleteClick(docName);
        }}
        disabled={isDocDeleting}
        title={`Delete ${docName}`}
      >
        {isDocDeleting ? "⏳" : "🗑️"}
      </button>
    </div>
  );
}