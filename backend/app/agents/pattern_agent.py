import copy
import json
import time
import pandas as pd

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
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
    """将 DataFrame 或 list 转换为 list[dict] 格式供图表工具调用"""
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


def invoke_tool_with_retry(tool_fn, tool_args, retries=3, wait_sec=4):
    """
    Invoke a tool function with retries if the result is missing an image.
    """
    for attempt in range(retries):
        result = tool_fn.invoke(tool_args)
        img_b64 = result.get("pattern_image")
        if img_b64:
            return result
        print(
            f"Tool returned no image, retrying in {wait_sec}s (attempt {attempt + 1}/{retries})..."
        )
        time.sleep(wait_sec)
    raise RuntimeError("Tool failed to generate image after multiple retries")


@performance_monitor("模式识别智能体")
def create_pattern_agent(tool_llm, graph_llm, toolkit):
    """
    Create a pattern recognition agent node for candlestick pattern analysis.
    现在直接生成K线图，然后让LLM分析，不再通过工具调用。
    """

    @performance_monitor("模式识别智能体执行")
    def pattern_agent_node(state):
        # 哈雷酱的进度跟踪！
        update_agent_progress("pattern", 10, "正在启动模式识别智能体...")

        kline_data = state["kline_data"]
        time_frame = state["time_frame"]
        
        # ✅ 检测是否为多时间框架模式
        is_multi_tf = isinstance(kline_data, dict) and not any(
            key in ['Open', 'High', 'Low', 'Close', 'Volume', 'Datetime'] 
            for key in kline_data.keys()
        )
        
        if is_multi_tf:
            print(f"⚡ 多时间框架模式：检测到 {len(kline_data)} 个时间框架 - {list(kline_data.keys())}")
        else:
            print(f"🔹 单一时间框架模式：{time_frame}")

        pattern_text = """
        Please refer to the following classic candlestick patterns:

        1. Inverse Head and Shoulders: Three lows with the middle one being the lowest, symmetrical structure, typically indicates an upcoming upward trend.
        2. Double Bottom: Two similar low points with a rebound in between, forming a 'W' shape.
        3. Rounded Bottom: Gradual price decline followed by a gradual rise, forming a 'U' shape.
        4. Hidden Base: Horizontal consolidation followed by a sudden upward breakout.
        5. Falling Wedge: Price narrows downward, usually breaks out upward.
        6. Rising Wedge: Price rises slowly but converges, often breaks down.
        7. Ascending Triangle: Rising support line with a flat resistance on top, breakout often occurs upward.
        8. Descending Triangle: Falling resistance line with flat support at the bottom, typically breaks down.
        9. Bullish Flag: After a sharp rise, price consolidates downward briefly before continuing upward.
        10. Bearish Flag: After a sharp drop, price consolidates upward briefly before continuing downward.
        11. Rectangle: Price fluctuates between horizontal support and resistance.
        12. Island Reversal: Two price gaps in opposite directions forming an isolated price island.
        13. V-shaped Reversal: Sharp decline followed by sharp recovery, or vice versa.
        14. Rounded Top / Rounded Bottom: Gradual peaking or bottoming, forming an arc-shaped pattern.
        15. Expanding Triangle: Highs and lows increasingly wider, indicating volatile swings.
        16. Symmetrical Triangle: Highs and lows converge toward the apex, usually followed by a breakout.
        """

        # --- 重试包装器 ---
        def invoke_with_retry(call_fn, *args, retries=3, wait_sec=8):
            for attempt in range(retries):
                try:
                    return call_fn(*args)
                except RateLimitError:
                    print(f"API限速，{wait_sec}秒后重试 (尝试 {attempt + 1}/{retries})...")
                    time.sleep(wait_sec)
                except Exception as e:
                    print(f"其他错误: {e}，{wait_sec}秒后重试 (尝试 {attempt + 1}/{retries})...")
                    time.sleep(wait_sec)
            raise RuntimeError("超过最大重试次数")

        # --- 直接生成K线图，不通过LLM工具调用 ---
        
        if is_multi_tf:
            # ✅ 多时间框架模式：循环生成多张图表
            multi_tf_images = {}
            
            try:
                for idx, (tf_name, tf_data) in enumerate(kline_data.items()):
                    progress = 20 + int((30 / len(kline_data)) * idx)
                    update_agent_progress("pattern", progress, f"正在生成 {tf_name} K线图表...")
                    
                    print(f"📊 正在生成 {tf_name} 时间框架的K线图...")
                    
                    # 转换数据格式
                    tf_data_list = convert_to_list_of_dicts(tf_data)
                    
                    # 生成图表（带重试机制）
                    max_retries = 3
                    wait_sec = 2
                    chart_result = None
                    
                    for attempt in range(max_retries):
                        try:
                            chart_result = toolkit.generate_kline_image.invoke({
                                "kline_data": copy.deepcopy(tf_data_list)
                            })
                            if chart_result and chart_result.get("pattern_image"):
                                break
                            print(f"图表生成无结果，{wait_sec}秒后重试 (尝试 {attempt + 1}/{max_retries})...")
                            if attempt < max_retries - 1:
                                time.sleep(wait_sec)
                        except Exception as e:
                            print(f"图表生成出错: {e}，{wait_sec}秒后重试 (尝试 {attempt + 1}/{max_retries})...")
                            if attempt < max_retries - 1:
                                time.sleep(wait_sec)
                    
                    if not chart_result or not chart_result.get("pattern_image"):
                        print(f"⚠️ {tf_name} 图表生成失败，跳过该时间框架")
                        continue
                    
                    multi_tf_images[tf_name] = chart_result.get("pattern_image")
                    print(f"✅ {tf_name} K线图生成成功")
                
                if not multi_tf_images:
                    raise RuntimeError("所有时间框架的图表生成均失败")
                    
                update_agent_progress("pattern", 60, "正在分析多时间框架K线图表...")
                
            except Exception as e:
                update_agent_progress("pattern", 100, "K线图表生成失败")
                return {
                    "messages": state.get("messages", []),
                    "pattern_report": f"K线图表生成失败: {str(e)}",
                    "error": str(e)
                }
        else:
            # ✅ 单一时间框架模式：保持原有逻辑
            update_agent_progress("pattern", 30, "正在生成K线图表...")

            try:
                # 直接调用图表生成工具，带重试机制
                max_retries = 3
                wait_sec = 2
                chart_result = None

                for attempt in range(max_retries):
                    try:
                        chart_result = toolkit.generate_kline_image.invoke({"kline_data": copy.deepcopy(kline_data)})
                        if chart_result and chart_result.get("pattern_image"):
                            break
                        print(f"图表生成无结果，{wait_sec}秒后重试 (尝试 {attempt + 1}/{max_retries})...")
                        if attempt < max_retries - 1:
                            time.sleep(wait_sec)
                    except Exception as e:
                        print(f"图表生成出错: {e}，{wait_sec}秒后重试 (尝试 {attempt + 1}/{max_retries})...")
                        if attempt < max_retries - 1:
                            time.sleep(wait_sec)

                if not chart_result or not chart_result.get("pattern_image"):
                    raise RuntimeError("图表生成失败，超过最大重试次数")

                pattern_image_b64 = chart_result.get("pattern_image")

                update_agent_progress("pattern", 60, "正在分析K线图表模式...")

            except Exception as e:
                update_agent_progress("pattern", 100, "K线图表生成失败")
                return {
                    "messages": state.get("messages", []),
                    "pattern_report": f"K线图表生成失败: {str(e)}",
                    "error": str(e)
                }

        # --- 使用图像进行视觉分析 ---
        if is_multi_tf:
            # ✅ Multi-timeframe mode: Build multi-image analysis prompt
            image_content = [
                {
                    "type": "text",
                    "text": (
                        f"🌐 **Multi-Timeframe Pattern Recognition Analysis**\n"
                        f"Trading Pair: {state.get('stock_name', 'Unknown')} | Analysis Period: {time_frame}\n\n"
                        f"I have provided {len(multi_tf_images)} timeframes' candlestick charts: {', '.join(multi_tf_images.keys())}\n\n"
                        f"{pattern_text}\n\n"
                        "📋 **Analysis Requirements**:\n"
                        "1. Identify pattern characteristics for each timeframe separately\n"
                        "2. Look for multi-timeframe confluence signals (e.g., same pattern appearing across multiple timeframes)\n"
                        "3. Identify timeframe divergences (conflicting patterns between long and short timeframes)\n"
                        "4. Provide comprehensive judgment: Long timeframes determine direction, short timeframes determine entry points\n"
                        "5. Clearly state pattern names and explain your reasoning based on structure, trend, and symmetry\n\n"
                        "Please provide a detailed answer in clear format."
                    ),
                }
            ]
            
            # Add charts for all timeframes
            for tf_name, img_b64 in multi_tf_images.items():
                image_content.append({
                    "type": "text",
                    "text": f"\n--- **{tf_name} Timeframe K-line Chart** ---"
                })
                image_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                })
        else:
            # ✅ Single timeframe mode: Original English prompt
            image_content = [
                {
                    "type": "text",
                    "text": (
                        f"This is a {time_frame} candlestick chart generated from recent OHLC market data.\n\n"
                        f"{pattern_text}\n\n"
                        "Determine whether the chart matches any of the classic patterns listed above. "
                        "Clearly state the matched pattern name(s), and explain your reasoning based on structure, trend, and symmetry. "
                        "Also provide your future prediction on whether there will be further trend development."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{pattern_image_b64}"},
                },
            ]

        final_response = invoke_with_retry(
            graph_llm.invoke,
            [
                SystemMessage(content="You are a trading pattern recognition assistant tasked with analyzing candlestick charts. You specialize in multi-timeframe comprehensive analysis."),
                HumanMessage(content=image_content),
            ],
        )

        update_agent_progress("pattern", 100, "模式识别分析完成")
        
        if is_multi_tf:
            return {
                "messages": state.get("messages", []) + [final_response],
                "pattern_report": final_response.content,
                "pattern_images": multi_tf_images,  # ✅ 多张图表的字典
                "multi_timeframe_mode": True,
                "timeframes": list(multi_tf_images.keys())
            }
        else:
            return {
                "messages": state.get("messages", []) + [final_response],
                "pattern_report": final_response.content,
                "pattern_image": pattern_image_b64,  # ✅ 单张图表（向后兼容）
            }

    return pattern_agent_node
