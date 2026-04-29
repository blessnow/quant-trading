/**
 * 服务端直连 FastAPI（middleware rewrite、app/api/chat/send 代理）。
 * Railway：在前端服务配置 BACKEND_URL 为后端私网地址，例如
 *   http://<后端服务名>.railway.internal:8000
 * （middleware 已设 runtime=nodejs，否则 Edge 连不上私网，/api 转发会失败）
 * 或使用「变量引用」里生成的 RAILWAY_SERVICE_*_URL（须为内网，勿填 *.up.railway.app）。
 * 本地未配置时默认 http://127.0.0.1:8000。
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
  const onLocalPage =
    typeof window !== "undefined" &&
    (window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1");
  if (lower.includes("localhost") || lower.includes("127.0.0.1")) {
    // 构建/SSR 无 window，或生产域名：禁止把浏览器指到本机 loopback
    if (!onLocalPage) return "";
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
