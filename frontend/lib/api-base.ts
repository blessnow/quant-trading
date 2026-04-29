/**
 * 服务端直连 FastAPI（middleware rewrite、app/api/chat/send 代理）。
 * Railway：
 * - 在前端服务配置 BACKEND_URL，请用控制台「后端服务 → Networking → Private」里复制的完整 URL，
 *   或使用变量引用，使「主机名 + 端口」与后端实际监听的 PORT 一致。
 * - 后端 `config.API_PORT` 使用环境变量 PORT（Railway 注入），往往**不是** 8000；不要手写
 *   `...railway.internal:8000` 除非后端 PORT 确为 8000，否则易出现登录 504（代理等后端响应超时）。
 * - 排查：浏览器打开同源 GET `/api/diag`，看 health_ms / login_post_ms。
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
