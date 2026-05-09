"""
决策智能体核心逻辑 (Core Decision Agent Logic)
brale-core migration: accepts structured JSON instead of free-text reports.
"""

import json
import sys
from pathlib import Path

from app.utils.llm_compat import invoke_llm_text
from app.utils.prompt_template import render_prompt_template

try:
    from app.core.progress import update_agent_progress
except ImportError:
    def update_agent_progress(agent_name, progress_within_agent=0, status=""):
        pass

try:
    from app.utils.performance import performance_monitor, monitor_llm_call
except ImportError:
    def performance_monitor(stage_name=None):
        def decorator(func):
            return func
        return decorator
    def monitor_llm_call(model_name=None):
        return performance_monitor(f"LLM调用: {model_name}" if model_name else "LLM调用")


def _format_brale_data(state, latest_price, stock_name) -> dict:
    """Extract brale structured data and format into prompt-compatible strings."""
    fusion = state.get("fusion_result") or {}
    indicator = state.get("indicator_summary") or {}
    structure = state.get("structure_summary") or {}
    mechanics = state.get("mechanics_summary") or {}

    # Build structured report strings
    indicator_report = json.dumps(indicator, ensure_ascii=False, indent=2) if indicator else ""
    pattern_report = json.dumps(structure, ensure_ascii=False, indent=2) if structure else ""
    trend_report = json.dumps(mechanics, ensure_ascii=False, indent=2) if mechanics else ""

    fusion_text = json.dumps(fusion, ensure_ascii=False, indent=2) if fusion else ""

    # Price summary
    if latest_price is not None:
        price_summary = f"Current {stock_name} latest price: {latest_price}"
        latest_price_str = str(latest_price)
    else:
        price_summary = f"Warning: Unable to retrieve current price for {stock_name}"
        latest_price_str = "Unknown"

    return {
        "indicator_report": indicator_report or "Indicator analysis unavailable",
        "pattern_report": pattern_report or "Structure analysis unavailable",
        "trend_report": trend_report or "Mechanics analysis unavailable",
        "fusion_text": fusion_text,
        "price_summary": price_summary,
        "latest_price_str": latest_price_str,
    }


def create_generic_decision_agent(llm, prompt_template: str, agent_name: str, agent_version: str = None):
    """
    创建通用的决策智能体 (brale migration: accepts structured JSON input).

    Supports placeholders:
        {stock_name}, {time_frame}, {price_summary}, {price_info_str},
        {latest_price_str},
        {indicator_report}, {pattern_report}, {trend_report},
        {fusion_text}  (NEW: brale consensus fusion result)
    """

    @performance_monitor(agent_name)
    def trade_decision_node(state) -> dict:
        update_agent_progress("decision", 10, f"正在启动{agent_name}...")

        is_multi_tf = state.get("multi_timeframe_mode", False)
        timeframes = state.get("timeframes", [])

        if is_multi_tf and timeframes:
            print(f"⚡ 多时间框架决策模式：{len(timeframes)} 个时间框架 - {timeframes}")
        else:
            print(f"🔹 单一时间框架决策模式")

        time_frame = state.get("time_frame", "Unknown")
        stock_name = state.get("stock_name", "Unknown trading pair")
        latest_price = state.get("latest_price", None)
        price_info = state.get("price_info", "")

        # Format brale structured data
        fmt = _format_brale_data(state, latest_price, stock_name)

        print(f"🧠 {agent_name} 为 {stock_name} ({time_frame}) 进行决策...")
        print(f"💰 price: {fmt['price_summary']}")

        try:
            prompt = render_prompt_template(
                prompt_template,
                stock_name=stock_name,
                time_frame=time_frame,
                price_summary=fmt["price_summary"],
                price_info_str=price_info or "",
                latest_price_str=fmt["latest_price_str"],
                indicator_report=fmt["indicator_report"],
                pattern_report=fmt["pattern_report"],
                trend_report=fmt["trend_report"],
                fusion_text=fmt["fusion_text"],
            )
        except KeyError as e:
            print(f"❌ Prompt formatting error: missing key {e}")
            prompt = f"Prompt Error: {e}"
        except Exception as e:
            print(f"❌ Prompt formatting unknown error: {e}")
            prompt = f"Prompt Error: {e}"

        update_agent_progress("decision", 80, f"正在生成{agent_name}决策...")

        try:
            content = invoke_llm_text(llm, prompt)
        except Exception as e:
            print(f"❌ LLM call failed: {e}")
            content = f'{{"error": "LLM call failed: {str(e)}", "decision": "HOLD"}}'
            from langchain_core.messages import AIMessage
            response = AIMessage(content=content)
        else:
            from langchain_core.messages import AIMessage
            response = AIMessage(content=content)

        update_agent_progress("decision", 100, f"{agent_name}决策生成完成")

        result = {
            "final_trade_decision": content,
            "messages": [response],
            "decision_prompt": prompt,
        }

        if agent_version:
            result["agent_version"] = agent_version

        if is_multi_tf:
            result["multi_timeframe_mode"] = True
            result["timeframes"] = timeframes

        return result

    return trade_decision_node
