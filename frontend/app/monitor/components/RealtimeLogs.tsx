"use client";

import { useEffect, useState, useRef } from "react";
import { clientWebSocketRoot } from "@/lib/api-base";

interface LogEntry {
  strategy_id: number;
  strategy_name: string;
  level: string;
  message: string;
  detail: string;
  time: string;
}

export function RealtimeLogs() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatRef = useRef<NodeJS.Timeout | null>(null);

  const connect = () => {
    const ws = new WebSocket(`${clientWebSocketRoot()}/ws/logs`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      console.log("[WebSocket] 已连接到日志流");
      // 启动心跳
      heartbeatRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send("ping");
        }
      }, 30000);
    };

    ws.onmessage = (event) => {
      try {
        const log = JSON.parse(event.data);
        setLogs((prev) => [log, ...prev].slice(0, 100));
      } catch (e) {
        console.error("[WebSocket] 解析日志失败:", e);
      }
    };

    ws.onerror = (error) => {
      console.error("[WebSocket] 错误:", error);
    };

    ws.onclose = () => {
      setConnected(false);
      console.log("[WebSocket] 连接已关闭，5秒后重连");
      // 清理心跳
      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
      // 5秒后重连
      reconnectTimerRef.current = setTimeout(connect, 5000);
    };
  };

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = 0;
    }
  }, [logs]);

  return (
    <div className="bg-[rgba(10,15,26,0.8)] rounded-xl overflow-hidden border border-white/10">
      <div className="flex items-center justify-between px-4 py-3 bg-white/5 border-b border-white/10">
        <span className="text-white text-sm font-medium">实时日志</span>
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${
              connected ? "bg-green-500 animate-pulse" : "bg-red-500"
            }`}
          />
          <span className="text-xs text-white/40">
            {connected ? "已连接" : "未连接"}
          </span>
        </div>
      </div>
      <div
        ref={containerRef}
        className="h-80 overflow-y-auto p-4 font-mono text-xs"
      >
        {logs.length === 0 ? (
          <div className="text-white/40 text-center py-8">
            等待日志...
          </div>
        ) : (
          logs.map((log, i) => (
            <div key={i} className="mb-2 leading-relaxed">
              <span className="text-white/40">[{log.time}]</span>{" "}
              <span className={
                log.level === "error" ? "text-red-400" :
                log.level === "warn" ? "text-yellow-400" :
                "text-green-400"
              }>
                [{log.level.toUpperCase()}]
              </span>{" "}
              <span className="text-blue-400">{log.strategy_name}:</span>{" "}
              <span className="text-white/70">{log.message}</span>
              {log.detail && (
                <div className="text-white/40 ml-4 mt-1">{log.detail}</div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}