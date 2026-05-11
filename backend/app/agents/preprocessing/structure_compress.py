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

# brale pattern detection
from app.agents.preprocessing.pattern.geometry import detect as detect_geometry, Options as GeometryOpts
from app.agents.preprocessing.pattern.cdl import detect as detect_candle, Options as CandleOpts
from app.agents.preprocessing.pattern.evidence import combine as combine_patterns, Options as EvidenceOpts

# ======================================================================
# Configuration
# ======================================================================


@dataclass
class StructureCompressOptions:
    fractal_span: int = 2              # span for isFractalHigh / isFractalLow (brale default)
    max_structure_points: int = 8
    dedup_distance_bars: int = 10
    dedup_atr_factor: float = 0.5
    prune_per_side: int = 3
    volume_lookback: int = 20
    ema_fast: int = 20
    ema_mid: int = 50
    ema_slow: int = 200
    bb_period: int = 20
    bb_multiplier: float = 2.0
    range_lookback: int = 30
    # SuperTrend
    supertrend_period: int = 14
    supertrend_multiplier: float = 2.5
    # SMC
    emit_smc: bool = True
    # Recent candles
    recent_candles: int = 5
    include_rsi: bool = True                    # RSI in recent candles
    include_structure_rsi: bool = True          # RSI in structure (fractal) points


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
    return float((n * sum_xy - sum_x * sum_y) / denom)


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
    return round(latest / avg, 3)


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
    highs: np.ndarray, lows: np.ndarray, span: int,
    atr: np.ndarray, rsi: np.ndarray, opts: StructureCompressOptions,
) -> list[dict]:
    """brale: selectStructurePoints with mergeStructurePoint (trend_compress_structure.go:12-103).

    Detects fractal highs/lows with inline dedup: same type, within
    dedup_distance_bars bars and atr*dedup_atr_factor price threshold
    → merge (highs keep higher, lows keep lower).
    """
    n = len(highs)
    points: list[dict] = []

    for i in range(n - span - 1, span - 1, -1):
        # ATR at this specific index (matching brale: atr[candidate.Idx])
        idx_atr = float(atr[i]) if i < len(atr) and np.isfinite(atr[i]) and abs(atr[i]) > 1e-9 else 0.0

        # --- fractal high ---
        if _is_fractal_high(highs, i, span):
            cand = {"type": "high", "idx": i, "price": round(float(highs[i]), 4)}
            if opts.include_structure_rsi and i < len(rsi):
                v = rsi[i]
                if np.isfinite(v):
                    cand["rsi"] = round(float(v), 1)
            merged = False
            for p in points:
                if p["type"] != "high":
                    continue
                if abs(p["idx"] - i) > opts.dedup_distance_bars:
                    continue
                threshold = idx_atr * opts.dedup_atr_factor
                if threshold <= 0:
                    pid_x = p["idx"]
                    p_atr = float(atr[pid_x]) if pid_x < len(atr) and np.isfinite(atr[pid_x]) else 0.0
                    threshold = p_atr * opts.dedup_atr_factor
                if threshold > 0 and abs(p["price"] - cand["price"]) <= threshold:
                    if cand["price"] > p["price"]:
                        p["price"] = cand["price"]
                        p["idx"] = i
                        if opts.include_structure_rsi and "rsi" in cand:
                            p["rsi"] = cand["rsi"]
                    merged = True
                    break
            if not merged and len(points) < opts.max_structure_points:
                points.append(cand)

        if len(points) >= opts.max_structure_points:
            continue

        # --- fractal low ---
        if _is_fractal_low(lows, i, span):
            cand = {"type": "low", "idx": i, "price": round(float(lows[i]), 4)}
            if opts.include_structure_rsi and i < len(rsi):
                v = rsi[i]
                if np.isfinite(v):
                    cand["rsi"] = round(float(v), 1)
            merged = False
            for p in points:
                if p["type"] != "low":
                    continue
                if abs(p["idx"] - i) > opts.dedup_distance_bars:
                    continue
                threshold = idx_atr * opts.dedup_atr_factor
                if threshold <= 0:
                    pid_x = p["idx"]
                    p_atr = float(atr[pid_x]) if pid_x < len(atr) and np.isfinite(atr[pid_x]) else 0.0
                    threshold = p_atr * opts.dedup_atr_factor
                if threshold > 0 and abs(p["price"] - cand["price"]) <= threshold:
                    if cand["price"] < p["price"]:
                        p["price"] = cand["price"]
                        p["idx"] = i
                        if opts.include_structure_rsi and "rsi" in cand:
                            p["rsi"] = cand["rsi"]
                    merged = True
                    break
            if not merged and len(points) < opts.max_structure_points:
                points.append(cand)

    points.sort(key=lambda p: p["idx"])
    return points


