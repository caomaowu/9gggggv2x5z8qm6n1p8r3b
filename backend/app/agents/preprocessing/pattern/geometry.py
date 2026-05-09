"""
geometry.py — Rule-based geometric pattern detection (brale geometry package).

Ported from brale-core-master internal/pkg/pattern/geometry/geometry.go

Detects 10 patterns via rolling-window analysis on OHLCV candles:
  - head_shoulders    (-150)  inverse_head_shoulders (+150)
  - double_top        (-120)  double_bottom         (+120)
  - triangle_asc      (+100)  triangle_desc         (-100)
  - wedge_rising      (-120)  wedge_falling         (+120)
  - channel_up        (+100)  channel_down          (-100)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class Options:
    window: int = 3
    lookback: int = 0
    double_threshold: float = 0.05
    channel_range: float = 0.1
    max_detected: int = 10


def default_options() -> Options:
    return Options()


class Candle:
    __slots__ = ("open", "high", "low", "close")

    def __init__(self, open: float, high: float, low: float, close: float):
        self.open = open
        self.high = high
        self.low = low
        self.close = close


# ======================================================================
# Public API
# ======================================================================


def detect(candles: list[Candle] | list[dict], opts: Options | None = None) -> dict[str, Any]:
    if not candles:
        return {"detected": [], "primary": "", "strength": 0}

    if opts is None:
        opts = default_options()
    opts = _normalize_options(opts, len(candles))

    if isinstance(candles[0], dict):
        candles = [Candle(**c) if isinstance(c, dict) else c for c in candles]  # type: ignore[arg-type]

    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    closes = [c.close for c in candles]

    high_roll, low_roll = _rolling_high_low(highs, lows, opts.window)
    trend_high, trend_low = _rolling_trend(highs, lows, opts.window)

    head_mask = _detect_head_shoulders(highs, high_roll)
    inv_head_mask = _detect_inv_head_shoulders(lows, low_roll)
    double_top_mask, double_bottom_mask = _detect_double_top_bottom(
        highs, lows, high_roll, low_roll, opts.double_threshold
    )
    tri_asc_mask, tri_desc_mask = _detect_triangle(highs, lows, closes, high_roll, low_roll)
    wedge_up_mask, wedge_down_mask = _detect_wedge(highs, lows, high_roll, low_roll, trend_high, trend_low)
    channel_up_mask, channel_down_mask = _detect_channel(
        highs, lows, high_roll, low_roll, trend_high, trend_low, opts.channel_range
    )

    detected: list[dict[str, Any]] = []
    _append_if_detected(detected, "head_shoulders", -150, head_mask, opts.lookback, len(candles))
    _append_if_detected(detected, "inv_head_shoulders", 150, inv_head_mask, opts.lookback, len(candles))
    _append_if_detected(detected, "double_top", -120, double_top_mask, opts.lookback, len(candles))
    _append_if_detected(detected, "double_bottom", 120, double_bottom_mask, opts.lookback, len(candles))
    _append_if_detected(detected, "triangle_asc", 100, tri_asc_mask, opts.lookback, len(candles))
    _append_if_detected(detected, "triangle_desc", -100, tri_desc_mask, opts.lookback, len(candles))
    _append_if_detected(detected, "wedge_rising", -120, wedge_up_mask, opts.lookback, len(candles))
    _append_if_detected(detected, "wedge_falling", 120, wedge_down_mask, opts.lookback, len(candles))
    _append_if_detected(detected, "channel_up", 100, channel_up_mask, opts.lookback, len(candles))
    _append_if_detected(detected, "channel_down", -100, channel_down_mask, opts.lookback, len(candles))

    if opts.max_detected > 0 and len(detected) > opts.max_detected:
        detected.sort(key=lambda x: (-abs(x["score"]), -x["idx"], x["name"]))
        detected = detected[:opts.max_detected]

    if not detected:
        return {"detected": [], "primary": "", "strength": 0}

    primary, strength = _pick_primary(detected)
    return {"detected": detected, "primary": primary, "strength": strength}


# ======================================================================
# Core detection algorithms
# ======================================================================


def _rolling_high_low(highs: list[float], lows: list[float], window: int) -> tuple[list[float], list[float]]:
    n = len(highs)
    hr = [math.nan] * n
    lr = [math.nan] * n
    for i in range(window - 1, n):
        win_h = highs[i - window + 1 : i + 1]
        win_l = lows[i - window + 1 : i + 1]
        hr[i] = max(win_h)
        lr[i] = min(win_l)
    return hr, lr


def _rolling_trend(highs: list[float], lows: list[float], window: int) -> tuple[list[int], list[int]]:
    n = len(highs)
    th = [0] * n
    tl = [0] * n
    for i in range(window - 1, n):
        start = i - window + 1
        th[i] = _trend_dir(highs[start], highs[i])
        tl[i] = _trend_dir(lows[start], lows[i])
    return th, tl


def _trend_dir(first: float, last: float) -> int:
    if last > first:
        return 1
    if last < first:
        return -1
    return 0


def _is_valid(v: float) -> bool:
    return not (math.isnan(v) or math.isinf(v))


def _detect_head_shoulders(highs: list[float], high_roll: list[float]) -> list[bool]:
    n = len(highs)
    mask = [False] * n
    for i in range(1, n - 1):
        roll = high_roll[i]
        if not _is_valid(roll):
            continue
        if roll > highs[i - 1] and roll > highs[i + 1] and highs[i] < highs[i - 1] and highs[i] < highs[i + 1]:
            mask[i] = True
    return mask


def _detect_inv_head_shoulders(lows: list[float], low_roll: list[float]) -> list[bool]:
    n = len(lows)
    mask = [False] * n
    for i in range(1, n - 1):
        roll = low_roll[i]
        if not _is_valid(roll):
            continue
        if roll < lows[i - 1] and roll < lows[i + 1] and lows[i] > lows[i - 1] and lows[i] > lows[i + 1]:
            mask[i] = True
    return mask


def _detect_double_top_bottom(
    highs: list[float], lows: list[float],
    high_roll: list[float], low_roll: list[float],
    threshold: float,
) -> tuple[list[bool], list[bool]]:
    n = len(highs)
    top = [False] * n
    bottom = [False] * n
    for i in range(1, n - 1):
        if _is_valid(high_roll[i]):
            if high_roll[i] >= highs[i - 1] and high_roll[i] >= highs[i + 1] and highs[i] < highs[i - 1] and highs[i] < highs[i + 1]:
                if _range_within_threshold(highs[i - 1], lows[i - 1], threshold) and _range_within_threshold(highs[i + 1], lows[i + 1], threshold):
                    top[i] = True
        if _is_valid(low_roll[i]):
            if low_roll[i] <= lows[i - 1] and low_roll[i] <= lows[i + 1] and lows[i] > lows[i - 1] and lows[i] > lows[i + 1]:
                if _range_within_threshold(highs[i - 1], lows[i - 1], threshold) and _range_within_threshold(highs[i + 1], lows[i + 1], threshold):
                    bottom[i] = True
    return top, bottom


def _detect_triangle(
    highs: list[float], lows: list[float], closes: list[float],
    high_roll: list[float], low_roll: list[float],
) -> tuple[list[bool], list[bool]]:
    n = len(highs)
    asc = [False] * n
    desc = [False] * n
    for i in range(1, n):
        if not _is_valid(high_roll[i]) or not _is_valid(low_roll[i]):
            continue
        if high_roll[i] >= highs[i - 1] and low_roll[i] <= lows[i - 1] and closes[i] > closes[i - 1]:
            asc[i] = True
        if high_roll[i] <= highs[i - 1] and low_roll[i] >= lows[i - 1] and closes[i] < closes[i - 1]:
            desc[i] = True
    return asc, desc


def _detect_wedge(
    highs: list[float], lows: list[float],
    high_roll: list[float], low_roll: list[float],
    trend_high: list[int], trend_low: list[int],
) -> tuple[list[bool], list[bool]]:
    n = len(highs)
    up = [False] * n
    down = [False] * n
    for i in range(1, n):
        if not _is_valid(high_roll[i]) or not _is_valid(low_roll[i]):
            continue
        if high_roll[i] >= highs[i - 1] and low_roll[i] <= lows[i - 1] and trend_high[i] == 1 and trend_low[i] == 1:
            up[i] = True
        if high_roll[i] <= highs[i - 1] and low_roll[i] >= lows[i - 1] and trend_high[i] == -1 and trend_low[i] == -1:
            down[i] = True
    return up, down


def _detect_channel(
    highs: list[float], lows: list[float],
    high_roll: list[float], low_roll: list[float],
    trend_high: list[int], trend_low: list[int],
    channel_range: float,
) -> tuple[list[bool], list[bool]]:
    n = len(highs)
    up = [False] * n
    down = [False] * n
    for i in range(1, n):
        if not _is_valid(high_roll[i]) or not _is_valid(low_roll[i]):
            continue
        if _channel_within_range(high_roll[i], low_roll[i], channel_range):
            if high_roll[i] >= highs[i - 1] and low_roll[i] <= lows[i - 1] and trend_high[i] == 1 and trend_low[i] == 1:
                up[i] = True
            if high_roll[i] <= highs[i - 1] and low_roll[i] >= lows[i - 1] and trend_high[i] == -1 and trend_low[i] == -1:
                down[i] = True
    return up, down


# ======================================================================
# Helpers
# ======================================================================


def _append_if_detected(
    detected: list[dict], name: str, score: int, mask: list[bool], lookback: int, total: int,
) -> None:
    idx, ok = _last_match(mask, lookback)
    if ok:
        detected.append({"name": name, "score": score, "idx": idx - total})


def _last_match(mask: list[bool], lookback: int) -> tuple[int, bool]:
    if not mask:
        return 0, False
    start = len(mask) - 1
    end = max(len(mask) - lookback, 0)
    for i in range(start, end - 1, -1):
        if mask[i]:
            return i, True
    return 0, False


def _pick_primary(items: list[dict]) -> tuple[str, int]:
    best_score = -1
    best_idx = -1
    strength = 0
    primary = ""
    for item in items:
        abs_s = abs(item["score"])
        strength += abs_s
        if abs_s > best_score:
            best_score = abs_s
            best_idx = item["idx"]
            primary = item["name"]
        elif abs_s == best_score and item["idx"] > best_idx:
            best_idx = item["idx"]
            primary = item["name"]
    return primary, strength


def _range_within_threshold(high: float, low: float, threshold: float) -> bool:
    avg = (high + low) / 2
    if avg == 0:
        return False
    return (high - low) <= threshold * avg


def _channel_within_range(high: float, low: float, channel_range: float) -> bool:
    return _range_within_threshold(high, low, channel_range)


def _normalize_options(opts: Options, total: int) -> Options:
    if opts.window <= 0:
        opts.window = 3
    if opts.lookback <= 0 or opts.lookback > total:
        opts.lookback = total
    if opts.double_threshold <= 0:
        opts.double_threshold = 0.05
    if opts.channel_range <= 0:
        opts.channel_range = 0.1
    return opts
