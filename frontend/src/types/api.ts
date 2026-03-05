/** 백엔드 API 타입 정의 */

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

export interface AuthResponse {
  message: string;
  user: User;
}

export interface User {
  id: string;
  email: string;
  role: "admin" | "user";
  is_active: boolean;
  created_at: string;
}

// ── 계좌 ──────────────────────────────────────
export interface AccountBalance {
  total_evaluation: number;
  total_deposit: number;
  total_profit_loss: number;
  profit_loss_rate: number;
}

export interface Holding {
  symbol: string;
  name: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  profit_loss: number;
  profit_loss_rate: number;
}

// ── 시세 ──────────────────────────────────────
export interface Quote {
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_rate: number;
  volume: number;
  high: number;
  low: number;
  open: number;
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
export type OrderSide = "buy" | "sell";
export type OrderType = "limit" | "market";
export type OrderStatus =
  | "created"
  | "submitted"
  | "accepted"
  | "partial_filled"
  | "filled"
  | "cancel_submitted"
  | "cancelled"
  | "rejected"
  | "failed";

export interface OrderRequest {
  symbol: string;
  side: OrderSide;
  order_type: OrderType;
  quantity: number;
  price?: number;
}

export interface Order {
  id: string;
  symbol: string;
  side: OrderSide;
  order_type: OrderType;
  quantity: number;
  price: number;
  filled_quantity: number;
  status: OrderStatus;
  created_at: string;
  updated_at: string;
}

// ── 설정 ──────────────────────────────────────
export interface BrokerCredential {
  id: string;
  label: string;
  is_mock: boolean;
  app_key_masked: string;
  account_no_masked: string;
  created_at: string;
}
