from typing import Dict, Any, Optional
import logging
import pandas as pd
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode

from app.core.config import settings
from app.core.providers import get_provider_config
from app.agents.decision.decision_configs import DECISION_AGENT_VERSIONS
from app.core.graph_setup import SetGraph
from app.utils.graph_util import TechnicalTools

logger = logging.getLogger(__name__)

class TradingEngine:
    """
    Service for running the trading analysis graph.
    Refactored from core/trading_graph.py
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # Initialize configuration
        self.decision_agent_version = "original"
        self.include_decision_agent = True
        
        # Configuration overrides
        override_agent_model = None
        override_graph_model = None
        override_agent_temp = None
        override_graph_temp = None

        if config:
            self.decision_agent_version = config.get("decision_agent_version", "original")
            self.include_decision_agent = config.get("include_decision_agent", True)
            
            override_agent_model = config.get("agent_llm_model")
            override_graph_model = config.get("graph_llm_model")
            override_agent_temp = config.get("agent_llm_temperature")
            override_graph_temp = config.get("graph_llm_temperature")

        # Initialize LLMs using the simplified factory function
        # Create specific LLM clients for each agent to support individual configuration (e.g. Thinking Mode)
        self.indicator_llm = self._create_llm_client(
            role="agent",
            agent_name="indicator",
            model=override_agent_model,
            temperature=override_agent_temp
        )

        self.pattern_llm = self._create_llm_client(
            role="graph",
            agent_name="pattern",
            model=override_graph_model,
            temperature=override_graph_temp
        )

        self.trend_llm = self._create_llm_client(
            role="graph",
            agent_name="trend",
            model=override_graph_model,
            temperature=override_graph_temp
        )
        
        self.decision_llm = self._create_llm_client(
            role="agent",
            agent_name="decision",
            model=override_agent_model,
            temperature=override_agent_temp
        )

        self.toolkit = TechnicalTools()
        self.tool_nodes = self._set_tool_nodes()

        # Setup Graph
        self.graph_setup = SetGraph(
            self.indicator_llm,
            self.pattern_llm,
            self.trend_llm,
            self.decision_llm,
            self.toolkit,
            self.tool_nodes,
            self.decision_agent_version,
            self.include_decision_agent,
        )
        self.graph = self.graph_setup.set_graph()

    def _create_llm_client(self, role: str, agent_name: str = None, model: Optional[str] = None, temperature: Optional[float] = None) -> ChatOpenAI:
        """创建 LLM 客户端"""
        # We need to import the factory from config to access the new logic
        from app.core.config import create_llm_client as create_llm_client_factory
        
        # Use the factory directly but allow overrides
        # Since the factory reads from settings, we just need to handle overrides here if any
        # However, the factory is static. 
        # To support overrides + thinking mode properly, we should rely on the factory's logic 
        # but maybe we need to update settings temporarily or pass overrides to factory?
        # Actually, the factory in config.py uses settings directly.
        
        # To keep it simple and reuse the new factory logic:
        # If no overrides, just call factory.
        # If overrides, we might need to manually construct or hack.
        
        # But wait, the `create_llm_client` in config.py doesn't accept overrides.
        # Let's modify the local helper to use the new logic we implemented in config.py
        # Actually, I should have updated the _create_llm_client in this file to match config.py's logic
        # OR better, delegate to config.py's factory.
        
        # Let's assume for now we use the factory in config.py but we need to pass overrides?
        # The current _create_llm_client implementation in this file duplicates logic from config.py
        
        # I will update this method to implement the thinking mode logic locally as well, 
        # matching what I did in config.py
        
        if role == "agent":
            provider = settings.AGENT_PROVIDER
            default_model = settings.AGENT_MODEL
            default_temperature = settings.AGENT_TEMPERATURE
        else:
            provider = settings.GRAPH_PROVIDER
            default_model = settings.GRAPH_MODEL
            default_temperature = settings.GRAPH_TEMPERATURE

        actual_model = model or default_model
        actual_temperature = temperature if temperature is not None else default_temperature

        cfg = get_provider_config(provider)
        if not cfg:
            raise ValueError(f"Unknown provider: {provider}")

        api_key = getattr(settings, cfg["api_key_env"], "")
        if not api_key:
            raise ValueError(f"API Key not found for provider {provider}. Please set {cfg['api_key_env']} in .env file")

        model_kwargs = {}
        
        # 判断是否开启思考模式
        enable_thinking = False
        reasoning_effort = "medium"
        
        if agent_name:
            if agent_name == "indicator":
                enable_thinking = settings.INDICATOR_THINKING_MODE
                reasoning_effort = settings.INDICATOR_REASONING_EFFORT
            elif agent_name == "pattern":
                enable_thinking = settings.PATTERN_THINKING_MODE
                reasoning_effort = settings.PATTERN_REASONING_EFFORT
            elif agent_name == "trend":
                enable_thinking = settings.TREND_THINKING_MODE
                reasoning_effort = settings.TREND_REASONING_EFFORT
            elif agent_name == "decision":
                enable_thinking = settings.DECISION_THINKING_MODE
                reasoning_effort = settings.DECISION_REASONING_EFFORT
        
        # 针对 OpenAI o1/o3/gpt-5 等推理模型处理
        # 如果开启思考模式且模型名称包含推理模型特征
        is_reasoning_model = actual_model.startswith(("o1", "o3", "gpt-o1", "gpt-o3", "gpt-5"))
        
        if enable_thinking:
            logger.info(f"🧠 [TradingEngine] Thinking Mode Enabled for Agent: {agent_name} | Model: {actual_model}")
            
            if provider == "openrouter":
                # OpenRouter 思考模式参数
                logger.info(f"[TradingEngine] Injecting OpenRouter reasoning params (extra_body)")
                model_kwargs["extra_body"] = {"reasoning": {"enabled": True}}
            elif is_reasoning_model:
                # OpenAI 原生推理模型参数
                logger.info(f"[TradingEngine] Injecting OpenAI reasoning params: effort={reasoning_effort}")
                model_kwargs["reasoning_effort"] = reasoning_effort
            else:
                logger.warning(f"[TradingEngine] Thinking Mode enabled but no specific params injected for provider {provider} and model {actual_model}. Standard behavior applies.")

        # 构建基础参数
        client_kwargs = {
            "model": actual_model,
            "api_key": api_key,
            "base_url": cfg["base_url"],
            "model_kwargs": model_kwargs,
            # 显式设置超时时间 (与 config.py 保持一致)
            "request_timeout": settings.LLM_TIMEOUT,
            # 增加最大重试次数
            "max_retries": 3,
            # 关闭流式传输
            "streaming": False,
        }

        # 仅在非推理模型或明确需要 temperature 时才传入
        if not (enable_thinking and is_reasoning_model):
            client_kwargs["temperature"] = actual_temperature

        return ChatOpenAI(**client_kwargs)

    def _set_tool_nodes(self) -> Dict[str, ToolNode]:
        return {
            "indicator": ToolNode([]),
            "pattern": ToolNode([]),
            "trend": ToolNode([]),
        }

    async def run_analysis(self, data: Any, symbol: str, timeframe: str) -> Dict[str, Any]:
        """
        Run the analysis graph.
        Supports both single timeframe (DataFrame) and multi-timeframe (Dict[str, DataFrame]) modes.
        """
        import json
        
        # ✅ 检测是否为多时间框架模式
        is_multi_tf = isinstance(data, dict) and not hasattr(data, 'to_dict')
        
        # Prepare initial state
        kline_data = data
        
        if is_multi_tf:
            # ✅ 多时间框架模式：data 是字典 {timeframe: DataFrame}
            logger.info(f"Processing multi-timeframe data: {list(data.keys())}")
            
            # 保持字典结构,但转换每个 DataFrame
            converted_data = {}
            for tf, df in data.items():
                if isinstance(df, pd.DataFrame):
                    df_temp = df.reset_index()
                    if 'Date' in df_temp.columns:
                        df_temp['Date'] = df_temp['Date'].dt.strftime('%Y-%m-%d %H:%M:%S')
                        df_temp.rename(columns={'Date': 'Datetime'}, inplace=True)
                    converted_data[tf] = df_temp
                else:
                    converted_data[tf] = df
            
            kline_data = converted_data
            
            # 提取最新价格(使用第一个时间框架)
            first_tf = list(converted_data.keys())[0]
            first_df = converted_data[first_tf]
            if isinstance(first_df, pd.DataFrame) and not first_df.empty:
                latest_price = first_df.iloc[-1]['Close']
            else:
                latest_price = None
                
        elif hasattr(data, 'to_json') or isinstance(data, pd.DataFrame):
            # ✅ 单时间框架模式：data 是单个 DataFrame
            df_temp = data.copy()
            if isinstance(data, pd.DataFrame):
                df_temp = data.reset_index()
                if 'Date' in df_temp.columns:
                    df_temp['Date'] = df_temp['Date'].dt.strftime('%Y-%m-%d %H:%M:%S')
                    df_temp.rename(columns={'Date': 'Datetime'}, inplace=True)
            
            kline_data = df_temp.to_dict(orient='records') if hasattr(df_temp, 'to_dict') else df_temp
            
            # Extract latest price
            latest_price = None
            if isinstance(kline_data, list) and len(kline_data) > 0:
                latest_price = kline_data[-1].get('Close')
        else:
            # 已经是处理好的数据
            latest_price = None
            if isinstance(kline_data, list) and len(kline_data) > 0:
                latest_price = kline_data[-1].get('Close')

        initial_state = {
            "kline_data": kline_data,
            "time_frame": timeframe,
            "stock_name": symbol,
            "messages": [],
            "latest_price": latest_price,
            "multi_timeframe_mode": is_multi_tf,
            "timeframes": list(data.keys()) if is_multi_tf else None
        }

        try:
            import asyncio

            result = await asyncio.to_thread(self.graph.invoke, initial_state)

            if "error" not in result:
                result["agent_version"] = self.decision_agent_version
                version_cfg = DECISION_AGENT_VERSIONS.get(self.decision_agent_version, {})
                result["agent_version_name"] = version_cfg.get("name", self.decision_agent_version)
                result["agent_version_description"] = version_cfg.get("description", "")
                logger.info(f"Analysis completed with version: {result['agent_version_name']}")

                # Parse decision agent JSON output for frontend structured display
                if "final_trade_decision" in result and isinstance(result["final_trade_decision"], str):
                    try:
                        import json
                        import re
                        
                        decision_str = result["final_trade_decision"]
                        # 尝试提取JSON块
                        json_match = re.search(r'```json\s*(\{.*?\})\s*```', decision_str, re.DOTALL)
                        if json_match:
                            decision_str = json_match.group(1)
                        else:
                            # 尝试无json标签的代码块
                            code_match = re.search(r'```\s*(\{.*?\})\s*```', decision_str, re.DOTALL)
                            if code_match:
                                decision_str = code_match.group(1)
                        
                        # 清理可能存在的非JSON字符
                        decision_str = decision_str.strip()
                        
                        decision_json = json.loads(decision_str)
                        
                        k1_action = decision_json.get("k1_decision") or decision_json.get("decision", "HOLD")
                        k2_action = decision_json.get("k2_decision") or decision_json.get("decision", "HOLD")
                        k1_confidence = decision_json.get("k1_confidence", decision_json.get("confidence_level", decision_json.get("confidence", 0)))
                        k2_confidence = decision_json.get("k2_confidence", decision_json.get("confidence_level", decision_json.get("confidence", 0)))

                        # Keep legacy fields for the frontend while exposing the exact
                        # independently scored K1/K2 contract to the backtest engine.
                        normalized_decision = {
                            "action": k2_action,
                            "k1_action": k1_action,
                            "k2_action": k2_action,
                            "k1_confidence": k1_confidence,
                            "k2_confidence": k2_confidence,
                            "reasoning": decision_json.get("decision_rationale") or decision_json.get("justification", ""),
                            "confidence": k2_confidence,
                            "signal_type": decision_json.get("market_environment", "N/A"),
                            "stop_loss": decision_json.get("stop_loss"),
                            "take_profit": decision_json.get("take_profit"),
                            "entry_point": decision_json.get("entry_point") or str(latest_price) if latest_price else None,
                            # Preserve all original fields for HTML report use
                            **decision_json
                        }
                        
                        result["decision"] = normalized_decision
                        logger.info("Successfully parsed and normalized trade decision JSON")
                    except Exception as e:
                        logger.warning(f"Failed to parse final_trade_decision JSON: {e}")
                        # Fallback: try to extract key information manually
                        result["decision"] = {
                            "action": "HOLD",  # Default to hold
                            "reasoning": f"Failed to parse decision data. Please check the original report. Error: {str(e)}",
                            "confidence": "Low",
                            "signal_type": "Error",
                            "raw_content": result["final_trade_decision"],
                            "decision": "HOLD" # Fallback
                        }

            # Construct market_data structure for frontend and HTML report
            result["market_data"] = {
                "analysis": {
                    "indicators": result.get("indicator_report", "Analysis failed"),
                    "patterns": result.get("pattern_report", "Analysis failed"),
                    "trend": result.get("trend_report", "Analysis failed")
                }
            }
            
            # 哈雷酱：暴露图表数据，确保 HTML 导出能使用
            # 这些图表由各个 agent (pattern_agent, trend_agent) 生成并保存在 state 中
            result["pattern_chart"] = result.get("pattern_chart") or result.get("pattern_image")
            result["trend_chart"] = result.get("trend_chart") or result.get("trend_image")

            return result
        except Exception as e:
            logger.exception("Analysis failed")
            return {
                "error": f"Analysis failed: {str(e)}",
                "messages": []
            }
