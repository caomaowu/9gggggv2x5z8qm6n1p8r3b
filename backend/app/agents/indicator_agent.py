"""
Agent for technical indicator analysis in high-frequency trading (HFT) context.
现在直接系统调用计算技术指标，然后让LLM分析结果，避免昂贵的LLM工具调用。
"""

import copy
import json

from langchain_core.messages import ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

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


@performance_monitor("技术指标智能体")
def create_indicator_agent(llm, toolkit):
    """
    Create an indicator analysis agent node for HFT.
    现在直接系统调用计算技术指标，然后让LLM分析结果，避免昂贵的LLM工具调用。
    """

    @performance_monitor("技术指标智能体执行")
    def indicator_agent_node(state):
        # 哈雷酱的进度跟踪！
        update_agent_progress("indicator", 10, "正在启动技术指标分析智能体...")

        kline_data = state["kline_data"]
        time_frame = state["time_frame"]

        # --- 直接系统调用计算所有技术指标 ---
        update_agent_progress("indicator", 30, "正在计算技术指标数据...")

        try:
            # 直接调用工具计算技术指标，避免LLM工具调用
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

            update_agent_progress("indicator", 60, "正在生成技术指标分析报告...")

        except Exception as e:
            update_agent_progress("indicator", 100, "技术指标计算失败")
            return {
                "messages": state.get("messages", []),
                "indicator_report": f"技术指标计算失败: {str(e)}",
                "error": str(e)
            }

        # --- 提取最新价格信息 ---
        latest_price = None
        # 兼容 list of dicts (Record-oriented) 和 dict of lists (Column-oriented) 格式
        if isinstance(kline_data, list) and len(kline_data) > 0:
            # Record-oriented: [{'Close': 100}, ...]
            latest_price = kline_data[-1].get("Close")
        elif isinstance(kline_data, dict) and "Close" in kline_data and len(kline_data["Close"]) > 0:
            # Column-oriented: {'Close': [100, ...]}
            latest_price = kline_data["Close"][-1]

        # --- 将计算结果整理为结构化文本供LLM分析 ---
        # 转义JSON花括号避免LangChain模板变量解析问题
        macd_json = json.dumps(indicator_results.get("MACD", {}), indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")
        rsi_json = json.dumps(indicator_results.get("RSI", {}), indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")
        roc_json = json.dumps(indicator_results.get("ROC", {}), indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")
        stoch_json = json.dumps(indicator_results.get("Stochastic", {}), indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")
        willr_json = json.dumps(indicator_results.get("Williams_R", {}), indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")

        # 转义完整的OHLC数据
        ohlc_data_json = json.dumps(kline_data, indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")

        price_info = f"当前最新收盘价: {latest_price}\n\n" if latest_price else ""

        # 哈雷酱的灵魂增强！营造真实交易环境
        indicators_text = f"""
⚡ **华尔街交易室 - 实时技术分析**
交易对：{state.get('stock_name', '未知')} | 时间框架：{time_frame}
分析时间：{kline_data.get('Datetime', ['未知'])[-1] if 'Datetime' in kline_data and len(kline_data['Datetime']) > 0 else '实时'}

💰 **当前价位**：{latest_price if latest_price else '未知'}
{price_info}

## 📊 **完整OHLC历史数据**
{ohlc_data_json}

🎯 **关键指标雷达扫描完成** - 已为你筛选出最重要的技术信号：

### 🔥 MACD指标 - 趋势追踪器
{macd_json}

### ⚡ RSI指标 - 超买超卖警报器
{rsi_json}

### 📈 ROC指标 - 动能加速器
{roc_json}

### 🌊 Stochastic指标 - 震荡捕手
{stoch_json}

### 🎯 Williams %R指标 - 极端探测器
{willr_json}

---

## 🏦 **交易分析师紧急指令**

"你是一名专业的加密货币交易技术分析总监，擅长基于预计算的技术指标数据进行快速准确的交易分析。"        
"你需要深入分析各种技术指标的数值、趋势和信号，为交易决策提供专业建议。"
"在总结处，你要给出当前的最新价格"

### 🎭 **你的性格设定**：
- **直觉敏锐**：能从数字中嗅出贪婪与恐惧
- **决策果断**：在模糊中寻找确定性信号
- **语言犀利**：用最少的文字表达最核心的观点
- **风险偏执**：永远先考虑最坏情况的保护措施

### ⚡ **紧急分析任务**：
基于完整OHLC历史数据和上述指标，进行实战化分析：

#### 🎯 **核心判断**（1句话）：
- 当前技术面处于什么状态？用最精炼的词语总结

#### 🔥 **关键指标解读**（从所有指标中识别最重要信号）：
- 基于当前市场环境，哪些指标给出了最强烈的信号？
- 分析所有指标的相互印证或矛盾关系
- 从实战经验判断各信号的可信度和优先级

#### 💥 **交易信号识别**：
- 明确给出：**做多** / **做空** / **观望**
- 信号强度：**强** / **中** / **弱**
- 时效性：**立即** / **等待确认** / **短期观察**

#### ⚠️ **风险预警**：
- 当前最大的风险点在哪里？
- 如果判断错误，最大的潜在损失是多少？
- 什么情况下需要立即止损？

#### 🌟 **专业建议**：
- 如果这是你的实盘账户，你会怎么操作？
- 仓位大小建议（保守/中等/激进）
- 持有时间预期（短线/中线/长线）

### 🎪 **分析自由度**：
- ✅ 可以用交易员黑话（"金叉"、"死叉"、"背离"、"破位"）
- ✅ 可以用表情符号增强表达（📈📉⚠️🎯💰）
- ✅ 可以质疑某些指标在当前市场的有效性
- ✅ 可以基于经验给出非常规但有逻辑的判断
- ✅ 可以忽略在当前环境下不重要的指标
- ✅ 可以用"以我10年经验..."来强调专业观点

### 🔥 **核心要求**：
- **不要死板罗列数据**，要给出你的**专业判断**
- **避免教科书式分析**，这是**真实交易战场**
- **强调时效性**，分析**当前时机的交易价值**
- **保持专业个性**，展现你的**交易风格和直觉**

💡 **记住**：我们需要你的**专业分析智慧**，不是简单的数据复述！
开始你的专业分析，技术分析专家！
"""

        # --- LLM分析预计算的指标结果 ---
        analysis_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """你是量化交易公司的首席技术分析师，拥有10年加密货币市场经验。

🎯 **你的分析风格**：
- 专业严谨，数据驱动分析
- 注重风险管理，每个观点都考虑保护措施  
- 可以适当使用交易员术语（金叉、死叉、背离等）
- 语言简洁有力，直击要点
- 可以用表情符号增强表达（📈📉⚠️🎯💰）

📊 **分析要求**：
1. **核心判断**（1句话总结当前技术面状态）
2. **关键信号分析**（从所有指标中识别最重要的信号）
3. **交易建议**（做多/做空/观望 + 强度评估：强/中/弱）
4. **风险提示**（止损位和潜在损失）
5. **操作建议**（仓位大小和持有时间）

⚡ **重要提醒**：
- 基于完整OHLC历史数据和所有技术指标进行综合判断
- 你需要自己判断哪些指标在当前市场环境下最重要
- 强调时效性，给出当前时点的具体判断
- 避免死板的数据罗列，重点是专业判断和实战建议

记住：这是真实的市场分析，每个判断都可能影响实际交易决策！"""
            ),
            ("human", indicators_text)
        ])

        chain = analysis_prompt | llm
        final_response = chain.invoke({})

        update_agent_progress("indicator", 100, "技术指标分析完成")
        return {
            "messages": state.get("messages", []) + [final_response],
            "indicator_report": final_response.content,
            "indicator_data": indicator_results,  # 保存原始指标数据供后续使用
            "latest_price": latest_price,        # 哈雷酱添加：保存最新价格到状态中
            "price_info": price_info             # 哈雷酱添加：保存价格信息
        }

    return indicator_agent_node