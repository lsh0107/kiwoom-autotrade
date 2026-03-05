"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { User, LoginRequest, RegisterRequest } from "@/types/api";

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  /** 현재 로그인 상태 확인 */
  const checkAuth = useCallback(async () => {
    try {
      const data = await api.get<User>("/api/v1/auth/me");
      setUser(data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  /** 로그인 */
  const login = async (data: LoginRequest) => {
    const res = await api.post<User>("/api/v1/auth/login", data);
    setUser(res);
    router.push("/dashboard");
  };

  /** 회원가입 */
  const register = async (data: RegisterRequest) => {
    const res = await api.post<User>("/api/v1/auth/register", data);
    setUser(res);
    router.push("/dashboard");
  };

  /** 로그아웃 */
  const logout = async () => {
    try {
      await api.post("/api/v1/auth/logout");
    } catch {
      // 로그아웃 실패해도 로컬 상태는 초기화
    }
    setUser(null);
    router.push("/login");
  };

  return { user, loading, login, register, logout, checkAuth };
}
