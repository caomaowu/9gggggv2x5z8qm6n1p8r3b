from typing import Dict, Any, Optional
import logging
import pandas as pd
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode

from app.core.config import settings, LLMConfig, APIConfig
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
        self.llm_config = LLMConfig()
        self.decision_agent_version = "constrained"
        self.include_decision_agent = True

        if config:
            self.llm_config.agent_model = config.get("agent_llm_model", self.llm_config.agent_model)
            self.llm_config.graph_model = config.get("graph_llm_model", self.llm_config.graph_model)
            self.llm_config.agent_temperature = config.get("agent_llm_temperature", self.llm_config.agent_temperature)
            self.llm_config.graph_temperature = config.get("graph_llm_temperature", self.llm_config.graph_temperature)
            
            self.decision_agent_version = config.get("decision_agent_version", "constrained")
            self.include_decision_agent = config.get("include_decision_agent", True)

        # Initialize LLMs
        self.agent_llm = ChatOpenAI(
            model=self.llm_config.agent_model,
            temperature=self.llm_config.agent_temperature,
            openai_api_key=self.llm_config.api_key,
            openai_api_base=self.llm_config.base_url,
        )
        self.graph_llm = ChatOpenAI(
            model=self.llm_config.graph_model,
            temperature=self.llm_config.graph_temperature,
            openai_api_key=self.llm_config.api_key,
            openai_api_base=self.llm_config.base_url,
        )
        
        self.toolkit = TechnicalTools()
        self.tool_nodes = self._set_tool_nodes()

        # Setup Graph
        self.graph_setup = SetGraph(
            self.agent_llm,
            self.graph_llm,
            self.toolkit,
            self.tool_nodes,
            self.decision_agent_version,
            self.include_decision_agent,
        )
        self.graph = self.graph_setup.set_graph()

    def _set_tool_nodes(self) -> Dict[str, ToolNode]:
        return {
            "indicator": ToolNode([]),
            "pattern": ToolNode([]),
            "trend": ToolNode([]),
        }

    async def run_analysis(self, data: Any, symbol: str, timeframe: str) -> Dict[str, Any]:
        """
        Run the analysis graph.
        """
        import json
        
        # Prepare initial state
        # Handle pandas DataFrame -> JSON conversion if needed
        kline_data = data
        if hasattr(data, 'to_json'):
             # Reset index to ensure Date/Datetime is included in the dictionary
              # and rename 'Date' to 'Datetime' as expected by consumers
              df_temp = data.copy()
              if isinstance(data, pd.DataFrame):
                  df_temp = data.reset_index()
                  if 'Date' in df_temp.columns:
                      # Convert to string to ensure JSON serialization and compatibility
                      df_temp['Date'] = df_temp['Date'].dt.strftime('%Y-%m-%d %H:%M:%S')
                      df_temp.rename(columns={'Date': 'Datetime'}, inplace=True)
              
              kline_data = df_temp.to_dict(orient='records')
        elif hasattr(data, 'to_dict'):
             kline_data = data.to_dict(orient='records')

        # Extract latest price
        latest_price = None
        if kline_data and len(kline_data) > 0:
             latest_price = kline_data[-1].get('Close')
             
             # Debug: Check keys
             logger.info(f"Kline data keys check: {list(kline_data[0].keys())}")

        initial_state = {
            "kline_data": kline_data,
            "time_frame": timeframe,
            "stock_name": symbol,
            "messages": [],
            "latest_price": latest_price
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

                # 哈雷酱添加：解析决策智能体的JSON输出，供前端结构化展示
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
                        
                        # 规范化字段名称以匹配前端 AnalysisResult.tsx 的期望
                        normalized_decision = {
                            "action": decision_json.get("decision", "HOLD"),
                            "reasoning": decision_json.get("decision_rationale") or decision_json.get("justification", ""),
                            "confidence": decision_json.get("confidence_level", "0"),
                            "signal_type": decision_json.get("market_environment", "N/A"),
                            "stop_loss": decision_json.get("stop_loss"),
                            "take_profit": decision_json.get("take_profit"),
                            "entry_point": decision_json.get("entry_point") or str(latest_price) if latest_price else None,
                            # 哈雷酱：保留所有原始字段供 HTML 报告使用
                            **decision_json
                        }
                        
                        result["decision"] = normalized_decision
                        logger.info("Successfully parsed and normalized trade decision JSON")
                    except Exception as e:
                        logger.warning(f"Failed to parse final_trade_decision JSON: {e}")
                        # 降级处理：尝试手动提取关键信息
                        result["decision"] = {
                            "action": "HOLD",  # 默认观望
                            "reasoning": f"无法解析决策数据，请查看原始报告。错误: {str(e)}",
                            "confidence": "Low",
                            "signal_type": "Error",
                            "raw_content": result["final_trade_decision"],
                            "decision": "HOLD" # Fallback
                        }

            # 哈雷酱：构造 market_data 结构，适配前端和 HTML 报告
            result["market_data"] = {
                "analysis": {
                    "indicators": result.get("indicator_report", "分析失败"),
                    "patterns": result.get("pattern_report", "分析失败"),
                    "trend": result.get("trend_report", "分析失败")
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
