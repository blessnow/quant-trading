"use client";

import { useState, KeyboardEvent } from "react";

interface Props {
  onSend: (content: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: Props) {
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (input.trim() && !disabled) {
      onSend(input.trim());
      setInput("");
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-white/10 bg-[rgba(10,15,26,0.8)] p-4">
      <div className="max-w-4xl mx-auto flex gap-3">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题，按 Enter 发送..."
          className="dark-input flex-1 rounded-xl px-4 py-3 resize-none"
          rows={1}
          disabled={disabled}
        />
        <button
          onClick={handleSend}
          disabled={disabled || !input.trim()}
          className="px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-500 disabled:bg-white/10 disabled:text-white/30 disabled:cursor-not-allowed transition-colors font-medium"
        >
          发送
        </button>
      </div>
    </div>
  );
}
