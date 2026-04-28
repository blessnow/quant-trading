import { NextRequest, NextResponse } from "next/server";
import { serverBackendBase } from "./lib/api-base";

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  if (pathname.startsWith("/api/")) {
    const target = new URL(pathname + search, serverBackendBase());
    return NextResponse.rewrite(target);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/api/:path*"],
};