# ======================================================================
# Candidate building  (EMA / BB / range levels)
# ======================================================================


def _ema_array(closes: np.ndarray, period: int) -> np.ndarray:
    """EMA with series[0] seed (matching brale emaSpan)."""
    n = len(closes)
    out = np.full(n, np.nan, dtype=np.float64)
    if n < period:
        return out
    alpha = 2.0 / (period + 1.0)
    out[0] = float(closes[0])
    for i in range(1, n):
        out[i] = alpha * float(closes[i]) + (1 - alpha) * out[i - 1]
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
    """brale: dedupCandidates — merge same-type candidates within ATR threshold, keeping younger (lower age)."""
    # latest valid ATR
    atr_latest = 0.0
    for v in reversed(atr):
        if np.isfinite(v) and abs(v) > 1e-9:
            atr_latest = float(v)
            break
    threshold = atr_latest * opts.dedup_atr_factor

    out: list[dict] = []
    for c in candidates:
        merged = False
        for i in range(len(out)):
            if out[i]["type"] != c["type"]:
                continue
            if threshold > 0 and abs(out[i]["price"] - c["price"]) <= threshold:
                # Keep younger (lower age_candles) — matching brale dedupCandidates
                if c["age_candles"] < out[i]["age_candles"] or out[i]["age_candles"] == 0:
                    out[i] = c
                merged = True
                break
        if not merged:
            out.append(c)

    out.sort(key=lambda x: (x["age_candles"], x["price"]))
    return out


def _prune_candidates(candidates: list[dict], current_price: float, per_side: int) -> list[dict]:
    """brale: pruneStructureCandidates (trend_compress_structure.go:315-361)"""
    below = [c for c in candidates if c["price"] < current_price]
    above = [c for c in candidates if c["price"] > current_price]

    below.sort(key=lambda x: current_price - x["price"])
    above.sort(key=lambda x: x["price"] - current_price)

    result = below[:per_side] + above[:per_side]
    result.sort(key=lambda x: (x["price"], x["age_candles"]))
    return result


# ======================================================================
# Pattern detection  (lightweight heuristic)
# ======================================================================


# (Removed _detect_pattern — lightweight heuristic never called; brale has no equivalent.)


# ======================================================================
# SuperTrend  (HMA-based, ported from brale trend_supertrend.go)
# ======================================================================


def _wma(values: np.ndarray, period: int) -> np.ndarray:
    """Weighted Moving Average (brale: wmaSeries)."""
    n = len(values)
    if n < period or period <= 0:
        return np.full(0, np.nan)
    divisor = float(period * (period + 1)) / 2.0
    out = np.full(n - period + 1, np.nan, dtype=np.float64)
    for end in range(period - 1, n):
        s = 0.0
        w = float(period)
        for idx in range(end - period + 1, end + 1):
            s += values[idx] * w
            w -= 1.0
        out[end - period + 1] = s / divisor
    return out


def _hma(values: np.ndarray, period: int) -> np.ndarray:
    """Hull Moving Average (brale: hmaSeries)."""
    n = len(values)
    if n == 0 or period <= 0:
        return np.full(0, np.nan)
    half_period = int(round(period / 2.0))
    sqrt_period = int(round(np.sqrt(float(period))))
    if half_period <= 0 or sqrt_period <= 0:
        return np.full(0, np.nan)

    wma1 = _wma(values, half_period)
    wma2 = _wma(values, period)
    if len(wma2) == 0:
        return np.full(0, np.nan)
    skip = period - half_period
    if skip < 0 or skip > len(wma1):
        return np.full(0, np.nan)
    wma1 = wma1[skip:]
    mn = min(len(wma1), len(wma2))
    wma1 = wma1[:mn]; wma2 = wma2[:mn]
    diff = 2.0 * wma1 - wma2
    return _wma(diff, sqrt_period)


