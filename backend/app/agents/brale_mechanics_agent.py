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
from app.agents.prompt_features import AGENT_OUTPUT_PREAMBLE, assemble_prompt_with_features


def _score_field_desc() -> str:
    """根据 AGENT_SCORE_MODE 返回 movement_score / movement_confidence 字段说明。"""
    try:
        from app.core.config import settings
        mode = settings.AGENT_SCORE_MODE
    except Exception:
        mode = "conservative"
    if mode == "lean":
        return (
            "- **movement_score**: [-1, 1]，+1=强烈看涨，-1=强烈看跌。\n"
            "  即使方向不明确，也请给出你认为最可能的微偏倾向（0.1~0.3 偏多，-0.1~-0.3 偏空）。\n"
            "  只有在完全无法判断时才使用 0。数据缺失时应靠近 0。\n"
            "- **movement_confidence**: [0, 1]，证据充分时偏高。数据大量缺失时应偏低于 0.3"
        )
    return (
        "- **movement_score**: [-1, 1]，+1=强烈看涨，0=无方向，-1=强烈看跌。\n"
        "  证据不足时分数应靠近 0。数据缺失时应靠近 0。\n"
        "- **movement_confidence**: [0, 1]，证据充分时偏高。数据大量缺失时应偏低于 0.3"
    )

logger = logging.getLogger(__name__)

_MECHANICS_SYSTEM_PROMPT = f"""{AGENT_OUTPUT_PREAMBLE}

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
- **open_interest_context**: 中文描述OI变化率、资金费率等关键证据。当数据大量标记为 `missing: true` 时，直接说明"衍生品数据不可用"
- **anomaly_detail**: 中文描述异常数据点（清算激增/费率极端/OI异动等），无明显异常则写"无明显异常"
{_score_field_desc()}
- **next_focus**: 下轮需重点关注的衍生品指标变化"""

_DEFAULT_OUTPUT: dict[str, Any] = {
    "leverage_state": "unknown",
    "crowding": "unknown",
    "risk_level": "unknown",
    "open_interest_context": "衍生品数据不可用",
    "anomaly_detail": "无明显异常",
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

        # 核心衍生品数据不足 → 跳过 LLM，直接返回零分
        # 阈值由 MECHANICS_MIN_DATA_SOURCES 控制（默认需 ≥3 个数据源可用）
        try:
            from app.core.config import settings
            min_sources = max(1, settings.MECHANICS_MIN_DATA_SOURCES)
        except Exception:
            min_sources = 3
        total_sources = 5
        missing = compressed.get("missing") or []
        if len(missing) > (total_sources - min_sources):
            logger.info(
                "[brale-mechanics] %d/%d mechanics data missing (%s); "
                "need ≥%d sources, forcing score=0, skipping LLM.",
                len(missing), total_sources, ", ".join(missing), min_sources,
            )
            return {"mechanics_summary": _DEFAULT_OUTPUT.copy()}

        interval = state.get("time_frame", "")
        symbol = state.get("stock_name", "") or compressed.get("symbol", "")

        # Assemble system prompt with conditional feature fragments
        full_system = assemble_prompt_with_features(prompt, "agent_mechanics", compressed)

        user_parts = [
            f"交易对: {symbol}",
            f"决策周期: {interval}",
            "以下是衍生品市场数据压缩 JSON（missing=true表示该数据源不可用）：",
            json.dumps(compressed, ensure_ascii=False, indent=2),
            "请严格按照 Schema 输出 MechanicsSummary JSON，只输出一个 JSON 对象。",
        ]
        user_msg = "\n".join(user_parts)

        try:
            response = invoke_llm_text(llm, f"{full_system}\n\n{user_msg}")
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
