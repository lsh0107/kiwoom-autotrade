"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { User, LoginRequest, RegisterRequest } from "@/types/api";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export { AuthContext };

export function useAuthProvider() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const checkAuth = useCallback(async () => {
    try {
      const data = await api.get<User>("/api/v1/auth/me", { skipCache: true });
      setUser(data);
    } catch {
      // access_token 만료 시 refresh 시도
      try {
        const refreshed = await api.post<User>("/api/v1/auth/refresh");
        setUser(refreshed);
      } catch {
        // 둘 다 실패 → 쿠키 정리 (무한 리다이렉트 방지)
        try {
          await api.post("/api/v1/auth/logout");
        } catch {
          // 로그아웃 실패해도 무시
        }
        setUser(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = async (data: LoginRequest) => {
    const res = await api.post<User>("/api/v1/auth/login", data);
    setUser(res);
    router.push("/dashboard");
  };

  const register = async (data: RegisterRequest) => {
    const res = await api.post<User>("/api/v1/auth/register", data);
    setUser(res);
    router.push("/dashboard");
  };

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

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
