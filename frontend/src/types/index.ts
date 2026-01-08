export interface Asset {
  symbol: string;
  name?: string;
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
  ai_version: string;
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
  
  [key: string]: any;
}
