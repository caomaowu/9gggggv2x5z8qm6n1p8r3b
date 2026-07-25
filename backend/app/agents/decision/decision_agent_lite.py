"""
轻量级决策智能体 - Lite Speed Decision Agent
精简版 Prompt，移除死板规则，利用大模型直觉进行快速综合判断。
"""

from .core_decision import create_generic_decision_agent

# 精简版 Prompt：目标驱动，减少显式规则验证
LITE_PROMPT_TEMPLATE = """You are a short-horizon directional forecasting specialist.
Your only goal is to predict the direction of the next two CLOSED candles for {stock_name}.

**Strict horizon contract:**
- Primary/scored timeframe: {primary_timeframe}
- Context-only timeframes: {context_timeframes}
- K1 means the first fully closed {primary_timeframe} candle after the analysis cutoff.
- K2 means the second fully closed {primary_timeframe} candle after the analysis cutoff.
- Compare each candle's close independently with the current analysis price.
- Context timeframes may support the forecast, but they never change the scored horizon.
- Do not invent a different forecast horizon.

**Current Market Status:**
{price_summary}
{price_info_str}

**Analysis Reports:**

---
### 1. Technical Indicators
{indicator_report}

---
### 2. Chart Patterns
{pattern_report}

---
### 3. Trend Analysis
{trend_report}

---

**Decision Task:**

Synthesize the reports and make two independent forecasts, one for K1 and one for K2.
- **Do not** mechanically verify every rule. Use your expert judgment to weigh conflicting signals.
- **Focus on** the confluence of major signals (e.g., trend direction + momentum).
- **Ignore** minor noise or weak signals.
- Use HOLD when neither direction has a defensible edge. Do not force a coin-flip trade.
- Confidence must represent the probability that the selected LONG/SHORT direction is correct.
- If the decision is HOLD, confidence must be below 0.70.

**Output Requirements:**

Provide your decision in the following JSON format:

```json
{{
    "primary_timeframe": "{primary_timeframe}",
    "k1_decision": "LONG" | "SHORT" | "HOLD",
    "k1_confidence": <float between 0.0 and 1.0>,
    "k2_decision": "LONG" | "SHORT" | "HOLD",
    "k2_confidence": <float between 0.0 and 1.0>,
    "justification": "Brief explanation of K1 and K2 drivers (max 3 sentences)"
}}
```

**Note:**
- Return valid JSON only, without markdown fences or extra text.
- K1 and K2 may have different directions.
- Speed is of the essence.
"""

def create_final_trade_decider_lite(llm):
    return create_generic_decision_agent(
        llm=llm,
        prompt_template=LITE_PROMPT_TEMPLATE,
        agent_name="轻量级决策智能体",
        agent_version="lite"
    )
