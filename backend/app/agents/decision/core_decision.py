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

def create_generic_decision_agent(llm, prompt_template: str, agent_name: str, agent_version: str = None):
    """
    创建通用的决策智能体
    
    Args:
        llm: LLM 实例
        prompt_template: Prompt 模板字符串，需要包含以下占位符：
            {stock_name}, {time_frame}, {price_summary}, {price_info_str}, 
            {custom_instructions}, {latest_price_str},
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
        
        # 2. 提取基础数据
        indicator_report = state.get("indicator_report", "技术指标分析不可用")
        pattern_report = state.get("pattern_report", "形态分析不可用")
        trend_report = state.get("trend_report", "趋势分析不可用")
        time_frame = state.get("time_frame", "未知")
        stock_name = state.get("stock_name", "未知交易对")
        
        latest_price = state.get("latest_price", None)
        price_info = state.get("price_info", "")
        custom_prompt = state.get("custom_prompt", None)
        
        # 3. 数据预处理
        if latest_price is not None:
            price_summary = f"当前{stock_name}最新价格: {latest_price}"
            latest_price_str = str(latest_price)
        else:
            price_summary = f"警告：无法获取{stock_name}的当前价格信息"
            latest_price_str = "未知"
            
        price_info_str = price_info if price_info else ""
        
        custom_instructions = ""
        if custom_prompt:
            custom_instructions = f"**User Custom Instructions / Position Context:**\n{custom_prompt}\n"
            # 兼容中文提示
            custom_instructions = custom_instructions.replace("User Custom Instructions", "用户特别指令")
            
        # 4. 错误处理与日志
        analysis_errors = []
        if "error" in indicator_report and isinstance(indicator_report, dict):
            analysis_errors.append(f"技术指标分析失败: {indicator_report['error']}")
            indicator_report = "技术指标分析失败"

        if "error" in pattern_report and isinstance(pattern_report, dict):
            analysis_errors.append(f"形态分析失败: {pattern_report['error']}")
            pattern_report = "形态分析失败"

        if "error" in trend_report and isinstance(trend_report, dict):
            analysis_errors.append(f"趋势分析失败: {trend_report['error']}")
            trend_report = "趋势分析失败"

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
                custom_instructions=custom_instructions,
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

        # 6. 调用 LLM
        update_agent_progress("decision", 80, f"正在生成{agent_name}决策...")
        
        try:
            response = llm.invoke(prompt)
            content = response.content
        except Exception as e:
            print(f"❌ LLM 调用失败: {e}")
            content = f'{{"error": "LLM调用失败: {str(e)}", "decision": "观望"}}'
            # 构造一个伪造的 response 对象以保持接口一致性
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
            
        return result

    return trade_decision_node
