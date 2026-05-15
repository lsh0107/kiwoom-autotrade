/** 백엔드 API 타입 정의 — src/api/v1/*.py, src/broker/schemas.py 기준 */

// ── 공통 ──────────────────────────────────────
export interface ApiError {
  error: string;
  message: string;
}

// ── 인증 ──────────────────────────────────────
export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  nickname: string;
  invite_code: string;
}

export interface User {
  id: string;
  email: string;
  nickname: string;
  role: "admin" | "user";
  is_active: boolean;
  created_at: string;
}

// ── 계좌 (AccountBalance — 단일 객체, holdings 포함) ──
export interface AccountBalance {
  total_eval: number;
  total_profit: number;
  total_profit_pct: number;
  /** 예수금 (정산 중에는 음수 가능) */
  deposit: number;
  /** 주문 가능 금액 (음수는 backend 에서 0으로 clamp) */
  available_cash: number;
  holdings: Holding[];
}

export interface Holding {
  symbol: string;
  name: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  eval_amount: number;
  profit: number;
  profit_pct: number;
}

// ── 종목 검색 ──────────────────────────────────
export interface StockSearchResult {
  symbol: string;
  name: string;
  market: string;
  sector: string;
}

// ── Top 종목 ──────────────────────────────────
export interface TopStockItem {
  symbol: string;
  name: string;
  rank: number;
  close: number;
  vol_ratio: number;
  sector: string;
}

// ── 시세 ──────────────────────────────────────
export interface Quote {
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
  volume: number;
  high: number;
  low: number;
  open: number;
  prev_close: number;
}

export interface OrderbookEntry {
  price: number;
  quantity: number;
}

export interface Orderbook {
  symbol: string;
  asks: OrderbookEntry[];
  bids: OrderbookEntry[];
}

// ── 주문 ──────────────────────────────────────
export type OrderSide = "BUY" | "SELL";

export interface CreateOrderRequest {
  symbol: string;
  symbol_name?: string;
  side: OrderSide;
  price: number;
  quantity: number;
  strategy_id?: string;
  reason?: string;
}

export interface Order {
  id: string;
  symbol: string;
  symbol_name: string;
  side: OrderSide;
  price: number;
  quantity: number;
  filled_quantity: number;
  filled_price: number;
  status: string;
  broker_order_no: string | null;
  is_mock: boolean;
  reason: string | null;
  error_message: string | null;
  created_at: string;
  submitted_at: string | null;
}

// ── 자동매매 ──────────────────────────────────
export interface Strategy {
  id: string;
  name: string;
  description: string;
  symbols: string[];
  status: "active" | "stopped" | "paused";
  is_auto_trading: boolean;
  max_investment: number;
  max_loss_pct: number;
  max_position_pct: number;
  kill_switch_active: boolean;
  created_at: string;
}

// ── 매매결과 ──────────────────────────────────
export interface ResultFile {
  filename: string;
  modified_at: string;
}

export interface BacktestMetrics {
  total_trades: number;
  win_count: number;
  loss_count: number;
  win_rate: number;
  avg_pnl: number;
  avg_win: number;
  avg_loss: number;
  max_drawdown: number;
  sharpe_ratio: number;
  monthly_avg_return: number;
  profit_factor: number;
}

export interface BacktestResultItem {
  symbol: string;
  error?: string;
  skipped?: boolean;
  metrics?: BacktestMetrics;
  params?: Record<string, number>;
  trades?: Array<Record<string, unknown>>;
  data_info?: {
    daily_bars: number;
    minute_bars: number;
    trading_dates: string[];
  };
}

export interface BacktestResult {
  run_at: string;
  params: Record<string, number>;
  trading_dates: string[];
  symbols: string[];
  results: BacktestResultItem[];
}

// ── 설정 ──────────────────────────────────────
export interface BrokerCredential {
  id: string;
  broker_name: string;
  app_key_masked: string;
  app_secret_masked: string;
  account_no: string;
  is_mock: boolean;
  is_active: boolean;
  created_at: string;
}

export interface BrokerCredentialCreate {
  app_key: string;
  app_secret: string;
  account_no: string;
  is_mock?: boolean;
}

// ── 전략 설정 ──────────────────────────────────
export interface StrategyConfigItem {
  id: string;
  key: string;
  value: unknown;
  description: string;
  updated_by: string;
  updated_at: string;
}

