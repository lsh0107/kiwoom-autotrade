/** API 클라이언트 — httpOnly cookie 인증 기반 */

import type { ApiError } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

interface CacheEntry {
  data: unknown;
  timestamp: number;
}

class ApiClient {
  private baseUrl: string;
  private cache = new Map<string, CacheEntry>();
  /** GET 캐시 유효 시간 (ms). 기본 10초 — 모의투자 초당 5건 제한 방어 */
  private cacheTtlMs = 10_000;
  /** 요청 타임아웃 (ms). 기본 10초 */
  private timeoutMs = 10_000;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

    let res: Response;
    try {
      res = await fetch(url, {
        ...options,
        signal: options.signal ?? controller.signal,
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...options.headers,
        },
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new ApiClientError(0, "TIMEOUT", "요청 시간이 초과되었습니다 (10초)");
      }
      throw error;
    } finally {
      clearTimeout(timeoutId);
    }

    if (!res.ok) {
      const error: ApiError = await res.json().catch(() => ({
        error: "UNKNOWN",
        message: `HTTP ${res.status}`,
      }));
      throw new ApiClientError(res.status, error.error, error.message);
    }

    if (res.status === 204) return undefined as T;
    return res.json();
  }

  get<T>(path: string, opts?: { skipCache?: boolean }) {
    // GET 요청 캐시: 동일 경로 요청이 cacheTtlMs 이내면 캐시 반환
    if (!opts?.skipCache) {
      const cached = this.cache.get(path);
      if (cached && Date.now() - cached.timestamp < this.cacheTtlMs) {
        return Promise.resolve(cached.data as T);
      }
    }

    return this.request<T>(path).then((data) => {
      this.cache.set(path, { data, timestamp: Date.now() });
      return data;
    });
  }

  post<T>(path: string, body?: unknown) {
    return this.request<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  put<T>(path: string, body?: unknown) {
    return this.request<T>(path, {
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  delete<T>(path: string) {
    return this.request<T>(path, { method: "DELETE" });
  }
}

export class ApiClientError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

export const api = new ApiClient(API_BASE);
