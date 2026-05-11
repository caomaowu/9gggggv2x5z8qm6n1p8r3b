"""
mechanics_state.py — Derivatives-market mechanics deterministic state classifier.

Ports brale-core-master internal/decision/features/mechanics_state.go (566 lines).

Consumes MechanicsCompressedInput (output of compress_mechanics) and produces:
  - OIState, FundingState, CrowdingState, LiquidationState, SentimentState
  - mechanics_conflict list, missing fields list, freshness_sec

Usage:
    from .mechanics_state import summarize_mechanics
    state = summarize_mechanics(mechanics_compressed_dict)
    # merge state into compressed dict before sending to LLM agent
"""

from __future__ import annotations

from typing import Any

# ======================================================================
# Thresholds (exact brale constants)
# ======================================================================

FUNDING_BIAS_THRESHOLD = 0.0001
FUNDING_HOT_THRESHOLD = 0.0005

CROWDING_LONG_LS_RATIO = 1.2
CROWDING_LONG_TAKER_RATIO = 1.1
CROWDING_SHORT_LS_RATIO = 0.8
CROWDING_SHORT_TAKER_RATIO = 0.9

FEAR_GREED_FEAR = 25
FEAR_GREED_NEUTRAL = 55
FEAR_GREED_GREED = 75
TOP_TRADER_LONG = 1.1
TOP_TRADER_SHORT = 0.9

LIQ_HIGH_ZSCORE = 2.5
LIQ_HIGH_VOL_OVER_OI = 0.08
LIQ_ELEVATED_ZSCORE = 1.5
LIQ_ELEVATED_VOL_OVER_OI = 0.04

OI_CHANGE_TREND_PCT = 2.0


# ======================================================================
# Public API
# ======================================================================


def summarize_mechanics(compressed: dict[str, Any]) -> dict[str, Any]:
    """Compute deterministic mechanics state from compressed input.
    
    Returns a dict with keys: oi_state, funding_state, crowding_state,
    liquidation_state, sentiment_state, mechanics_conflict, missing, freshness_sec.
    """
    state: dict[str, Any] = {}

    state["freshness_sec"] = _compute_freshness(compressed)
    state["oi_state"] = _classify_oi(compressed)
    state["funding_state"] = _classify_funding(compressed)
    state["liquidation_state"] = _classify_liquidation(compressed)
    state["crowding_state"] = _classify_crowding(
        compressed, state["funding_state"], state["liquidation_state"]
    )
    state["sentiment_state"] = _classify_sentiment(compressed)
    state["mechanics_conflict"] = _detect_conflicts(state)
    state["missing"] = _detect_missing(state)

    return state


def merge_state_into_compressed(compressed: dict[str, Any]) -> dict[str, Any]:
    """Merge state summary into compressed dict, stripping legacy noise fields.
    
    This produces the equivalent of brale's buildMechanicsStateRaw → strip.
    """
    state = summarize_mechanics(compressed)
    merged = {**compressed, **state}
    _strip_legacy_fields(merged)
    return merged


# ======================================================================
# OI State
# ======================================================================


def _classify_oi(compressed: dict[str, Any]) -> dict[str, Any] | None:
    oi_history = compressed.get("oi_history", {})
    intervals = [k for k in oi_history if isinstance(oi_history[k], dict)]
    if not intervals:
        return None
    entry = oi_history[intervals[0]]
    if entry.get("missing", False):
        return None
    change_pct = float(entry.get("change_pct", 0) or 0)
    price_change_pct = float(entry.get("price_change_pct", 0) or 0)
    return {
        "change_state": _classify_oi_change(change_pct),
        "oi_change_pct": round(change_pct, 2),
        "price_change_pct": round(price_change_pct, 2),
        "oi_price_relation": _classify_oi_price_relation(price_change_pct, change_pct),
    }


def _classify_oi_change(change_pct: float) -> str:
    if change_pct >= OI_CHANGE_TREND_PCT:
        return "rising"
    if change_pct <= -OI_CHANGE_TREND_PCT:
        return "falling"
    return "flat"


def _classify_oi_price_relation(price_pct: float, oi_pct: float) -> str:
    p = _sign_label(price_pct)
    o = _sign_label(oi_pct)
    if p == "up" and o == "up":
        return "price_up_oi_up"
    if p == "up" and o == "down":
        return "price_up_oi_down"
    if p == "down" and o == "up":
        return "price_down_oi_up"
    if p == "down" and o == "down":
        return "price_down_oi_down"
    if p == "flat" and o == "flat":
        return "mixed"
    return "unknown" if p == "unknown" or o == "unknown" else "mixed"


def _sign_label(value: float) -> str:
    if value > 0:
        return "up"
    if value < 0:
        return "down"
    return "flat"


# ======================================================================
# Funding State
# ======================================================================


