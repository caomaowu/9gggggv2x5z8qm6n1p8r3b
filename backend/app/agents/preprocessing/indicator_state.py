"""
indicator_state.py — OHLCV multi-timeframe indicator deterministic state classifier.

Ports brale-core-master internal/decision/features/indicator_state.go (669 lines).

Consumes IndicatorCompressedInput (output of compress_indicator) and produces:
  - Per-TF: Trend, Momentum, Volatility, Bias, Events
  - Cross-TF: alignment, conflict summary

Usage:
    from .indicator_state import summarize_indicator, build_indicator_state_json
    state = summarize_indicator(compressed_dict)
    # merge state into compressed before sending to LLM agent
    multi_tf_state = build_indicator_state_json(by_interval_dict, decision_interval, symbol)
"""

from __future__ import annotations

from typing import Any

# ======================================================================
# Thresholds (exact brale constants)
# ======================================================================

PRICE_VS_EMA_NEAR_ATR_RATIO = 0.25

RSI_ZONE_LOW = 35.0
RSI_ZONE_WEAK_LOW = 45.0
RSI_ZONE_WEAK_HIGH = 55.0
RSI_ZONE_HIGH = 65.0

RSI_SLOPE_TREND = 0.15
OBV_SLOPE_TREND = 0.02

ATR_EXPANSION_PCT = 5.0
ATR_CONTRACTION_PCT = -5.0

BB_NEAR_LOWER_PCT_B = 0.2
BB_NEAR_UPPER_PCT_B = 0.8
BB_ABOVE_UPPER_PCT_B = 1.0
BB_WIDTH_SQUEEZE_PCT = 2.0
BB_WIDTH_WIDE_PCT = 6.0

CHOP_TRENDING = 38.2
CHOP_CHOPPY = 61.8

STOCH_RSI_OVERSOLD = 0.2
STOCH_RSI_OVERBOUGHT = 0.8

AROON_STRONG = 70.0
AROON_WEAK = 30.0


# ======================================================================
# Public API
# ======================================================================

_TF_MINUTES: dict[str, int] = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "4h": 240, "1d": 1440, "1w": 10080,
}

def _tf_minutes(tf: str) -> int:
    return _TF_MINUTES.get(tf.lower().strip(), 60)


def summarize_indicator(compressed: dict[str, Any]) -> dict[str, Any]:
    """Summarize single-TF indicator compressed data into deterministic state.
    
    Returns the equivalent of brale's indicatorTFState.
    """
    market = compressed.get("market", {})
    data = compressed.get("data", {})
    meta = compressed.get("_meta", {})
    atr_val = _atr_latest(data)

    state: dict[str, Any] = {
        "interval": market.get("interval", ""),
        "freshness_sec": (meta.get("data_age_sec") or {}).get("indicator", 0),
        "missing": _detect_indicator_missing(data),
        "trend": _classify_trend(market, data, atr_val),
        "momentum": _classify_momentum(data),
        "volatility": _classify_volatility(data),
        "events": _detect_indicator_events(market, data),
    }
    state["bias"] = _compute_indicator_bias(state)
    return state


def build_indicator_state_json(
    by_interval: dict[str, dict[str, Any]],
    decision_interval: str,
    symbol: str = ""
) -> dict[str, Any]:
    """Build multi-TF indicator state JSON from by-interval compressed data.
    
    Ports brale's BuildIndicatorStateJSON (indicator_state.go:95-136).
    Returns: {decision_interval, multi_tf: [...], cross_tf_summary: {...}, missing: [...]}
    """
    available = list(by_interval.keys())
    if not available:
        return {}
    selected = _select_intervals(decision_interval, available)
    if not selected:
        return {}
    decision_interval = (decision_interval or "").strip().lower()
    if not decision_interval:
        decision_interval = selected[min(1, len(selected) - 1)]

    results = []
    missing = []
    for iv in selected:
        raw = by_interval.get(iv)
        if raw is None:
            missing.append(iv)
            continue
        try:
            state = summarize_indicator(raw)
            results.append(state)
        except Exception:
            missing.append(iv)

    cross_tf = _build_cross_tf_summary(results, decision_interval)

    return {
        "decision_interval": decision_interval,
        "multi_tf": results,
        "cross_tf_summary": cross_tf,
        "missing": missing,
    }


