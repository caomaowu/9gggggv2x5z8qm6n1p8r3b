// ── 枚举 ──
export type TaskStatus = 'STOPPED' | 'RUNNING';
export type BetMode = 'fixed' | 'percent';
export type Direction = 'long' | 'short' | 'none';
export type RoundResult = 'WIN' | 'LOSE' | 'SKIP';
export type RoundStatus = 'BET_PLACED' | 'SETTLED';
export type WsMessageType =
  | 'task_started'
  | 'task_stopped'
  | 'task_deleted'
  | 'round_completed'
  | 'stats_updated';

// ── 请求 ──
export interface TaskCreateRequest {
  asset: string;
  timeframe: string;
  bet_mode?: BetMode;
  bet_amount?: number;
  bet_percent?: number | null;
  fee_rate?: number;
  initial_capital?: number;
}

// ── 响应 ──
export interface TaskResponse {
  id: string;
  asset: string;
  timeframe: string;
  status: TaskStatus;
  bet_amount: number;
  bet_mode: BetMode;
  bet_percent: number | null;
  fee_rate: number;
  initial_capital: number;
  current_capital: number;
  total_rounds: number;
  wins: number;
  losses: number;
  skips: number;
  best_win_streak: number;
  worst_lose_streak: number;
  current_streak: string | null;
  last_kline_ts: string | null;
  created_at: string;
  updated_at: string;
}

export interface RoundResponse {
  id: string;
  task_id: string;
  round_seq: number;
  status: RoundStatus;
  trigger_kline_ts: string;
  direction: string | null;
  score: number | null;
  confidence: number | null;
  entry_point: number | null;
  indicator_score: number | null;
  indicator_confidence: number | null;
  structure_score: number | null;
  structure_confidence: number | null;
  mechanics_score: number | null;
  mechanics_confidence: number | null;
  bet_direction: string | null;
  bet_amount: number | null;
  fee_amount: number;
  settle_price: number | null;
  result: RoundResult | null;
  pnl: number | null;
  created_at: string;
  settled_at: string | null;
}

export interface EquityPoint {
  round_seq: number;
  pnl: number;
  cumulative_pnl: number;
}

export interface StatsResponse {
  task_id: string;
  total_rounds: number;
  wins: number;
  losses: number;
  skips: number;
  win_rate: number;
  total_pnl: number;
  current_capital: number;
  roi: number;
  max_drawdown: number;
  sharpe_ratio: number;
  profit_factor: number;
  best_win_streak: number;
  worst_lose_streak: number;
  current_streak: string | null;
}

export interface RoundListResponse {
  rounds: RoundResponse[];
  total: number;
  offset: number;
  limit: number;
}

// ── WebSocket ──
export interface WsMessage {
  type: WsMessageType;
  task_id: string;
  data: Record<string, unknown>;
}
