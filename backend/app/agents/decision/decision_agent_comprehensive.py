"""
综合分析版决策智能体
融合三报告与结构位/波动性依据，直接给出止损止盈，不使用风险回报比
"""

from .core_decision import create_generic_decision_agent

COMPREHENSIVE_PROMPT_TEMPLATE = """你是一名专业的量化交易分析师，正在分析{stock_name}的{time_frame}K线图。请综合技术指标、形态与趋势，直接给出数值型止损与止盈，不得使用或推导任何风险回报比。

当前价格信息：
{price_summary}
{price_info_str}

预测范围说明：
- 例如 TIME_FRAME = 15分钟 → 预测接下来的15分钟
- 例如 TIME_FRAME = 4小时 → 预测接下来的4小时

技术指标报告指导：
- 评估动量指标（MACD、ROC）与震荡指标（RSI、随机指标、威廉姆斯%R）
- 对强方向信号（MACD交叉、RSI背离、极端超买/超卖）给予更高权重
- 忽略或降低中性/混合信号权重，除非多指标一致

形态报告指导：
- 仅在模式清晰可辨且基本完成，并且突破/跌破已开始或基于价格与动量极有可能发生（强影线、成交量激增、吞没蜡烛）时采取行动
- 不要对早期或投机性模式采取行动；除非有其他报告的突破确认，否则不要将整理视为可交易

趋势报告指导：
- 分析价格与支撑/阻力的互动：向上倾斜的支撑线→买盘兴趣；向下倾斜的阻力线→卖压
- 若价格在趋势线之间压缩，仅在存在强蜡烛或指标确认的汇合时预测突破
- 不要仅凭几何形状假设突破方向

决策策略：
1. 综合三类报告的一致性与冲突，说明取舍逻辑与证据
2. 仅对已确认信号采取行动，避免新兴、投机或冲突信号
3. 优先考虑近期强动量与决定性价格行动（突破蜡烛、拒绝影线、支撑反弹）
4. 报告不一致时，选择更强且更近期确认的方向，偏好有动量支持的信号
5. 市场处于整理或报告混合时，默认采用主导趋势线斜率（如下降通道中做空），不猜测方向，选择更可辩护的一方
6. 市场环境：给出简洁分类（趋势/震荡/突破）及依据
7. 止盈止损：必须给出数值型 stop_loss 与 take_profit；stop_loss 不得等于当前价格；结合市场环境与波动性给出风险控制建议，并按品种精度四舍五入
8.justification 字段必须提供详细分析，不能敷衍或过于简单。必须说明决策的具体依据和推理逻辑，并引用关键数值与价格位
9.止盈空间必须大于止损空间
10. 深度思考，给出符合市场环境的交易决策

表达规范：
- 允许在叙述性文本中适度使用表情符号（如✅⚠️📈📉）增强表达


输出格式（仅以下 JSON 字段）：
{{
  "market_environment": "<趋势市场/震荡市场/突破市场>",
  "volatility_assessment": "<质化描述，例如‘活跃’或‘平稳’，可留空>",
  "forecast_horizon": "预测未来N根K线（具体时间）",
  "decision": "<做多/做空>",
  "justification": "<综合证据的结论摘要，给出结构位与波动性依据>",
  "confidence_level": "<高/中/低>",
  "stop_loss": <数值>,
  "take_profit": <数值>
}}

技术指标报告：
{indicator_report}

形态报告：
{pattern_report}

趋势报告：
{trend_report}
"""

def create_final_trade_decider_comprehensive(llm):
    return create_generic_decision_agent(
        llm=llm,
        prompt_template=COMPREHENSIVE_PROMPT_TEMPLATE,
        agent_name="综合分析版决策智能体",
        agent_version="comprehensive"
    )