def merge_state_into_compressed(compressed: dict[str, Any]) -> dict[str, Any]:
    """Merge single-TF indicator state into the compressed dict."""
    state = summarize_indicator(compressed)
    # Remove nested dicts from state before merging (keep flat keys)
    flat = {}
    flat["indicator_trend"] = state.get("trend")
    flat["indicator_momentum"] = state.get("momentum")
    flat["indicator_volatility"] = state.get("volatility")
    flat["indicator_bias"] = state.get("bias")
    flat["indicator_events"] = state.get("events")
    flat["indicator_missing"] = state.get("missing")
    flat["indicator_freshness_sec"] = state.get("freshness_sec")
    return {**compressed, **flat}


# ======================================================================
# Interval Selection (brale: selectIndicatorIntervals)
# ======================================================================


def _select_intervals(decision: str, available: list[str]) -> list[str]:
    if not available:
        return []
    keys = sorted(available, key=_tf_minutes)
    target = decision.lower().strip()
    target_dur = _tf_minutes(target) if target else _tf_minutes(keys[0])

    shorter = ""
    longer = ""
    for k in keys:
        d = _tf_minutes(k)
        if d < target_dur:
            shorter = k
        elif d > target_dur and not longer:
            longer = k

    selected = []
    seen = set()
    for v in (shorter, target, longer):
        v = v.strip()
        if v and v not in seen:
            selected.append(v)
            seen.add(v)
    return selected


# ======================================================================
# Trend State
# ======================================================================


def _classify_trend(market: dict[str, Any], data: dict[str, Any], atr: float) -> dict[str, Any]:
    price = market.get("current_price") or 0
    return {
        "price_vs_ema_fast": _classify_price_vs_ema(price, _ema_latest(data.get("ema_fast")), atr),
        "price_vs_ema_mid": _classify_price_vs_ema(price, _ema_latest(data.get("ema_mid")), atr),
        "price_vs_ema_slow": _classify_price_vs_ema(price, _ema_latest(data.get("ema_slow")), atr),
        "ema_stack": _classify_ema_stack(
            _ema_latest(data.get("ema_fast")),
            _ema_latest(data.get("ema_mid")),
            _ema_latest(data.get("ema_slow")),
        ),
        "ema_distance_fast_atr": _compute_ema_distance_atr(price, _ema_latest(data.get("ema_fast")), atr),
        "ema_distance_mid_atr": _compute_ema_distance_atr(price, _ema_latest(data.get("ema_mid")), atr),
        "ema_distance_slow_atr": _compute_ema_distance_atr(price, _ema_latest(data.get("ema_slow")), atr),
    }


def _classify_price_vs_ema(price: float, ema: float, atr: float) -> str:
    if price == 0 or ema == 0:
        return "unknown"
    diff = price - ema
    if atr > 0 and abs(diff) / atr <= PRICE_VS_EMA_NEAR_ATR_RATIO:
        return "near"
    if diff > 0:
        return "above"
    return "below"


def _classify_ema_stack(fast: float, mid: float, slow: float) -> str:
    if fast == 0 or mid == 0 or slow == 0:
        return "unknown"
    if fast > mid and mid > slow:
        return "bull"
    if fast < mid and mid < slow:
        return "bear"
    return "mixed"


def _compute_ema_distance_atr(price: float, ema: float, atr: float) -> float:
    if price == 0 or ema == 0 or atr <= 0:
        return 0.0
    return round((price - ema) / atr, 4)


# ======================================================================
# Momentum State
# ======================================================================


def _classify_momentum(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "rsi_zone": _classify_rsi_zone(_rsi_latest(data.get("rsi"))),
        "rsi_slope_state": _classify_rsi_slope(data.get("rsi")),
        "stc_state": _classify_stc_state(data.get("stc")),
        "obv_slope_state": _classify_obv_slope(data.get("obv")),
        "stoch_rsi_zone": _classify_stoch_rsi_zone(data.get("stoch_rsi")),
    }


