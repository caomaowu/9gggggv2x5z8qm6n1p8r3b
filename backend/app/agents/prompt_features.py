"""
prompt_features.py — Dynamic feature fragment injection (ports brale prompt_features.go).

Injects condition-specific guidance fragments into agent system prompts,
only when the corresponding data is present in the compressed input.
"""

from __future__ import annotations

from typing import Any

# ======================================================================
# Shared preamble (matches Go agentOutputPreamble in prompts.go)
# ======================================================================

AGENT_OUTPUT_PREAMBLE = """你是 brale-core AI 驱动量化交易系统中的分析模块。
你的输出会被后续程序直接解析、审计并进入自动化处理链路。
硬性输出规则：
- 只输出一个 JSON 对象；禁止输出 markdown、代码块、注释、解释文字、数组根对象、多个对象
- 输出必须严格匹配下方给出的字段约束或 JSON Schema；不得新增字段、不得缺字段、字段类型必须正确
- 只能使用输入里已有的信息；禁止编造任何数据、阈值、行情、上下文或外部事实
- 若证据不足，必须保持保守，并在允许字段内如实表达不确定性"""

# ======================================================================
# Feature fragments (1:1 matching Go featureFragmentZH)
# ======================================================================

_INDICATOR_FRAGMENTS: dict[str, str] = {
    "ema":        "- EMA 已可用时，优先读取 `price_vs_ema_*` 与 `ema_stack`，判断价格相对均线位置、均线顺序和趋势一致性。",
    "rsi":        "- RSI 已可用时，结合 `rsi_zone` 与 `rsi_slope_state` 判断动量强弱、回落还是加速。",
    "atr":        "- ATR 已可用时，参考 `atr_expand_state` 与 `atr_change_pct` 判断波动率是在扩张、收缩还是稳定。",
    "obv":        "- OBV 已可用时，参考 `obv_slope_state` 判断量价是否同向支持当前动量。",
    "stc":        "- STC 已可用时，参考 `stc_state` 判断趋势节奏是否仍在强化或已经转弱。",
    "bb":         "- 布林带已可用时，结合 `bb_zone` 与 `bb_width_state` 判断价格所处带内位置与压缩/扩张状态。",
    "chop":       "- CHOP 已可用时，使用 `chop_regime` 区分趋势环境、震荡环境或过渡阶段。",
    "stoch_rsi":  "- StochRSI 已可用时，参考 `stoch_rsi_zone` 判断短线是否过热、过冷或中性。",
    "aroon":      "- Aroon 已可用时，优先留意 `events` 中的 `aroon_*` 事件，它表示趋势强化或强反转线索。",
    "td":         "- TD Sequential 已可用时，优先留意 `events` 中的 `td_*` 事件，把它作为潜在衰竭/延续提示而不是单独结论。",
}

_STRUCTURE_FRAGMENTS: dict[str, str] = {
    "supertrend":  "- SuperTrend 已可用时，参考 `supertrend.state/level/distance_pct` 判断趋势方向与失效距离。",
    "ema_context": "- 结构中的 EMA 上下文已可用时，结合 `ema20/ema50/ema200` 判断结构方向是否有中长期均线支撑。",
    "rsi_context": "- 结构中的 RSI 上下文已可用时，可交叉读取 `recent_candles[].rsi` 与 `fractal_points[].rsi`，判断突破或回踩时动量是否配合。",
    "patterns":    "- 形态识别已可用时，仅在 `pattern` 明确存在时引用，并结合 `quality` 与最近突破反应判断其可靠度。",
    "smc":         "- SMC 信息已可用时，参考 `smc.order_block` 与 `smc.fvg` 判断关键供需区是否仍然有效。",
}

_MECHANICS_FRAGMENTS: dict[str, str] = {
    "oi":                "- OI 已可用时，优先结合 `oi_state` 与 `oi_history` 判断杠杆是在堆积、释放还是无明显变化。",
    "funding":           "- 资金费率已可用时，参考 `funding` 与 `funding_state` 判断方向偏置和过热程度。",
    "long_short":        "- 多空比已可用时，结合 `long_short_by_interval` 与 `crowding_state` 判断拥挤方向与反转风险。",
    "fear_greed":        "- 情绪指数已可用时，参考 `fear_greed` 与 `sentiment_state` 判断情绪极端是否在放大机制风险。",
    "liquidations":      "- 清算数据已可用时，重点读取 `liquidation_state.stress` 与 `liquidations` 判断清算压力等级。",
    "cvd":               "- CVD 已可用时，结合 `cvd_by_interval` 判断主动买卖量是否支持当前方向。",
    "sentiment":         None,   # not implemented (Go sentiment_by_interval not ported)
    "futures_sentiment": "- 期货情绪已可用时，参考 `futures_sentiment` 判断顶级交易者与 taker 流向是否同向强化。",
}