def _compute_supertrend(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    period: int = 14, multiplier: float = 2.5,
) -> dict[str, Any] | None:
    """HMA-based SuperTrend (brale: computeSuperTrendSeries + buildSuperTrendSnapshot)."""
    n = len(closes)
    if n < 2 or period <= 0:
        return None

    tr = np.maximum(highs[1:] - lows[1:],
                    np.maximum(np.abs(highs[1:] - closes[:-1]),
                               np.abs(lows[1:] - closes[:-1])))
    atr = _hma(tr, period)
    if len(atr) == 0:
        return None

    sqrt_period = int(round(np.sqrt(float(period))))
    atr_idle = period + sqrt_period - 1
    if atr_idle >= n:
        return None

    medians = (highs[atr_idle:] + lows[atr_idle:]) / 2.0
    closings = closes[atr_idle:]
    mn_atr = min(len(atr), len(medians), len(closings))
    atr = atr[:mn_atr]; medians = medians[:mn_atr]; closings = closings[:mn_atr]

    st_series = np.full(mn_atr, np.nan, dtype=np.float64)
    up_trend = False
    final_upper = 0.0
    final_lower = 0.0
    prev_close = 0.0

    for i in range(mn_atr):
        median = medians[i]
        atr_m = atr[i] * multiplier
        close_v = closings[i]
        basic_upper = median + atr_m
        basic_lower = median - atr_m

        if i == 0:
            final_upper = basic_upper
            final_lower = basic_lower
            st_series[i] = final_lower
        else:
            if basic_upper < final_upper or prev_close > final_upper:
                final_upper = basic_upper
            if basic_lower > final_lower or prev_close < final_lower:
                final_lower = basic_lower
            if up_trend:
                if close_v <= final_upper:
                    st_series[i] = final_upper
                else:
                    st_series[i] = final_lower
                    up_trend = False
            else:
                if close_v >= final_lower:
                    st_series[i] = final_lower
                else:
                    st_series[i] = final_upper
                    up_trend = True
        prev_close = close_v

    for i in range(mn_atr - 1, -1, -1):
        level = st_series[i]
        close_v = closings[i]
        if np.isnan(level) or np.isinf(level) or abs(level) <= 1e-12:
            continue
        if np.isnan(close_v) or np.isinf(close_v) or abs(close_v) <= 1e-12:
            continue
        state = "UP" if close_v >= level else "DOWN"
        return {
            "interval": "",
            "state": state,
            "level": round(float(level), 4),
            "distance_pct": round(abs(close_v - level) / close_v * 100.0, 4),
        }
    return None


# ======================================================================
# SMC — OrderBlock + FVG  (ported from brale trend_compress.go)
# ======================================================================


def _detect_smc(highs: np.ndarray, lows: np.ndarray, opens: np.ndarray, closes: np.ndarray) -> dict[str, Any] | None:
    """Detect OrderBlock and FVG (Fair Value Gap)."""
    n = len(closes)
    if n < 5:
        return None

    # Bias from EMA34 (matching brale emaSpan(34))
    alpha_34 = 2.0 / (34.0 + 1.0)
    ema34 = float(closes[0])
    for i in range(1, n):
        ema34 = alpha_34 * float(closes[i]) + (1.0 - alpha_34) * ema34
    bias = "bullish" if closes[-1] >= ema34 else "bearish"

    ob = _detect_order_block(opens, highs, lows, closes, bias)
    fvg = _detect_fvg(highs, lows, closes)

    return {"order_block": ob, "fvg": fvg}  # always return dict (matching brale TrendSMC)


def _detect_order_block(
    opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, bias: str
) -> dict[str, Any] | None:
    """Find OB in last 8 bars. Bullish→bear candle as support, Bearish→bull candle as resistance."""
    n = len(closes)
    recent = slice(max(n - 8, 0), n)
    r_opens = opens[recent]; r_highs = highs[recent]; r_lows = lows[recent]; r_closes = closes[recent]
    for i in range(len(r_closes) - 1, -1, -1):
        o, h, l, c = r_opens[i], r_highs[i], r_lows[i], r_closes[i]
        if bias == "bullish" and c < o:
            return {
                "type": "bullish",
                "upper": round(float(max(o, c)), 4),
                "lower": round(float(min(l, o)), 4),
            }
        if bias == "bearish" and c > o:
            return {
                "type": "bearish",
                "upper": round(float(max(o, h)), 4),
                "lower": round(float(min(o, c)), 4),
            }
    return None


