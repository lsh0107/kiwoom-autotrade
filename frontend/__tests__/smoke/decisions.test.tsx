/**
 * /decisions 페이지 + useDecisions 훅 테스트.
 *
 * 검증 포커스:
 *  - status 필터별 useDecisions 호출 인자(쿼리/URL)가 정확한가
 *  - status 별 배지/버튼 표시가 명확한가 (사람이 봐도 구분 가능)
 *  - 페이지 스모크 (빈 데이터 + 로딩 모두 크래시 없음)
 *
 * Radix Select 의 트리거 클릭 시뮬레이션은 jsdom + portal 환경에서 불안정해
 * useDecisions 훅 자체의 URL 빌딩을 독립적으로 검증한다. 페이지 측은
 * useDecisions 를 mock 해 초기 호출 인자만 확인한다.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import { TestWrapper } from "./helpers";
import type { LLMDecision } from "@/types/api";

// ── 공통 Mock (페이지 의존성) ──────────────────

vi.mock("next/navigation", () => ({
  usePathname: () => "/decisions",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
    back: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
  Toaster: () => null,
}));

const emptyMutation = {
  mutate: vi.fn(),
  mutateAsync: vi.fn(),
  isPending: false,
  isError: false,
};

vi.mock("@/hooks/mutations/use-review-decision", () => ({
  useReviewDecision: () => emptyMutation,
}));

// ── useDecisions Mock (호출 인자 캡처 + 동적 응답) ──

const mockUseDecisions = vi.fn();

vi.mock("@/hooks/queries/use-decisions", () => ({
  useDecisions: (status?: string) => mockUseDecisions(status),
}));

import DecisionsPage from "@/app/(authenticated)/decisions/page";

// ── 헬퍼: 결정 mock 생성 ──────────────────────

function makeDecision(overrides: Partial<LLMDecision>): LLMDecision {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    date: "2026-05-20",
    decision_type: "symbol_bias",
    context_source: "overnight",
    content: { symbol: "005930", bias: "block_buy" },
    confidence: 0.8,
    status: "pending",
    raw_response: "{}",
    applied_at: null,
    evaluation: null,
    created_at: "2026-05-20T08:00:00Z",
    updated_at: "2026-05-20T08:00:00Z",
    ...overrides,
  } as LLMDecision;
}

function readyQuery(decisions: LLMDecision[]) {
  return {
    data: decisions,
    isLoading: false,
    error: null,
    isError: false,
  };
}

const loadingQuery = {
  data: undefined,
  isLoading: true,
  error: null,
  isError: false,
};

beforeEach(() => {
  mockUseDecisions.mockReset();
});

// ── 페이지: 스모크 + 초기 useDecisions 호출 인자 ────

describe("/decisions 페이지 스모크 + 초기 필터", () => {
  it("로딩 상태에서 크래시 없이 렌더링", () => {
    mockUseDecisions.mockReturnValue(loadingQuery);
    const { container } = render(
      <TestWrapper>
        <DecisionsPage />
      </TestWrapper>
    );
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it("초기 마운트 시 useDecisions(undefined) — '전체' 필터", () => {
    mockUseDecisions.mockReturnValue(readyQuery([]));
    render(
      <TestWrapper>
        <DecisionsPage />
      </TestWrapper>
    );
    expect(mockUseDecisions).toHaveBeenCalled();
    expect(mockUseDecisions).toHaveBeenCalledWith(undefined);
  });

  it("결정 없으면 빈 상태 메시지 표시", () => {
    mockUseDecisions.mockReturnValue(readyQuery([]));
    const { container } = render(
      <TestWrapper>
        <DecisionsPage />
      </TestWrapper>
    );
    expect(container.textContent).toContain("결정이 없습니다");
  });
});

// ── 상태별 배지/액션 표시 검증 ─────────────────

describe("/decisions 상태별 표시 — 사람이 봐도 명확한지", () => {
  it("pending: '검토 필요' 배지 + 승인/거부 버튼 표시", () => {
    mockUseDecisions.mockReturnValue(
      readyQuery([makeDecision({ id: "p1", status: "pending" })])
    );
    const { container } = render(
      <TestWrapper>
        <DecisionsPage />
      </TestWrapper>
    );
    expect(container.textContent).toContain("검토 필요");
    expect(container.textContent).toContain("승인");
    expect(container.textContent).toContain("거부");
    // 대기 헤더 카운트 배지
    expect(container.textContent).toContain("1건 대기");
  });

  it("approved: '승인됨 — 다음 실행 시 후보' + 승인/거부 버튼 없음", () => {
    mockUseDecisions.mockReturnValue(
      readyQuery([makeDecision({ id: "a1", status: "approved" })])
    );
    const { container } = render(
      <TestWrapper>
        <DecisionsPage />
      </TestWrapper>
    );
    expect(container.textContent).toContain("승인됨");
    expect(container.textContent).toContain("다음 실행 시 후보");
    // 액션 버튼 없음 (pending만 노출)
    const buttons = container.querySelectorAll("button");
    const labels = Array.from(buttons).map((b) => b.textContent ?? "");
    expect(labels.some((t) => t === "승인")).toBe(false);
    expect(labels.some((t) => t === "거부")).toBe(false);
  });

  it("applied: '적용 완료' + 적용 timestamp 표시", () => {
    mockUseDecisions.mockReturnValue(
      readyQuery([
        makeDecision({
          id: "ap1",
          status: "applied",
          applied_at: "2026-05-20T08:30:00Z",
        }),
      ])
    );
    const { container } = render(
      <TestWrapper>
        <DecisionsPage />
      </TestWrapper>
    );
    expect(container.textContent).toContain("적용 완료");
    expect(container.textContent).toContain("적용:");
  });

  it("rejected: '거부됨' + 액션 버튼 없음", () => {
    mockUseDecisions.mockReturnValue(
      readyQuery([makeDecision({ id: "r1", status: "rejected" })])
    );
    const { container } = render(
      <TestWrapper>
        <DecisionsPage />
      </TestWrapper>
    );
    expect(container.textContent).toContain("거부됨");
    const buttons = container.querySelectorAll("button");
    const labels = Array.from(buttons).map((b) => b.textContent ?? "");
    expect(labels.some((t) => t === "승인")).toBe(false);
  });

  it("approved 에는 적용 timestamp 미표시 (applied_at 무관)", () => {
    // approved 인데 applied_at 이 있어도 '적용:' 텍스트는 띄우지 않는다 (status 가 진실)
    mockUseDecisions.mockReturnValue(
      readyQuery([
        makeDecision({
          id: "a2",
          status: "approved",
          applied_at: "2026-05-20T08:30:00Z",
        }),
      ])
    );
    const { container } = render(
      <TestWrapper>
        <DecisionsPage />
      </TestWrapper>
    );
    expect(container.textContent).not.toContain("적용:");
  });
});

// useDecisions 훅의 status → URL 매핑은 별도 단위 테스트
// (__tests__/smoke/use-decisions.hook.test.ts) 에서 검증한다.
