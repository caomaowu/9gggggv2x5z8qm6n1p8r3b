"""
indicator_compress.py — OHLCV multi-timeframe indicator compression.

Replicates brale-core-master internal/decision/features/indicator_compress.go
and indicator_stc.go.  Computes 10 indicators, builds structured snapshots,
and emits a compressed JSON input for the Indicator Agent.

Design:
    - All series computations use NumPy vectorisation where possible.
    - NaN/Inf are filtered before snapshot building (sanitise → bounds → tail).
    - Output structure matches brale's IndicatorCompressedInput JSON shape.

Reference defaults (from brale internal/config/defaults.go):
    EMAFast=21   EMA_Mid=50   EMA_Slow=200
    RSI=14       ATRPeriod=14
    STC_Fast=23  STC_Slow=50  STC_K=10  STC_D=3
    BB=20        BB_Mult=2.0
    CHOP=14      StochRSI=14
    Aroon=25     LastN=5
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

# ======================================================================
# Configuration
# ======================================================================


@dataclass
class IndicatorCompressOptions:
    """brale: IndicatorCompressOptions (indicator_compress.go:19-44)"""

    ema_fast: int = 21
    ema_mid: int = 50
    ema_slow: int = 200
    rsi_period: int = 14
    atr_period: int = 14
    stc_fast: int = 23
    stc_slow: int = 50
    stc_k: int = 10       # DefaultSTCKPeriod (stochastic K window)
    stc_d: int = 3        # DefaultSTCDPeriod  (smoothing window)
    bb_period: int = 20
    bb_multiplier: float = 2.0
    chop_period: int = 14
    stoch_rsi_period: int = 14
    aroon_period: int = 25
    last_n: int = 5

    skip_ema: bool = False
    skip_rsi: bool = False
    skip_atr: bool = False
    skip_obv: bool = False
    skip_stc: bool = False
    skip_bb: bool = False
    skip_chop: bool = False
    skip_stoch_rsi: bool = False
    skip_aroon: bool = False
    skip_td_sequential: bool = False

    pretty: bool = False


DEFAULT_OPTIONS = IndicatorCompressOptions()

# ======================================================================
# Numeric helpers  (1:1 brale)
# ======================================================================


def _clamp(v: float, lo: float, hi: float) -> float:
    """brale: clampFloat64 (indicator_stc.go:92-100)"""
    return max(lo, min(hi, v))


def _sanitize(series: np.ndarray) -> np.ndarray:
    """brale: sanitizeSeries (indicator_compress.go:525-537)
    Filter NaN/Inf, keep 4 decimal places."""
    mask = np.isfinite(series)
    clean = series[mask]
    return np.round(clean, 4)


def _bounds(series: np.ndarray) -> tuple[float, float]:
    """brale: seriesBounds (indicator_compress.go:539-560)"""
    clean = series[np.isfinite(series)]
    if len(clean) == 0:
        return 0.0, 0.0
    return float(np.min(clean)), float(np.max(clean))


def _tail(series: np.ndarray, n: int) -> np.ndarray:
    """brale: roundSeriesTail (indicator_compress.go:562-575)"""
    clean = series[np.isfinite(series)]
    if len(clean) == 0:
        return np.array([], dtype=np.float64)
    return np.round(clean[-min(n, len(clean)):], 4)


def _safe_div(a: float, b: float) -> float | None:
    """Return a / b, or None when b is near zero."""
    if abs(b) < 1e-12:
        return None
    return a / b


def _compute_slope(series: np.ndarray) -> dict:
    """brale: computeSlopeSeries (indicator_compress.go:577-599)

    Returns {slope, normalized} using the last ≤5 points."""
    clean = _sanitize(series)
    pts = clean[-min(5, len(clean)):]
    n = len(pts)
    if n < 2:
        return {"slope": 0.0, "normalized": 0.0}
    first = float(pts[0])
    last = float(pts[-1])
    steps = n - 1
    raw = (last - first) / steps
    norm = raw
    if abs(first) > 1e-9:
        norm = (raw / abs(first)) * 100.0 / steps
    return {"slope": round(raw, 6), "normalized": round(norm, 6)}


def _compute_change_pct(series: np.ndarray) -> float:
    """brale: computeChangePct (indicator_compress.go:601-612)"""
    clean = _sanitize(series)
    if len(clean) < 2:
        return 0.0
    prev = float(clean[-2])
    last = float(clean[-1])
    if abs(prev) < 1e-9:
        return 0.0
    return round(((last - prev) / abs(prev)) * 100.0, 4)


def _slope_state(normalized: float) -> str:
    """brale: indicatorSlopeState (indicator_compress.go:614-627)
    → 'FLAT' | 'MODERATE' | 'STEEP'"""
    if normalized is None or not np.isfinite(normalized):
        return "FLAT"
    a = abs(normalized)
    if a < 0.1:
        return "FLAT"
    if a < 0.4:
        return "MODERATE"
    return "STEEP"


def _nanarr(n: int) -> np.ndarray:
    return np.full(n, np.nan, dtype=np.float64)


# ======================================================================
# EMA
# ======================================================================


def _ema(series: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average (1 / alpha = period)."""
    if len(series) < period:
        return _nanarr(len(series))
    alpha = 2.0 / (period + 1.0)
    out = np.full(len(series), np.nan, dtype=np.float64)
    out[period - 1] = np.mean(series[:period])
    for i in range(period, len(series)):
        out[i] = alpha * series[i] + (1 - alpha) * out[i - 1]
    return np.round(out, 4)