def _classify_rsi_zone(value: float) -> str:
    if value <= 0:
        return "unknown"
    if value < RSI_ZONE_LOW:
        return "<35"
    if value < RSI_ZONE_WEAK_LOW:
        return "35_45"
    if value < RSI_ZONE_WEAK_HIGH:
        return "45_55"
    if value < RSI_ZONE_HIGH:
        return "55_65"
    return ">65"


def _classify_rsi_slope(rsi: dict[str, Any] | None) -> str:
    if not rsi:
        return "unknown"
    ns = rsi.get("normalized_slope")
    if ns is None:
        return "unknown"
    if ns >= RSI_SLOPE_TREND:
        return "rising"
    if ns <= -RSI_SLOPE_TREND:
        return "falling"
    return "flat"


def _classify_stc_state(stc: dict[str, Any] | None) -> str:
    if not stc:
        return "unknown"
    state = (stc.get("state") or "").lower().strip()
    return state if state else "unknown"


def _classify_obv_slope(obv: dict[str, Any] | None) -> str:
    if not obv:
        return "unknown"
    cr = obv.get("change_rate")
    if cr is None:
        return "unknown"
    if cr >= OBV_SLOPE_TREND:
        return "up"
    if cr <= -OBV_SLOPE_TREND:
        return "down"
    return "flat"


def _classify_stoch_rsi_zone(sr: dict[str, Any] | None) -> str:
    if not sr:
        return ""
    val = sr.get("value")
    if val is None:
        return ""
    if val <= STOCH_RSI_OVERSOLD:
        return "oversold"
    if val >= STOCH_RSI_OVERBOUGHT:
        return "overbought"
    return "neutral"


# ======================================================================
# Volatility State
# ======================================================================


def _classify_volatility(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "atr_expand_state": _classify_atr_expansion(data.get("atr")),
        "atr_change_pct": _atr_change_pct(data.get("atr")),
        "bb_zone": _classify_bb_zone(data.get("bb")),
        "bb_width_state": _classify_bb_width(data.get("bb")),
        "chop_regime": _classify_chop_regime(data.get("chop")),
    }


def _classify_atr_expansion(atr: dict[str, Any] | None) -> str:
    if not atr:
        return "unknown"
    cp = atr.get("change_pct")
    if cp is None:
        return "unknown"
    cp = float(cp)
    if cp >= ATR_EXPANSION_PCT:
        return "expanding"
    if cp <= ATR_CONTRACTION_PCT:
        return "contracting"
    return "stable"


def _classify_bb_zone(bb: dict[str, Any] | None) -> str:
    if not bb:
        return ""
    pct_b = bb.get("pct_b")
    if pct_b is None:
        return ""
    if pct_b < 0:
        return "below_lower"
    if pct_b <= BB_NEAR_LOWER_PCT_B:
        return "near_lower"
    if pct_b >= BB_ABOVE_UPPER_PCT_B:
        return "above_upper"
    if pct_b >= BB_NEAR_UPPER_PCT_B:
        return "near_upper"
    return "mid"


def _classify_bb_width(bb: dict[str, Any] | None) -> str:
    if not bb:
        return ""
    bw = bb.get("bandwidth")
    if bw is None:
        return ""
    bw = float(bw)
    if bw < BB_WIDTH_SQUEEZE_PCT:
        return "squeeze"
    if bw > BB_WIDTH_WIDE_PCT:
        return "wide"
    return "normal"


def _classify_chop_regime(chop: dict[str, Any] | None) -> str:
    if not chop:
        return ""
    v = chop.get("latest")
    if v is None:
        return ""
    if v < CHOP_TRENDING:
        return "trending"
    if v > CHOP_CHOPPY:
        return "choppy"
    return "transition"


# ======================================================================
# Indicator Bias (5-factor voting)
# ======================================================================


