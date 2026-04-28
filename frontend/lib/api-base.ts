/**
 * 服务端直连 FastAPI：须配置 BACKEND_URL（或 Railway RAILWAY_SERVICE_*），本地未配时默认 127.0.0.1:8000。
 */
export function serverBackendBase(): string {
  const u = process.env.BACKEND_URL || process.env.RAILWAY_SERVICE_BACKEND_URL;
  if (u) return u.replace(/\/$/, "");
  return "http://127.0.0.1:8000";
}

/**
 * 浏览器 HTTP：未配 NEXT_PUBLIC_BACKEND_URL 时用同源（相对路径），由 middleware 转到后端。
 * 忽略误配到内网/本机的 NEXT_PUBLIC（旧构建或错误 env 会导致浏览器「网络错误」）。
 */
export function clientApiOrigin(): string {
  const raw = process.env.NEXT_PUBLIC_BACKEND_URL?.trim() || "";
  if (!raw) return "";
  const lower = raw.toLowerCase();
  if (lower.includes("railway.internal")) return "";
  if (typeof window !== "undefined" && window.location.hostname !== "localhost") {
    if (lower.includes("localhost") || lower.includes("127.0.0.1")) return "";
  }
  return raw.replace(/\/$/, "");
}

/**
 * 浏览器 WebSocket：与 clientApiOrigin 同源策略一致，再 http(s)→ws(s)。
 */
export function clientWebSocketRoot(): string {
  const httpBase = clientApiOrigin();
  if (httpBase) {
    return httpBase.startsWith("https://")
      ? `wss://${httpBase.slice("https://".length)}`
      : httpBase.startsWith("http://")
        ? `ws://${httpBase.slice("http://".length)}`
        : `ws://${httpBase}`;
  }
  if (typeof window !== "undefined" && window.location.hostname === "localhost") {
    return "ws://127.0.0.1:8000";
  }
  if (typeof window !== "undefined") {
    return window.location.protocol === "https:" ? `wss://${window.location.host}` : `ws://${window.location.host}`;
  }
  return "ws://127.0.0.1:8000";
}
