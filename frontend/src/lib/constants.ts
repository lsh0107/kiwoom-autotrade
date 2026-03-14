/** 애플리케이션 전역 상수 */

/** API 엔드포인트 경로 */
export const API_PATHS = {
  BALANCE: "/api/v1/account/balance",
  QUOTE: (symbol: string) => `/api/v1/market/quote/${symbol}`,
  ORDERBOOK: (symbol: string) => `/api/v1/market/orderbook/${symbol}`,
  ORDERS: "/api/v1/orders",
  STRATEGIES: "/api/v1/bot/strategies",
  STRATEGY: (id: string) => `/api/v1/bot/strategies/${id}`,
  STRATEGY_ACTION: (id: string, action: "start" | "stop") =>
    `/api/v1/bot/strategies/${id}/${action}`,
  KILL_SWITCH: "/api/v1/bot/kill-switch",
  CREDENTIALS: "/api/v1/settings/broker",
  CREDENTIAL: (id: string) => `/api/v1/settings/broker/${id}`,
  RESULTS_LIST: "/api/v1/results/list",
  RESULT: (filename: string) => `/api/v1/results/${filename}`,
  // 전략 설정
  STRATEGY_CONFIG: "/api/v1/settings/strategy",
  STRATEGY_SUGGESTIONS: "/api/v1/settings/strategy/suggestions",
  STRATEGY_SUGGESTION_APPROVE: (id: string) =>
    `/api/v1/settings/strategy/suggestions/${id}/approve`,
  STRATEGY_SUGGESTION_REJECT: (id: string) =>
    `/api/v1/settings/strategy/suggestions/${id}/reject`,
  // Kill Switch (새 API)
  TRADING_SOFT_STOP: "/api/v1/trading/soft-stop",
  TRADING_HARD_STOP: "/api/v1/trading/hard-stop",
  TRADING_RESUME: "/api/v1/trading/resume",
  KILL_SWITCH_STATUS: "/api/v1/trading/kill-switch-status",
  // 차트
  DAILY_CHART: (symbol: string) => `/api/v1/market/chart/${symbol}/daily`,
  // Bot 트레이딩
  BOT_TRADING_START: "/api/v1/bot/trading/start",
  BOT_TRADING_STOP: "/api/v1/bot/trading/stop",
  BOT_TRADING_STATUS: "/api/v1/bot/trading/status",
  BOT_TRADING_LOGS: "/api/v1/bot/trading/logs",
  BOT_TRADE_HISTORY: "/api/v1/bot/trade-history",
} as const;

/** TanStack Query 쿼리 키 */
export const QUERY_KEYS = {
  BALANCE: ["balance"] as const,
  QUOTE: (symbol: string) => ["quote", symbol] as const,
  ORDERBOOK: (symbol: string) => ["orderbook", symbol] as const,
  STRATEGIES: ["strategies"] as const,
  CREDENTIALS: ["credentials"] as const,
  RESULTS: ["results"] as const,
  STRATEGY_CONFIG: ["strategy-config"] as const,
  STRATEGY_SUGGESTIONS: ["strategy-suggestions"] as const,
  KILL_SWITCH_STATUS: ["kill-switch-status"] as const,
  DAILY_CHART: (symbol: string) => ["daily-chart", symbol] as const,
  TRADING_STATUS: ["trading-status"] as const,
  TRADING_LOGS: ["trading-logs"] as const,
  TRADE_HISTORY: ["trade-history"] as const,
} as const;

/** 전략 상태 레이블 */
export const STRATEGY_STATUS_LABELS: Record<string, string> = {
  active: "실행 중",
  paused: "일시정지",
  stopped: "중지",
};