def _detect_fvg(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> dict[str, Any] | None:
    """Detect Fair Value Gap — gap between 3 bars with unfilled space."""
    n = len(closes)
    for offset in range(2, 6):
        idx = n - offset
        if idx - 2 < 0:
            break
        hi_prev = highs[idx - 2]; lo_prev = lows[idx - 2]
        hi_cur = highs[idx]; lo_cur = lows[idx]
        # Bullish FVG: gap above
        if lows[idx - 1] > hi_prev and lo_cur > hi_prev:
            return {
                "type": "bullish",
                "gap_top": round(float(lo_cur), 4),
                "gap_bottom": round(float(hi_prev), 4),
            }
        # Bearish FVG: gap below
        if highs[idx - 1] < lo_prev and hi_cur < lo_prev:
            return {
                "type": "bearish",
                "gap_top": round(float(lo_prev), 4),
                "gap_bottom": round(float(hi_cur), 4),
            }
    return None


# ======================================================================
# Recent Candles  (brale: buildRecentCandles, trend_compress.go:644-672)
# ======================================================================


def _rsi_wilder(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder smoothing RSI for structure context."""
    n = len(closes)
    rsi = np.full(n, np.nan, dtype=np.float64)
    if n < period + 1:
        return rsi
    gains = np.maximum(np.diff(closes, prepend=closes[0]), 0.0)
    losses = np.maximum(-np.diff(closes, prepend=closes[0]), 0.0)
    avg_gain = np.mean(gains[1:period + 1])
    avg_loss = np.mean(losses[1:period + 1])
    rsi[period] = 100.0 - 100.0 / (1.0 + avg_gain / max(avg_loss, 1e-12))
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rsi[i] = 100.0 - 100.0 / (1.0 + avg_gain / max(avg_loss, 1e-12))
    return np.round(rsi, 1)


def _build_recent_candles(
    opens: np.ndarray, highs: np.ndarray, lows: np.ndarray,
    closes: np.ndarray, volumes: np.ndarray, rsi: np.ndarray,
    opts: StructureCompressOptions,
) -> list[dict[str, Any]]:
    """Build last N candles with OHLVC + optional RSI."""
    n = len(closes)
    keep = min(opts.recent_candles, n)
    start = n - keep
    out: list[dict[str, Any]] = []
    for idx in range(start, n):
        rc: dict[str, Any] = {
            "idx": idx,
            "o": round(float(opens[idx]), 4),
            "h": round(float(highs[idx]), 4),
            "l": round(float(lows[idx]), 4),
            "c": round(float(closes[idx]), 4),
            "v": round(float(volumes[idx]), 4),
        }
        if opts.include_rsi and idx < len(rsi):
            v = rsi[idx]
            if (not np.isnan(v)) and (not np.isinf(v)):
                rc["rsi"] = float(v)
        out.append(rc)
    return out


# ======================================================================
# Key Levels  (brale: buildTrendKeyLevels, trend_compress.go:475-501)
# ======================================================================


def _build_key_levels(points: list[dict]) -> dict[str, Any] | None:
    """Extract last_swing_high and last_swing_low from fractal points."""
    last_high = None
    last_low = None
    for p in reversed(points):
        t = p.get("type", "")
        if last_high is None and t == "high":
            last_high = {"price": p["price"], "idx": p["idx"]}
        if last_low is None and t == "low":
            last_low = {"price": p["price"], "idx": p["idx"]}
        if last_high and last_low:
            break
    if not last_high and not last_low:
        return None
    result: dict[str, Any] = {}
    if last_high:
        result["last_swing_high"] = last_high
    if last_low:
        result["last_swing_low"] = last_low
    return result


# ======================================================================
# Break Events  (brale: detectLatestBreakEvent, trend_compress.go:522-558)
# ======================================================================


def _build_break_events(
    closes: np.ndarray, key_levels: dict[str, Any] | None
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """brale: detectLatestBreakEvent — single scan from end, return the most recent break event."""
    n = len(closes)
    if n < 2 or key_levels is None:
        return [], None

    latest_idx = n - 1
    high = key_levels.get("last_swing_high")
    low = key_levels.get("last_swing_low")

    for i in range(latest_idx, 0, -1):
        prev_c = closes[i - 1]
        curr_c = closes[i]
        if high and prev_c <= high["price"] < curr_c:
            evt = {
                "type": "break_up",
                "level_price": high["price"],
                "level_idx": high["idx"],
                "bar_idx": i,
                "bar_age": latest_idx - i,
                "confirm": "close",
            }
            summary = {
                "latest_event_type": evt["type"],
                "latest_event_age": evt["bar_age"],
                "latest_event_bar_idx": evt["bar_idx"],
                "latest_event_level_price": evt["level_price"],
                "latest_event_level_idx": evt["level_idx"],
            }
            return [evt], summary
        if low and prev_c >= low["price"] > curr_c:
            evt = {
                "type": "break_down",
                "level_price": low["price"],
                "level_idx": low["idx"],
                "bar_idx": i,
                "bar_age": latest_idx - i,
                "confirm": "close",
            }
            summary = {
                "latest_event_type": evt["type"],
                "latest_event_age": evt["bar_age"],
                "latest_event_bar_idx": evt["bar_idx"],
                "latest_event_level_price": evt["level_price"],
                "latest_event_level_idx": evt["level_idx"],
            }
            return [evt], summary

    return [], None


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

    # ATR (Wilder-smoothed, matching brale ta.ATR / rma)
    tr_arr = np.maximum(highs[1:] - lows[1:],
               np.maximum(np.abs(highs[1:] - closes[:-1]),
                           np.abs(lows[1:] - closes[:-1])))
    atr_raw = np.full(n, np.nan)
    period_atr = 14
    if n >= period_atr:
        tr_full = np.empty(n)
        tr_full[0] = highs[0] - lows[0]
        tr_full[1:] = tr_arr
        # initial SMA
        atr_raw[period_atr - 1] = np.mean(tr_full[:period_atr])
        # Wilder smoothing
        for i in range(period_atr, n):
            atr_raw[i] = (atr_raw[i - 1] * (period_atr - 1) + tr_full[i]) / period_atr

    # RSI (for recent_candles with RSI context)
    rsi_raw = np.full(n, np.nan, dtype=np.float64)
    if opts.include_rsi:
        rsi_raw = _rsi_wilder(closes, 14)

    # Fractal points (with inline mergeStructurePoint dedup)
    points = _select_structure_points(highs, lows, opts.fractal_span, atr_raw, rsi_raw, opts)

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

    # Pattern detection (brale geometry + cdl + evidence)
    pattern = None
    try:
        candles_list = [{"open": float(opens[i]), "high": float(highs[i]), "low": float(lows[i]), "close": float(closes[i])}
                        for i in range(n)]
        geom_res = detect_geometry(candles_list)
        candle_res = detect_candle(candles_list)
        pattern = combine_patterns(geom_res, candle_res)
    except Exception:
        pass

    # SuperTrend (HMA-based, ported from brale trend_supertrend.go)
    supertrend = None
    if opts.supertrend_period > 0:
        supertrend = _compute_supertrend(highs, lows, closes, opts.supertrend_period, opts.supertrend_multiplier)

    # SMC: OrderBlock + FVG
    smc = None
    if opts.emit_smc:
        smc = _detect_smc(highs, lows, opens, closes)

    # Recent candles (brale: buildRecentCandles)
    recent_candles = _build_recent_candles(opens, highs, lows, closes, volumes, rsi_raw, opts)

    # Key levels (brale: buildTrendKeyLevels)
    key_levels = _build_key_levels(points)

    # Break events + summary (brale: detectLatestBreakEvent)
    break_events, break_summary = _build_break_events(closes, key_levels)

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
        "supertrend": supertrend,
        "smc": smc,
        "recent_candles": recent_candles,
        "key_levels": key_levels,
        "break_events": break_events,
        "break_summary": break_summary,
        "fractal_points": points,
        "candidates": candidates,
        "supports": supports,
        "resistances": resistances,
        "pattern": pattern,
    }

    return {"_meta": _meta, "market": market, "data": data}
