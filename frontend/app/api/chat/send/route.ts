import { serverBackendBase } from "@/lib/api-base";

export const dynamic = "force-dynamic";
export const maxDuration = 1200;

/**
 * 流式代理：浏览器 → Next（同源）→ FastAPI SSE。
 * middleware rewrite 对外部 text/event-stream 不可靠，故单独走 Route Handler。
 */
export async function POST(request: Request) {
  const base = serverBackendBase();
  const url = `${base}/api/chat/send`;

  const contentType = request.headers.get("content-type") || "application/json";
  const cookie = request.headers.get("cookie");
  const authorization = request.headers.get("authorization");

  const upstream = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": contentType,
      Accept: "text/event-stream",
      ...(cookie ? { Cookie: cookie } : {}),
      ...(authorization ? { Authorization: authorization } : {}),
    },
    body: request.body,
    cache: "no-store",
    duplex: "half",
  } as RequestInit & { duplex: "half" });

  if (!upstream.body) {
    const fallback = await upstream.text().catch(() => "");
    return new Response(fallback || "后端未返回流", { status: upstream.status || 502 });
  }

  const ct = upstream.headers.get("content-type") || "text/event-stream";

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": ct.includes("text/event-stream") ? ct : "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
