"""
Agent for trend analysis in high-frequency trading (HFT) context.
Uses LLM and toolkit to generate and interpret trendline charts for short-term prediction.
"""

import json
import time
import copy
import pandas as pd

from langchain_core.messages import HumanMessage, SystemMessage
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


def convert_to_list_of_dicts(data):
    """将 DataFrame 或 list 转换为 list[dict] 格式供工具调用"""
    if isinstance(data, pd.DataFrame):
        df_reset = data.reset_index()
        if 'Date' in df_reset.columns:
            df_reset['Date'] = df_reset['Date'].dt.strftime('%Y-%m-%d %H:%M:%S')
            df_reset.rename(columns={'Date': 'Datetime'}, inplace=True)
        return df_reset.to_dict(orient='records')
    elif isinstance(data, list):
        return data
    else:
        raise TypeError(f"Unsupported data type: {type(data)}")


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
    强制生成趋势图，基于纯视觉分析，移除所有复杂指标计算。
    """

    @performance_monitor("趋势分析智能体执行")
    def trend_agent_node(state):
        # 哈雷酱的进度跟踪！
        update_agent_progress("trend", 10, "正在启动趋势分析智能体...")

        kline_data = state.get("kline_data")
        time_frame = state.get("time_frame", "未知")
        
        # ✅ 检测是否为多时间框架模式
        is_multi_tf = isinstance(kline_data, dict) and not any(
            key in ['Open', 'High', 'Low', 'Close', 'Volume', 'Datetime'] 
            for key in kline_data.keys()
        )
        
        if is_multi_tf:
            print(f"⚡ 多时间框架模式：检测到 {len(kline_data)} 个时间框架 - {list(kline_data.keys())}")
        else:
            print(f"🔹 单一时间框架模式：{time_frame}")

        # --- 强制生成趋势图 (保留核心功能) ---
        
        multi_tf_trends = {}  # 存储多周期的结果
        final_image_b64 = None # 单周期兼容
        
        if is_multi_tf:
            # ✅ 多时间框架模式：循环生成多张趋势图
            try:
                for idx, (tf_name, tf_data) in enumerate(kline_data.items()):
                    progress = 20 + int((60 / len(kline_data)) * idx)
                    update_agent_progress("trend", progress, f"正在处理 {tf_name} 时间框架...")
                    
                    print(f"📈 正在生成 {tf_name} 时间框架的趋势图...")
                    
                    # 转换数据格式
                    tf_data_list = convert_to_list_of_dicts(tf_data)
                    
                    # 生成趋势图（带重试机制）
                    max_retries = 3
                    wait_sec = 2
                    chart_result = None
                    
                    for attempt in range(max_retries):
                        try:
                            chart_result = toolkit.generate_trend_image.invoke({
                                "kline_data": copy.deepcopy(tf_data_list)
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
                        print(f"⚠️ {tf_name} 趋势图生成失败，跳过该时间框架")
                        continue
                    
                    # 仅保存图片信息，不再计算指标
                    multi_tf_trends[tf_name] = {
                        "trend_image": chart_result.get("trend_image"),
                        "trend_image_filename": chart_result.get("trend_image_filename", f"trend_graph_{tf_name}.png"),
                        "trend_image_description": chart_result.get("trend_image_description", "Trend chart"),
                    }
                    print(f"✅ {tf_name} 趋势图准备完成")
                
                if not multi_tf_trends:
                    raise RuntimeError("所有时间框架的趋势图生成均失败")
                    
                update_agent_progress("trend", 80, "正在生成多时间框架分析报告...")
                
            except Exception as e:
                update_agent_progress("trend", 100, "趋势分析失败")
                return {
                    "messages": [],
                    "trend_report": f"趋势分析失败: {str(e)}",
                    "error": str(e)
                }
        else:
            # ✅ 单一时间框架模式
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

                final_image_b64 = chart_result.get("trend_image")
                update_agent_progress("trend", 80, "图表生成完成，正在分析...")

            except Exception as e:
                update_agent_progress("trend", 100, "趋势图生成失败")
                return {
                    "messages": [],
                    "trend_report": f"趋势图生成失败: {str(e)}",
                    "error": str(e)
                }

        # --- 构建消息并调用 LLM (回归原始纯视觉风格) ---
        
        # 1. 准备 Image Content
        image_content = []
        
        if is_multi_tf:
            # 多周期 Prompt
            image_content.append({
                "type": "text",
                "text": (
                    f"Here are the trendline charts for multiple timeframes: {', '.join(multi_tf_trends.keys())}.\n"
                    "The **blue line** is support, and the **red line** is resistance, both derived from recent closing prices.\n\n"
                    "Analyze how price interacts with these lines across different timeframes.\n"
                    "Look for confluence (signals aligning) or divergence (conflicting signals).\n"
                    "Based on trendline slope, spacing, and recent K-line behavior, predict the likely short-term trend: **upward**, **downward**, or **sideways**.\n"
                    "Support your prediction with reasoning."
                )
            })
            
            for tf_name, tf_info in multi_tf_trends.items():
                image_content.append({
                    "type": "text",
                    "text": f"\n\n--- **{tf_name} Timeframe Chart** ---"
                })
                image_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{tf_info['trend_image']}"}
                })
        else:
            # 单周期 Prompt (原始风格)
            image_content = [
                {
                    "type": "text",
                    "text": (
                        f"This candlestick ({time_frame} K-line) chart includes automated trendlines: the **blue line** is support, and the **red line** is resistance, both derived from recent closing prices.\n\n"
                        "Analyze how price interacts with these lines — are candles bouncing off, breaking through, or compressing between them?\n\n"
                        "Based on trendline slope, spacing, and recent K-line behavior, predict the likely short-term trend: **upward**, **downward**, or **sideways**. "
                        "Support your prediction with respect to prediction, reasoning, signals."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{final_image_b64}"},
                },
            ]

        # 2. 调用 LLM
        update_agent_progress("trend", 90, "Analyzing trendlines...")
        
        # 还原原始 System Prompt
        system_prompt_content = (
            "You are a K-line trend pattern recognition assistant operating in a high-frequency trading context. "
            "Your task is to analyze candlestick charts annotated with support and resistance trendlines."
        )

        human_msg = HumanMessage(content=image_content)
        
        try:
            final_response = invoke_with_retry(
                graph_llm.invoke,
                [
                    SystemMessage(content=system_prompt_content),
                    human_msg,
                ],
            )
        except Exception as e:
            # 简单的 Anthropic 错误处理
            if "at least one message" in str(e).lower():
                final_response = invoke_with_retry(graph_llm.invoke, [human_msg])
            else:
                raise e

        update_agent_progress("trend", 100, "趋势分析完成")
        
        if is_multi_tf:
            return {
                "messages": state.get("messages", []) + [final_response],
                "trend_report": final_response.content,
                "trend_images": {tf: info["trend_image"] for tf, info in multi_tf_trends.items()},
                "multi_timeframe_mode": True,
                "timeframes": list(multi_tf_trends.keys())
            }
        else:
            # 原始风格返回
            trend_image_filename = chart_result.get("trend_image_filename", "trend_graph.png") if chart_result else "trend_graph.png"
            trend_image_description = chart_result.get("trend_image_description", "Trend-enhanced candlestick chart with support/resistance lines") if chart_result else "Trend-enhanced candlestick chart with support/resistance lines"
            
            return {
                "messages": state.get("messages", []) + [final_response],
                "trend_report": final_response.content,
                "trend_image": final_image_b64,
                "trend_image_filename": trend_image_filename,
                "trend_image_description": trend_image_description,
            }

    return trend_agent_node
