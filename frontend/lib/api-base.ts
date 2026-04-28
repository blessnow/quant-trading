/**
 * 服务端直连 FastAPI：须配置 BACKEND_URL（或 Railway RAILWAY_SERVICE_*），本地未配时默认 127.0.0.1:8000。
 */
export function serverBackendBase(): string {
  const u = process.env.BACKEND_URL || process.env.RAILWAY_SERVICE_BACKEND_URL;
  if (u) return u.replace(/\/$/, "");
  return "http://127.0.0.1:8000";
}

/**
 * 浏览器 HTTP：未配 NEXT_PUBLIC_BACKEND_URL 时用同源（相对路径），由 middleware / rewrites 转到后端。
 */
export function clientApiOrigin(): string {
  const u = process.env.NEXT_PUBLIC_BACKEND_URL?.trim();
  if (u) return u.replace(/\/$/, "");
  return "";
}

/**
 * 浏览器 WebSocket：优先 NEXT_PUBLIC；本地开发直连后端；否则同源（需网关把 /ws 转到后端，否则请配公网后端 URL）。
 */
export function clientWebSocketRoot(): string {
  const u = process.env.NEXT_PUBLIC_BACKEND_URL?.trim().replace(/\/$/, "");
  if (u) {
    return u.startsWith("https://")
      ? `wss://${u.slice("https://".length)}`
      : u.startsWith("http://")
        ? `ws://${u.slice("http://".length)}`
        : u;
  }
  if (typeof window !== "undefined" && window.location.hostname === "localhost") {
    return "ws://127.0.0.1:8000";
  }
  if (typeof window !== "undefined") {
    return window.location.protocol === "https:" ? `wss://${window.location.host}` : `ws://${window.location.host}`;
  }
  return "ws://127.0.0.1:8000";
}
