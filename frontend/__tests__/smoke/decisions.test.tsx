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
import { fireEvent, render } from "@testing-library/react";
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

// ── 카드 UX: 타입별 요약 + 원본 JSON 토글 ───────

describe("/decisions 카드 UX — 타입별 요약 + 원본 토글", () => {
  it("symbol_bias (ai_hedge): 핵심 필드들이 요약으로 렌더링됨", () => {
    mockUseDecisions.mockReturnValue(
      readyQuery([
        makeDecision({
          id: "ai1",
          decision_type: "symbol_bias",
          context_source: "ai_hedge",
          status: "pending",
          content: {
            symbol: "005930",
            bias: "block_buy",
            source: "kr-ai-hedge",
            original_action: "hold",
            risk_flags: ["POSITION_LIMIT_REACHED"],
            reason: "종목 비중 한도 초과",
            suggested_quantity: 0,
            suggested_notional_krw: 0,
            evidence: {
              latest_close: 279500,
              latest_date: "2026-05-19",
              momentum_20d: 0.293981,
              momentum_60d: 0.447437,
              drawdown_60d: -0.066778,
              volume_ratio_20d: 0.834053,
              holding_qty: 617,
              current_position_value: 172451500,
              position_limit_krw: 46351491,
            },
          },
        }),
      ])
    );
    const { container } = render(
      <TestWrapper>
        <DecisionsPage />
      </TestWrapper>
    );
    const text = container.textContent ?? "";
    // 라벨
    expect(text).toContain("종목");
    expect(text).toContain("판단");
    expect(text).toContain("사유");
    expect(text).toContain("출처");
    expect(text).toContain("리스크");
    expect(text).toContain("제안 수량/금액");
    expect(text).toContain("현재 보유");
    expect(text).toContain("비중 한도");
    expect(text).toContain("지표");
    // 값/라벨 매핑
    expect(text).toContain("005930");
    expect(text).toContain("매수 차단"); // block_buy → 한글 라벨
    expect(text).toContain("종목 비중 한도 초과");
    expect(text).toContain("kr-ai-hedge");
    expect(text).toContain("원시 액션 hold");
    expect(text).toContain("비중 한도 초과"); // risk flag label
    expect(text).toContain("617"); // holding_qty
    expect(text).toContain("종가"); // latest_close 표시
    expect(text).toContain("mom20"); // 모멘텀 표시
    expect(text).toContain("AI Hedge"); // context_source label
  });

  it("universe_adjust: 제외 종목 + 사유 표시", () => {
    mockUseDecisions.mockReturnValue(
      readyQuery([
        makeDecision({
          id: "u1",
          decision_type: "universe_adjust",
          context_source: "overnight",
          content: {
            exclude: ["005930", "000660"],
            reason: "변동성 급증",
          },
        }),
      ])
    );
    const { container } = render(
      <TestWrapper>
        <DecisionsPage />
      </TestWrapper>
    );
    const text = container.textContent ?? "";
    expect(text).toContain("제외 종목");
    expect(text).toContain("005930");
    expect(text).toContain("000660");
    expect(text).toContain("변동성 급증");
  });

  it("strategy_param_hint: 전략 + 파라미터 key/value + 사유 표시", () => {
    mockUseDecisions.mockReturnValue(
      readyQuery([
        makeDecision({
          id: "sp1",
          decision_type: "strategy_param_hint",
          context_source: "overnight",
          content: {
            strategy: "momentum",
            params: { volume_ratio: 0.9, atr_stop_mult: 1.5 },
            reason: "변동성 완화",
          },
        }),
      ])
    );
    const { container } = render(
      <TestWrapper>
        <DecisionsPage />
      </TestWrapper>
    );
    const text = container.textContent ?? "";
    expect(text).toContain("전략");
    expect(text).toContain("momentum");
    expect(text).toContain("파라미터");
    expect(text).toContain("volume_ratio");
    expect(text).toContain("0.9");
    expect(text).toContain("atr_stop_mult");
    expect(text).toContain("1.5");
    expect(text).toContain("변동성 완화");
  });

  it("원본 JSON 토글: 기본 닫힘 → 클릭 시 펼침", () => {
    mockUseDecisions.mockReturnValue(
      readyQuery([
        makeDecision({
          id: "t1",
          decision_type: "symbol_bias",
          content: { symbol: "005930", bias: "block_buy", __raw_marker__: "RAW_VAL" },
        }),
      ])
    );
    const { container, getByText, getByRole, queryByTestId } = render(
      <TestWrapper>
        <DecisionsPage />
      </TestWrapper>
    );
    // 초기: 토글 버튼 노출, raw json pre 미렌더
    expect(getByText(/원본 보기/)).toBeTruthy();
    expect(queryByTestId("decision-raw-json")).toBeNull();
    // 요약은 보이지만 마커는 raw 영역에만 있으므로 미노출
    expect(container.textContent ?? "").not.toContain("RAW_VAL");

    // 토글 클릭
    const btn = getByRole("button", { name: /원본 보기/ });
    fireEvent.click(btn);

    const raw = queryByTestId("decision-raw-json");
    expect(raw).not.toBeNull();
    expect(raw?.textContent ?? "").toContain("RAW_VAL");
    expect(getByText(/원본 숨기기/)).toBeTruthy();
  });

  it("기본 화면에 raw content 의 모든 key 가 그대로 나열되지 않음 (regression)", () => {
    // 이전 구현은 Object.entries(content).map 으로 모든 키를 노출했음.
    // 새 구현은 type 별 요약만 보여주므로 일반 키(__qa_marker__)는 표시 X.
    mockUseDecisions.mockReturnValue(
      readyQuery([
        makeDecision({
          id: "r1",
          decision_type: "symbol_bias",
          content: {
            symbol: "005930",
            bias: "block_buy",
            __qa_marker__: "SHOULD_NOT_SHOW_BY_DEFAULT",
          },
        }),
      ])
    );
    const { container } = render(
      <TestWrapper>
        <DecisionsPage />
      </TestWrapper>
    );
    const text = container.textContent ?? "";
    expect(text).not.toContain("__qa_marker__");
    expect(text).not.toContain("SHOULD_NOT_SHOW_BY_DEFAULT");
  });
});
