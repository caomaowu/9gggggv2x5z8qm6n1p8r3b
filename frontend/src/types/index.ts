export interface Asset {
  symbol: string;
  name?: string;
}

export interface AnalyzeRequest {
  asset: string;
  timeframe: string;
  data_source: string;
  data_method: "latest" | "date_range" | "to_end";
  kline_count: number;
  future_kline_count: number;
  start_date?: string;
  start_time?: string;
  end_date?: string;
  end_time?: string;
  use_current_time: boolean;
  ai_version: string;
  custom_prompt?: string;
}

export interface DecisionResult {
  action: string;
  decision?: string; // 为了兼容性
  confidence: number;
  reasoning: string;
  justification?: string; // 兼容性
  signal_type?: string;
  entry_point?: number;
  stop_loss?: number | string; // 允许 '未提供'
  take_profit?: number | string; // 允许 '未提供'
  market_environment?: string;
  volatility_assessment?: string;
  forecast_horizon?: string;
  risk_reward_ratio?: string;
  risk_reward?: string;
  confidence_level?: string;
  time_horizon?: string;
  model_name?: string;
  [key: string]: any;
}

export interface AnalysisResult {
  decision?: DecisionResult;
  indicator_report?: string;
  pattern_report?: string;
  trend_report?: string;
  latest_price?: number;
  price_info?: Record<string, any>;
  messages?: any[];
  agent_version_name?: string;
  agent_version_description?: string;
  decision_agent_version?: string;
  result_id?: string;
  data_method_short?: string;
  analysis_time_display?: string;
  [key: string]: any;
}
