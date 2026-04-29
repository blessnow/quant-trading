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
    const target = new URL(pathname + search, serverBackendBase());
    return NextResponse.rewrite(target);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/api/:path*"],
};
