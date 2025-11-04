import React, { useEffect, useRef } from "react";
import ChatMessage from "./ChatMessage";

export default function MessagesList({ messages = [], onSourceClick }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages]);

  return (
    <div className="messages-list">
      {messages.map((m, idx) => (
        <ChatMessage
          key={idx}
          role={m.role}
          text={m.text}
          time={m.time}
          onClickSource={() => onSourceClick && onSourceClick(m)}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
