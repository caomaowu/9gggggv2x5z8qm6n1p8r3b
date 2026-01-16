"""
Agent for trend analysis in high-frequency trading (HFT) context.
Uses LLM and toolkit to generate and interpret trendline charts for short-term prediction.
"""

import json
import time
import copy
import pandas as pd

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
    现在直接生成趋势图，然后让LLM分析，不再通过工具调用。
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

        # --- 直接生成趋势图和计算指标 ---
        
        if is_multi_tf:
            # ✅ 多时间框架模式：循环生成多张趋势图和多组指标
            multi_tf_trends = {}  # 存储每个时间框架的趋势图和指标
            
            try:
                for idx, (tf_name, tf_data) in enumerate(kline_data.items()):
                    progress = 20 + int((50 / len(kline_data)) * idx)
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
                    
                    # 计算该时间框架的技术指标
                    print(f"📊 正在计算 {tf_name} 的技术指标...")
                    indicator_results = {}
                    
                    try:
                        macd_result = toolkit.compute_macd.invoke({"kline_data": copy.deepcopy(tf_data_list)})
                        indicator_results["MACD"] = macd_result
                    except Exception as e:
                        print(f"MACD计算失败 ({tf_name}): {e}")
                        indicator_results["MACD"] = {"error": str(e)}
                    
                    try:
                        rsi_result = toolkit.compute_rsi.invoke({"kline_data": copy.deepcopy(tf_data_list)})
                        indicator_results["RSI"] = rsi_result
                    except Exception as e:
                        print(f"RSI计算失败 ({tf_name}): {e}")
                        indicator_results["RSI"] = {"error": str(e)}
                    
                    try:
                        roc_result = toolkit.compute_roc.invoke({"kline_data": copy.deepcopy(tf_data_list)})
                        indicator_results["ROC"] = roc_result
                    except Exception as e:
                        print(f"ROC计算失败 ({tf_name}): {e}")
                        indicator_results["ROC"] = {"error": str(e)}
                    
                    try:
                        stoch_result = toolkit.compute_stoch.invoke({"kline_data": copy.deepcopy(tf_data_list)})
                        indicator_results["Stochastic"] = stoch_result
                    except Exception as e:
                        print(f"Stochastic计算失败 ({tf_name}): {e}")
                        indicator_results["Stochastic"] = {"error": str(e)}
                    
                    try:
                        willr_result = toolkit.compute_willr.invoke({"kline_data": copy.deepcopy(tf_data_list)})
                        indicator_results["Williams_R"] = willr_result
                    except Exception as e:
                        print(f"Williams %R计算失败 ({tf_name}): {e}")
                        indicator_results["Williams_R"] = {"error": str(e)}
                    
                    # 保存该时间框架的所有数据
                    multi_tf_trends[tf_name] = {
                        "trend_image": chart_result.get("trend_image"),
                        "trend_image_filename": chart_result.get("trend_image_filename", f"trend_graph_{tf_name}.png"),
                        "trend_image_description": chart_result.get("trend_image_description", "Trend chart"),
                        "indicators": indicator_results,
                        "ohlc_data": tf_data_list
                    }
                    
                    print(f"✅ {tf_name} 趋势分析数据准备完成")
                
                if not multi_tf_trends:
                    raise RuntimeError("所有时间框架的趋势分析均失败")
                    
                update_agent_progress("trend", 80, "正在生成多时间框架综合分析...")
                
            except Exception as e:
                update_agent_progress("trend", 100, "趋势分析失败")
                return {
                    "messages": [],
                    "trend_report": f"趋势分析失败: {str(e)}",
                    "error": str(e)
                }
        else:
            # ✅ 单一时间框架模式：保持原有逻辑
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

        # --- 使用图像进行视觉分析 ---
        if is_multi_tf:
            # ✅ Multi-timeframe mode: Build multi-timeframe comprehensive analysis prompt
            image_content = [
                {
                    "type": "text",
                    "text": (
                        f"⚠️ **Multi-Timeframe Trend Comprehensive Analysis** ⚠️\n\n"
                        f"Trading Pair: {state.get('stock_name', 'Unknown')} | Analysis Period: {time_frame}\n\n"
                        f"I have provided trend analysis data for {len(multi_tf_trends)} timeframes: {', '.join(multi_tf_trends.keys())}\n\n"
                        f"Each chart contains: **Blue support line** and **Red resistance line**, along with corresponding real technical indicator data.\n\n"
                    )
                }
            ]
            
            # Add charts and indicator data for each timeframe
            for tf_name, tf_info in multi_tf_trends.items():
                indicators_summary = f"""
**📊 {tf_name} Real Technical Indicators:**

### 🔥 MACD Indicator
{json.dumps(tf_info["indicators"].get("MACD", {}), indent=2, ensure_ascii=False)}

### ⚡ RSI Indicator  
{json.dumps(tf_info["indicators"].get("RSI", {}), indent=2, ensure_ascii=False)}

### 📈 ROC Indicator
{json.dumps(tf_info["indicators"].get("ROC", {}), indent=2, ensure_ascii=False)}

### 🌊 Stochastic Indicator
{json.dumps(tf_info["indicators"].get("Stochastic", {}), indent=2, ensure_ascii=False)}

### 🎯 Williams %R Indicator
{json.dumps(tf_info["indicators"].get("Williams_R", {}), indent=2, ensure_ascii=False)}
"""
                
                image_content.append({
                    "type": "text",
                    "text": f"\n\n--- **{tf_name} Timeframe Trend Analysis** ---\n{indicators_summary}"
                })
                image_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{tf_info['trend_image']}"}
                })
            
            # Add multi-timeframe comprehensive analysis requirements
            image_content.append({
                "type": "text",
                "text": (
                    f"\n\n**🎯 Multi-Timeframe Comprehensive Analysis Requirements:**\n"
                    f"1. **Trend Consistency Analysis**: Are trend directions consistent across multiple timeframes?\n"
                    f"2. **Confluence Signal Recognition**: Strong signals appearing simultaneously across multiple timeframes\n"
                    f"3. **Divergence Handling**: Judgment logic when long and short timeframe trends conflict\n"
                    f"4. **Comprehensive Judgment**: Long timeframes determine direction, short timeframes determine entry points\n"
                    f"5. **Key Price Levels**: Support/resistance levels based on multiple timeframe analysis\n"
                    f"6. **Trading Strategy**: Specific operation recommendations based on multi-timeframe analysis\n\n"
                    f"**Format Requirements:**\n"
                    f"- Use ## headings and - bullet points\n"
                    f"- Bold important data\n"
                    f"- Analyze each timeframe separately first, then provide comprehensive judgment\n"
                    f"- Base analysis on real indicator data, avoid speculation\n\n"
                    f"Please provide professional and accurate analysis."
                )
            })
        else:
            # ✅ Single timeframe mode: Original English prompt
            ohlc_data = kline_data if kline_data else state.get("kline_data", {})
            
            indicators_summary = f"""
**📊 Real Calculated Technical Indicator Data:**

### 🔥 MACD Indicator
{json.dumps(indicator_results.get("MACD", {}), indent=2, ensure_ascii=False)}

### ⚡ RSI Indicator  
{json.dumps(indicator_results.get("RSI", {}), indent=2, ensure_ascii=False)}

### 📈 ROC Indicator
{json.dumps(indicator_results.get("ROC", {}), indent=2, ensure_ascii=False)}

### 🌊 Stochastic Indicator
{json.dumps(indicator_results.get("Stochastic", {}), indent=2, ensure_ascii=False)}

### 🎯 Williams %R Indicator
{json.dumps(indicator_results.get("Williams_R", {}), indent=2, ensure_ascii=False)}
"""
            
            image_content = [
                {
                    "type": "text",
                    "text": (
                        f"This candlestick ({time_frame} K-line) chart includes automated trendlines: the **blue line** is support, and the **red line** is resistance, both derived from recent closing prices.\n\n"
                        f"**OHLC Historical Data:**\n"
                        f"{json.dumps(ohlc_data, indent=2, ensure_ascii=False)}\n\n"
                        f"{indicators_summary}\n\n"
                        f"**🎯 Professional Trend Analysis Requirements:**\n"
                        f"1. **Trend Strength Analysis**: Evaluate trendline reliability combined with real technical indicators\n"
                        f"2. **Price Interaction Analysis**: Real interaction between price and support/resistance levels\n"
                        f"3. **Technical Indicator Validation**: Confirm trend signals using real MACD, RSI, etc.\n"
                        f"4. **Momentum Assessment**: Velocity changes from real ROC and Stochastic indicators\n"
                        f"5. **Comprehensive Judgment**: Provide trend prediction based on real calculated data\n\n"
                        f"**Please provide professional analysis based on the above real calculated technical indicator data and chart:**\n"
                        f"- **Trend Direction**: Clearly state upward/downward/sideways\n"
                        f"- **Trend Strength**: Strong/Medium/Weak, with specific rationale\n"
                        f"- **Technical Indicator Signals**: Real MACD golden cross/death cross, RSI overbought/oversold, etc.\n"
                        f"- **Key Price Levels**: Specific values for support and resistance\n"
                        f"- **Short-term Prediction**: Expected price movement for 1-3 candlesticks\n"
                        f"- **Trading Recommendation**: Specific operation strategy\n\n"
                        f"**Format Requirements:**\n"
                        f"Use ## headings and - bullet points, bold important data\n"
                        f"Base analysis on real calculated indicator data, absolutely avoid speculative analysis\n"
                        f"Maintain professionalism and practicality\n\n"
                        f"Please provide professional and accurate analysis."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{trend_image_b64}"},
                },
            ]

        update_agent_progress("trend", 90, "Analyzing trendlines and candlestick patterns...")

        final_response = invoke_with_retry(
            graph_llm.invoke,
            [
                SystemMessage(
                    content="You are a professional quantitative trading trend analyst with extensive market experience. "
                    "Your task is to perform comprehensive analysis combining self-calculated real technical indicator data, OHLC historical data, and trendline charts. "
                    "All technical indicators are real-time calculated through professional tools, not derived data. "
                    "You specialize in multi-timeframe comprehensive analysis and can identify multi-timeframe confluence signals and trend consistency. "
                    "You can select some key indicators for analysis and ignore those you consider unimportant. "
                    "Focus on trend strength validation, technical indicator confirmation, support/resistance level analysis, and short-term trend prediction. "
                    "Provide professional and accurate analysis with specific values and clear judgments. You can use some emojis to enhance visual effect."
                ),
                HumanMessage(content=image_content),  # ✅ Use unified image_content
            ],
        )

        update_agent_progress("trend", 100, "趋势分析完成")
        
        if is_multi_tf:
            return {
                "messages": state.get("messages", []) + [final_response],
                "trend_report": final_response.content,
                "trend_images": {tf: info["trend_image"] for tf, info in multi_tf_trends.items()},  # ✅ 多张图
                "trend_data": multi_tf_trends,  # ✅ 完整数据（图表+指标）
                "multi_timeframe_mode": True,
                "timeframes": list(multi_tf_trends.keys())
            }
        else:
            # 从图表结果中获取实际的文件名
            trend_image_filename = chart_result.get("trend_image_filename", "trend_graph.png") if chart_result else "trend_graph.png"
            trend_image_description = chart_result.get("trend_image_description", "Trend-enhanced candlestick chart with support/resistance lines") if chart_result else "Trend-enhanced candlestick chart with support/resistance lines"
            
            return {
                "messages": state.get("messages", []) + [final_response],
                "trend_report": final_response.content,
                "trend_image": trend_image_b64,  # ✅ 单张图（向后兼容）
                "trend_image_filename": trend_image_filename,
                "trend_image_description": trend_image_description,
            }

    return trend_agent_node
