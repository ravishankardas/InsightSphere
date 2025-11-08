// src/components/ChatInput.js
import React, { useState, useEffect, useRef } from 'react';
import './ChatInput.css';
import { FaMicrophone } from "react-icons/fa";

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
  const [isListening, setIsListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(true);
  const recognitionRef = useRef(null);
  const finalTranscriptRef = useRef('');

  // Check if browser supports speech recognition
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setSpeechSupported(false);
      return;
    }

    recognitionRef.current = new SpeechRecognition();
    recognitionRef.current.continuous = true;
    recognitionRef.current.interimResults = true;
    recognitionRef.current.lang = 'en-US';

    recognitionRef.current.onstart = () => {
      setIsListening(true);
      finalTranscriptRef.current = '';
      setQuery(''); // Clear the input when starting
    };

    recognitionRef.current.onresult = (event) => {
      let interimTranscript = '';
      
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          // Add final text to our accumulated transcript
          finalTranscriptRef.current += transcript + ' ';
        } else {
          // This is interim (real-time) text
          interimTranscript = transcript;
        }
      }

      // Show final text + current interim text
      const displayText = finalTranscriptRef.current + (interimTranscript ? `[${interimTranscript}]` : '');
      setQuery(displayText.trim());
    };

    recognitionRef.current.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      setIsListening(false);
      
      if (event.error === 'not-allowed') {
        alert('Microphone access denied. Please allow microphone permissions.');
      }
    };

    recognitionRef.current.onend = () => {
      setIsListening(false);
      // Remove any remaining brackets when done
      setQuery(finalTranscriptRef.current.trim());
    };

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    };
  }, [setQuery]);

  const toggleListening = () => {
    if (!speechSupported) {
      alert('Speech recognition is not supported in your browser. Try Chrome or Edge.');
      return;
    }

    if (isListening) {
      recognitionRef.current.stop();
    } else {
      finalTranscriptRef.current = '';
      recognitionRef.current.start();
      setIsListening(true);
    }
  };

  return (
    <div className="chat-input-container">
      {uploadStatus && (
        <div className={`upload-status ${uploadStatus.type}`}>
          {uploadStatus.message}
        </div>
      )}

      <div className="input-group">
        {/* File Upload */}
        <label className="file-upload-label">
          <input
            type="file"
            id="file-upload"
            accept=".pdf"
            onChange={handleFileChange}
            disabled={uploading}
          />
          <span className="upload-icon">
            {uploading ? '⏳' : '📎'}
          </span>
        </label>

        {/* Text Input */}
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={selectedDocument ? "Ask a question about the document..." : "Upload a document to start chatting..."}
          disabled={!selectedDocument || querying || rateLimited}
          rows="1"
        />

        {/* Voice Input Button */}
        <button
          className={`voice-btn ${isListening ? 'listening' : ''}`}
          onClick={toggleListening}
          type="button"
          disabled={!speechSupported || !selectedDocument || querying || rateLimited}
          title={speechSupported ? "Voice input" : "Voice not supported"}
        >
          {isListening ? '🎤🔴' : '🎤'}
        </button>

        {/* Send Button */}
        <button
          onClick={handleQuery}
          disabled={!selectedDocument || !query.replace(/\[.*?\]/g, '').trim() || querying || rateLimited}
          className="send-btn"
        >
          {querying ? '⏳' : '➤'}
        </button>
      </div>

      {/* Rate limiting message */}
      {rateLimited && (
        <div className="rate-limit-message">
          ⚠️ Rate limited: Only {numQueriesAllowed} queries allowed. Try again later.
        </div>
      )}

      {/* Voice listening indicator */}
      {isListening && (
        <div className="listening-indicator">
          🎤 Listening... Speak now. Click microphone again to stop.
        </div>
      )}
    </div>
  );
}