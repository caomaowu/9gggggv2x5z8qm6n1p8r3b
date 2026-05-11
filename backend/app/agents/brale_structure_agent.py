"""
brale_structure_agent.py — Market Structure 分析 Agent (brale-core 移植).

Replicates brale-core-master internal/llm/app/llm_prompts.go AgentStructurePrompt()
+ internal/config/prompts.go defaultAgentStructurePrompt.

输出: StructureSummary {regime, last_break, quality, pattern, volume_action,
                        candle_reaction, movement_score, movement_confidence, next_focus}
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
            "  只有在完全无法判断时才使用 0。\n"
            "- **movement_confidence**: [0, 1]"
        )
    return (
        "- **movement_score**: [-1, 1]，+1=强烈看涨，0=无方向，-1=强烈看跌。\n"
        "  当 regime 为 range/mixed/unclear，或 last_break 为 none/unknown，\n"
        "  或 quality 为 messy/unclear 时：movement_score 靠近 0，movement_confidence 偏低。\n"
        "- **movement_confidence**: [0, 1]"
    )

logger = logging.getLogger(__name__)

_STRUCTURE_SYSTEM_PROMPT = f"""{AGENT_OUTPUT_PREAMBLE}

你是交易系统的 Market Structure 分析器。接收价格结构压缩 JSON，输出结构分析摘要。

## 输出 Schema
```json
{{
  "regime": "trend_up|trend_down|range|mixed|unclear",
  "last_break": "bos_up|bos_down|choch_up|choch_down|none|unknown",
  "quality": "clean|messy|mixed|unclear",
  "pattern": "double_top|double_bottom|head_shoulders|inv_head_shoulders|triangle_sym|triangle_asc|triangle_desc|wedge_rising|wedge_falling|flag|pennant|channel_up|channel_down|none|unknown",
  "volume_action": "中文成交量特征描述，≤200字",
  "candle_reaction": "中文K线反应特征描述，≤200字",
  "movement_score": 0.0,
  "movement_confidence": 0.0,
  "next_focus": "下轮待验证焦点，≤160字，禁止交易建议"
}}
```

## 字段说明
- **regime**: 市场状态。trend_up=上升趋势, trend_down=下降趋势, range=震荡, mixed=多周期矛盾
- **last_break**: 最近一次结构突破。bos_up=向上突破结构, bos_down=向下跌破结构, choch_up=向上特征改变, choch_down=向下特征改变
- **quality**: 结构清晰度。clean=结构边界清晰, messy=边界混乱, mixed=部分清晰
- **pattern**: 识别的形态类型（详见枚举），none=无形态
- **volume_action**: 中文描述成交量特征（放量/缩量/背离等）
- **candle_reaction**: 中文描述K线对关键位的反应（支撑位反弹/阻力位受压等）
{_score_field_desc()}
- **next_focus**: 下轮需验证的结构位置或形态"""

_DEFAULT_OUTPUT: dict[str, Any] = {
    "regime": "unclear",
    "last_break": "unknown",
    "quality": "unclear",
    "pattern": "none",
    "volume_action": "分析失败，使用默认值",
    "candle_reaction": "分析失败",
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
    valid_regime = {"trend_up", "trend_down", "range", "mixed", "unclear"}
    valid_break = {"bos_up", "bos_down", "choch_up", "choch_down", "none", "unknown"}
    valid_quality = {"clean", "messy", "mixed", "unclear"}
    valid_pattern = {
        "double_top", "double_bottom", "head_shoulders", "inv_head_shoulders",
        "triangle_sym", "triangle_asc", "triangle_desc", "wedge_rising",
        "wedge_falling", "flag", "pennant", "channel_up", "channel_down",
        "none", "unknown",
    }

    def pick(val, valid, default):
        if isinstance(val, str):
            val = val.lower().strip()
        return val if val in valid else default

    regime = pick(raw.get("regime"), valid_regime, "unclear")
    last_break = pick(raw.get("last_break"), valid_break, "unknown")
    quality = pick(raw.get("quality"), valid_quality, "unclear")
    pattern = pick(raw.get("pattern"), valid_pattern, "none")

    volume_action = str(raw.get("volume_action", ""))[:200]
    candle_reaction = str(raw.get("candle_reaction", ""))[:200]
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
        "regime": regime, "last_break": last_break, "quality": quality,
        "pattern": pattern, "volume_action": volume_action,
        "candle_reaction": candle_reaction,
        "movement_score": score, "movement_confidence": confidence,
        "next_focus": next_focus,
    }


def create_brale_structure_agent(llm: Any, system_prompt: str | None = None):
    prompt = system_prompt or _STRUCTURE_SYSTEM_PROMPT

    def structure_agent_node(state: dict[str, Any]) -> dict[str, Any]:
        compressed = state.get("structure_compressed")
        if compressed is None:
            logger.warning("[brale-structure] No structure_compressed; returning default.")
            return {"structure_summary": _DEFAULT_OUTPUT.copy()}

        interval = state.get("time_frame", "") or compressed.get("market", {}).get("interval", "")
        symbol = state.get("stock_name", "") or compressed.get("market", {}).get("symbol", "")

        # Assemble system prompt with conditional feature fragments
        full_system = assemble_prompt_with_features(prompt, "agent_structure", compressed)

        user_parts = [
            f"交易对: {symbol}",
            f"决策周期: {interval}",
            "以下是价格结构压缩数据 JSON：",
            json.dumps(compressed, ensure_ascii=False, indent=2),
            "请严格按照 Schema 输出 StructureSummary JSON，只输出一个 JSON 对象。",
        ]
        user_msg = "\n".join(user_parts)

        try:
            response = invoke_llm_text(llm, f"{full_system}\n\n{user_msg}")
            parsed = _extract_json(response)
            if parsed is None:
                logger.warning("[brale-structure] JSON parse failed. raw=%s", response[:200])
                return {"structure_summary": _DEFAULT_OUTPUT.copy()}
            result = _normalize_output(parsed)
            logger.info(
                "[brale-structure] score=%.3f conf=%.3f regime=%s pattern=%s",
                result["movement_score"], result["movement_confidence"],
                result["regime"], result["pattern"],
            )
            return {"structure_summary": result}
        except Exception as exc:
            logger.error("[brale-structure] LLM call failed: %s", exc)
            return {"structure_summary": _DEFAULT_OUTPUT.copy()}

    return structure_agent_node
