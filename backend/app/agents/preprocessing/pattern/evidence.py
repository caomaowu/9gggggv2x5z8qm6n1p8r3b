"""
evidence.py — Combine geometry + candle pattern results into unified evidence.

Ported from brale-core-master internal/pkg/pattern/evidence/evidence.go

Merges geometry and candle DetectedPattern lists, filters by MinScore,
sorts by abs(score) desc / idx desc / name asc, and limits to MaxDetected.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Options:
    min_score: int = 100
    max_detected: int = 3


def default_options() -> Options:
    return Options()


def combine(
    geom_result: dict[str, Any] | None,
    candle_result: dict[str, Any] | None,
    opts: Options | None = None,
) -> dict[str, Any]:
    if opts is None:
        opts = default_options()
    opts = _normalize_options(opts)

    geom_detected = geom_result.get("detected", []) if geom_result else []
    candle_detected = candle_result.get("detected", []) if candle_result else []

    if not geom_detected and not candle_detected:
        return {"detected": [], "primary": "", "strength": 0}

    items: list[dict[str, Any]] = []
    for item in geom_detected:
        items.append({
            "name": item["name"],
            "score": item["score"],
            "bias": _bias_from_score(item["score"]),
            "idx": item["idx"],
        })
    for item in candle_detected:
        items.append({
            "name": item["name"],
            "score": item["score"],
            "bias": _bias_from_score(item["score"]),
            "idx": item["idx"],
        })

    # Filter by MinScore
    if opts.min_score > 0:
        items = [i for i in items if abs(i["score"]) >= opts.min_score]

    if not items:
        return {"detected": [], "primary": "", "strength": 0}

    # Sort: abs(score) desc, idx desc, name asc
    items.sort(key=lambda x: (-abs(x["score"]), -x["idx"], x["name"]))

    # Limit
    if opts.max_detected > 0 and len(items) > opts.max_detected:
        items = items[:opts.max_detected]

    strength = sum(abs(i["score"]) for i in items)
    primary = items[0]["name"]

    return {"detected": items, "primary": primary, "strength": strength}


def _bias_from_score(score: int) -> str:
    if score > 0:
        return "bullish"
    if score < 0:
        return "bearish"
    return "neutral"


def _normalize_options(opts: Options) -> Options:
    if opts.min_score <= 0:
        opts.min_score = default_options().min_score
    if opts.max_detected <= 0:
        opts.max_detected = default_options().max_detected
    return opts
