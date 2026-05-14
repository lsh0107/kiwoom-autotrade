/**
 * middleware isTokenValid 단위 테스트.
 *
 * JWT_SECRET_KEY 미설정(fail-closed) / fake token / valid signed token 검증.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// jose.jwtVerify 를 모킹하여 middleware 내 isTokenValid 로직만 검증
vi.mock("jose", () => ({
  jwtVerify: vi.fn(),
}));

// next/server 모킹 — middleware 함수가 호출하는 NextResponse/NextRequest
const mockRedirect = vi.fn().mockReturnValue({
  cookies: { delete: vi.fn() },
});

vi.mock("next/server", () => ({
  NextResponse: {
    redirect: (...args: unknown[]) => mockRedirect(...args),
    next: vi.fn().mockReturnValue({ type: "next" }),
  },
  NextRequest: vi.fn(),
}));

import { jwtVerify } from "jose";

// middleware.ts 를 동적으로 import 하기 위해 함수로 감싼다
async function loadMiddleware() {
  // 매번 fresh module 로 가져오기 위해 cache bust
  const mod = await import("@/middleware");
  return mod;
}

function createMockRequest(pathname: string, cookieToken?: string) {
  const url = new URL(`http://localhost:3000${pathname}`);
  return {
    nextUrl: Object.assign(url, { clone: () => new URL(url.href) }),
    cookies: {
      get: (name: string) =>
        name === "access_token" && cookieToken
          ? { value: cookieToken }
          : undefined,
    },
  };
}

describe("isTokenValid — fail-closed 동작", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("JWT_SECRET_KEY 미설정 + fake token → /login 리다이렉트 (fail-closed)", async () => {
    // secret 미설정
    delete process.env.JWT_SECRET_KEY;

    const { middleware } = await loadMiddleware();
    const req = createMockRequest("/decisions", "fake-token");
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    await middleware(req as any);

    // 리다이렉트 호출 확인
    expect(mockRedirect).toHaveBeenCalled();
    const redirectUrl = mockRedirect.mock.calls[0][0] as URL;
    expect(redirectUrl.pathname).toBe("/login");
  });

  it("JWT_SECRET_KEY 설정 + 유효 서명 → 통과 (리다이렉트 없음)", async () => {
    process.env.JWT_SECRET_KEY = "test-secret-key-for-unit-test";
    vi.mocked(jwtVerify).mockResolvedValueOnce({
      payload: { sub: "user1" },
      protectedHeader: { alg: "HS256" },
    } as never);

    const { middleware } = await loadMiddleware();
    const req = createMockRequest("/decisions", "valid-signed-token");
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result = await middleware(req as any);

    // NextResponse.next() 반환 = 리다이렉트 없음
    expect(result).toEqual({ type: "next" });
  });

  it("JWT_SECRET_KEY 설정 + 만료/불일치 서명 → /login 리다이렉트", async () => {
    process.env.JWT_SECRET_KEY = "test-secret-key-for-unit-test";
    vi.mocked(jwtVerify).mockRejectedValueOnce(new Error("JWS verification failed"));

    const { middleware } = await loadMiddleware();
    const req = createMockRequest("/decisions", "expired-or-bad-token");
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    await middleware(req as any);

    expect(mockRedirect).toHaveBeenCalled();
    const redirectUrl = mockRedirect.mock.calls[0][0] as URL;
    expect(redirectUrl.pathname).toBe("/login");
  });

  it("쿠키 없이 인증 경로 접근 → /login 리다이렉트", async () => {
    process.env.JWT_SECRET_KEY = "test-secret-key-for-unit-test";

    const { middleware } = await loadMiddleware();
    const req = createMockRequest("/dashboard");
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    await middleware(req as any);

    expect(mockRedirect).toHaveBeenCalled();
    const redirectUrl = mockRedirect.mock.calls[0][0] as URL;
    expect(redirectUrl.pathname).toBe("/login");
  });
});
