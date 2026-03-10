import { NextRequest, NextResponse } from "next/server";

const AUTH_ROUTES = ["/dashboard", "/settings", "/trade", "/bot", "/results"];
const PUBLIC_ROUTES = ["/login", "/register"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasToken = request.cookies.has("access_token");

  // 인증 필요 경로에 토큰 없으면 → /login
  const isAuthRoute = AUTH_ROUTES.some((r) => pathname.startsWith(r));
  if (isAuthRoute && !hasToken) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  // 이미 로그인된 상태에서 login/register 접근 → /dashboard
  const isPublicRoute = PUBLIC_ROUTES.some((r) => pathname.startsWith(r));
  if (isPublicRoute && hasToken) {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/settings/:path*", "/trade/:path*", "/bot/:path*", "/results/:path*", "/login", "/register"],
};
