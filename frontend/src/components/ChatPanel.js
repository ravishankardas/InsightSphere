// src/components/ChatPanel.js
import React from 'react';
import ChatMessages from './ChatMessages';
import ChatInput from './ChatInput';
import ExportChatButton from './ExportChatButton';

export default function ChatPanel({
  selectedDocument,
  messages,
  query,
  setQuery,
  handleQuery,
  handleKeyPress,
  handleFileChange,
  querying,
  uploading,
  uploadStatus,
  rateLimited,
  numQueriesAllowed,
  loadingChats,
  loadingChatHistory 
}) {
  return (
    <div className="chat-panel">
      <div className="chat-header">
        <div className="chat-header-content">
          <div className="chat-title-section">
            <h2 className="chat-title">
              {selectedDocument ? `Chat with ${selectedDocument}` : "Select a document to start chatting"}
              {loadingChats && <span className="loading-indicator"> (Loading...)</span>}
              {loadingChatHistory && <span className="loading-indicator"> (Loading history...)</span>}
            </h2>
            {!selectedDocument && (
              <p className="documents-subtitle">
                Choose a document from the sidebar or upload a new one
              </p>
            )}
          </div>
          
          {/* Export Button - Only show when document is selected */}
          {selectedDocument && messages.length > 0 && (
            <div className="export-section">
              <ExportChatButton 
                messages={messages}
                selectedDocument={selectedDocument}
                disabled={!selectedDocument || messages.length === 0 || loadingChatHistory}
              />
            </div>
          )}
        </div>
      </div>

      <ChatMessages
        messages={messages}
        querying={querying}
        selectedDocument={selectedDocument}
      />

      <ChatInput
        query={query}
        setQuery={setQuery}
        handleQuery={handleQuery}
        handleKeyPress={handleKeyPress}
        handleFileChange={handleFileChange}
        querying={querying}
        uploading={uploading}
        uploadStatus={uploadStatus}
        selectedDocument={selectedDocument}
        rateLimited={rateLimited}
        numQueriesAllowed={numQueriesAllowed}
      />
    </div>
  );
}