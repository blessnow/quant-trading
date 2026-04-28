"use client";

import { useState, useEffect, useRef } from "react";
import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import StrategySelector from "./components/StrategySelector";
import SessionList from "./components/SessionList";
import MessageList from "./components/MessageList";
import ChatInput from "./components/ChatInput";
import PromptTemplates from "./components/PromptTemplates";
import { clientApiOrigin } from "@/lib/api-base";

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
  const { user, loading } = useAuth();
  const router = useRouter();
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [currentStrategy, setCurrentStrategy] = useState<Strategy | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSession, setCurrentSession] = useState<Session | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const isStreamingRef = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/auth/login");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="h-[calc(100vh-64px)] flex items-center justify-center">
        <div className="text-white/50">加载中...</div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="h-[calc(100vh-64px)] flex items-center justify-center">
        <div className="text-white/50">请先登录...</div>
      </div>
    );
  }

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
    if (isStreamingRef.current) return;
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
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    isStreamingRef.current = true;

    // SSE：默认同源 /api，由 middleware/rewrites 转到后端
    const sseApiBase = clientApiOrigin();

    // SSE 流式响应
    let res;
    try {
      res = await fetch(`${sseApiBase}/api/chat/send`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream",
        },
        body: JSON.stringify({ session_id: sessionId, content }),
        cache: "no-store",
      });
    } catch (e) {
      console.error("请求失败:", e);
      setIsLoading(false);
      isStreamingRef.current = false;
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
      isStreamingRef.current = false;
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
    let buffer = "";
    // 使用本地变量追踪工具调用，避免 React 状态更新延迟问题
    let localToolCalls: { name: string; args: Record<string, unknown>; result?: string }[] = [];
    let localContent = "";
    let hasAssistantMsg = false;

    if (reader) {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmedLine = line.trim();
          if (!trimmedLine || !trimmedLine.startsWith("data: ")) continue;

          const data = trimmedLine.slice(6);
          if (data === "[DONE]") {
            setIsLoading(false);
            isStreamingRef.current = false;
            return;
          }

          try {
            const event = JSON.parse(data);

            if (event.type === "tool_call") {
              // 添加到本地工具调用列表
              localToolCalls.push({ name: event.name, args: event.args, result: undefined });
              // 立即更新 UI
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last?.role === "assistant") {
                  return [...prev.slice(0, -1), { ...last, tool_calls: [...localToolCalls] }];
                }
                hasAssistantMsg = true;
                return [...prev, {
                  id: Date.now(),
                  role: "assistant",
                  content: "",
                  tool_calls: [...localToolCalls],
                  created_at: new Date().toISOString(),
                }];
              });
            } else if (event.type === "tool_result") {
              // 更新本地工具调用结果
              const idx = localToolCalls.findIndex(tc => tc.result === undefined);
              if (idx !== -1) {
                localToolCalls[idx].result = event.result;
                // 立即更新 UI
                setMessages((prev) => {
                  const last = prev[prev.length - 1];
                  if (last?.role === "assistant") {
                    return [...prev.slice(0, -1), { ...last, tool_calls: [...localToolCalls] }];
                  }
                  return prev;
                });
              }
            } else if (event.type === "content") {
              setIsLoading(false);
              localContent = event.content;
              // 立即更新 UI
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last?.role === "assistant") {
                  return [...prev.slice(0, -1), {
                    ...last,
                    content: localContent,
                    tool_calls: localToolCalls.length > 0 ? localToolCalls : null
                  }];
                }
                return [...prev, {
                  id: Date.now(),
                  role: "assistant",
                  content: localContent,
                  tool_calls: localToolCalls.length > 0 ? localToolCalls : null,
                  created_at: new Date().toISOString(),
                }];
              });
            } else if (event.type === "error") {
              setIsLoading(false);
              setMessages((prev) => [...prev, {
                id: Date.now(),
                role: "assistant",
                content: `错误: ${event.content}`,
                tool_calls: null,
                created_at: new Date().toISOString(),
              }]);
            }
          } catch (e) {
            console.error("[SSE] parse error:", e);
          }
        }
      }
    }

    setIsLoading(false);
    isStreamingRef.current = false;
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
    <div className="h-[calc(100vh-64px)] flex flex-col">
      {/* 顶部策略选择器 */}
      <header className="glass-card mx-0 rounded-none border-x-0 border-t-0 px-4 py-3">
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
        <aside className="w-64 glass-card rounded-none border-t-0 border-b-0 border-l-0 flex flex-col">
          <div className="p-3 border-b border-white/10">
            <button
              onClick={createSession}
              className="btn-primary w-full flex items-center justify-center gap-2"
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
        <main className="flex-1 flex flex-col bg-[rgba(10,15,26,0.5)]">
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