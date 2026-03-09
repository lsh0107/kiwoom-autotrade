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
