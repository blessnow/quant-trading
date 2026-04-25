"use client";

import { useState, useEffect, useRef } from "react";
import StrategySelector from "./components/StrategySelector";
import SessionList from "./components/SessionList";
import MessageList from "./components/MessageList";
import ChatInput from "./components/ChatInput";
import PromptTemplates from "./components/PromptTemplates";

interface Strategy {
  id: string;
  name: string;
  avatar: string;
  color: string;
  description: string;
  prompts: { title: string; content: string; icon: string }[];
}

interface Session {
  id: number;
  strategy_id: string;
  title: string;
  updated_at: string;
}

interface Message {
  id: number;
  role: string;
  content: string;
  tool_calls: { name: string; args: Record<string, unknown>; result?: string }[] | null;
  created_at: string;
}

export default function ChatPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [currentStrategy, setCurrentStrategy] = useState<Strategy | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSession, setCurrentSession] = useState<Session | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 加载策略列表
  useEffect(() => {
    fetch("/api/chat/strategies")
      .then((res) => res.json())
      .then((data) => {
        setStrategies(data.strategies);
        if (data.strategies.length > 0) {
          setCurrentStrategy(data.strategies[0]);
        }
      });
  }, []);

  // 加载会话列表
  useEffect(() => {
    fetch("/api/chat/sessions")
      .then((res) => res.json())
      .then((data) => {
        setSessions(data.sessions);
      })
      .catch(() => {
        // 未登录时不报错
      });
  }, []);

  // 切换会话时加载消息
  useEffect(() => {
    if (currentSession) {
      fetch(`/api/chat/sessions/${currentSession.id}/messages`)
        .then((res) => res.json())
        .then((data) => {
          setMessages(data.messages);
        });
    } else {
      setMessages([]);
    }
  }, [currentSession]);

  // 滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // 创建新会话
  const createSession = async (): Promise<Session | null> => {
    if (!currentStrategy) return null;

    try {
      const res = await fetch("/api/chat/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy_id: currentStrategy.id }),
      });

      if (res.ok) {
        const data = await res.json();
        const newSession: Session = {
          id: data.session_id,
          strategy_id: currentStrategy.id,
          title: data.title,
          updated_at: new Date().toISOString(),
        };
        setSessions([newSession, ...sessions]);
        setCurrentSession(newSession);
        return newSession;
      }
    } catch (e) {
      console.error("创建会话失败:", e);
    }
    return null;
  };

  // 发送消息
  const sendMessage = async (content: string) => {
    let session = currentSession;

    // 如果没有会话，先创建
    if (!session) {
      session = await createSession();
      if (!session) {
        console.error("无法创建会话");
        return;
      }
    }

    const sessionId = session.id;

    // 添加用户消息
    const userMessage: Message = {
      id: Date.now(),
      role: "user",
      content,
      tool_calls: null,
      created_at: new Date().toISOString(),
    };
    setMessages([...messages, userMessage]);
    setIsLoading(true);

// SSE 流式响应 - 直接请求后端，绕过 Next.js rewrite
      let res;
      try {
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
        res = await fetch(`${backendUrl}/api/chat/send`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, content }),
        });
    } catch (e) {
      console.error("请求失败:", e);
      setIsLoading(false);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: "assistant",
          content: `网络错误，请检查后端服务是否运行`,
          tool_calls: null,
          created_at: new Date().toISOString(),
        },
      ]);
      return;
    }

    if (!res.ok) {
      setIsLoading(false);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: "assistant",
          content: `请求失败: ${res.status}`,
          tool_calls: null,
          created_at: new Date().toISOString(),
        },
      ]);
      return;
    }

    const reader = res.body?.getReader();
    const decoder = new TextDecoder();
    let assistantContent = "";
    let toolCalls: { name: string; args: Record<string, unknown>; result?: string }[] = [];

    if (reader) {
      outerLoop:
      while (true) {
        const { done, value } = await reader.read();
        console.log("[SSE] read:", { done, value: value ? value.length : 0 });
        if (done) break;

        const text = decoder.decode(value);
        console.log("[SSE] text:", text.substring(0, 200));
        const lines = text.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            console.log("[SSE] data:", data.substring(0, 100));
            if (data === "[DONE]") {
              console.log("[SSE] DONE");
              break outerLoop;
            }

            try {
              const event = JSON.parse(data);
              console.log("[SSE] event:", event.type);

              if (event.type === "tool_call") {
                toolCalls.push({ name: event.name, args: event.args });
                setMessages((prev) => {
                  const last = prev[prev.length - 1];
                  if (last.role === "assistant") {
                    return [...prev.slice(0, -1), { ...last, tool_calls: [...toolCalls] }];
                  }
                  return [
                    ...prev,
                    {
                      id: Date.now(),
                      role: "assistant",
                      content: "",
                      tool_calls: [...toolCalls],
                      created_at: new Date().toISOString(),
                    },
                  ];
                });
              } else if (event.type === "tool_result") {
                if (toolCalls.length > 0) {
                  toolCalls[toolCalls.length - 1].result = event.result;
                  setMessages((prev) => {
                    const last = prev[prev.length - 1];
                    if (last.role === "assistant") {
                      return [...prev.slice(0, -1), { ...last, tool_calls: [...toolCalls] }];
                    }
                    return prev;
                  });
                }
              } else if (event.type === "content") {
                console.log("[SSE] content received:", event.content.substring(0, 100));
                assistantContent = event.content;
                setIsLoading(false);
                setMessages((prev) => {
                  const last = prev[prev.length - 1];
                  if (last.role === "assistant") {
                    return [...prev.slice(0, -1), { ...last, content: assistantContent }];
                  }
                  return [
                    ...prev,
                    {
                      id: Date.now(),
                      role: "assistant",
                      content: assistantContent,
                      tool_calls: toolCalls.length > 0 ? toolCalls : null,
                      created_at: new Date().toISOString(),
                    },
                  ];
                });
              } else if (event.type === "error") {
                setIsLoading(false);
                setMessages((prev) => [
                  ...prev,
                  {
                    id: Date.now(),
                    role: "assistant",
                    content: `错误: ${event.content}`,
                    tool_calls: null,
                    created_at: new Date().toISOString(),
                  },
                ]);
                break outerLoop;
              }
            } catch (e) {
              console.error("[SSE] parse error:", e);
            }
          }
        }
      }
    }

    console.log("[SSE] finished, assistantContent:", assistantContent.substring(0, 100));
    setIsLoading(false);
  };

  // 删除会话
  const deleteSession = async (sessionId: number) => {
    await fetch(`/api/chat/sessions/${sessionId}`, { method: "DELETE" });
    setSessions(sessions.filter((s) => s.id !== sessionId));
    if (currentSession?.id === sessionId) {
      setCurrentSession(null);
    }
  };

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* 顶部策略选择器 */}
      <header className="bg-white border-b px-4 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <StrategySelector
            strategies={strategies}
            current={currentStrategy}
            onSelect={(s) => {
              setCurrentStrategy(s);
              setCurrentSession(null);
            }}
          />
          {currentStrategy && (
            <PromptTemplates
              prompts={currentStrategy.prompts}
              onSelect={(content) => sendMessage(content)}
            />
          )}
        </div>
      </header>

      {/* 主体区域 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左侧会话列表 */}
        <aside className="w-64 bg-white border-r flex flex-col">
          <div className="p-3 border-b">
            <button
              onClick={createSession}
              className="w-full py-2 px-4 bg-blue-500 text-white rounded-lg hover:bg-blue-600 flex items-center justify-center gap-2"
            >
              <span>+</span> 新对话
            </button>
          </div>
          <SessionList
            sessions={sessions}
            current={currentSession}
            onSelect={setCurrentSession}
            onDelete={deleteSession}
          />
        </aside>

        {/* 右侧消息区域 */}
        <main className="flex-1 flex flex-col">
          <MessageList
            messages={messages}
            isLoading={isLoading}
            strategyColor={currentStrategy?.color || "#3b82f6"}
          />
          <div ref={messagesEndRef} />
          <ChatInput onSend={sendMessage} disabled={isLoading} />
        </main>
      </div>
    </div>
  );
}
