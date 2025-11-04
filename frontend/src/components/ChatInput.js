import React from "react";

export default function ChatInput({ value, onChange, onSend, disabled, uploading }) {
  return (
    <form className="chat-input" onSubmit={(e) => { e.preventDefault(); onSend(); }}>
      <div className="left-controls">
        <label htmlFor="file-upload" className={`mini-upload ${uploading ? "disabled" : ""}`} title="Upload PDF">
          +
        </label>
        <input id="file-upload" type="file" accept="application/pdf" style={{display: "none"}} />
      </div>

      <input
        className="chat-text-input"
        placeholder={disabled ? "Sign in and select a document to ask..." : "Ask a question..."}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      />

      <button className="send-btn" type="submit" disabled={disabled || !value.trim()}>
        Send
      </button>
    </form>
  );
}
