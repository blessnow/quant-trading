import { serverBackendBase } from "@/lib/api-base";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

const UPSTREAM_MS = 55_000;

function buildForwardHeaders(request: Request, target: URL): Headers {
  const h = new Headers();
  h.set("host", target.host);
  const origHost = request.headers.get("host");
  if (origHost) {
    h.set("x-forwarded-host", origHost);
  }
  const pass = [
    "content-type",
    "authorization",
    "cookie",
    "accept",
    "accept-language",
    "user-agent",
    "origin",
    "access-control-request-method",
    "access-control-request-headers",
  ];
  for (const name of pass) {
    const v = request.headers.get(name);
    if (v) {
      h.set(name, v);
    }
  }
  return h;
}

/** 与 /api/auth 相同：避免 middleware rewrite 到内网时 GET/POST 挂死 */
async function proxy(request: Request, pathSegments: string[]) {
  const sub = pathSegments.length ? pathSegments.join("/") : "";
  const base = serverBackendBase().replace(/\/$/, "");
  const q = new URL(request.url).search;
  const targetUrl = `${base}/api/wechat/${sub}${q}`;
  const target = new URL(targetUrl);

  const method = request.method;
  const noBody = method === "GET" || method === "HEAD";

  let body: string | undefined;
  if (!noBody && method !== "OPTIONS") {
    try {
      body = await request.text();
    } catch {
      return Response.json({ detail: "无法读取请求体" }, { status: 400 });
    }
  }

  const controller = new AbortController();
  const onAbort = () => controller.abort();
  request.signal.addEventListener("abort", onAbort);
  const timer = setTimeout(onAbort, UPSTREAM_MS);

  try {
    const upstream = await fetch(targetUrl, {
      method,
      headers: buildForwardHeaders(request, target),
      body: noBody || method === "OPTIONS" ? undefined : body,
      signal: controller.signal,
      cache: "no-store",
    });
    clearTimeout(timer);
    request.signal.removeEventListener("abort", onAbort);

    if (!upstream.body && method !== "HEAD") {
      const fallback = await upstream.text().catch(() => "");
      return new Response(fallback || "后端无响应", { status: upstream.status || 502 });
    }

    return new Response(upstream.body, {
      status: upstream.status,
      headers: upstream.headers,
    });
  } catch (e) {
    clearTimeout(timer);
    request.signal.removeEventListener("abort", onAbort);
    const aborted = e instanceof Error && e.name === "AbortError";
    const msg =
      aborted && request.signal.aborted
        ? "客户端已取消"
        : aborted
          ? "连接后端超时，请稍后重试"
          : "无法连接后端服务";
    return Response.json({ detail: msg }, { status: aborted ? 504 : 502 });
  }
}

type Ctx = { params: Promise<{ path?: string[] }> };

export async function GET(request: Request, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(request, path ?? []);
}

export async function POST(request: Request, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(request, path ?? []);
}

export async function OPTIONS(request: Request, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(request, path ?? []);
}
