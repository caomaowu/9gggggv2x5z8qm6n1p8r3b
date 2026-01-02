import copy
import json
import time

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

        pattern_text = """
        请参考以下经典K线形态：

        1. 倒头肩形：三个低点，中间最低，对称结构，通常预示上涨趋势
        2. 双重底：两个相似低点，中间反弹，形成'W'形状
        3. 圆形底：价格逐渐下跌后逐渐上涨，形成'U'形状
        4. 潜伏底：水平整理后突然向上突破
        5. 下降楔形：价格向下收窄，通常向上突破
        6. 上升楔形：价格缓慢上涨但收敛，经常向下突破
        7. 上升三角形：上升支撑线，顶部水平阻力，通常向上突破
        8. 下降三角形：下降阻力线，底部水平支撑，通常向下突破
        9. 牛市旗形：急涨后短暂向下整理，继续上涨
        10. 熊市旗形：急跌后短暂向上整理，继续下跌
        11. 矩形：价格在水平支撑和阻力间波动
        12. 岛形反转：两个相反方向的价格缺口，形成孤立价格岛屿
        13. V形反转：急跌后急涨，或相反
        14. 圆形顶/底：逐渐见顶或见底，形成弧形形态
        15. 扩张三角形：高点和低点越来越宽，显示剧烈波动
        16. 对称三角形：高点和低点向顶点收敛，通常后有突破
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
        image_prompt = [
            {
                "type": "text",
                "text": (
                    f"这是一张根据最近OHLC市场数据生成的{time_frame}K线图表。\n\n"
                    f"{pattern_text}\n\n"
                    "请确定图表是否匹配所列出的任何经典形态。"
                    "明确说出匹配的形态名称，并基于结构、趋势和对称性解释你的分析理由。请用中文回答。"
                    "并做出你的未来预测，是否会有进一步的趋势发展。"
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
                SystemMessage(content="你是一名专业的交易形态识别助手，任务是分析K线图表。"),
                HumanMessage(content=image_prompt),
            ],
        )

        update_agent_progress("pattern", 100, "模式识别分析完成")
        return {
            "messages": state.get("messages", []) + [final_response],
            "pattern_report": final_response.content,
            "pattern_image": pattern_image_b64,  # 保存图像供后续使用
        }

    return pattern_agent_node
