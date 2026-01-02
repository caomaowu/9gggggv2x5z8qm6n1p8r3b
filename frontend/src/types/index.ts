export interface Asset {
  symbol: string;
  name?: string;
}

export interface DualModelConfig {
  dual_model: boolean;
  model_1?: string;
  model_2?: string;
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
  dual_model_config?: DualModelConfig;
}

export interface AIModel {
  id: string;
  name: string;
  provider: string;
  description: string;
}

export const AVAILABLE_MODELS: AIModel[] = [
    { id: 'MiniMax/MiniMax-M2', name: 'MiniMax M2', provider: 'MiniMax', description: '高性能通用模型，适合大多数交易场景' },
    { id: 'deepseek-ai/DeepSeek-V3.2-Exp', name: 'DeepSeek V3.2 Exp', provider: 'DeepSeek', description: '实验性高性能模型，分析能力强' },
    { id: 'Qwen/Qwen3-VL-235B-A22B-Instruct', name: 'Qwen3 VL 235B', provider: 'Qwen', description: '视觉语言大模型，擅长图表分析' },
    { id: 'Qwen/Qwen3-Next-80B-A3B-Instruct', name: 'Qwen3 Next 80B', provider: 'Qwen', description: '下一代高性能模型，推理能力强' },
    { id: 'ZhipuAI/GLM-4.6', name: 'GLM 4.6', provider: 'ZhipuAI', description: '智谱AI最新模型，综合能力优秀' },
    { id: 'Qwen/Qwen3-VL-30B-A3B-Instruct', name: 'Qwen3 VL 30B', provider: 'Qwen', description: '视觉语言模型，支持多模态分析' }
];

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

export interface DualModelAnalysis {
  model_1_result?: DecisionResult;
  model_2_result?: DecisionResult;
  comparison?: {
    consensus: boolean;
    [key: string]: any;
  };
}

export interface AnalysisResult {
  decision?: DecisionResult;
  dual_model_analysis?: DualModelAnalysis;
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
