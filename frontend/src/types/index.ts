export interface Asset {
  symbol: string;
  name?: string;
}

export type FutureKlineDataRow = {
  datetime?: string;
  date?: string;
  open: string | number;
  high: string | number;
  low: string | number;
  close: string | number;
  [key: string]: unknown;
};

export interface LLMRuntimeInfo {
  provider?: string;
  name?: string;
  model?: string;
  temperature?: number;
}

export interface LLMRuntimeConfig {
  agent?: LLMRuntimeInfo;
  graph?: LLMRuntimeInfo;
  // brale per-agent
  indicator?: LLMRuntimeInfo;
  structure?: LLMRuntimeInfo;
  mechanics?: LLMRuntimeInfo;
}

export interface AnalyzeRequest {
  asset: string;
  timeframe: string | string[];
  data_source: string;
  data_method: "latest" | "date_range" | "to_end";
  kline_count: number;
  future_kline_count: number;
  start_date?: string;
  start_time?: string;
  end_date?: string;
  end_time?: string;
  use_current_time: boolean;
  /** @deprecated — removed in brale migration, kept for backward compat */
  ai_version?: string;
  multi_timeframe_mode?: boolean;
  timeframes?: string[];
}

// ---- brale agent summary types ----

export interface AgentScore {
  score: number;
  confidence: number;
}

export interface ResonanceInfo {
  active: boolean;
  bonus: number;
  aligned_count: number;
}

export interface FusionResult {
  direction: "long" | "short" | "none";
  score: number;
  confidence: number;
  agreement: number;
  coverage: number;
  resonance: ResonanceInfo;
  agents: {
    indicator: AgentScore;
    structure: AgentScore;
    mechanics: AgentScore;
  };
}

export interface AgentVerificationItem {
  score: number;
  direction: "up" | "down" | "neutral";
  matched: boolean;
}

export interface AgentVerification {
  actual_direction: "up" | "down" | "unknown";
  period: string;
  agents: {
    indicator: AgentVerificationItem;
    structure: AgentVerificationItem;
    mechanics: AgentVerificationItem;
    fusion: AgentVerificationItem;
  };
}

export interface ExcursionViolation {
  index: number;
  close: number;
  deviation_pct: number;
}

export interface ExcursionVerification {
  threshold: number;
  timeframe: string;
  candles_checked: number;
  baseline_price: number;
  predicted_direction: "up" | "down";
  violations: ExcursionViolation[];
  is_clean: boolean;
}

export interface IndicatorSummary {
  expansion: string;
  alignment: string;
  noise: string;
  momentum_detail: string;
  conflict_detail: string;
  movement_score: number;
  movement_confidence: number;
  next_focus: string;
}

export interface StructureSummary {
  regime: string;
  last_break: string;
  quality: string;
  pattern: string;
  volume_action: string;
  candle_reaction: string;
  movement_score: number;
  movement_confidence: number;
  next_focus: string;
}

export interface MechanicsSummary {
  leverage_state: string;
  crowding: string;
  risk_level: string;
  open_interest_context: string;
  anomaly_detail: string;
  movement_score: number;
  movement_confidence: number;
  next_focus: string;
}

// ---- decision (derived from Fusion) ----

export interface DecisionResult {
  action: string;
  decision?: string;
  direction?: string;
  score?: number;
  confidence: number;
  confidence_level?: string;
  reasoning: string;
  justification?: string;
  signal_type?: string;
  entry_point?: number;
  stop_loss?: number | string | null;
  take_profit?: number | string | null;
  market_environment?: string;
  volatility_assessment?: string;
  forecast_horizon?: string;
  risk_reward_ratio?: string | null;
  agreement?: number;
  resonance?: ResonanceInfo;
  agent_scores?: Record<string, AgentScore>;
  fusion_raw?: FusionResult;
  [key: string]: unknown;
}

export interface LLMRoleConfig {
  provider: string;
  name: string;
  model: string;
  temperature: number;
}

export interface LLMConfig {
  agent: LLMRoleConfig;
  graph: LLMRoleConfig;
}

export interface AnalysisResult {
  decision?: DecisionResult;
  asset?: string;
  asset_name?: string;
  timeframe?: string;
  data_length?: number;
  kline_data?: Array<Record<string, unknown>>;
  future_kline_chart_base64?: string;
  future_kline_data?: FutureKlineDataRow[];
  future_15m_chart_base64?: string;
  future_15m_kline_data?: FutureKlineDataRow[];
  agent_verification?: AgentVerification;
  adverse_excursion?: ExcursionVerification;
  history_chart_base64?: string;
  latest_price?: number;
  price_info?: Record<string, unknown>;
  messages?: unknown[];
  result_id?: string;
  data_method_short?: string;
  analysis_time_display?: string;
  multi_timeframe_mode?: boolean;
  timeframes?: string[];
  llm_config?: LLMRuntimeConfig;

  // ---- brale structured data ----
  fusion_result?: FusionResult;
  indicator_summary?: IndicatorSummary;
  structure_summary?: StructureSummary;
  mechanics_summary?: MechanicsSummary;
  market_data?: Record<string, unknown>;

  // ---- deprecated (kept for backward compat, no longer populated) ----
  /** @deprecated use indicator_summary */
  indicator_report?: string;
  /** @deprecated use indicator_summary */
  technical_indicators?: string;
  /** @deprecated use structure_summary */
  pattern_report?: string;
  /** @deprecated use structure_summary */
  pattern_analysis?: string;
  /** @deprecated use mechanics_summary */
  trend_report?: string;
  /** @deprecated use mechanics_summary */
  trend_analysis?: string;
  /** @deprecated brale agents don't generate images */
  pattern_chart?: string;
  /** @deprecated */
  pattern_image?: string;
  /** @deprecated */
  pattern_images?: Record<string, string>;
  /** @deprecated */
  trend_chart?: string;
  /** @deprecated */
  trend_image?: string;
  /** @deprecated */
  trend_images?: Record<string, string>;
  /** @deprecated Decision Agent removed */
  agent_version_name?: string;
  /** @deprecated */
  agent_version_description?: string;
  /** @deprecated */
  decision_agent_version?: string;

  [key: string]: unknown;
}
