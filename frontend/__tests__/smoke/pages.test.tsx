/**
 * 전 페이지 스모크 테스트 — null/undefined 데이터에서 크래시 없는지 검증.
 *
 * 각 페이지가 로딩 상태 + 빈 데이터에서도 에러 없이 렌더링되는지 확인한다.
 * API 훅은 모두 모킹하여 네트워크 요청 없이 실행된다.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import { TestWrapper } from "./helpers";
import type { StrategyCurrentResponse } from "@/types/api";

// ── 공통 Mock ──────────────────────────────────

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
    back: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

// ── Query Hooks Mock (로딩 상태) ──────────────

const loadingQuery = { data: undefined, isLoading: true, error: null, isError: false };
const emptyQuery = { data: [], isLoading: false, error: null, isError: false };
const emptyMutation = { mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false, isError: false };

vi.mock("@/hooks/queries/use-balance", () => ({
  useBalance: () => loadingQuery,
}));

vi.mock("@/hooks/queries/use-strategies", () => ({
  useStrategies: () => emptyQuery,
}));

vi.mock("@/hooks/queries/use-strategy-config", () => ({
  useStrategyConfig: () => emptyQuery,
}));

vi.mock("@/hooks/queries/use-trade-history", () => ({
  useTradeHistory: () => emptyQuery,
}));

vi.mock("@/hooks/queries/use-results", () => ({
  useResults: () => loadingQuery,
}));

vi.mock("@/hooks/queries/use-quote", () => ({
  useQuote: () => loadingQuery,
}));

vi.mock("@/hooks/queries/use-orderbook", () => ({
  useOrderbook: () => loadingQuery,
}));

vi.mock("@/hooks/queries/use-credentials", () => ({
  useCredentials: () => loadingQuery,
}));

// ── useStrategyCurrent Mock (동적 교체 가능) ────

const mockStrategyCurrent = vi.fn();

vi.mock("@/hooks/queries/use-strategy-current", () => ({
  useStrategyCurrent: () => mockStrategyCurrent(),
}));

// ── Mutation Hooks Mock ──────────────────────

vi.mock("@/hooks/mutations/use-toggle-strategy", () => ({
  useToggleStrategy: () => emptyMutation,
}));

vi.mock("@/hooks/mutations/use-kill-switch", () => ({
  useKillSwitch: () => emptyMutation,
}));

vi.mock("@/hooks/mutations/use-place-order", () => ({
  usePlaceOrder: () => emptyMutation,
}));

vi.mock("@/hooks/mutations/use-save-credential", () => ({
  useSaveCredential: () => emptyMutation,
}));

vi.mock("@/hooks/mutations/use-delete-credential", () => ({
  useDeleteCredential: () => emptyMutation,
}));

// ── Realtime Hook Mock ────────────────────────

vi.mock("@/hooks/use-realtime", () => ({
  useRealtime: () => ({
    ticks: new Map(),
    isConnected: false,
  }),
}));

// ── Auth Hook Mock ──────────────────────────

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    user: { id: 1, username: "test", is_admin: false },
    isLoading: false,
    logout: vi.fn(),
  }),
}));

// ── sonner mock ──────────────────────────────

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
  Toaster: () => null,
}));

// ── 페이지 import ────────────────────────────

import DashboardPage from "@/app/(authenticated)/dashboard/page";
import BotPage from "@/app/(authenticated)/bot/page";
import ResultsPage from "@/app/(authenticated)/results/page";
import StrategyPage from "@/app/(authenticated)/strategy/page";
import TradePage from "@/app/(authenticated)/trade/page";
import SettingsPage from "@/app/(authenticated)/settings/page";

// ── 헬퍼: useStrategyCurrent 응답 생성 ─────────

function makeStrategyCurrentQuery(data: StrategyCurrentResponse) {
  return { data, isLoading: false, error: null, isError: false };
}

const crossMomentumResponse: StrategyCurrentResponse = {
  active_strategy: "cross_momentum",
  cross_momentum: {
    rebalance_freq: "monthly",
    n_positions: 5,
    top_pct: 0.20,
    use_vol_filter: false,
    use_trend_filter: false,
    min_order_amount: 500000,
    max_order_amount: 2000000,
    cash_buffer_pct: 0.10,
    universe_size: 196,
    next_rebalance_kst: "2026-05-29T14:55:00+09:00",
    formula: "12-1mo momentum",
    target_preview: [],
    expected_orders: null,
  },
  multi_regime: null,
};

const noneResponse: StrategyCurrentResponse = {
  active_strategy: "none",
  cross_momentum: null,
  multi_regime: null,
};

const multiRegimeResponse: StrategyCurrentResponse = {
  active_strategy: "multi_regime",
  cross_momentum: null,
  multi_regime: {},
};

// ── 테스트 ───────────────────────────────────

beforeEach(() => {
  mockStrategyCurrent.mockReturnValue(
    makeStrategyCurrentQuery(crossMomentumResponse),
  );
});

describe("페이지 스모크 테스트 — 로딩/빈 데이터에서 크래시 없는지 검증", () => {
  it("Dashboard: 로딩 상태 렌더링", () => {
    const { container } = render(
      <TestWrapper>
        <DashboardPage />
      </TestWrapper>
    );
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it("Bot (자동매매): 로딩 상태 렌더링", () => {
    const { container } = render(
      <TestWrapper>
        <BotPage />
      </TestWrapper>
    );
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it("Results (매매 결과): 로딩 상태 렌더링", () => {
    const { container } = render(
      <TestWrapper>
        <ResultsPage />
      </TestWrapper>
    );
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it("Strategy (전략 현황): 렌더링", () => {
    const { container } = render(
      <TestWrapper>
        <StrategyPage />
      </TestWrapper>
    );
    expect(container.innerHTML.length).toBeGreaterThan(0);
    expect(container.textContent).toContain("전략 현황");
  });

  it("Trade (트레이딩): 로딩 상태 렌더링", () => {
    const { container } = render(
      <TestWrapper>
        <TradePage />
      </TestWrapper>
    );
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it("Settings (설정): 로딩 상태 렌더링", () => {
    const { container } = render(
      <TestWrapper>
        <SettingsPage />
      </TestWrapper>
    );
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });
});

describe("Strategy 페이지: cross_momentum 분기", () => {
  it("cross_momentum 대시보드 렌더 + universe_size 표시", () => {
    mockStrategyCurrent.mockReturnValue(
      makeStrategyCurrentQuery(crossMomentumResponse),
    );
    const { container } = render(
      <TestWrapper>
        <StrategyPage />
      </TestWrapper>
    );
    expect(container.textContent).toContain("196종목");
    expect(container.textContent).toContain("크로스 모멘텀");
  });

  it("cross_momentum n_positions 표시", () => {
    mockStrategyCurrent.mockReturnValue(
      makeStrategyCurrentQuery(crossMomentumResponse),
    );
    const { container } = render(
      <TestWrapper>
        <StrategyPage />
      </TestWrapper>
    );
    expect(container.textContent).toContain("5");
  });

  it("거래 이력 빈 상태 표시", () => {
    const { container } = render(
      <TestWrapper>
        <StrategyPage />
      </TestWrapper>
    );
    expect(container.textContent).toContain("오늘 매매 이력이 없습니다");
  });
});

describe("Strategy 페이지: none 분기", () => {
  it("전략 비활성 placeholder 표시", () => {
    mockStrategyCurrent.mockReturnValue(
      makeStrategyCurrentQuery(noneResponse),
    );
    const { container } = render(
      <TestWrapper>
        <StrategyPage />
      </TestWrapper>
    );
    expect(container.textContent).toContain("전략 비활성 상태");
  });
});

describe("Strategy 페이지: multi_regime 분기", () => {
  it("multi_regime 시 기존 ParamSummary 표시 유지", () => {
    mockStrategyCurrent.mockReturnValue(
      makeStrategyCurrentQuery(multiRegimeResponse),
    );
    const { container } = render(
      <TestWrapper>
        <StrategyPage />
      </TestWrapper>
    );
    expect(container.textContent).toContain("모멘텀 돌파");
    expect(container.textContent).toContain("52주고 기준");
    expect(container.textContent).toContain("75%");
  });
});
