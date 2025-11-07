// src/components/ChatMessage.js
import React from 'react';

export default function ChatMessage({ message, selectedDocument }) {
  // Utility function for processing sources (moved from App.js render)
  const renderSources = (retrieved) => {
    if (!retrieved || retrieved.length === 0) return null;

    return (
      <div className="sources-section">
        <div className="sources-title">📚 Top Sources</div>
        <div className="sources-grid">
          {retrieved
            .map((src, srcIndex) => {
              const sourceName = typeof src === 'string' ? src : (src.metadata?.source || src.source || src.filename || selectedDocument);
              const sourceContent = typeof src === 'string' ? "Source content" : (src.snippet || src.content || src.text || src.chunk || "No preview available");
              const score = src.distance !== undefined ? -1 * Math.round((1 - src.distance) * 100) : null;
              return {
                ...src,
                sourceName,
                sourceContent,
                score,
                originalIndex: srcIndex
              };
            })
            .sort((a, b) => (a.distance || 1) - (b.distance || 1)) 
            .slice(0, 2) 
            .map((src, displayIndex) => (
              <div
                key={src.originalIndex}
                className="source-item"
                onClick={() => console.log("Source clicked:", src)}
              >
                <div className="source-main">
                  <span className="source-number">#{displayIndex + 1}</span>
                  <span className="source-filename" title={src.sourceName}>
                    {src.sourceName.length > 20 ? src.sourceName.substring(0, 20) + "..." : src.sourceName}
                  </span>
                  {src.score && <span className="source-score"> {src.score}%</span>}
                </div>
                <div className="source-chunk" title={src.sourceContent}>
                  {src.sourceContent.length > 80 ? src.sourceContent.substring(0, 80) + "..." : src.sourceContent}
                </div>
              </div>
            ))
          }
        </div>
      </div>
    );
  };

  return (
    <div className={`chat-message ${message.isUser ? 'user' : 'assistant'}`}>
      <div className="chat-avatar">
        {message.isUser ? 'U' : 'AI'}
      </div>
      <div className="chat-content">
        <div className="chat-bubble">
          {message.content}
        </div>
        {renderSources(message.retrieved)}
      </div>
    </div>
  );
}