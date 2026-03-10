"""
决策智能体核心逻辑 (Core Decision Agent Logic)
提取了不同版本决策智能体的公共逻辑，减少代码重复。
"""

import sys
from pathlib import Path

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
        # 使用 safe_format 避免模板中存在的其他花括号导致报错（如 JSON 示例中的花括号）
        # 但通常我们使用双花括号 {{ }} 来转义，所以直接 format 应该没问题，前提是模板里的 JSON 示例已经转义
        try:
            prompt = prompt_template.format(
                stock_name=stock_name,
                time_frame=time_frame,
                price_summary=price_summary,
                price_info_str=price_info_str,
                latest_price_str=latest_price_str,
                indicator_report=indicator_report,
                pattern_report=pattern_report,
                trend_report=trend_report
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
            response = llm.invoke(prompt)
            content = response.content
        except Exception as e:
            print(f"❌ LLM 调用失败: {e}")
            content = f'{{"error": "LLM call failed: {str(e)}", "decision": "HOLD"}}'
            # Construct a fake response object to maintain interface consistency
            from langchain_core.messages import AIMessage
            response = AIMessage(content=content)

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