def _classify_funding(compressed: dict[str, Any]) -> dict[str, Any] | None:
    funding = compressed.get("funding")
    if not funding or funding.get("missing"):
        return None
    rate = float(funding.get("rate", 0) or 0)
    rate = round(rate, 6)
    bias = "neutral"
    if rate > FUNDING_BIAS_THRESHOLD:
        bias = "long"
    elif rate < -FUNDING_BIAS_THRESHOLD:
        bias = "short"
    heat = "hot" if abs(rate) >= FUNDING_HOT_THRESHOLD else "neutral"
    return {"bias": bias, "heat": heat, "rate": rate}


# ======================================================================
# Crowding State
# ======================================================================


def _classify_crowding(
    compressed: dict[str, Any],
    funding_state: dict[str, Any] | None,
    liq_state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    ls_ratio, taker_ratio, ok = _crowding_anchors(compressed)
    if not ok:
        return None
    bias = "balanced"
    if ls_ratio > CROWDING_LONG_LS_RATIO and taker_ratio > CROWDING_LONG_TAKER_RATIO:
        bias = "long_crowded"
    elif ls_ratio < CROWDING_SHORT_LS_RATIO and taker_ratio < CROWDING_SHORT_TAKER_RATIO:
        bias = "short_crowded"

    reversal_risk = "low"
    if bias != "balanced":
        hot_funding = funding_state is not None and funding_state.get("heat") == "hot"
        high_liq = liq_state is not None and liq_state.get("stress") == "high"
        if hot_funding and high_liq:
            reversal_risk = "high"
        elif hot_funding or high_liq:
            reversal_risk = "medium"

    return {
        "bias": bias,
        "ls_ratio": round(ls_ratio, 4),
        "taker_ratio": round(taker_ratio, 4),
        "reversal_risk": reversal_risk,
    }


def _crowding_anchors(compressed: dict[str, Any]) -> tuple[float, float, bool]:
    fut = compressed.get("futures_sentiment")
    if fut and not fut.get("missing"):
        ls = fut.get("ls_ratio") or 0
        tr = fut.get("taker_long_short_vol_ratio") or 0
        if ls or tr:
            return float(ls), float(tr), True

    ls_bi = compressed.get("long_short_by_interval", {})
    intervals = sorted(ls_bi.keys()) if ls_bi else []
    for iv in intervals:
        v = ls_bi[iv]
        if isinstance(v, dict) and not v.get("missing"):
            ratio = v.get("ratio")
            if ratio is not None:
                return float(ratio), 0, True
    return 0, 0, False


# ======================================================================
# Liquidation State
# ======================================================================


def _classify_liquidation(compressed: dict[str, Any]) -> dict[str, Any] | None:
    liq_by_window = compressed.get("liquidations_by_window", {})
    if not liq_by_window:
        return None
    intervals = sorted(liq_by_window.keys())
    best: dict[str, Any] | None = None
    best_score = -1
    for iv in intervals:
        window = liq_by_window[iv]
        if not isinstance(window, dict):
            continue
        current = _summarize_liquidation_window(iv, window)
        score = _liquidation_stress_score(current.get("stress", "unknown"))
        if best is None or score > best_score or (
            score == best_score and _liquidation_tiebreaker(current) > _liquidation_tiebreaker(best)
        ):
            best = current
            best_score = score
    return best


def _summarize_liquidation_window(name: str, window: dict[str, Any]) -> dict[str, Any]:
    imbalance = float(window.get("imbalance", 0) or 0)

    rel = window.get("rel") or window.get("Rel")
    zscore = 0.0
    vol_over_oi = 0.0
    spike = False
    if rel and isinstance(rel, dict):
        zscore = float(rel.get("zscore", rel.get("ZScore", 0)) or 0)
        vol_over_oi = float(rel.get("vol_over_oi", rel.get("VolOverOI", 0)) or 0)
        spike = bool(rel.get("spike", rel.get("Spike", False)))

    base = {
        "window": name,
        "zscore": round(zscore, 4),
        "vol_over_oi": round(vol_over_oi, 4),
        "spike": spike,
        "imbalance": round(imbalance, 4),
    }

    stress = "low"
    if spike or zscore >= LIQ_HIGH_ZSCORE or vol_over_oi >= LIQ_HIGH_VOL_OVER_OI:
        stress = "high"
    elif zscore >= LIQ_ELEVATED_ZSCORE or vol_over_oi >= LIQ_ELEVATED_VOL_OVER_OI:
        stress = "elevated"

    return {**base, "stress": stress}


def _liquidation_stress_score(stress: str) -> int:
    return {"high": 3, "elevated": 2, "low": 1}.get(stress, 0)


def _liquidation_tiebreaker(state: dict[str, Any] | None) -> float:
    if state is None:
        return 0
    return abs(state.get("zscore", 0)) * 100 + abs(state.get("vol_over_oi", 0)) * 10 + abs(state.get("imbalance", 0))


# ======================================================================
# Sentiment State
# ======================================================================


def _classify_sentiment(compressed: dict[str, Any]) -> dict[str, Any] | None:
    fear_greed = compressed.get("fear_greed")
    has_fg = bool(fear_greed and not fear_greed.get("missing") and fear_greed.get("value") is not None)

    fut = compressed.get("futures_sentiment", {})
    top_trader_lsr = float(fut.get("top_trader_lsr") or 0) if fut else 0
    if top_trader_lsr == 0:
        top_trader_lsr = float(fut.get("ls_ratio") or 0) if fut else 0
    has_tt = top_trader_lsr != 0

    if not has_fg and not has_tt:
        return None

    fg_label = "unknown"
    if has_fg:
        v = int(round(fear_greed["value"]))
        if v <= FEAR_GREED_FEAR:
            fg_label = "fear"
        elif v <= FEAR_GREED_NEUTRAL:
            fg_label = "neutral"
        elif v <= FEAR_GREED_GREED:
            fg_label = "greed"
        else:
            fg_label = "extreme_greed"

    tt_bias = "unknown"
    if has_tt:
        if top_trader_lsr > TOP_TRADER_LONG:
            tt_bias = "long"
        elif top_trader_lsr < TOP_TRADER_SHORT:
            tt_bias = "short"
        else:
            tt_bias = "neutral"

    return {"fear_greed": fg_label, "top_trader_bias": tt_bias}


# ======================================================================
# Conflict Detection
# ======================================================================


def _detect_conflicts(state: dict[str, Any]) -> list[str]:
    conflicts: list[str] = []

    oi = state.get("oi_state")
    if oi:
        rel = oi.get("oi_price_relation", "")
        if rel in ("price_up_oi_down", "price_down_oi_down"):
            conflicts.append(rel)

    crowding = state.get("crowding_state")
    liq = state.get("liquidation_state")
    if crowding and liq and liq.get("stress") == "high":
        bias = crowding.get("bias", "")
        if bias == "long_crowded":
            conflicts.append("crowding_long_but_liq_stress_high")
        elif bias == "short_crowded":
            conflicts.append("crowding_short_but_liq_stress_high")

    funding = state.get("funding_state")
    if funding and oi:
        if funding.get("bias") == "long" and oi.get("change_state") == "falling":
            conflicts.append("funding_long_but_oi_falling")
        if funding.get("bias") == "short" and oi.get("change_state") == "rising":
            conflicts.append("funding_short_but_oi_rising")

    return conflicts


# ======================================================================
# Missing Detection
# ======================================================================


def _detect_missing(state: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if state.get("oi_state") is None:
        missing.append("oi_state")
    if state.get("funding_state") is None:
        missing.append("funding_state")
    if state.get("crowding_state") is None:
        missing.append("crowding_state")
    if state.get("liquidation_state") is None:
        missing.append("liquidation_state")
    if state.get("sentiment_state") is None:
        missing.append("sentiment_state")
    return missing


# ======================================================================
# Freshness
# ======================================================================


def _compute_freshness(compressed: dict[str, Any]) -> int:
    """Compute data freshness in seconds (minimum age across all sources)."""
    import time as _time
    from datetime import datetime, timezone

    ts_str = compressed.get("timestamp", "")
    try:
        ref = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return 0
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)

    best: float | None = None

    def visit(ts: str) -> None:
        nonlocal best
        ts = str(ts).strip()
        if not ts:
            return
        try:
            parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return
        age = int((ref - parsed).total_seconds())
        if age < 0:
            age = 0
        if best is None or age < best:
            best = age

    oi = compressed.get("oi")
    if oi and isinstance(oi, dict):
        visit(oi.get("timestamp", ""))
        visit(oi.get("price_timestamp", ""))

    funding = compressed.get("funding")
    if funding and isinstance(funding, dict):
        visit(funding.get("timestamp", ""))

    ls = compressed.get("long_short_by_interval", {})
    for v in ls.values():
        if isinstance(v, dict):
            visit(v.get("timestamp", ""))

    cvd = compressed.get("cvd_by_interval", {})
    for v in cvd.values():
        if isinstance(v, dict):
            visit(v.get("timestamp", ""))

    fg = compressed.get("fear_greed")
    if fg and isinstance(fg, dict):
        visit(fg.get("timestamp", ""))

    liq = compressed.get("liquidations")
    if liq and isinstance(liq, dict):
        visit(liq.get("timestamp", ""))

    fs = compressed.get("futures_sentiment")
    if fs and isinstance(fs, dict):
        visit(fs.get("timestamp", ""))

    return int(best) if best is not None else 0


# ======================================================================
# Strip legacy fields (brale: stripMechanicsStateLegacyFields)
# ======================================================================


def _strip_legacy_fields(payload: dict[str, Any]) -> None:
    """Remove fields that brale strips from the final state payload."""
    legacy_keys = {
        "timestamp", "fear_greed_next_update_sec", "fear_greed_history",
        "sentiment_by_interval", "bins", "price_bins_bps",
    }
    for key in legacy_keys:
        payload.pop(key, None)

    # Recursively strip empty sub-dicts
    to_delete = []
    for k, v in payload.items():
        if isinstance(v, dict):
            _strip_legacy_fields(v)
            if len(v) == 0:
                to_delete.append(k)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    _strip_legacy_fields(item)
    for k in to_delete:
        payload.pop(k, None)
