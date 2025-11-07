// src/components/ChatInput.js
import React from 'react';

export default function ChatInput({
  query,
  setQuery,
  handleQuery,
  handleKeyPress,
  handleFileChange,
  querying,
  uploading,
  uploadStatus,
  selectedDocument,
  rateLimited,
  numQueriesAllowed
}) {
  
  const handleAttachClick = () => {
    document.getElementById('file-upload').click();
  };

  const getPlaceholder = () => {
    if (rateLimited) {
      return `Rate limited. Only allowed ${numQueriesAllowed} queries per day.`;
    }
    if (uploading) {
      return "Uploading document...";
    }
    return "Ask a question about your document...";
  };

  return (
    <div className="chat-input-container">
      {uploadStatus && (
        <div className={`alert alert-${uploadStatus.type}`}>
          <div className="alert-icon">
            {uploadStatus.type === "success" ? "✅" : 
             uploadStatus.type === "error" ? "⚠️" : "⏳"}
          </div>
          <div className="alert-text">{uploadStatus.message}</div>
        </div>
      )}

      <div className="chat-input-wrapper">
        <div className="chat-input-actions">
          <button
            className="attach-button"
            onClick={handleAttachClick}
            disabled={uploading || rateLimited}
            title="Attach PDF"
          >
            {uploading ? "⏳" : "📎"}
          </button>
          <input
            id="file-upload"
            type="file"
            accept=".pdf"
            onChange={handleFileChange}
            className="file-input-hidden"
            disabled={uploading}
          />
        </div>

        <div className="chat-input-area">
          <textarea
            className="chat-input"
            placeholder={getPlaceholder()}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={querying || uploading || rateLimited || !selectedDocument}
            rows="1"
          />
          <button
            className="send-button"
            onClick={handleQuery}
            disabled={querying || !query.trim() || uploading || !selectedDocument || rateLimited}
            title={rateLimited ? `Rate limited. Only allowed ${numQueriesAllowed} queries per day.` : "Send message"}
          >
            {rateLimited ? "⏳" : "➤"}
          </button>
        </div>
      </div>
    </div>
  );
}