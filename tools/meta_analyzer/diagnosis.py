import os
from typing import Dict, Any
from langchain_openai import ChatOpenAI

try:
    from tools.meta_analyzer.config import settings
except ImportError:
    from config import settings

class MetaAgent:
    def __init__(self):
        self.llm = self._init_llm()
        
        # 加载 Prompt 模板
        template_path = os.path.join(os.path.dirname(__file__), "templates", "critic_prompt.md")
        self.prompt_template = ""
        if os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                self.prompt_template = f.read()
        else:
            print(f"Warning: Prompt template not found at {template_path}")

    def _init_llm(self):
        """Initialize LLM client using independent configuration"""
        try:
            valid, msg = settings.validate()
            if not valid:
                print(f"Config Error: {msg}")
                return None

            print(f"Initializing LLM: Model={settings.LLM_MODEL}, BaseURL={settings.LLM_BASE_URL}")
            
            return ChatOpenAI(
                model=settings.LLM_MODEL,
                temperature=settings.LLM_TEMPERATURE,
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
            )
        except Exception as e:
            print(f"Error initializing LLM client: {e}")
            return None

    def diagnose_case(self, case_data: Dict[str, Any]):
        """
        对单个案例进行诊断
        """
        if not self.llm:
            return "Error: LLM Client not initialized. Please check config.py or .env."

        # 1. 提取 Agent 决策上下文
        decision = case_data.get("decision", {})
        analysis_results = case_data.get("analysis_results", {})
        
        # 提取各个 Agent 的报告
        indicator_report = "N/A"
        pattern_report = "N/A"
        trend_report = "N/A"
        
        if "Indicator" in analysis_results:
             indicator_report = analysis_results["Indicator"].get("indicator_report", "N/A")
        
        if "Pattern" in analysis_results:
             pattern_report = analysis_results["Pattern"].get("pattern_report", "N/A")
             
        if "Trend" in analysis_results:
             trend_report = analysis_results["Trend"].get("trend_report", "N/A")

        # 3. 计算盈亏 (获取 entry_point 以供 Prompt 使用)
        max_profit, max_drawdown, entry_point = self._calculate_pnl(case_data)

        # 2. 格式化未来市场走势 (依赖 entry_point)
        future_kline = case_data.get("future_kline_data", [])
        action = decision.get("action", "HOLD")
        future_summary = self._format_future_market(future_kline, entry_point, action)

        # 4. 构建 Prompt
        if not self.prompt_template:
            return "Error: Prompt template not found."

        prompt = self.prompt_template.format(
            asset=case_data.get("asset", "Unknown"),
            timeframe=case_data.get("timeframe", "4h"),
            action=decision.get("action", "HOLD"),
            reasoning=decision.get("reasoning", "N/A"),
            indicator_report=indicator_report,
            pattern_report=pattern_report,
            trend_report=trend_report,
            future_market_summary=future_summary,
            max_profit=max_profit,
            max_drawdown=max_drawdown
        )
        
        # 5. 调用 LLM
        return self.llm.stream(prompt)

    def _format_future_market(self, klines: list, entry_price: float, action: str) -> str:
        if not klines:
            return "No future data available."
            
        summary = []
        summary.append(f"Entry Price: {entry_price}")
        
        # 1. 统计概览
        highs = [k.get("high", 0) for k in klines]
        lows = [k.get("low", 0) for k in klines]
        closes = [k.get("close", 0) for k in klines]
        
        if not highs: return "Invalid data."

        max_h = max(highs)
        min_l = min(lows)
        final_c = closes[-1]
        
        summary.append(f"Price Range: Low {min_l} -> High {max_h}")
        summary.append(f"Final Close: {final_c} (after {len(klines)} candles)")
        
        # 2. 详细 K 线 (限制前 10 根 + 关键极值点)
        summary.append("\nPrice Action Sequence:")
        for i, k in enumerate(klines[:10]): 
            dt = k.get("datetime", "")
            o = k.get("open", 0)
            h = k.get("high", 0)
            l = k.get("low", 0)
            c = k.get("close", 0)
            # 计算单根 K 线的涨跌幅
            change = round((c - o) / o * 100, 2)
            summary.append(f"#{i+1} [{dt}] O:{o} H:{h} L:{l} C:{c} ({change}%)")
            
        if len(klines) > 10:
            summary.append(f"... and {len(klines)-10} more candles ...")
            
        return "\n".join(summary)

    def _calculate_pnl(self, data: Dict) -> tuple:
        # 增强版 PnL 计算：考虑时间序列和路径
        future_kline = data.get("future_kline_data", [])
        decision = data.get("decision", {})
        action = decision.get("action", "HOLD")
        
        # 尝试获取 entry_point
        entry_point = decision.get("entry_point", 0)
        if isinstance(entry_point, str):
            try:
                entry_point = float(entry_point.replace(",", ""))
            except:
                entry_point = 0
        
        if not entry_point:
             entry_point = data.get("latest_price", 0)
             
        # 如果还是没有，尝试从第一根未来K线的Open获取
        if not entry_point and future_kline:
            entry_point = future_kline[0].get("open", 0)

        if not future_kline or not entry_point or action not in ["LONG", "SHORT"]:
            return 0.0, 0.0, entry_point
            
        entry_point = float(entry_point)
        
        max_p = 0.0
        max_d = 0.0
        
        # 逐根遍历，记录路径
        # 这里我们简单记录最大值和最小值
        # 更好的做法是：记录“先达到止盈还是先达到止损”，但目前没有 TP/SL 数据
        # 所以我们维持 Max P / Max D，但在 Prompt 里描述路径
        
        highs = [float(k.get("high", 0)) for k in future_kline]
        lows = [float(k.get("low", 0)) for k in future_kline]
        
        if not highs: return 0.0, 0.0, entry_point

        if action == "LONG":
            max_p = (max(highs) - entry_point) / entry_point * 100
            max_d = (min(lows) - entry_point) / entry_point * 100
        else:
            max_p = (entry_point - min(lows)) / entry_point * 100
            max_d = (entry_point - max(highs)) / entry_point * 100
            
        return round(max_p, 2), round(max_d, 2), entry_point