_FEATURE_HEADER = "当前启用且可用的特征说明:"

_STAGE_ORDERS: dict[str, tuple[str, ...]] = {
    "agent_indicator": ("ema", "rsi", "atr", "obv", "stc", "bb", "chop", "stoch_rsi", "aroon", "td"),
    "agent_structure": ("supertrend", "ema_context", "rsi_context", "patterns", "smc"),
    "agent_mechanics": ("oi", "funding", "long_short", "fear_greed", "liquidations", "cvd", "sentiment", "futures_sentiment"),
}

_STAGE_FRAGMENTS: dict[str, dict[str, str]] = {
    "agent_indicator": _INDICATOR_FRAGMENTS,
    "agent_structure": _STRUCTURE_FRAGMENTS,
    "agent_mechanics": _MECHANICS_FRAGMENTS,
}


# ======================================================================
# Public API
# ======================================================================


def assemble_prompt_with_features(core_prompt: str, stage: str, compressed: dict[str, Any] | None) -> str:
    """Assemble system prompt with conditionally injected feature fragments.

    Parameters
    ----------
    core_prompt : str
        Base system prompt (role + schema + field descriptions only).
    stage : str
        One of 'agent_indicator', 'agent_structure', 'agent_mechanics'.
    compressed : dict | None
        The compressed input dict for this agent.

    Returns
    -------
    str
        Base prompt + feature fragments (if data present), or base prompt alone.
    """
    if compressed is None:
        return core_prompt

    fragments = _collect_fragments(stage, compressed)
    if not fragments:
        return core_prompt

    return core_prompt + "\n\n" + _FEATURE_HEADER + "\n" + "\n".join(fragments)


def _collect_fragments(stage: str, compressed: dict[str, Any]) -> list[str]:
    """Detect which features are present and return ordered fragments."""
    try:
        has = _DETECTORS[stage](compressed)
    except Exception:
        return []

    order = _STAGE_ORDERS.get(stage, ())
    frag_map = _STAGE_FRAGMENTS.get(stage, {})
    out: list[str] = []
    for key in order:
        if has.get(key) and key in frag_map and frag_map[key]:
            out.append(frag_map[key])
    return out


# ======================================================================
# Feature detectors (porting Go indicatorFeatureFragments etc.)
# ======================================================================


def _detect_indicator_features(compressed: dict[str, Any]) -> dict[str, bool]:
    d = compressed.get("data", {})
    has: dict[str, bool] = {}

    has["ema"] = all(k in d for k in ("ema_fast", "ema_mid", "ema_slow"))
    has["rsi"] = "rsi" in d
    has["atr"] = "atr" in d
    has["obv"] = "obv" in d
    has["stc"] = "stc" in d
    has["bb"] = "bb" in d
    has["chop"] = "chop" in d
    has["stoch_rsi"] = "stoch_rsi" in d

    events: list = compressed.get("indicator_events", []) or []
    has["aroon"] = any(str(e).startswith("aroon_") for e in events)
    has["td"] = any(str(e).startswith("td_") for e in events)

    return has


def _detect_structure_features(compressed: dict[str, Any]) -> dict[str, bool]:
    d = compressed.get("data", {})
    has: dict[str, bool] = {}

    has["supertrend"] = d.get("supertrend") is not None

    ec = d.get("ema_context") or {}
    has["ema_context"] = ec.get("ema20") is not None

    has["rsi_context"] = any(
        rc.get("rsi") is not None
        for rc in (d.get("recent_candles") or [])
    )

    pat = d.get("pattern")
    has["patterns"] = pat is not None and isinstance(pat, dict)

    smc = d.get("smc")
    has["smc"] = smc is not None and isinstance(smc, dict)

    return has


def _detect_mechanics_features(compressed: dict[str, Any]) -> dict[str, bool]:
    has: dict[str, bool] = {}

    has["oi"] = _has_data(compressed, "oi")
    has["funding"] = _has_data(compressed, "funding")
    has["long_short"] = any(
        v.get("missing") == False
        for v in (compressed.get("long_short_by_interval") or {}).values()
    )
    has["fear_greed"] = _has_data(compressed, "fear_greed")
    has["liquidations"] = _has_data(compressed, "liquidations")
    has["cvd"] = any(
        v.get("missing") == False
        for v in (compressed.get("cvd_by_interval") or {}).values()
    )
    has["sentiment"] = False  # not implemented
    has["futures_sentiment"] = _has_data(compressed, "futures_sentiment")

    return has


def _has_data(compressed: dict[str, Any], key: str) -> bool:
    v = compressed.get(key)
    if v is None:
        return False
    if isinstance(v, dict) and v.get("missing") == True:
        return False
    return True


_DETECTORS = {
    "agent_indicator": _detect_indicator_features,
    "agent_structure": _detect_structure_features,
    "agent_mechanics": _detect_mechanics_features,
}
