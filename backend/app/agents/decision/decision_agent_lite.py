"""
轻量级决策智能体 - Lite Speed Decision Agent
精简版 Prompt，移除死板规则，利用大模型直觉进行快速综合判断。
"""

from .core_decision import create_generic_decision_agent

# 精简版 Prompt：目标驱动，减少显式规则验证
LITE_PROMPT_TEMPLATE = """You are a senior high-frequency trading (HFT) consultant with sharp market intuition.
Your goal is to provide a clear trading recommendation for {stock_name} ({time_frame}) based on the provided analysis reports.

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

Synthesize the above information and determine the most likely short-term market direction.
- **Do not** mechanically verify every rule. Use your expert judgment to weigh conflicting signals.
- **Focus on** the confluence of major signals (e.g., trend direction + momentum).
- **Ignore** minor noise or weak signals.

**Output Requirements:**

Provide your decision in the following JSON format:

```json
{{
    "decision": "LONG" | "SHORT",
    "confidence": <float between 0.0 and 1.0>,
    "forecast_horizon": "Predicting next N candles",
    "justification": "Brief summary of key drivers (max 2 sentences)",
    "risk_reward_ratio": <float between 1.2 and 2.5>
}}
```

**Note:**
- If signals are strong, be decisive.
- If signals are mixed but a dominant trend exists, follow the trend.
- Speed is of the essence.
"""

def create_final_trade_decider_lite(llm):
    return create_generic_decision_agent(
        llm=llm,
        prompt_template=LITE_PROMPT_TEMPLATE,
        agent_name="轻量级决策智能体",
        agent_version="lite"
    )
