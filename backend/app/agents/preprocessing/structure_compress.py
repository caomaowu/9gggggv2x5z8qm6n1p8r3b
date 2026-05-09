"""
structure_compress.py — Market structure feature compression.

Replicates brale-core-master internal/decision/features/trend_compress_structure.go:
    - Fractal-point detection (swing highs/lows with configurable span)
    - Structure-candidate deduplication  & pruning (atr-based)
    - EMA context, Bollinger Band context, range-high/low extraction
    - Linear-regression slope, volume ratio helpers

Output: a compressed structure JSON fed to the Structure Agent.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

# ======================================================================
# Configuration
# ======================================================================


@dataclass
class StructureCompressOptions:
    fractal_span: int = 5              # span for isFractalHigh / isFractalLow
    max_structure_points: int = 12     # after merge
    dedup_distance_bars: int = 3       # dedup window in bars
    dedup_atr_factor: float = 0.5      # price-distance factor × ATR
    prune_per_side: int = 3            # max candidates above / below price
    volume_lookback: int = 20          # for volumeRatio
    ema_fast: int = 20                 # EMA periods for context
    ema_mid: int = 50
    ema_slow: int = 200
    bb_period: int = 20
    bb_multiplier: float = 2.0
    range_lookback: int = 30


DEFAULT_STRUCTURE_OPTIONS = StructureCompressOptions()


# ======================================================================
# Numeric helpers
# ======================================================================


def _lin_reg_slope(series: np.ndarray) -> float:
    """brale: linRegSlope (trend_compress_structure.go:105-124) — OLS slope."""
    mask = np.isfinite(series)
    ys = series[mask]
    n = len(ys)
    if n < 2:
        return 0.0
    xs = np.arange(n, dtype=np.float64)
    sum_x = np.sum(xs); sum_y = np.sum(ys)
    sum_xy = np.sum(xs * ys); sum_xx = np.sum(xs * xs)
    denom = n * sum_xx - sum_x * sum_x
    if abs(denom) < 1e-12:
        return 0.0
    return round(float((n * sum_xy - sum_x * sum_y) / denom), 6)


def _normalized_slope(series: np.ndarray) -> float:
    """brale: normalizedSlope (trend_compress_structure.go:170-180)"""
    mask = np.isfinite(series)
    ys = series[mask]
    if len(ys) < 2:
        return 0.0
    first = float(ys[0]); last = float(ys[-1])
    if abs(first) < 1e-9:
        return 0.0
    return round(((last - first) / abs(first)) * 100.0 / (len(ys) - 1), 6)


def _trend_slope_state(norm: float) -> str:
    """brale: trendSlopeState → FLAT | MODERATE | STEEP"""
    if norm is None or not np.isfinite(norm):
        return "FLAT"
    a = abs(norm)
    if a < 0.1: return "FLAT"
    if a < 0.4: return "MODERATE"
    return "STEEP"


def _volume_ratio(volumes: np.ndarray, lookback: int = 20) -> float:
    """brale: volumeRatio (trend_compress_structure.go:126-154)"""
    clean = volumes[np.isfinite(volumes)]
    n = len(clean)
    if n < 2:
        return 1.0
    latest = float(clean[-1])
    count = min(lookback, n - 1)
    if count < 1:
        return 1.0
    avg = np.mean(clean[-(1 + count): -1])
    if avg < 1e-12:
        return 1.0
    return round(latest / avg, 4)


# ======================================================================
# Fractal detection
# ======================================================================


def _is_fractal_high(highs: np.ndarray, idx: int, span: int) -> bool:
    """brale: isFractalHigh"""
    if idx < span or idx + span >= len(highs):
        return False
    v = highs[idx]
    for i in range(1, span + 1):
        if highs[idx - i] >= v or highs[idx + i] >= v:
            return False
    return True


def _is_fractal_low(lows: np.ndarray, idx: int, span: int) -> bool:
    """brale: isFractalLow"""
    if idx < span or idx + span >= len(lows):
        return False
    v = lows[idx]
    for i in range(1, span + 1):
        if lows[idx - i] <= v or lows[idx + i] <= v:
            return False
    return True


def _select_structure_points(
    highs: np.ndarray, lows: np.ndarray, span: int, max_points: int = 12
) -> list[dict]:
    """brale: selectStructurePoints (trend_compress_structure.go:12-42)"""
    n = len(highs)
    points: list[dict] = []
    for i in range(n - span - 1, span - 1, -1):
        if len(points) >= max_points * 2:
            break
        if _is_fractal_high(highs, i, span):
            points.append({"type": "high", "idx": i, "price": round(float(highs[i]), 4)})
            if len(points) >= max_points * 2:
                break
        if _is_fractal_low(lows, i, span):
            points.append({"type": "low", "idx": i, "price": round(float(lows[i]), 4)})
    points.sort(key=lambda p: p["idx"])
    return points


# ======================================================================
# Candidate building  (EMA / BB / range levels)
# ======================================================================


def _ema_array(closes: np.ndarray, period: int) -> np.ndarray:
    n = len(closes)
    out = np.full(n, np.nan, dtype=np.float64)
    if n < period:
        return out
    alpha = 2.0 / (period + 1.0)
    out[period - 1] = np.mean(closes[:period])
    for i in range(period, n):
        out[i] = alpha * closes[i] + (1 - alpha) * out[i - 1]
    return np.round(out, 4)


def _bbands(closes: np.ndarray, period: int, mult: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(closes)
    mid, upper, lower = (
        np.full(n, np.nan, dtype=np.float64),
        np.full(n, np.nan, dtype=np.float64),
        np.full(n, np.nan, dtype=np.float64),
    )
    for i in range(period - 1, n):
        win = closes[i - period + 1: i + 1]
        m = np.mean(win); s = np.std(win)
        mid[i] = m; upper[i] = m + mult * s; lower[i] = m - mult * s
    return np.round(mid, 4), np.round(upper, 4), np.round(lower, 4)


def _build_structure_candidates(
    closes: np.ndarray, highs: np.ndarray, lows: np.ndarray,
    volumes: np.ndarray, atr_series: np.ndarray,
    points: list[dict],
    opts: StructureCompressOptions,
) -> list[dict]:
    """brale: buildStructureCandidates (trend_compress_structure.go:194-277)"""
    n = len(closes)
    candidates: list[dict] = []
    current_price = float(closes[-1])
    timestamp = ""

    # 1. Fractal points
    for p in points:
        idx = p["idx"]
        age = n - 1 - idx
        source = "fractal_high" if p["type"] == "high" else "fractal_low"
        cat = "resistance" if p["type"] == "high" else "support"
        candidates.append({
            "source": source, "type": cat, "price": p["price"],
            "age_candles": age, "idx": idx, "timestamp": timestamp,
        })

    # 2. EMA context
    ema20 = _ema_array(closes, opts.ema_fast)
    ema50 = _ema_array(closes, opts.ema_mid)
    ema200 = _ema_array(closes, opts.ema_slow)
    for label, arr in [("ema_20", ema20), ("ema_50", ema50), ("ema_200", ema200)]:
        if np.isfinite(arr[-1]):
            candidates.append({
                "source": label, "type": "ema", "price": round(float(arr[-1]), 4),
                "age_candles": 0, "idx": n - 1, "timestamp": timestamp,
            })

    # 3. Bollinger Bands
    _, bb_up, bb_lo = _bbands(closes, opts.bb_period, opts.bb_multiplier)
    if np.isfinite(bb_up[-1]):
        candidates.append({
            "source": "band_upper", "type": "band_upper", "price": round(float(bb_up[-1]), 4),
            "age_candles": 0, "idx": n - 1, "timestamp": timestamp,
        })
    if np.isfinite(bb_lo[-1]):
        candidates.append({
            "source": "band_lower", "type": "band_lower", "price": round(float(bb_lo[-1]), 4),
            "age_candles": 0, "idx": n - 1, "timestamp": timestamp,
        })

    # 4. Range high / low
    lookback = min(opts.range_lookback, n)
    win_h = highs[-lookback:]; win_l = lows[-lookback:]
    range_hi = float(np.max(win_h[np.isfinite(win_h)])) if len(win_h) else None
    range_lo = float(np.min(win_l[np.isfinite(win_l)])) if len(win_l) else None
    if range_hi is not None:
        candidates.append({
            "source": "range_high", "type": "range_high", "price": round(range_hi, 4),
            "age_candles": 0, "idx": n - 1, "timestamp": timestamp,
        })
    if range_lo is not None:
        candidates.append({
            "source": "range_low", "type": "range_low", "price": round(range_lo, 4),
            "age_candles": 0, "idx": n - 1, "timestamp": timestamp,
        })

    # Dedup
    deduped = _dedup_candidates(candidates, atr_series, opts)

    # Prune
    return _prune_candidates(deduped, current_price, opts.prune_per_side)


def _dedup_candidates(candidates: list[dict], atr: np.ndarray, opts: StructureCompressOptions) -> list[dict]:
    """brale: dedupCandidates (trend_compress_structure.go:279-313)"""
    threshold = float(np.nanmean(atr[np.isfinite(atr)])) * opts.dedup_atr_factor if len(atr) > 0 else 0.0
    grouped: dict[tuple, list[dict]] = {}
    for c in candidates:
        key = (c["type"],)
        grouped.setdefault(key, []).append(c)

    result: list[dict] = []
    for items in grouped.values():
        items.sort(key=lambda x: (x["age_candles"], x["price"]))
        kept: list[dict] = []
        for it in items:
            can_merge = False
            for k in kept:
                if abs(it["price"] - k["price"]) < threshold:
                    can_merge = True
                    if it["type"] in ("fractal_high", "resistance", "band_upper", "range_high") and it["price"] > k["price"]:
                        k["price"] = it["price"]
                    elif it["type"] in ("fractal_low", "support", "band_lower", "range_low") and it["price"] < k["price"]:
                        k["price"] = it["price"]
                    break
            if not can_merge:
                if len(kept) < opts.max_structure_points:
                    kept.append(it)
        result.extend(kept)

    result.sort(key=lambda x: (x["age_candles"], x["price"]))
    return result


def _prune_candidates(candidates: list[dict], current_price: float, per_side: int) -> list[dict]:
    """brale: pruneStructureCandidates (trend_compress_structure.go:315-361)"""
    below = [c for c in candidates if c["price"] < current_price]
    above = [c for c in candidates if c["price"] > current_price]

    below.sort(key=lambda x: current_price - x["price"])
    above.sort(key=lambda x: x["price"] - current_price)

    result = below[:per_side] + above[:per_side]
    result.sort(key=lambda x: x["price"])
    return result


# ======================================================================
# Pattern detection  (lightweight heuristic)
# ======================================================================


def _detect_pattern(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> str:
    """Lightweight pattern detection: double-top/bottom, head-shoulders signal.

    Returns a pattern label string (matching brale's Pattern enum)."""
    n = len(closes)
    if n < 40:
        return "none"

    recent_h = highs[-20:]; recent_l = lows[-20:]
    hh = float(np.max(recent_h[np.isfinite(recent_h)]))
    ll = float(np.min(recent_l[np.isfinite(recent_l)]))

    # find extremes in last 20 bars
    h_idx = int(np.nanargmax(highs[-20:]) + n - 20) if len(highs[-20:]) > 0 else n - 1
    l_idx = int(np.nanargmin(lows[-20:]) + n - 20) if len(lows[-20:]) > 0 else n - 1

    # Heuristic: double-top when two comparable highs exist
    highs_clean = highs[np.isfinite(highs)]
    if len(highs_clean) >= 30:
        top1 = float(np.max(highs_clean[-30:-15]))
        top2 = float(np.max(highs_clean[-15:]))
        if abs(top1 - top2) / max(abs(top1), 1e-9) < 0.03:
            return "double_top"

    lows_clean = lows[np.isfinite(lows)]
    if len(lows_clean) >= 30:
        bot1 = float(np.min(lows_clean[-30:-15]))
        bot2 = float(np.min(lows_clean[-15:]))
        if abs(bot1 - bot2) / max(abs(bot1), 1e-9) < 0.03:
            return "double_bottom"

    return "none"


# ======================================================================
# Main compress entry-point
# ======================================================================


def compress_structure(
    candles: pd.DataFrame,
    interval: str,
    symbol: str = "",
    opts: StructureCompressOptions | None = None,
) -> dict[str, Any]:
    if opts is None:
        opts = DEFAULT_STRUCTURE_OPTIONS

    df = candles.copy()
    if "Date" in df.columns and not isinstance(df.index, pd.DatetimeIndex):
        df["_dt"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.drop(columns=["Date"], errors="ignore")
        df = df.set_index("_dt")
    df = df.sort_index()

    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    opens = df["Open"].values.astype(np.float64)
    highs = df["High"].values.astype(np.float64)
    lows = df["Low"].values.astype(np.float64)
    closes = df["Close"].values.astype(np.float64)
    volumes = df["Volume"].values.astype(np.float64)

    n = len(closes)
    current_price = float(closes[-1]) if n else None

    # ATR estimate (simple true-range average)
    tr_arr = np.maximum(highs - lows,
               np.maximum(np.abs(highs - np.roll(closes, 1)),
                          np.abs(lows - np.roll(closes, 1))))
    tr_arr[0] = highs[0] - lows[0]
    atr_raw = np.full(n, np.nan)
    period = 14
    for i in range(period - 1, n):
        atr_raw[i] = np.mean(tr_arr[i - period + 1: i + 1])

    # Fractal points
    points = _select_structure_points(highs, lows, opts.fractal_span, opts.max_structure_points)

    # Candidates
    candidates = _build_structure_candidates(closes, highs, lows, volumes, atr_raw, points, opts)

    # Key levels
    supports = [c for c in candidates if c["type"] in ("support", "fractal_low", "ema", "band_lower", "range_low")]
    resistances = [c for c in candidates if c["type"] in ("resistance", "fractal_high", "band_upper", "range_high")]

    # Slope & state
    clean_c = closes[np.isfinite(closes)]
    raw_slope = _lin_reg_slope(clean_c[-30:]) if len(clean_c) >= 30 else _lin_reg_slope(clean_c)
    norm_slope = _normalized_slope(clean_c[-30:]) if len(clean_c) >= 30 else _normalized_slope(clean_c)
    slope_state = _trend_slope_state(norm_slope)

    # Volume action
    vol_ratio = _volume_ratio(volumes, opts.volume_lookback)

    # Pattern
    pattern = _detect_pattern(closes, highs, lows)

    # EMA context
    ema20 = _ema_array(closes, 20)
    ema50 = _ema_array(closes, 50)
    ema200 = _ema_array(closes, 200)
    ema_bullish = bool(np.isfinite(ema20[-1]) and np.isfinite(ema50[-1]) and np.isfinite(ema200[-1])
                       and ema20[-1] > ema50[-1] > ema200[-1])
    ema_bearish = bool(np.isfinite(ema20[-1]) and np.isfinite(ema50[-1]) and np.isfinite(ema200[-1])
                       and ema20[-1] < ema50[-1] < ema200[-1])

    _meta = {
        "series_order": "oldest_to_latest",
        "version": "structure_compress_v1",
        "timestamp_now_ts": int(time.time() * 1000),
    }

    market = {"symbol": symbol, "interval": interval, "current_price": current_price}

    data = {
        "candles_count": n,
        "slope": raw_slope,
        "normalized_slope": norm_slope,
        "slope_state": slope_state,
        "volume_ratio": vol_ratio,
        "ema_context": {"ema20_bullish": ema_bullish, "ema20_bearish": ema_bearish,
                        "ema20": round(float(ema20[-1]), 4) if np.isfinite(ema20[-1]) else None,
                        "ema50": round(float(ema50[-1]), 4) if np.isfinite(ema50[-1]) else None,
                        "ema200": round(float(ema200[-1]), 4) if np.isfinite(ema200[-1]) else None},
        "fractal_points": points,
        "candidates": candidates,
        "supports": supports,
        "resistances": resistances,
        "pattern_hint": pattern,
    }

    return {"_meta": _meta, "market": market, "data": data}
