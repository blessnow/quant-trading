"use client";

import MessageItem from "./MessageItem";

interface Message {
  id: number;
  role: string;
  content: string;
  tool_calls: { name: string; args: Record<string, unknown>; result?: string }[] | null;
  created_at: string;
}

interface Props {
  messages: Message[] | undefined;
  isLoading: boolean;
  strategyColor: string;
}

export default function MessageList({ messages = [], isLoading, strategyColor }: Props) {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {(!messages || messages.length === 0) && !isLoading ? (
        <div className="h-full flex items-center justify-center text-gray-400">
          <div className="text-center">
            <p className="text-4xl mb-4">💬</p>
            <p>选择一个策略，开始对话吧</p>
          </div>
        </div>
      ) : (
        messages.map((m) => (
          <MessageItem key={m.id} message={m} strategyColor={strategyColor} />
        ))
      )}

      {isLoading && (
        <div className="flex items-center gap-2 text-gray-400">
          <div className="animate-spin w-4 h-4 border-2 border-gray-300 border-t-gray-600 rounded-full" />
          <span>思考中...</span>
        </div>
      )}
    </div>
  );
}