"""
brale_mechanics_agent.py — Market Mechanics 分析 Agent (brale-core 移植).

Replicates brale-core-master internal/llm/app/llm_prompts.go AgentMechanicsPrompt()
+ internal/config/prompts.go defaultAgentMechanicsPrompt.

输出: MechanicsSummary {leverage_state, crowding, risk_level, open_interest_context,
                        anomaly_detail, movement_score, movement_confidence, next_focus}
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.utils.llm_compat import invoke_llm_text

logger = logging.getLogger(__name__)

_AGENT_OUTPUT_PREAMBLE = """你是 brale-core AI 驱动量化交易系统中的分析模块。
硬性输出规则：
- 只输出一个 JSON 对象；禁止 markdown/代码块/注释/数组根
- 字段严格匹配 Schema；不得增删
- 只能使用输入已有信息；禁止编造
- 证据不足必须保持保守"""

_MECHANICS_SYSTEM_PROMPT = f"""{_AGENT_OUTPUT_PREAMBLE}

你是交易系统的 Market Mechanics 分析器。接收衍生品市场数据压缩 JSON，输出市场机制分析摘要。

## 输出 Schema
```json
{{
  "leverage_state": "increasing|stable|overheated|unknown",
  "crowding": "long_crowded|short_crowded|balanced|unknown",
  "risk_level": "low|medium|high|unknown",
  "open_interest_context": "中文OI/资金费率证据描述，≤200字",
  "anomaly_detail": "中文异常/压力描述，无明显异常则写'无明显异常'",
  "movement_score": 0.0,
  "movement_confidence": 0.0,
  "next_focus": "下轮待验证焦点，≤160字，禁止交易建议"
}}
```

## 字段说明
- **leverage_state**: 杠杆使用状态。increasing=杠杆增加中(加仓), stable=稳定, overheated=过热(拥挤)
- **crowding**: 持仓拥挤方向。long_crowded=多头拥挤, short_crowded=空头拥挤, balanced=平衡
- **risk_level**: 当前风险等级。low=低, medium=中等, high=高
- **open_interest_context**: 中文描述OI变化率、资金费率等关键证据
- **anomaly_detail**: 中文描述异常数据点（清算激增/费率极端/OI异动等）
- **movement_score**: [-1, 1]，+1=强烈看涨，0=无方向，-1=强烈看跌
- **movement_confidence**: [0, 1]
- **next_focus**: 下轮需重点关注的衍生品指标变化

## 分析原则
1. **OI变化**: OI上升+价格上涨=多头资金流入(看涨)；OI上升+价格下跌=空头资金流入(看跌)
2. **资金费率**: 正值偏高=多头拥挤(做多成本高)；负值偏低=空头拥挤(做空成本高)
3. **多空比**: >1=多头持仓多(偏拥挤)；<1=空头持仓多；极端值>2或<0.5需关注反转
4. **清算**: 大量多头清算=杠杆多头被清(短空信号)；大量空头清算=杠杆空头被清(短多信号)
5. **CVD累积成交量差**: 正值持续=主动买盘主导；负值持续=主动卖盘主导；与价格背离=潜在反转
6. 数据标记 `missing: true` 时该维度不做判断，保守处理
7. 多指标矛盾时 movement_score 靠近 0
8. 极端资金费率 + 极端多空比 = 高风险反转场景"""

_DEFAULT_OUTPUT: dict[str, Any] = {
    "leverage_state": "unknown",
    "crowding": "unknown",
    "risk_level": "unknown",
    "open_interest_context": "分析失败，使用默认值",
    "anomaly_detail": "分析失败",
    "movement_score": 0.0,
    "movement_confidence": 0.0,
    "next_focus": "重新采集数据后重试",
}


def _extract_json(text: str) -> dict | None:
    if not text or not text.strip():
        return None
    text = text.strip()
    strategies = [
        lambda t: json.loads(t),
        lambda t: json.loads(re.sub(r"^```(?:json)?\s*\n?", "", t)),
        lambda t: json.loads(t.rstrip("`").rstrip()),
        lambda t: json.loads(t[t.find("{"): t.rfind("}") + 1]),
    ]
    for strat in strategies:
        try:
            result = strat(text)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError, IndexError):
            continue
    return None


def _normalize_output(raw: dict[str, Any]) -> dict[str, Any]:
    valid_leverage = {"increasing", "stable", "overheated", "unknown"}
    valid_crowding = {"long_crowded", "short_crowded", "balanced", "unknown"}
    valid_risk = {"low", "medium", "high", "unknown"}

    def pick(val, valid, default):
        if isinstance(val, str):
            val = val.lower().strip()
        return val if val in valid else default

    leverage_state = pick(raw.get("leverage_state"), valid_leverage, "unknown")
    crowding = pick(raw.get("crowding"), valid_crowding, "unknown")
    risk_level = pick(raw.get("risk_level"), valid_risk, "unknown")

    oi_context = str(raw.get("open_interest_context", ""))[:200]
    anomaly_detail = str(raw.get("anomaly_detail", ""))[:200]
    next_focus = str(raw.get("next_focus", ""))[:160]

    try:
        score = float(raw.get("movement_score", 0))
        score = max(-1.0, min(1.0, score))
    except (TypeError, ValueError):
        score = 0.0
    try:
        confidence = float(raw.get("movement_confidence", 0))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.0

    return {
        "leverage_state": leverage_state,
        "crowding": crowding,
        "risk_level": risk_level,
        "open_interest_context": oi_context,
        "anomaly_detail": anomaly_detail,
        "movement_score": score,
        "movement_confidence": confidence,
        "next_focus": next_focus,
    }


def create_brale_mechanics_agent(llm: Any, system_prompt: str | None = None):
    prompt = system_prompt or _MECHANICS_SYSTEM_PROMPT

    def mechanics_agent_node(state: dict[str, Any]) -> dict[str, Any]:
        compressed = state.get("mechanics_compressed")
        if compressed is None:
            logger.warning("[brale-mechanics] No mechanics_compressed; returning default.")
            return {"mechanics_summary": _DEFAULT_OUTPUT.copy()}

        interval = state.get("time_frame", "")
        symbol = state.get("stock_name", "") or compressed.get("symbol", "")

        user_parts = [
            f"交易对: {symbol}",
            f"决策周期: {interval}",
            "以下是衍生品市场数据压缩 JSON（missing=true表示该数据源不可用）：",
            json.dumps(compressed, ensure_ascii=False, indent=2),
            "请严格按照 Schema 输出 MechanicsSummary JSON，只输出一个 JSON 对象。",
        ]
        user_msg = "\n".join(user_parts)

        try:
            response = invoke_llm_text(llm, f"{prompt}\n\n{user_msg}")
            parsed = _extract_json(response)
            if parsed is None:
                logger.warning("[brale-mechanics] JSON parse failed. raw=%s", response[:200])
                return {"mechanics_summary": _DEFAULT_OUTPUT.copy()}
            result = _normalize_output(parsed)
            logger.info(
                "[brale-mechanics] score=%.3f conf=%.3f leverage=%s crowding=%s risk=%s",
                result["movement_score"], result["movement_confidence"],
                result["leverage_state"], result["crowding"], result["risk_level"],
            )
            return {"mechanics_summary": result}
        except Exception as exc:
            logger.error("[brale-mechanics] LLM call failed: %s", exc)
            return {"mechanics_summary": _DEFAULT_OUTPUT.copy()}

    return mechanics_agent_node
