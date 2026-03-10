/** 애플리케이션 전역 상수 */

/** API 엔드포인트 경로 */
export const API_PATHS = {
  BALANCE: "/api/v1/account/balance",
  QUOTE: (symbol: string) => `/api/v1/market/quote/${symbol}`,
  ORDERBOOK: (symbol: string) => `/api/v1/market/orderbook/${symbol}`,
  ORDERS: "/api/v1/orders",
  STRATEGIES: "/api/v1/bot/strategies",
  STRATEGY_ACTION: (id: string, action: "start" | "stop") =>
    `/api/v1/bot/strategies/${id}/${action}`,
  KILL_SWITCH: "/api/v1/bot/kill-switch",
  CREDENTIALS: "/api/v1/settings/broker",
  CREDENTIAL: (id: string) => `/api/v1/settings/broker/${id}`,
  RESULTS_LIST: "/api/v1/results/list",
  RESULT: (filename: string) => `/api/v1/results/${filename}`,
} as const;

/** TanStack Query 쿼리 키 */
export const QUERY_KEYS = {
  BALANCE: ["balance"] as const,
  QUOTE: (symbol: string) => ["quote", symbol] as const,
  ORDERBOOK: (symbol: string) => ["orderbook", symbol] as const,
  STRATEGIES: ["strategies"] as const,
  CREDENTIALS: ["credentials"] as const,
  RESULTS: ["results"] as const,
} as const;

/** 전략 상태 레이블 */
export const STRATEGY_STATUS_LABELS: Record<string, string> = {
  active: "실행 중",
  paused: "일시정지",
  stopped: "중지",
};
