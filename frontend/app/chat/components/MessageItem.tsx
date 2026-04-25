"use client";

import ToolCallDisplay from "./ToolCallDisplay";

interface Message {
  id: number;
  role: string;
  content: string;
  tool_calls: { name: string; args: Record<string, unknown>; result?: string }[] | null;
  created_at: string;
}

interface Props {
  message: Message;
  strategyColor: string;
}

export default function MessageItem({ message, strategyColor }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] ${
          isUser
            ? "bg-blue-500 text-white rounded-2xl rounded-br-md"
            : "bg-white border rounded-2xl rounded-bl-md"
        } px-4 py-3`}
      >
        {/* 工具调用展示 */}
        {message.tool_calls && message.tool_calls.length > 0 && (
          <div className="mb-3 space-y-2">
            {message.tool_calls.map((tc, i) => (
              <ToolCallDisplay key={i} toolCall={tc} />
            ))}
          </div>
        )}

        {/* 消息内容 */}
        {message.content && (
          <div className={`prose prose-sm ${isUser ? "prose-invert" : ""} max-w-none`}>
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>
        )}

        {/* 时间 */}
        <p className={`text-xs mt-2 ${isUser ? "text-blue-100" : "text-gray-400"}`}>
          {new Date(message.created_at).toLocaleTimeString()}
        </p>
      </div>
    </div>
  );
}