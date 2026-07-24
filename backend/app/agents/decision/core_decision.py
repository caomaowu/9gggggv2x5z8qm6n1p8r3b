"""
决策智能体核心逻辑 (Core Decision Agent Logic)
提取了不同版本决策智能体的公共逻辑，减少代码重复。
"""

import sys
import json
import re
from pathlib import Path

from app.utils.llm_compat import invoke_llm_text
from app.utils.prompt_template import render_prompt_template

# L4: 确定性弃权门槛。edge_score 低于该值或制度为 HIGH_VOL/UNKNOWN 时强制 HOLD。
# 阀值集中在此，便于后续在验证集上按期望值调参。
EDGE_ABSTAIN_THRESHOLD = 0.25


def _extract_decision_json(text: str):
    """从 LLM 输出中提取决策 JSON，失败返回 None。"""
    if not text or not str(text).strip():
        return None
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    idx = text.find("{")
    if idx >= 0:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[idx:])
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _apply_edge_gate(content: str, edge_score: float, regime: str):
    """
    L4 确定性弃权：若无可衡量优势，将方向性决策强制改为 HOLD。
    只会将 LONG/SHORT 降为 HOLD，绝不会凭空制造交易。返回 (新content, 是否已门槛)。
    """
    try:
        should_gate = (
            regime in ("HIGH_VOL", "UNKNOWN")
            or (edge_score is not None and edge_score < EDGE_ABSTAIN_THRESHOLD)
        )
        if not should_gate:
            return content, False
        obj = _extract_decision_json(content)
        if not obj:
            return content, False
        decision = str(obj.get("decision", "")).upper().strip()
        if decision not in ("LONG", "SHORT"):
            return content, False
        note = (
            f"[Edge gate] Forced HOLD: edge_score={edge_score}, regime={regime} "
            f"(below {EDGE_ABSTAIN_THRESHOLD} threshold / no reliable structure). "
        )
        obj["decision"] = "HOLD"
        obj["confidence_level"] = "\u4f4e"
        obj["justification"] = (note + str(obj.get("justification", "")))[:2000]
        new_content = "```json\n" + json.dumps(obj, ensure_ascii=False, indent=2) + "\n```"
        return new_content, True
    except Exception:
        return content, False

try:
    from app.core.progress import update_agent_progress
except ImportError:
    # 如果导入失败，使用空函数避免破坏
    def update_agent_progress(agent_name, progress_within_agent=0, status=""):
        pass

# 性能监控系统！
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

