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
  multi_timeframe_mode?: boolean;
  timeframes?: string[];
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
  llm_config?: LLMConfig;
  kline_data?: Array<Record<string, unknown>>;
  future_kline_chart_base64?: string;
  future_kline_data?: FutureKlineDataRow[];
  indicator_report?: string;
  technical_indicators?: string;
  pattern_report?: string;
  pattern_analysis?: string;
  trend_report?: string;
  trend_analysis?: string;
  latest_price?: number;
  price_info?: Record<string, unknown>;
  messages?: unknown[];
  result_id?: string;
  data_method_short?: string;
  analysis_time_display?: string;
  
  // 多时间框架支持
  multi_timeframe_mode?: boolean;
  timeframes?: string[];
  
  // 模式识别图表
  pattern_chart?: string;              // 单时间框架(向后兼容)
  pattern_image?: string;              // 单时间框架(向后兼容别名)
  pattern_images?: Record<string, string>; // 多时间框架
  
  // 趋势分析图表
  trend_chart?: string;                // 单时间框架(向后兼容)
  trend_image?: string;                // 单时间框架(向后兼容别名)
  trend_images?: Record<string, string>;   // 多时间框架
  
  [key: string]: unknown;
}