export interface StrategyConfigUpdateRequest {
  items: Array<{
    key: string;
    value: unknown;
    description?: string;
    updated_by?: string;
  }>;
}

export interface StrategyConfigSuggestion {
  id: string;
  config_key: string;
  current_value: unknown;
  suggested_value: unknown;
  reason: string;
  source: string;
  status: string;
  created_at: string;
}

export interface SuggestionReviewRequest {
  reviewed_by: string;
}

// ── LLM 결정 ──────────────────────────────────────
export interface LLMDecision {
  id: string;
  date: string;
  decision_type: string;
  context_source: string;
  content: Record<string, unknown>;
  confidence: number | null;
  status: string;
  applied_at: string | null;
  evaluation: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

// ── Kill Switch ─────────────────────────────────
export interface KillSwitchStatus {
  status: "normal" | "soft_stopped" | "hard_stopped";
  user_id: string;
}

export interface KillSwitchResponse {
  status: string;
  message: string;
}

// ── 차트 ──────────────────────────────────────
export interface OHLCVData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ── 트레이딩 프로세스 ────────────────────────────
export interface TradingStatus {
  status: "idle" | "starting" | "running" | "stopping" | "crashed" | "waiting_next";
  pid: number | null;
  started_at: string | null;
  uptime_seconds: number;
  stdout_tail: string[];
}

export interface TradingLogs {
  stdout: string[];
  stderr: string[];
}

export interface TradingActionResponse {
  status: string;
  message: string;
}

// ── 전략 현황 (GET /api/v1/strategy/current) ──────
export interface ExpectedOrdersPreview {
  sells: string[];
  buys: string[];
  target_symbols: string[];
  cash_per_position: number;
  total_notional: number;
}

export interface CrossMomentumDetail {
  rebalance_freq: string;
  n_positions: number;
  top_pct: number | null;
  use_vol_filter: boolean;
  use_trend_filter: boolean;
  min_order_amount: number;
  max_order_amount: number;
  cash_buffer_pct: number;
  universe_size: number;
  next_rebalance_kst: string | null;
  formula: string;
  target_preview: string[];
  expected_orders: ExpectedOrdersPreview | null;
}

export interface StrategyCurrentResponse {
  active_strategy: "none" | "cross_momentum" | "multi_regime" | "short_swing";
  cross_momentum: CrossMomentumDetail | null;
  short_swing: ShortSwingDetail | null;
  multi_regime: unknown | null;
}

// ── Short Swing ─────────────────────────────────
export interface ShortSwingDetail {
  enabled: boolean;
  entry_window: string;
  exit_window: string;
  next_candidate_screen_at: string;
  max_positions: number;
  max_daily_new_positions: number;
  stop_loss: number;
  take_profit: number;
  trailing_armed_pct: number;
  trailing_stop_pct: number;
  max_holding_days: number;
  min_order_amount: number;
  cash_buffer_pct: number;
  universe_size: number;
  open_positions: number;
  today_new_positions: number;
}

export interface ShortSwingStatus {
  entry_window: string;
  exit_window: string;
  open_positions: number;
  max_positions: number;
  today_new_positions: number;
  kill_switch_active: boolean;
}

export interface ShortSwingCandidate {
  id: string;
  trade_date: string;
  symbol: string;
  name: string;
  close: number;
  ma20: number;
  ma60: number;
  high_60d: number;
  drawdown_from_high: number;
  trading_value: number;
  avg_trading_value_20d: number;
  return_5d: number;
  score: number;
  reason_json: Record<string, unknown>;
}

export interface ShortSwingCandidatesResponse {
  date: string;
  count: number;
  candidates: ShortSwingCandidate[];
}

export interface ShortSwingPosition {
  id: string;
  symbol: string;
  name: string;
  entry_date: string;
  entry_price: number;
  quantity: number;
  highest_price_since_entry: number;
  stop_price: number;
  take_profit_price: number;
  trailing_armed: boolean;
  max_holding_until: string;
  status: string;
  exit_reason: string | null;
}

export interface ShortSwingPositionsResponse {
  count: number;
  positions: ShortSwingPosition[];
}

// ── 매매 이력 ────────────────────────────────────
export interface TradeHistoryItem {
  id: string;
  symbol: string;
  side: string;
  price: number;
  quantity: number;
  order_amount: number;
  filled_price: number;
  filled_quantity: number;
  filled_amount: number;
  event_type: string;
  message: string;
  is_mock: boolean;
  created_at: string;
}
