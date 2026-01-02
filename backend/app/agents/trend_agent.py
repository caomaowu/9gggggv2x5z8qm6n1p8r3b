"""
Agent for trend analysis in high-frequency trading (HFT) context.
Uses LLM and toolkit to generate and interpret trendline charts for short-term prediction.
"""

import json
import time
import copy

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from openai import RateLimitError

# 哈雷酱的进度跟踪导入！
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from app.core.progress import update_agent_progress
except ImportError:
    # 如果导入失败，使用空函数避免破坏
    def update_agent_progress(agent_name, progress_within_agent=0, status=""):
        pass

# 哈雷酱的性能监控系统！
try:
    from app.utils.performance import performance_monitor, monitor_llm_call
except ImportError:
    # 如果导入失败，使用空装饰器
    def performance_monitor(stage_name=None):
        def decorator(func):
            return func
        return decorator
    def monitor_llm_call(model_name=None):
        return performance_monitor(f"LLM调用: {model_name}" if model_name else "LLM调用")


# --- Retry wrapper for LLM invocation ---
def invoke_with_retry(call_fn, *args, retries=3, wait_sec=4):
    """
    Retry a function call with exponential backoff for rate limits or errors.
    """
    for attempt in range(retries):
        try:
            result = call_fn(*args)
            return result
        except RateLimitError:
            print(
                f"Rate limit hit, retrying in {wait_sec}s (attempt {attempt + 1}/{retries})..."
            )
        except Exception as e:
            print(
                f"Other error: {e}, retrying in {wait_sec}s (attempt {attempt + 1}/{retries})..."
            )
        # Only sleep if not the last attempt
        if attempt < retries - 1:
            time.sleep(wait_sec)
    raise RuntimeError("Max retries exceeded")


