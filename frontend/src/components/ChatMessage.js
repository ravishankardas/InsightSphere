import React from "react";

export default function ChatMessage({ role = "assistant", text, time, onClickSource }) {
  const isUser = role === "user";
  const containerClass = isUser ? "msg-row user" : "msg-row assistant";
  const bubbleClass = isUser ? "msg-bubble user-bubble" : "msg-bubble assistant-bubble";

  return (
    <div className={containerClass}>
      <div className="msg-avatar">{isUser ? "You" : "AI"}</div>
      <div className={bubbleClass} onClick={onClickSource}>
        <div className="msg-text" dangerouslySetInnerHTML={{ __html: text }} />
        {time && <div className="msg-time">{time}</div>}
      </div>
    </div>
  );
}