def _compute_indicator_bias(state: dict[str, Any]) -> str:
    up = 0
    down = 0

    def apply(direction: str) -> None:
        nonlocal up, down
        if direction == "up":
            up += 1
        elif direction == "down":
            down += 1

    trend = state.get("trend", {})
    if trend.get("price_vs_ema_mid") == "above":
        apply("up")
    elif trend.get("price_vs_ema_mid") == "below":
        apply("down")
    if trend.get("ema_stack") == "bull":
        apply("up")
    elif trend.get("ema_stack") == "bear":
        apply("down")

    momentum = state.get("momentum", {})
    if momentum.get("rsi_slope_state") == "rising":
        apply("up")
    elif momentum.get("rsi_slope_state") == "falling":
        apply("down")
    if momentum.get("stc_state") == "rising":
        apply("up")
    elif momentum.get("stc_state") == "falling":
        apply("down")
    if momentum.get("obv_slope_state") == "up":
        apply("up")
    elif momentum.get("obv_slope_state") == "down":
        apply("down")

    if up >= 3 and down <= 1:
        return "up"
    if down >= 3 and up <= 1:
        return "down"
    return "mixed"


# ======================================================================
# Indicator Events (cross detection)
# ======================================================================


def _detect_indicator_events(market: dict[str, Any], data: dict[str, Any]) -> list[str]:
    events: list[str] = []
    current_price = market.get("current_price") or 0
    prev_price = market.get("previous_price") or 0

    def append_evt(name: str, ok: bool) -> None:
        if ok:
            events.append(name)

    append_evt("price_cross_ema_fast_up",
               _crossed_above(prev_price, _prev_ema(data.get("ema_fast")),
                              current_price, _ema_latest(data.get("ema_fast"))))
    append_evt("price_cross_ema_fast_down",
               _crossed_below(prev_price, _prev_ema(data.get("ema_fast")),
                              current_price, _ema_latest(data.get("ema_fast"))))
    append_evt("price_cross_ema_mid_up",
               _crossed_above(prev_price, _prev_ema(data.get("ema_mid")),
                              current_price, _ema_latest(data.get("ema_mid"))))
    append_evt("price_cross_ema_mid_down",
               _crossed_below(prev_price, _prev_ema(data.get("ema_mid")),
                              current_price, _ema_latest(data.get("ema_mid"))))

    prev_stack = _classify_ema_stack(
        _prev_ema(data.get("ema_fast")),
        _prev_ema(data.get("ema_mid")),
        _prev_ema(data.get("ema_slow")),
    )
    cur_stack = _classify_ema_stack(
        _ema_latest(data.get("ema_fast")),
        _ema_latest(data.get("ema_mid")),
        _ema_latest(data.get("ema_slow")),
    )
    append_evt("ema_stack_bull_flip", prev_stack != "bull" and cur_stack == "bull")
    append_evt("ema_stack_bear_flip", prev_stack != "bear" and cur_stack == "bear")

    aroon_sig = _classify_aroon_signal(data.get("aroon"))
    if aroon_sig == "strong_up":
        events.append("aroon_strong_bullish")
    elif aroon_sig == "strong_down":
        events.append("aroon_strong_bearish")

    td = data.get("td_sequential")
    if td:
        buy = td.get("buy_setup", 0) or 0
        sell = td.get("sell_setup", 0) or 0
        if buy >= 8:
            events.append(f"td_buy_setup_{buy}")
        if sell >= 8:
            events.append(f"td_sell_setup_{sell}")

    return events


def _crossed_above(prev_price: float, prev_ema: float, cur_price: float, cur_ema: float) -> bool:
    return prev_price > 0 and prev_ema > 0 and cur_price > 0 and cur_ema > 0 and prev_price <= prev_ema and cur_price > cur_ema


def _crossed_below(prev_price: float, prev_ema: float, cur_price: float, cur_ema: float) -> bool:
    return prev_price > 0 and prev_ema > 0 and cur_price > 0 and cur_ema > 0 and prev_price >= prev_ema and cur_price < cur_ema


def _classify_aroon_signal(aroon: dict[str, Any] | None) -> str:
    if not aroon:
        return ""
    up_dict = aroon.get("up")
    down_dict = aroon.get("down")
    if not isinstance(up_dict, dict) or not isinstance(down_dict, dict):
        return ""
    up = up_dict.get("latest")
    down = down_dict.get("latest")
    if up is None or down is None:
        return ""
    if up > AROON_STRONG and down < AROON_WEAK:
        return "strong_up"
    if down > AROON_STRONG and up < AROON_WEAK:
        return "strong_down"
    if up > AROON_STRONG and down > AROON_STRONG:
        return "crossover"
    return "neutral"