@performance_monitor("趋势分析智能体")
def create_trend_agent(tool_llm, graph_llm, toolkit):
    """
    Create a trend analysis agent node for HFT.
    现在直接生成趋势图，然后让LLM分析，不再通过工具调用。
    """

    @performance_monitor("趋势分析智能体执行")
    def trend_agent_node(state):
        # 哈雷酱的进度跟踪！
        update_agent_progress("trend", 10, "正在启动趋势分析智能体...")

        kline_data = state.get("kline_data")
        time_frame = state.get("time_frame", "未知")

        # --- 直接生成趋势图，不通过LLM工具调用 ---
        update_agent_progress("trend", 30, "正在生成趋势分析图表...")

        try:
            # 直接调用趋势图生成工具，带重试机制
            max_retries = 3
            wait_sec = 2
            chart_result = None

            for attempt in range(max_retries):
                try:
                    chart_result = toolkit.generate_trend_image.invoke({
                        "kline_data": copy.deepcopy(kline_data)
                    })
                    if chart_result and chart_result.get("trend_image"):
                        break
                    print(f"趋势图生成无结果，{wait_sec}秒后重试 (尝试 {attempt + 1}/{max_retries})...")
                    if attempt < max_retries - 1:
                        time.sleep(wait_sec)
                except Exception as e:
                    print(f"趋势图生成出错: {e}，{wait_sec}秒后重试 (尝试 {attempt + 1}/{max_retries})...")
                    if attempt < max_retries - 1:
                        time.sleep(wait_sec)

            if not chart_result or not chart_result.get("trend_image"):
                raise RuntimeError("趋势图生成失败，超过最大重试次数")

            trend_image_b64 = chart_result.get("trend_image")

        except Exception as e:
            update_agent_progress("trend", 100, "趋势图生成失败")
            return {
                "messages": [],
                "trend_report": f"趋势图生成失败: {str(e)}",
                "error": str(e)
            }

        # --- 计算技术指标 ---
        update_agent_progress("trend", 50, "正在计算技术指标数据...")

        try:
            # 直接调用工具计算技术指标
            indicator_results = {}

            # 计算MACD
            try:
                macd_result = toolkit.compute_macd.invoke({"kline_data": copy.deepcopy(kline_data)})
                indicator_results["MACD"] = macd_result
            except Exception as e:
                print(f"MACD计算失败: {e}")
                indicator_results["MACD"] = {"error": str(e)}

            # 计算RSI
            try:
                rsi_result = toolkit.compute_rsi.invoke({"kline_data": copy.deepcopy(kline_data)})
                indicator_results["RSI"] = rsi_result
            except Exception as e:
                print(f"RSI计算失败: {e}")
                indicator_results["RSI"] = {"error": str(e)}

            # 计算ROC
            try:
                roc_result = toolkit.compute_roc.invoke({"kline_data": copy.deepcopy(kline_data)})
                indicator_results["ROC"] = roc_result
            except Exception as e:
                print(f"ROC计算失败: {e}")
                indicator_results["ROC"] = {"error": str(e)}

            # 计算Stochastic
            try:
                stoch_result = toolkit.compute_stoch.invoke({"kline_data": copy.deepcopy(kline_data)})
                indicator_results["Stochastic"] = stoch_result
            except Exception as e:
                print(f"Stochastic计算失败: {e}")
                indicator_results["Stochastic"] = {"error": str(e)}

            # 计算Williams %R
            try:
                willr_result = toolkit.compute_willr.invoke({"kline_data": copy.deepcopy(kline_data)})
                indicator_results["Williams_R"] = willr_result
            except Exception as e:
                print(f"Williams %R计算失败: {e}")
                indicator_results["Williams_R"] = {"error": str(e)}

            update_agent_progress("trend", 80, "技术指标计算完成，正在生成分析报告...")

        except Exception as e:
            update_agent_progress("trend", 100, "技术指标计算失败")
            return {
                "messages": [],
                "trend_report": f"技术指标计算失败: {str(e)}",
                "error": str(e)
            }

        # --- 使用图像进行视觉分析，融合OHLC数据和技术指标 ---
        # 获取OHLC数据用于综合分析
        ohlc_data = kline_data if kline_data else state.get("kline_data", {})

        # 准备技术指标数据
        indicators_summary = f"""
**📊 真实计算的技术指标数据：**

### 🔥 MACD指标
{json.dumps(indicator_results.get("MACD", {}), indent=2, ensure_ascii=False)}

### ⚡ RSI指标  
{json.dumps(indicator_results.get("RSI", {}), indent=2, ensure_ascii=False)}

### 📈 ROC指标
{json.dumps(indicator_results.get("ROC", {}), indent=2, ensure_ascii=False)}

### 🌊 Stochastic指标
{json.dumps(indicator_results.get("Stochastic", {}), indent=2, ensure_ascii=False)}

### 🎯 Williams %R指标
{json.dumps(indicator_results.get("Williams_R", {}), indent=2, ensure_ascii=False)}
"""

        image_prompt = [
            {
                "type": "text",
                "text": (
                    f"⚠️ 重要：请使用中文进行专业分析，你可以选择一些关键的指标进行分析，可以忽略你觉得不重要的指标。\n\n"
                    f"这张{time_frame}K线图表包含了自动绘制的趋势线：**蓝色线**是支撑线，**红色线**是阻力线，两者都基于最近的收盘价格计算得出。\n\n"
                    f"**OHLC历史数据：**\n"
                    f"{json.dumps(ohlc_data, indent=2, ensure_ascii=False)}\n\n"
                    f"{indicators_summary}\n\n"
                    f"**🎯 专业趋势分析要求：**\n"
                    f"1. **趋势强度分析**：结合真实技术指标评估趋势线的可靠性\n"
                    f"2. **价格交互分析**：价格与支撑/阻力位的真实互动情况\n"
                    f"3. **技术指标验证**：用真实MACD、RSI等指标确认趋势信号\n"
                    f"4. **动量评估**：真实ROC和Stochastic指标的速度变化\n"
                    f"5. **综合判断**：基于真实计算数据给出趋势预测\n\n"
                    f"**请基于以上真实计算的技术指标数据和图表进行专业分析：**\n"
                    f"- **趋势方向**：明确上升/下降/横盘\n"
                    f"- **趋势强度**：强/中/弱，并说明具体依据\n"
                    f"- **技术指标信号**：真实MACD金叉死叉、RSI超买超卖等\n"
                    f"- **关键价位**：支撑阻力位的具体数值\n"
                    f"- **短期预测**：1-3根K线的走势预期\n"
                    f"- **交易建议**：具体的操作策略\n\n"
                    f"**格式要求：**\n"
                    f"使用##标题和-项目符号，重要数据加粗\n"
                    f"基于真实计算的指标数据，绝对避免推测性分析\n"
                    f"保持专业性和实用性\n\n"
                    f"请用专业、准确的中文进行分析。"
                ),
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{trend_image_b64}"},
            },
        ]

        update_agent_progress("trend", 90, "正在分析趋势线和K线形态...")

        final_response = invoke_with_retry(
            graph_llm.invoke,
            [
                SystemMessage(
                    content="你是专业的量化交易趋势分析师，拥有丰富的市场经验。"
                    "你的任务是结合自己计算的真实技术指标数据、OHLC历史数据和趋势线图表进行综合分析。"
                    "所有技术指标都是通过专业工具实时计算的，不是推导数据。"
                    "你可以选择一些关键的指标进行分析，可以忽略你觉得不重要的指标。"
                    "重点关注趋势强度验证、技术指标确认、支撑阻力位分析和短期走势预测。"
                    "用中文进行专业、准确的分析，给出具体的数值和明确的判断，你可以使用一些表情符号来增加视觉效果。"
                ),
                HumanMessage(content=image_prompt),
            ],
        )

        update_agent_progress("trend", 100, "趋势分析完成")
        # 从图表结果中获取实际的文件名
        trend_image_filename = chart_result.get("trend_image_filename", "trend_graph.png") if chart_result else "trend_graph.png"
        trend_image_description = chart_result.get("trend_image_description", "Trend-enhanced candlestick chart with support/resistance lines") if chart_result else "Trend-enhanced candlestick chart with support/resistance lines"

        return {
            "messages": state.get("messages", []) + [final_response],
            "trend_report": final_response.content,
            "trend_image": trend_image_b64,
            "trend_image_filename": trend_image_filename,
            "trend_image_description": trend_image_description,
        }

    return trend_agent_node
