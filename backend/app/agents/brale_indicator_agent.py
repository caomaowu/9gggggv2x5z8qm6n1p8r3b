"""
brale_indicator_agent.py — Indicator 分析 Agent (brale-core 移植).

Replicates brale-core-master internal/llm/app/llm_prompts.go AgentIndicatorPrompt()
+ internal/config/prompts.go defaultAgentIndicatorPrompt.

Design:
    - 输入：indicator_compress.py 产出的压缩 JSON
    - 输出：严格 JSON Schema → IndicatorSummary {expansion, alignment, noise,
            momentum_detail, conflict_detail, movement_score, movement_confidence,
            next_focus}
    - 纯文本 LLM 调用，不依赖 LangChain tool / 图表
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.utils.llm_compat import invoke_llm_text
from app.agents.prompt_features import AGENT_OUTPUT_PREAMBLE, assemble_prompt_with_features

logger = logging.getLogger(__name__)

# ======================================================================
# System Prompt  (1:1 brale prompts.go + feature fragments)
# ======================================================================

# Shared preamble imported from prompt_features.py

_INDICATOR_SYSTEM_PROMPT = f"""{AGENT_OUTPUT_PREAMBLE}

你是交易系统的 Indicator 分析器。接收预计算的技术指标压缩 JSON，输出结构化的指标分析摘要。

## 输出 Schema
```json
{{
  "expansion": "expanding|contracting|stable|mixed|unknown",
  "alignment": "aligned|mixed|divergent|unknown",
  "noise": "low|medium|high|mixed|unknown",
  "momentum_detail": "中文关键证据，≤200字",
  "conflict_detail": "中文冲突描述，若无冲突写'无明显冲突'",
  "movement_score": 0.0,
  "movement_confidence": 0.0,
  "next_focus": "下轮待验证焦点，≤160字，禁止交易建议"
}}
```

## 字段说明
- **expansion**: 波动扩张状态。expanding=波动扩大, contracting=波动收窄, stable=稳定, mixed=多周期矛盾
- **alignment**: 指标方向一致性。aligned=多指标同向, mixed=部分一致, divergent=互相矛盾
- **noise**: 市场噪音水平。low=趋势清晰, medium=一般, high=频繁假信号
- **momentum_detail**: 中文描述当前动能特征（方向/强度/加速或衰减），引用具体指标证据
- **conflict_detail**: 中文描述指标间矛盾之处
- **movement_score**: [-1, 1]，+1=强烈看涨，0=无方向，-1=强烈看跌
- **movement_confidence**: [0, 1]，当前证据的充分程度
- **next_focus**: 下轮分析需验证的关键点，不包含交易建议"""

# ======================================================================
# Default / fallback output
# ======================================================================

_DEFAULT_OUTPUT: dict[str, Any] = {
    "expansion": "unknown",
    "alignment": "unknown",
    "noise": "unknown",
    "momentum_detail": "分析失败，使用默认值",
    "conflict_detail": "分析失败",
    "movement_score": 0.0,
    "movement_confidence": 0.0,
    "next_focus": "重新采集数据后重试",
}


# ======================================================================
# JSON extraction helpers
# ======================================================================


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract structured JSON from LLM output, with error tolerance."""
    if not text or not text.strip():
        return None

    text = text.strip()

    strategies = [
        # 1. Direct parse
        lambda t: json.loads(t),
        # 2. Strip ```json … ```
        lambda t: json.loads(re.sub(r"^```(?:json)?\s*\n?", "", t)),
        # 3. Strip trailing ```
        lambda t: json.loads(t.rstrip("`").rstrip()),
        # 4. Find first { … } pair
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
    """Coerce LLM output fields to the expected types."""
    valid_expansion = {"expanding", "contracting", "stable", "mixed", "unknown"}
    valid_alignment = {"aligned", "mixed", "divergent", "unknown"}
    valid_noise = {"low", "medium", "high", "mixed", "unknown"}

    expansion = raw.get("expansion", "unknown")
    if isinstance(expansion, str):
        expansion = expansion.lower().strip()
    expansion = expansion if expansion in valid_expansion else "unknown"

    alignment = raw.get("alignment", "unknown")
    if isinstance(alignment, str):
        alignment = alignment.lower().strip()
    alignment = alignment if alignment in valid_alignment else "unknown"

    noise = raw.get("noise", "unknown")
    if isinstance(noise, str):
        noise = noise.lower().strip()
    noise = noise if noise in valid_noise else "unknown"

    momentum_detail = str(raw.get("momentum_detail", ""))[:200]
    conflict_detail = str(raw.get("conflict_detail", ""))[:200]
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
        "expansion": expansion,
        "alignment": alignment,
        "noise": noise,
        "momentum_detail": momentum_detail,
        "conflict_detail": conflict_detail,
        "movement_score": score,
        "movement_confidence": confidence,
        "next_focus": next_focus,
    }


# ======================================================================
# Agent node factory
# ======================================================================


def create_brale_indicator_agent(llm: Any, system_prompt: str | None = None):
    """Factory: return an indicator_agent_node(state) closure.

    Parameters
    ----------
    llm : ChatOpenAI-compatible instance
    system_prompt : str | None
        Override system prompt (defaults to brale indicator prompt).
    """

    prompt = system_prompt or _INDICATOR_SYSTEM_PROMPT

    def indicator_agent_node(state: dict[str, Any]) -> dict[str, Any]:
        """LangGraph node: consume compressed indicator JSON → emit IndicatorSummary."""
        compressed = state.get("indicator_compressed")
        if compressed is None:
            logger.warning("[brale-indicator] No indicator_compressed in state; returning default.")
            return {"indicator_summary": _DEFAULT_OUTPUT.copy()}

        interval = state.get("time_frame", "") or compressed.get("market", {}).get("interval", "")
        symbol = state.get("stock_name", "") or compressed.get("market", {}).get("symbol", "")

        # Assemble system prompt with conditional feature fragments
        full_system = assemble_prompt_with_features(prompt, "agent_indicator", compressed)

        # Build user message
        user_parts = [
            f"交易对: {symbol}",
            f"决策周期: {interval}",
            "以下是多周期技术指标压缩数据 JSON：",
            json.dumps(compressed, ensure_ascii=False, indent=2),
            "请严格按照 Schema 输出 IndicatorSummary JSON，只输出一个 JSON 对象。",
        ]
        user_msg = "\n".join(user_parts)

        full_prompt = f"{full_system}\n\n{user_msg}"

        try:
            response = invoke_llm_text(llm, full_prompt)
            parsed = _extract_json(response)

            if parsed is None:
                logger.warning("[brale-indicator] JSON parse failed, using defaults. raw=%s", response[:200])
                return {"indicator_summary": _DEFAULT_OUTPUT.copy()}

            result = _normalize_output(parsed)
            logger.info(
                "[brale-indicator] score=%.3f conf=%.3f expansion=%s alignment=%s noise=%s",
                result["movement_score"], result["movement_confidence"],
                result["expansion"], result["alignment"], result["noise"],
            )
            return {"indicator_summary": result}

        except Exception as exc:
            logger.error("[brale-indicator] LLM call failed: %s", exc)
            return {"indicator_summary": _DEFAULT_OUTPUT.copy()}

    return indicator_agent_node
