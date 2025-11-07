// src/components/ChatPanel.js
import React from 'react';
import ChatMessages from './ChatMessages';
import ChatInput from './ChatInput';

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
  numQueriesAllowed
}) {
  return (
    <div className="chat-panel">
      <div className="chat-header">
        <h2 className="chat-title">
          {selectedDocument ? `Chat with ${selectedDocument}` : "Select a document to start chatting"}
        </h2>
        {!selectedDocument && (
          <p className="documents-subtitle" style={{marginTop: '0.5rem', fontSize: '0.875rem'}}>
            Choose a document from the sidebar or upload a new one
          </p>
        )}
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