def create_generic_decision_agent(llm, prompt_template: str, agent_name: str, agent_version: str = None):
    """
    创建通用的决策智能体
    
    Args:
        llm: LLM 实例
        prompt_template: Prompt 模板字符串，需要包含以下占位符：
            {stock_name}, {time_frame}, {price_summary}, {price_info_str}, 
            {latest_price_str},
            {indicator_report}, {pattern_report}, {trend_report}
        agent_name: 智能体名称（用于日志和监控）
        agent_version: 版本标识（可选）
        
    Returns:
        trade_decision_node 函数
    """
    
    @performance_monitor(agent_name)
    def trade_decision_node(state) -> dict:
        # 1. 进度更新
        update_agent_progress("decision", 10, f"正在启动{agent_name}...")
        
        # ✅ 检测是否为多时间框架模式
        is_multi_tf = state.get("multi_timeframe_mode", False)
        timeframes = state.get("timeframes", [])
        
        if is_multi_tf and timeframes:
            print(f"⚡ 多时间框架决策模式：{len(timeframes)} 个时间框架 - {timeframes}")
        else:
            print(f"🔹 单一时间框架决策模式")
        
        # 2. Extract basic data
        indicator_report = state.get("indicator_report", "Technical indicator analysis unavailable")
        pattern_report = state.get("pattern_report", "Pattern analysis unavailable")
        trend_report = state.get("trend_report", "Trend analysis unavailable")
        time_frame = state.get("time_frame", "Unknown")
        stock_name = state.get("stock_name", "Unknown trading pair")
        
        latest_price = state.get("latest_price", None)
        price_info = state.get("price_info", "")

        # Regime context (L1) injected by the Regime Analyzer node
        regime = state.get("regime", "UNKNOWN")
        regime_direction = state.get("regime_direction", "NONE")
        regime_report = state.get("regime_report", "Regime analysis unavailable")
        edge_score = state.get("edge_score", 0.0)
        try:
            edge_score = float(edge_score)
        except (TypeError, ValueError):
            edge_score = 0.0
        
        # 3. Data preprocessing
        if latest_price is not None:
            price_summary = f"Current {stock_name} latest price: {latest_price}"
            latest_price_str = str(latest_price)
        else:
            price_summary = f"Warning: Unable to retrieve current price for {stock_name}"
            latest_price_str = "Unknown"
            
        price_info_str = price_info if price_info else ""
        
        # 4. Error handling and logging
        analysis_errors = []
        if indicator_report and isinstance(indicator_report, dict) and "error" in indicator_report:
            analysis_errors.append(f"Technical indicator analysis failed: {indicator_report['error']}")
            indicator_report = "Technical indicator analysis failed"
        elif indicator_report is None:
            analysis_errors.append("Technical indicator analysis unavailable (None)")
            indicator_report = "Technical indicator analysis unavailable"

        if pattern_report and isinstance(pattern_report, dict) and "error" in pattern_report:
            analysis_errors.append(f"Pattern analysis failed: {pattern_report['error']}")
            pattern_report = "Pattern analysis failed"
        elif pattern_report is None:
            analysis_errors.append("Pattern analysis unavailable (None)")
            pattern_report = "Pattern analysis unavailable"

        if trend_report and isinstance(trend_report, dict) and "error" in trend_report:
            analysis_errors.append(f"Trend analysis failed: {trend_report['error']}")
            trend_report = "Trend analysis failed"
        elif trend_report is None:
            analysis_errors.append("Trend analysis unavailable (None)")
            trend_report = "Trend analysis unavailable"

        print(f"🧠 {agent_name} 收到分析结果，正在为 {stock_name} ({time_frame}) 进行分析...")
        print(f"💰 当前价格信息: {price_summary}")
        
        # 5. 构建 Prompt
        # 仅替换允许的占位符，保留 JSON 示例中的普通花括号不变。
        try:
            prompt = render_prompt_template(
                prompt_template,
                stock_name=stock_name,
                time_frame=time_frame,
                price_summary=price_summary,
                price_info_str=price_info_str,
                latest_price_str=latest_price_str,
                indicator_report=indicator_report,
                pattern_report=pattern_report,
                trend_report=trend_report,
                regime=regime,
                regime_direction=regime_direction,
                edge_score=edge_score,
                regime_report=regime_report,
            )
        except KeyError as e:
            print(f"❌ Prompt 格式化错误: 缺少键值 {e}")
            prompt = f"Prompt Error: {e}"
        except Exception as e:
            print(f"❌ Prompt 格式化发生未知错误: {e}")
            prompt = f"Prompt Error: {e}"

        # 6. Call LLM
        update_agent_progress("decision", 80, f"正在生成{agent_name}决策...")
        
        try:
            content = invoke_llm_text(llm, prompt)
        except Exception as e:
            print(f"❌ LLM 调用失败: {e}")
            content = f'{{"error": "LLM call failed: {str(e)}", "decision": "HOLD"}}'
            # Construct a fake response object to maintain interface consistency
            from langchain_core.messages import AIMessage
            response = AIMessage(content=content)
        else:
            from langchain_core.messages import AIMessage
            response = AIMessage(content=content)

        # L4: 确定性 edge 门槛（规则化弃权，不依赖 LLM 自觉）
        content, _gated = _apply_edge_gate(content, edge_score, regime)
        if _gated:
            from langchain_core.messages import AIMessage
            response = AIMessage(content=content)
            print(f"⚖️ edge 门槛触发：已强制 HOLD (edge={edge_score}, regime={regime})")

        update_agent_progress("decision", 100, f"{agent_name}决策生成完成")
        
        # 7. 返回结果
        result = {
            "final_trade_decision": content,
            "messages": [response],
            "decision_prompt": prompt,
        }
        
        if agent_version:
            result["agent_version"] = agent_version
        
        # ✅ 添加多时间框架标识
        if is_multi_tf:
            result["multi_timeframe_mode"] = True
            result["timeframes"] = timeframes
            
        return result

    return trade_decision_node