# ======================================================================
# Cross-TF Summary
# ======================================================================


def _build_cross_tf_summary(results: list[dict[str, Any]], decision_interval: str) -> dict[str, Any]:
    out = {"decision_tf_bias": "mixed", "alignment": "mixed"}
    if not results:
        return out

    decision_dur = _tf_minutes(decision_interval)
    lower = None
    decision = None
    higher = None

    for r in results:
        iv = r.get("interval", "")
        if iv == decision_interval:
            decision = r
        d = _tf_minutes(iv)
        if d < decision_dur:
            lower = r
        elif d > decision_dur and higher is None:
            higher = r

    if decision is None:
        for r in results:
            if r.get("interval") == decision_interval:
                decision = r
                break

    if decision is None:
        return out

    out["decision_tf_bias"] = decision.get("bias", "mixed")
    conflict_count = 0

    # Always include lower_tf_agreement (default false, matching brale)
    if lower is not None and decision.get("bias", "mixed") != "mixed":
        out["lower_tf_agreement"] = lower.get("bias") == decision.get("bias")
        lb = lower.get("bias", "mixed")
        if lb != "mixed" and lb != decision.get("bias"):
            conflict_count += 1
    else:
        out["lower_tf_agreement"] = False

    # Always include higher_tf_agreement (default false, matching brale)
    if higher is not None and decision.get("bias", "mixed") != "mixed":
        out["higher_tf_agreement"] = higher.get("bias") == decision.get("bias")
        hb = higher.get("bias", "mixed")
        if hb != "mixed" and hb != decision.get("bias"):
            conflict_count += 1
    else:
        out["higher_tf_agreement"] = False

    out["conflict_count"] = conflict_count

    if decision.get("bias") == "mixed":
        out["alignment"] = "mixed"
    elif conflict_count > 0:
        out["alignment"] = "conflict"
    else:
        out["alignment"] = "aligned"

    return out


# ======================================================================
# Missing Detection
# ======================================================================


def _detect_indicator_missing(data: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    checks = [
        ("ema", ["ema_fast", "ema_mid", "ema_slow"], all),
        ("rsi", ["rsi"], lambda ks: data.get(ks[0]) is not None),
        ("atr", ["atr"], lambda ks: data.get(ks[0]) is not None),
        ("obv", ["obv"], lambda ks: data.get(ks[0]) is not None),
        ("stc", ["stc"], lambda ks: data.get(ks[0]) is not None),
        ("bb", ["bb"], lambda ks: data.get(ks[0]) is not None),
        ("chop", ["chop"], lambda ks: data.get(ks[0]) is not None),
        ("stoch_rsi", ["stoch_rsi"], lambda ks: data.get(ks[0]) is not None),
        ("aroon", ["aroon"], lambda ks: data.get(ks[0]) is not None),
        ("td_sequential", ["td_sequential"], lambda ks: data.get(ks[0]) is not None),
    ]
    for label, keys, check_fn in checks:
        if not check_fn(keys):
            missing.append(label)
    return missing


# ======================================================================
# Helpers — extract values from Python compressed dict (adapted field names)
# ======================================================================


def _ema_latest(ema: dict[str, Any] | None) -> float:
    if not ema:
        return 0.0
    return float(ema.get("latest", 0) or 0)


def _prev_ema(ema: dict[str, Any] | None) -> float:
    if not ema:
        return 0.0
    last_n = ema.get("last_n") or []
    return float(last_n[-2]) if len(last_n) >= 2 else 0.0


def _rsi_latest(rsi: dict[str, Any] | None) -> float:
    if not rsi:
        return 0.0
    return float(rsi.get("latest", 0) or 0)


def _atr_latest(data: dict[str, Any]) -> float:
    atr = data.get("atr")
    if not atr:
        return 0.0
    return float(atr.get("latest", 0) or 0)


def _atr_change_pct(atr: dict[str, Any] | None) -> float:
    if not atr:
        return 0.0
    cp = atr.get("change_pct")
    return float(cp) if cp is not None else 0.0
