import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.RAILWAY_SERVICE_BACKEND_URL ||
  "http://localhost:8000";

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  if (pathname.startsWith("/api/")) {
    const target = new URL(pathname + search, BACKEND_URL);
    return NextResponse.rewrite(target);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/api/:path*"],
};