# ======================================================================
# RSI
# ======================================================================


def _rsi(closes: np.ndarray, period: int) -> np.ndarray:
    """Wilder's smoothed RSI."""
    n = len(closes)
    if n < period + 1:
        return _nanarr(n)
    delta = np.diff(closes)
    gains = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)
    out = np.full(n, np.nan, dtype=np.float64)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    if avg_loss < 1e-12:
        out[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        out[period] = 100.0 - 100.0 / (1.0 + rs)
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        if avg_loss < 1e-12:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - 100.0 / (1.0 + rs)
    return np.round(out, 4)


# ======================================================================
# ATR  (Wilder)
# ======================================================================


def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> np.ndarray:
    n = len(closes)
    if n < period + 1:
        return _nanarr(n)
    outs = np.full(n, np.nan, dtype=np.float64)
    prev_close = closes[:-1]
    tr = np.maximum(highs[1:] - lows[1:],
                    np.maximum(np.abs(highs[1:] - prev_close),
                               np.abs(lows[1:] - prev_close)))
    outs[period] = np.mean(tr[:period])
    for i in range(period + 1, n):
        outs[i] = (outs[i - 1] * (period - 1) + tr[i - 1]) / period
    return np.round(outs, 4)


# ======================================================================
# OBV
# ======================================================================


def _obv(closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
    """brale: computeOBVSeries (indicator_compress.go:480-499)"""
    n = len(closes)
    obv = np.full(n, np.nan, dtype=np.float64)
    obv[0] = float(volumes[0])
    for i in range(1, n):
        diff = closes[i] - closes[i - 1]
        direction = 1.0 if diff > 0 else (-1.0 if diff < 0 else 0.0)
        obv[i] = obv[i - 1] + direction * float(volumes[i])
    return np.round(obv, 4)


# ======================================================================
# Bollinger Bands
# ======================================================================


def _bollinger(closes: np.ndarray, period: int, mult: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (middle, upper, lower)."""
    n = len(closes)
    if n < period:
        nan = _nanarr(n)
        return nan, nan, nan
    middle = np.full(n, np.nan, dtype=np.float64)
    upper = np.full(n, np.nan, dtype=np.float64)
    lower = np.full(n, np.nan, dtype=np.float64)
    for i in range(period - 1, n):
        win = closes[i - period + 1: i + 1]
        m = np.mean(win)
        s = np.std(win)
        middle[i] = m
        upper[i] = m + mult * s
        lower[i] = m - mult * s
    return np.round(middle, 4), np.round(upper, 4), np.round(lower, 4)


# ======================================================================
# CHOP  (Choppiness Index  —  E.W.Dreiss)
# ======================================================================


def _choppiness(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> np.ndarray:
    """CHOP (Choppiness Index by E.W.Dreiss) using standard True Range."""
    n = len(closes)
    if n < period + 1:
        return _nanarr(n)
    out = np.full(n, np.nan, dtype=np.float64)
    for i in range(period, n):
        start = i - period + 1
        win_h = highs[start: i + 1]
        win_l = lows[start: i + 1]
        tr_sum = 0.0
        for k in range(period):
            h = win_h[k]
            l = win_l[k]
            prev_c = closes[start + k - 1]
            tr_sum += max(h - l, abs(h - prev_c), abs(l - prev_c))
        hh = np.max(win_h)
        ll = np.min(win_l)
        denom = hh - ll
        if denom < 1e-12:
            out[i] = 0.0
        else:
            out[i] = 100.0 * np.log10(tr_sum / denom) / np.log10(float(period))
    return np.round(out, 4)


# ======================================================================
# Stochastic RSI  (RSI of RSI, then stochastic of that)
# ======================================================================


def _stoch_rsi_values(closes: np.ndarray, period: int) -> np.ndarray:
    """StochRSI — apply stochastic formula to RSI values."""
    r = _rsi(closes, period)
    n = len(r)
    out = np.full(n, np.nan, dtype=np.float64)
    for i in range(period * 2 - 1, n):
        win = r[i - period + 1: i + 1]
        lo = np.min(win); hi = np.max(win)
        if hi - lo < 1e-12:
            out[i] = 0.0
        else:
            out[i] = (r[i] - lo) / (hi - lo)
    # Scale to 0-100
    out *= 100.0
    return np.round(out, 4)


# ======================================================================
# Aroon
# ======================================================================


def _aroon(highs: np.ndarray, lows: np.ndarray, period: int) -> tuple[np.ndarray, np.ndarray]:
    n = len(highs)
    up = np.full(n, np.nan, dtype=np.float64)
    down = np.full(n, np.nan, dtype=np.float64)
    for i in range(period, n):
        win_h = highs[i - period: i + 1]
        win_l = lows[i - period: i + 1]
        hh_idx = period - np.argmax(win_h)
        ll_idx = period - np.argmin(win_l)
        up[i] = ((period - hh_idx) / period) * 100.0
        down[i] = ((period - ll_idx) / period) * 100.0
    return np.round(up, 4), np.round(down, 4)


# ======================================================================
# STC  (Schaff Trend Cycle)
# ======================================================================
# brale: indicator_stc.go  —  two-layer stochastic + SMA smoothing.
#
# Algorithm:
#   1. EMA_fast(23) - EMA_slow(50)  →  MACD-like line
#   2. Stochastic-1 of that line (K=STC_K)  →  smoothed with SMA(D=STC_D)
#   3. Stochastic-2 of the smoothed (K=STC_K)  →  smoothed with SMA(D=STC_D) = STC
# ======================================================================


def _rolling_stochastic(series: np.ndarray, period: int) -> np.ndarray:
    """brale: rollingStochastic (indicator_stc.go:40-64)"""
    n = len(series)
    out = np.full(n, np.nan, dtype=np.float64)
    for i in range(n):
        lo = max(0, i - period + 1)
        win = series[lo: i + 1]
        hi = np.max(win)
        lo_v = np.min(win)
        if hi - lo_v <= 1e-12:
            continue
        out[i] = 100.0 * (series[i] - lo_v) / (hi - lo_v)
    return out


def _rolling_sma(series: np.ndarray, period: int) -> np.ndarray:
    """brale: rollingSMA (indicator_stc.go:66-90)"""
    n = len(series)
    out = np.full(n, np.nan, dtype=np.float64)
    for i in range(period - 1, n):
        win = series[i - period + 1: i + 1]
        fv = win[np.isfinite(win)]
        if len(fv) == 0:
            continue
        out[i] = np.mean(fv)
    return out


def _compute_stc(closes: np.ndarray, fast: int, slow: int, stc_k: int, stc_d: int) -> np.ndarray:
    """brale: ComputeSTC equivalent (IndicatorComputer interface)"""
    n = len(closes)
    if n < max(fast, slow) + stc_k + stc_d:
        return _nanarr(n)

    ema_f = _ema(closes, fast)
    ema_s = _ema(closes, slow)
    macd_line = ema_f - ema_s

    # Layer 1: stochastic → SMA smooth
    stoch1 = _rolling_stochastic(macd_line, stc_k)
    smooth1 = _rolling_sma(stoch1, stc_d)

    # Layer 2: stochastic → SMA smooth = final STC
    stoch2 = _rolling_stochastic(smooth1, stc_k)
    stc = _rolling_sma(stoch2, stc_d)

    return np.round(stc, 4)


# ======================================================================
# TD Sequential
# ======================================================================
# Simplified version: count consecutive candles where close compares to
# close 4 bars ago.  After 9 consecutive, enter countdown (13 bars).


def _td_sequential(closes: np.ndarray) -> dict:
    """Return {current, count, phase, last_n, state} snapshot."""
    n = len(closes)
    if n < 5:
        return {"current": 0, "count": 0, "phase": "none", "last_n": [], "state": "flat"}

    setup_counts = []
    run = 0
    last_dir = 0
    for i in range(4, n):
        if closes[i] > closes[i - 4]:
            if last_dir == 1:
                run += 1
            else:
                run = 1
            last_dir = 1
        elif closes[i] < closes[i - 4]:
            if last_dir == -1:
                run += 1
            else:
                run = 1
            last_dir = -1
        else:
            run = 0
            last_dir = 0
        setup_counts.append(run)

    current = setup_counts[-1] if setup_counts else 0
    phase = "countdown" if current >= 9 else ("setup" if current >= 6 else "none")
    last_n_vals = setup_counts[-5:] if len(setup_counts) >= 5 else setup_counts
    state = "rising" if last_dir == 1 else ("falling" if last_dir == -1 else "flat")

    return {"current": current, "count": current, "phase": phase, "last_n": last_n_vals, "state": state}


# ======================================================================
# Snapshot builders  (1:1 brale)
# ======================================================================


def _build_ema_snapshot(series: np.ndarray, price: float, tail_n: int) -> dict:
    """brale: buildEMASnapshot (indicator_compress.go:430-446)"""
    clean = _sanitize(series)
    latest = float(clean[-1]) if len(clean) else None
    last_n = _tail(series, tail_n).tolist()
    delta = None
    delta_pct = None
    if latest is not None and price is not None:
        delta = round(price - latest, 4)
        if abs(latest) > 1e-12:
            delta_pct = round((delta / latest) * 100.0, 4)
    return {"latest": latest, "last_n": last_n, "delta_to_price": delta, "delta_pct": delta_pct}


def _build_rsi_snapshot(series: np.ndarray, tail_n: int) -> dict:
    """brale: buildRSISnapshot (indicator_compress.go:448-466)"""
    clean = _sanitize(series)
    if len(clean) == 0:
        return {"latest": None, "min": None, "max": None, "last_n": [],
                "slope": 0.0, "normalized_slope": 0.0, "slope_state": "FLAT"}
    lo, hi = _bounds(series)
    latest = float(clean[-1])
    slope = _compute_slope(series)
    return {
        "latest": latest,
        "min": lo,
        "max": hi,
        "distance_to_high": round(hi - latest, 4) if hi is not None else None,
        "distance_to_low": round(latest - lo, 4) if lo is not None else None,
        "last_n": _tail(series, tail_n).tolist(),
        "slope": slope["slope"],
        "normalized_slope": slope["normalized"],
        "slope_state": _slope_state(slope["normalized"]),
    }


def _build_atr_snapshot(series: np.ndarray, tail_n: int) -> dict:
    """brale: buildATRSnapshot (indicator_compress.go:468-478)"""
    clean = _sanitize(series)
    if len(clean) == 0:
        return {"latest": None, "last_n": [], "change_pct": 0.0}
    return {
        "latest": round(float(clean[-1]), 4),
        "last_n": _tail(series, tail_n).tolist(),
        "change_pct": _compute_change_pct(clean),
    }


def _build_obv_snapshot(series: np.ndarray) -> dict:
    """brale: buildOBVSnapshot (indicator_compress.go:501-519)"""
    clean = _sanitize(series)
    if len(clean) == 0:
        return {"value": None, "change_rate": 0.0}
    latest = float(clean[-1])
    base = clean[-min(30, len(clean))]
    if abs(base) > 1e-12:
        change_rate = round((latest - base) / abs(base), 4)
    else:
        change_rate = 0.0
    return {"value": latest, "change_rate": change_rate}


def _build_stc_snapshot(series: np.ndarray, tail_n: int) -> dict:
    """brale: buildSTCSnapshot (indicator_stc.go:13-38)"""
    clean = _sanitize(series)
    current = round(float(clean[-1]), 4) if len(clean) else None
    last_n = _tail(series, tail_n).tolist()
    state = "flat"
    if len(last_n) >= 2:
        cur = last_n[-1]
        prev = last_n[-2]
        if cur - prev > 2.0:
            state = "rising"
        elif prev - cur > 2.0:
            state = "falling"
    return {"current": current, "last_n": last_n, "state": state}


def _build_bb_snapshot(mid: np.ndarray, up: np.ndarray, lo: np.ndarray, price: float, tail_n: int) -> dict:
    clean_m = _sanitize(mid)
    clean_u = _sanitize(up)
    clean_l = _sanitize(lo)
    latest_mid = float(clean_m[-1]) if len(clean_m) else None
    latest_up = float(clean_u[-1]) if len(clean_u) else None
    latest_lo = float(clean_l[-1]) if len(clean_l) else None
    bandwidth = None
    pct_b = None
    if latest_up is not None and latest_lo is not None and abs(latest_up - latest_lo) > 1e-12:
        bandwidth = round((latest_up - latest_lo) / latest_mid * 100.0, 4) if latest_mid and abs(latest_mid) > 1e-12 else None
    if latest_up is not None and latest_lo is not None and abs(latest_up - latest_lo) > 1e-12 and price is not None:
        pct_b = round((price - latest_lo) / (latest_up - latest_lo), 4)
    return {
        "middle": {"latest": latest_mid, "last_n": _tail(mid, tail_n).tolist()},
        "upper": {"latest": latest_up, "last_n": _tail(up, tail_n).tolist()},
        "lower": {"latest": latest_lo, "last_n": _tail(lo, tail_n).tolist()},
        "bandwidth": bandwidth,
        "pct_b": pct_b,
    }


def _build_chop_snapshot(series: np.ndarray, tail_n: int) -> dict:
    clean = _sanitize(series)
    if len(clean) == 0:
        return {"latest": None, "last_n": [], "state": "choppy"}
    latest = float(clean[-1])
    state = "choppy" if latest > 61.8 else ("trending" if latest < 38.2 else "neutral")
    return {"latest": latest, "last_n": _tail(series, tail_n).tolist(), "state": state}


def _build_stoch_rsi_snapshot(series: np.ndarray, tail_n: int) -> dict:
    clean = _sanitize(series)
    if len(clean) == 0:
        return {"latest": None, "last_n": [], "overbought": False, "oversold": False}
    latest = float(clean[-1])
    return {
        "latest": latest,
        "last_n": _tail(series, tail_n).tolist(),
        "overbought": latest > 80.0,
        "oversold": latest < 20.0,
    }


def _build_aroon_snapshot(up: np.ndarray, down: np.ndarray, tail_n: int) -> dict:
    clean_u = _sanitize(up)
    clean_d = _sanitize(down)
    latest_u = float(clean_u[-1]) if len(clean_u) else None
    latest_d = float(clean_d[-1]) if len(clean_d) else None
    return {
        "up": {"latest": latest_u, "last_n": _tail(up, tail_n).tolist()},
        "down": {"latest": latest_d, "last_n": _tail(down, tail_n).tolist()},
    }


# ======================================================================
# Main compress entry-point
# ======================================================================


def compress_indicator(
    candles: pd.DataFrame,
    interval: str,
    symbol: str = "",
    opts: IndicatorCompressOptions | None = None,
) -> dict[str, Any]:
    """
    Compress OHLCV candles into the IndicatorCompressedInput JSON shape.

    Parameters
    ----------
    candles : pd.DataFrame
        Must have columns Date (index or column), Open, High, Low, Close, Volume.
    interval : str
        e.g. "15m", "1H", "4H" (brale time-frame label).
    symbol : str
        Trading pair, e.g. "BTC-USDT-SWAP".

    Returns
    -------
    dict  matching brale's IndicatorCompressedInput JSON.
    """
    if opts is None:
        opts = DEFAULT_OPTIONS

    # --- ensure columns ---
    df = candles.copy()
    if "Date" in df.columns and not isinstance(df.index, pd.DatetimeIndex):
        df["_dt"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.drop(columns=["Date"], errors="ignore")
        df = df.set_index("_dt")
    df = df.sort_index()

    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in OHLCV data: {missing}")

    opens = df["Open"].values.astype(np.float64)
    highs = df["High"].values.astype(np.float64)
    lows = df["Low"].values.astype(np.float64)
    closes = df["Close"].values.astype(np.float64)
    volumes = df["Volume"].values.astype(np.float64)

    current_price = float(closes[-1]) if len(closes) else None
    prev_price = float(closes[-2]) if len(closes) > 1 else None
    price_ts = str(df.index[-1]) if len(df.index) else ""

    data: dict[str, Any] = {}

    # --- EMA ---
    if not opts.skip_ema:
        ema_f = _ema(closes, opts.ema_fast)
        ema_m = _ema(closes, opts.ema_mid)
        ema_s = _ema(closes, opts.ema_slow)
        data["ema_fast"] = _build_ema_snapshot(ema_f, current_price, opts.last_n)
        data["ema_mid"] = _build_ema_snapshot(ema_m, current_price, opts.last_n)
        data["ema_slow"] = _build_ema_snapshot(ema_s, current_price, opts.last_n)

    # --- RSI ---
    if not opts.skip_rsi:
        r = _rsi(closes, opts.rsi_period)
        data["rsi"] = _build_rsi_snapshot(r, opts.last_n)

    # --- ATR ---
    if not opts.skip_atr:
        a = _atr(highs, lows, closes, opts.atr_period)
        data["atr"] = _build_atr_snapshot(a, opts.last_n)

    # --- OBV ---
    if not opts.skip_obv:
        o = _obv(closes, volumes)
        data["obv"] = _build_obv_snapshot(o)

    # --- STC ---
    if not opts.skip_stc:
        s = _compute_stc(closes, opts.stc_fast, opts.stc_slow, opts.stc_k, opts.stc_d)
        data["stc"] = _build_stc_snapshot(s, opts.last_n)

    # --- Bollinger Bands ---
    if not opts.skip_bb:
        m, u, l = _bollinger(closes, opts.bb_period, opts.bb_multiplier)
        data["bb"] = _build_bb_snapshot(m, u, l, current_price, opts.last_n)

    # --- CHOP ---
    if not opts.skip_chop:
        c = _choppiness(highs, lows, closes, opts.chop_period)
        data["chop"] = _build_chop_snapshot(c, opts.last_n)

    # --- StochRSI ---
    if not opts.skip_stoch_rsi:
        sr = _stoch_rsi_values(closes, opts.stoch_rsi_period)
        data["stoch_rsi"] = _build_stoch_rsi_snapshot(sr, opts.last_n)

    # --- Aroon ---
    if not opts.skip_aroon:
        up, down = _aroon(highs, lows, opts.aroon_period)
        data["aroon"] = _build_aroon_snapshot(up, down, opts.last_n)

    # --- TD Sequential ---
    if not opts.skip_td_sequential:
        data["td_sequential"] = _td_sequential(closes)

    # --- metadata ---
    _meta = {
        "series_order": "oldest_to_latest",
        "sampled_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "version": "indicator_compress_v1",
        "timestamp_now_ts": int(time.time() * 1000),
        "data_age_sec": {},
    }

    market = {
        "symbol": symbol,
        "interval": interval,
        "current_price": current_price,
        "previous_price": prev_price,
        "price_timestamp": price_ts,
    }

    return {"_meta": _meta, "market": market, "data": data}
