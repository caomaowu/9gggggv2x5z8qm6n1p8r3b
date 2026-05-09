"""
cdl.py — Candle pattern detection without TA-Lib (pure Python).

Ported from brale-core-master internal/pkg/pattern/cdl/cdl.go
Original uses talib-cdl-go; this implements equivalent logic manually.

Detects 8 candle patterns:
  - doji, doji_star, piercing, three_inside, three_outside,
  - three_black_crows, three_white_soldiers, evening_star
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class Options:
    lookback: int = 5
    penetration: float = 0.3
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

    n = len(candles)
    detected: list[dict[str, Any]] = []

    def _try(name: str, score: int, idx: int) -> None:
        detected.append({"name": name, "score": score, "idx": idx - n})

    # Scan ONLY lookback window, record LAST (most recent) non-zero per pattern
    def _last_in_lookback(pattern_fn, *args) -> bool:
        """Find last non-zero signal in lookback window. Returns True if found."""
        for i in range(n - 1, max(n - opts.lookback, 0) - 1, -1):
            score = pattern_fn(candles, i, *args) if args else pattern_fn(candles, i)
            if score:
                _try(pattern_fn.__name__[1:], score, i)
                return True
        return False

    _last_in_lookback(_doji)
    _last_in_lookback(_doji_star)
    _last_in_lookback(_piercing)
    _last_in_lookback(_three_inside)
    _last_in_lookback(_three_outside)
    _last_in_lookback(_three_black_crows)
    _last_in_lookback(_three_white_soldiers)
    _last_in_lookback(_evening_star, opts.penetration)

    if not detected:
        return {"detected": [], "primary": "", "strength": 0}

    # Limit to max_detected (sort by abs score desc, then idx desc)
    if opts.max_detected > 0 and len(detected) > opts.max_detected:
        detected.sort(key=lambda x: (-abs(x["score"]), -x["idx"], x["name"]))
        detected = detected[:opts.max_detected]

    # Pick primary + compute strength
    primary = ""
    strength = 0
    best_score = -1
    best_idx = -n - 1
    for item in detected:
        abs_s = abs(item["score"])
        strength += abs_s
        if abs_s > best_score:
            best_score = abs_s
            best_idx = item["idx"]
            primary = item["name"]
        elif abs_s == best_score and item["idx"] > best_idx:
            best_idx = item["idx"]
            primary = item["name"]

    return {"detected": detected, "primary": primary, "strength": strength}


# ======================================================================
# Candle pattern implementations (pure Python, no TA-Lib)
# ======================================================================


def _body(c: Candle) -> float:
    """Real body size."""
    return c.close - c.open


def _upper_shadow(c: Candle) -> float:
    return c.high - max(c.open, c.close)


def _lower_shadow(c: Candle) -> float:
    return min(c.open, c.close) - c.low


def _real_body(c: Candle) -> float:
    return abs(c.close - c.open)


def _is_bullish(c: Candle) -> bool:
    return c.close > c.open


def _is_bearish(c: Candle) -> bool:
    return c.close < c.open


def _doji(candles: list[Candle], i: int) -> int:
    """Doji: open == close (within tiny tolerance)."""
    if i < 0:
        return 0
    c = candles[i]
    body = _real_body(c)
    total = c.high - c.low
    if total <= 0:
        return 0
    if body / total < 0.05:
        if i > 0:
            return 100 if c.close >= candles[i - 1].close else -100
        return 100
    return 0


def _doji_star(candles: list[Candle], i: int) -> int:
    """Doji Star: doji that gaps away from previous candle."""
    if i < 1:
        return 0
    c = candles[i]
    prev = candles[i - 1]
    if _doji(candles, i) == 0:
        return 0
    if c.low > prev.high:
        return 100
    if c.high < prev.low:
        return -100
    return 0


def _piercing(candles: list[Candle], i: int) -> int:
    """Piercing pattern: bullish reversal after bear candle, close > midpoint.
    TA-Lib CDLPIERCING: black body → white candle opens below prev close, closes > midpoint."""
    if i < 1:
        return 0
    c = candles[i]
    prev = candles[i - 1]
    if not _is_bearish(prev) or not _is_bullish(c):
        return 0
    if c.open >= prev.close:  # must open below previous close (gap down)
        return 0
    mid = (prev.open + prev.close) / 2
    if c.close > mid:
        return 100
    return 0


def _three_inside(candles: list[Candle], i: int) -> int:
    """Three Inside (Harami): small body inside previous body. TA-Lib CDLHARAMI."""
    if i < 1:
        return 0
    c = candles[i]
    prev = candles[i - 1]
    if _real_body(c) >= _real_body(prev) or _real_body(prev) <= 0:
        return 0
    if _is_bearish(prev) and _is_bullish(c) and c.open >= prev.close and c.close <= prev.open:
        return 100
    if _is_bullish(prev) and _is_bearish(c) and c.open <= prev.close and c.close >= prev.open:
        return -100
    return 0


def _three_outside(candles: list[Candle], i: int) -> int:
    """Three Outside (Engulfing): body engulfs previous body."""
    if i < 1:
        return 0
    c = candles[i]
    prev = candles[i - 1]
    prev_body = _real_body(prev)
    curr_body = _real_body(c)
    if curr_body <= prev_body:
        return 0
    if _is_bearish(prev) and _is_bullish(c) and c.open <= prev.close and c.close >= prev.open:
        return 100  # bullish engulfing
    if _is_bullish(prev) and _is_bearish(c) and c.open >= prev.close and c.close <= prev.open:
        return -100  # bearish engulfing
    return 0


def _three_black_crows(candles: list[Candle], i: int) -> int:
    """Three Black Crows: 3 consecutive bearish candles."""
    if i < 2:
        return 0
    a, b, c = candles[i - 2], candles[i - 1], candles[i]
    if not all(_is_bearish(x) for x in (a, b, c)):
        return 0
    if b.open < a.open and b.close < a.close and c.open < b.open and c.close < b.close:
        return -100
    return 0


def _three_white_soldiers(candles: list[Candle], i: int) -> int:
    """Three White Soldiers: 3 consecutive bullish candles."""
    if i < 2:
        return 0
    a, b, c = candles[i - 2], candles[i - 1], candles[i]
    if not all(_is_bullish(x) for x in (a, b, c)):
        return 0
    if b.open > a.open and b.close > a.close and c.open > b.open and c.close > b.close:
        return 100
    return 0


def _evening_star(candles: list[Candle], i: int, penetration: float) -> int:
    """Evening Star: large bull + small body gap up + large bear gap down.
    TA-Lib CDLEVENINGSTAR: Close[0] < Close[2] - body * Penetration."""
    if i < 2:
        return 0
    a, b, c = candles[i - 2], candles[i - 1], candles[i]
    if not _is_bullish(a) or not _is_bearish(c):
        return 0
    mid_body = _real_body(b)
    first_body = _real_body(a)
    if first_body <= 0 or mid_body > first_body * 0.3:
        return 0
    if b.close <= a.close:  # middle must gap UP from first
        return 0
    if c.open >= b.close:   # third must gap DOWN from middle
        return 0
    # TA-Lib: close below (first_close - body * penetration)
    target = a.close - first_body * penetration
    if c.close < target:
        return -100
    return 0


# ======================================================================
# Helpers
# ======================================================================


def _normalize_options(opts: Options, total: int) -> Options:
    if opts.lookback <= 0 or opts.lookback > total:
        opts.lookback = total
    if opts.penetration <= 0:
        opts.penetration = 0.3
    return opts
