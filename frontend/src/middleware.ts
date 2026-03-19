import { NextRequest, NextResponse } from "next/server";
import { jwtVerify } from "jose";

const AUTH_ROUTES = ["/dashboard", "/settings", "/trade", "/bot", "/results", "/strategy"];
const PUBLIC_ROUTES = ["/login", "/register"];

/** JWT 서명/만료 검증. JWT_SECRET_KEY 미설정 시 토큰 존재만 확인 (로컬 개발 fallback) */
async function isTokenValid(token: string): Promise<boolean> {
  const secretKey = process.env.JWT_SECRET_KEY;
  if (!secretKey) {
    // JWT_SECRET_KEY 미설정 → 토큰 존재만 확인 (로컬 개발 편의)
    return true;
  }

  try {
    const secret = new TextEncoder().encode(secretKey);
    await jwtVerify(token, secret);
    return true;
  } catch {
    // 만료/서명 불일치
    return false;
  }
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get("access_token")?.value;

  // 인증 필요 경로 — 토큰 없거나 유효하지 않으면 → /login
  const isAuthRoute = AUTH_ROUTES.some((r) => pathname.startsWith(r));
  if (isAuthRoute) {
    if (!token || !(await isTokenValid(token))) {
      const url = request.nextUrl.clone();
      url.pathname = "/login";
      // 만료된 쿠키 제거
      const response = NextResponse.redirect(url);
      if (token) {
        response.cookies.delete("access_token");
      }
      return response;
    }
  }

  // 이미 로그인된 상태에서 login/register 접근 → /dashboard
  const isPublicRoute = PUBLIC_ROUTES.some((r) => pathname.startsWith(r));
  if (isPublicRoute && token && (await isTokenValid(token))) {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/settings/:path*", "/trade/:path*", "/bot/:path*", "/results/:path*", "/strategy/:path*", "/login", "/register"],
};
