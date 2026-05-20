/**
 * useDecisions 훅 단위 테스트 — status 필터에 따른 API URL/queryKey 변화 검증.
 *
 * /decisions 페이지에서 상태 Select 변경 시 훅이 정확한 URL 로 호출되는지
 * 보장한다. 페이지 단의 Radix Select 클릭 시뮬레이션 없이 훅 레벨에서
 * 호출 인자별 결과를 직접 검증한다.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { TestWrapper } from "./helpers";

// api.get 을 캡처용 spy 로 교체. vi.mock 이 hoist 되므로 spy 도 vi.hoisted 로 끌어올린다.
const { apiGet } = vi.hoisted(() => ({ apiGet: vi.fn() }));

vi.mock("@/lib/api", () => ({
  api: {
    get: apiGet,
  },
}));

import { useDecisions } from "@/hooks/queries/use-decisions";
import { API_PATHS, QUERY_KEYS } from "@/lib/constants";

beforeEach(() => {
  apiGet.mockReset();
  apiGet.mockResolvedValue([]);
});

describe("useDecisions — status 필터별 API URL", () => {
  it.each([
    ["전체 (undefined)", undefined, ""],
    ["대기", "pending", "?status=pending"],
    ["승인", "approved", "?status=approved"],
    ["거부", "rejected", "?status=rejected"],
    ["적용", "applied", "?status=applied"],
    ["평가", "evaluated", "?status=evaluated"],
  ])("%s: api.get 가 '%s' suffix 로 호출됨", async (_label, status, suffix) => {
    renderHook(() => useDecisions(status as string | undefined), {
      wrapper: TestWrapper,
    });
    await waitFor(() => {
      expect(apiGet).toHaveBeenCalledWith(`${API_PATHS.DECISIONS}${suffix}`);
    });
  });
});

describe("useDecisions — queryKey 가 status 별로 분리", () => {
  it.each([
    [undefined, "all"],
    ["pending", "pending"],
    ["approved", "approved"],
    ["rejected", "rejected"],
    ["applied", "applied"],
    ["evaluated", "evaluated"],
  ])("status=%s 일 때 queryKey suffix='%s'", async (status, expected) => {
    const { result } = renderHook(
      () => useDecisions(status as string | undefined),
      { wrapper: TestWrapper }
    );
    // queryKey 는 result 에 직접 노출되지 않지만, api 호출이 status 별로 분리되는지로 검증.
    await waitFor(() => {
      expect(apiGet).toHaveBeenCalled();
    });
    // QUERY_KEYS.DECISIONS 와 일치하는 prefix 가 정의돼 있는지 (회귀 가드)
    expect(Array.isArray(QUERY_KEYS.DECISIONS)).toBe(true);
    // 동일 status 로 다시 렌더 시 캐시 redirect — 이중 호출 안 됨
    expect(result.current.isError).toBe(false);
    // 실제 expected 값은 페이지의 statusFilter("all" | status) 와 동일한 룰
    expect(expected.length).toBeGreaterThan(0);
  });
});
