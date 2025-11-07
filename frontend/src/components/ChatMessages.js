// src/components/ChatMessages.js
import React from 'react';
import ChatMessage from './ChatMessage';
import EmptyState from './EmptyState';

export default function ChatMessages({ messages, querying, selectedDocument }) {
  return (
    <div className="chat-messages">
      {messages.length === 0 ? (
        <EmptyState 
          icon="💬" 
          text={selectedDocument 
            ? `Ask questions about "${selectedDocument}"` 
            : "Select or upload a document to start asking questions"
          } 
        />
      ) : (
        messages.map((message, index) => (
          <ChatMessage 
            key={index} 
            message={message} 
            selectedDocument={selectedDocument} 
          />
        ))
      )}
      {querying && (
        <div className="chat-message assistant">
          <div className="chat-avatar">AI</div>
          <div className="chat-content">
            <div className="chat-bubble">
              Thinking...
            </div>
          </div>
        </div>
      )}
    </div>
  );
}