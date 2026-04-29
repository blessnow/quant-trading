import { NextRequest, NextResponse } from "next/server";
import { serverBackendBase } from "./lib/api-base";

/** Edge 无法可靠访问 *.railway.internal；私网 BACKEND_URL 必须在 Node 里做 rewrite */
export const runtime = "nodejs";

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  if (pathname.startsWith("/api/")) {
    // SSE 不能走 rewrite 到外部：会被缓冲/改头，客户端一直等不到分块（见 Next #45048）
    if (pathname === "/api/chat/send") {
      return NextResponse.next();
    }
    // POST/GET + 内网 rewrite 易挂死/502；改由 app/api/*/route.ts 代理
    if (pathname.startsWith("/api/auth") || pathname.startsWith("/api/wechat")) {
      return NextResponse.next();
    }
    const baseStr = serverBackendBase().replace(/\/$/, "");
    const baseForParse = baseStr.endsWith("/") ? baseStr : `${baseStr}/`;
    const baseUrl = new URL(baseForParse);
    const target = new URL(`${pathname}${search}`, baseUrl);

    // rewrite 到内网时若不改 Host，后端仍收到前端公网 Host，BACKEND_PRIVATE_ONLY 会误判 → 404
    const headers = new Headers(request.headers);
    headers.set("host", target.host);
    const origHost = request.headers.get("host");
    if (origHost) {
      headers.set("x-forwarded-host", origHost);
    }

    return NextResponse.rewrite(target, { request: { headers } });
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/api/:path*"],
};
