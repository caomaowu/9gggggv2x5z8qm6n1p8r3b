"""
fusion.py — Consensus-weighted fusion (brale-core 移植).

Replicates brale-core-master internal/decision/direction/consensus.go:
    - ComputeConsensus() with base weights, confidence-power, resonance bonus.
    - Output: direction (long/short/none) + confidence + agreement + coverage.

Reference weights & thresholds (internal/config/defaults.go):
    weightStructure  = 1.0
    weightIndicator  = 0.7
    weightMechanics  = 0.5
    confidencePower  = 1.0
    ScoreThreshold   = 0.35
    ConfidenceThreshold = 0.52
    ResonanceBonusCap = 0.12
    ResonanceBonusScale = 0.4
"""

from __future__ import annotations

from typing import Any

# ======================================================================
# Constants (1:1 brale)
# ======================================================================

WEIGHT_STRUCTURE = 1.0
WEIGHT_INDICATOR = 0.7
WEIGHT_MECHANICS = 0.5
CONFIDENCE_POWER = 1.0
THRESHOLD_SCORE = 0.35
THRESHOLD_CONFIDENCE = 0.52
RESONANCE_MIN_CONFIDENCE = 0.35
RESONANCE_MIN_SCORE_ABS = 0.30
RESONANCE_OPPOSE_CONFIDENCE = 0.55
RESONANCE_OPPOSE_SCORE_ABS = 0.45
RESONANCE_BONUS_SCALE = 0.4
RESONANCE_BONUS_CAP = 0.12

Source = str  # "indicator" | "structure" | "mechanics"


# ======================================================================
# Evidence extraction
# ======================================================================


def _extract_evidence(summary: dict | None, source: Source) -> dict | None:
    """Extract {score, confidence} from a brale agent summary dict."""
    if summary is None:
        return None
    score = summary.get("movement_score")
    conf = summary.get("movement_confidence")
    if score is None or conf is None:
        return None
    try:
        score = float(score)
        conf = float(conf)
    except (TypeError, ValueError):
        return None
    # Clamp
    score = max(-1.0, min(1.0, score))
    conf = max(0.0, min(1.0, conf))
    return {"source": source, "score": score, "confidence": conf}


def _base_weight(source: Source) -> float:
    return {
        "indicator": WEIGHT_INDICATOR,
        "structure": WEIGHT_STRUCTURE,
        "mechanics": WEIGHT_MECHANICS,
    }.get(source, 0.5)


# ======================================================================
# computeResonance  (brale consensus.go:173-220)
# ======================================================================


def _compute_resonance(evidences: list[dict]) -> dict:
    """Compute resonance bonus when ≥2 agents agree on direction.

    Returns {active: bool, bonus: float, aligned_count: int}.
    """
    aligned: list[dict] = []
    oppose: list[dict] = []

    for e in evidences:
        if e["confidence"] < RESONANCE_MIN_CONFIDENCE:
            continue
        if abs(e["score"]) < RESONANCE_MIN_SCORE_ABS:
            continue
        direction = 1 if e["score"] > 0 else -1
        e_dir = {"source": e["source"], "score": e["score"],
                  "confidence": e["confidence"], "direction": direction}
        if len(aligned) == 0:
            aligned.append(e_dir)
        else:
            if aligned[0]["direction"] == direction:
                aligned.append(e_dir)
            else:
                oppose.append(e_dir)

    if len(aligned) < 2:
        return {"active": False, "bonus": 0.0, "aligned_count": len(aligned)}

    # Check for strong opposing signal
    cancelled = False
    for o in oppose:
        if o["confidence"] >= RESONANCE_OPPOSE_CONFIDENCE and abs(o["score"]) >= RESONANCE_OPPOSE_SCORE_ABS:
            cancelled = True
            break
    if cancelled:
        return {"active": False, "bonus": 0.0, "aligned_count": len(aligned)}

    total_base = sum(_base_weight(a["source"]) for a in aligned)
    total_base_all = sum(_base_weight(e["source"]) for e in evidences)
    aligned_weight_ratio = total_base / total_base_all if total_base_all > 0 else 0.0
    aligned_conf_avg = sum(a["confidence"] for a in aligned) / len(aligned)
    aligned_score_avg = abs(sum(a["score"] for a in aligned)) / len(aligned)
    strength = aligned_weight_ratio * aligned_conf_avg * aligned_score_avg
    bonus = min(RESONANCE_BONUS_CAP, RESONANCE_BONUS_SCALE * strength)

    return {"active": True, "bonus": bonus, "aligned_count": len(aligned)}


# ======================================================================
# computeConsensus  (brale consensus.go:95-164)
# ======================================================================


def compute_consensus(
    indicator_summary: dict | None = None,
    structure_summary: dict | None = None,
    mechanics_summary: dict | None = None,
) -> dict[str, Any]:
    """Fuse three agent summaries into a directional consensus.

    Returns
    -------
    dict with keys:
        direction   : "long" | "short" | "none"
        score       : float  [-1, 1]
        confidence  : float  [0, 1]
        agreement   : float  [0, 1]
        coverage    : float  [0, 1]
        resonance   : {active, bonus, aligned_count}
        agents      : {indicator, structure, mechanics} → {score, confidence}
    """
    raw = [
        _extract_evidence(indicator_summary, "indicator"),
        _extract_evidence(structure_summary, "structure"),
        _extract_evidence(mechanics_summary, "mechanics"),
    ]
    evidences = [e for e in raw if e is not None]

    if len(evidences) == 0:
        return {
            "direction": "none", "score": 0.0, "confidence": 0.0,
            "agreement": 0.0, "coverage": 0.0,
            "resonance": {"active": False, "bonus": 0.0, "aligned_count": 0},
            "agents": {
                "indicator": {"score": indicator_summary.get("movement_score", 0) if indicator_summary else 0,
                              "confidence": indicator_summary.get("movement_confidence", 0) if indicator_summary else 0},
                "structure": {"score": structure_summary.get("movement_score", 0) if structure_summary else 0,
                              "confidence": structure_summary.get("movement_confidence", 0) if structure_summary else 0},
                "mechanics": {"score": mechanics_summary.get("movement_score", 0) if mechanics_summary else 0,
                              "confidence": mechanics_summary.get("movement_confidence", 0) if mechanics_summary else 0},
            },
        }

    sum_w = 0.0
    sum_ws = 0.0
    sum_w_sign = 0.0
    sum_base = 0.0

    for e in evidences:
        bw = _base_weight(e["source"])
        eff_w = bw * (e["confidence"] ** CONFIDENCE_POWER)
        sum_w += eff_w
        sum_ws += eff_w * e["score"]
        sum_w_sign += eff_w * (1.0 if e["score"] > 0 else (-1.0 if e["score"] < 0 else 0.0))
        sum_base += bw

    if sum_w < 1e-12:
        return {
            "direction": "none", "score": 0.0, "confidence": 0.0,
            "agreement": 0.0, "coverage": 0.0,
            "resonance": {"active": False, "bonus": 0.0, "aligned_count": 0},
            "agents": {
                "indicator": {"score": indicator_summary.get("movement_score", 0) if indicator_summary else 0,
                              "confidence": indicator_summary.get("movement_confidence", 0) if indicator_summary else 0},
                "structure": {"score": structure_summary.get("movement_score", 0) if structure_summary else 0,
                              "confidence": structure_summary.get("movement_confidence", 0) if structure_summary else 0},
                "mechanics": {"score": mechanics_summary.get("movement_score", 0) if mechanics_summary else 0,
                              "confidence": mechanics_summary.get("movement_confidence", 0) if mechanics_summary else 0},
            },
        }

    score = max(-1.0, min(1.0, sum_ws / sum_w))
    agreement = min(1.0, abs(sum_w_sign) / sum_w) if sum_w > 0 else 0.0
    coverage = min(1.0, sum_w / sum_base) if sum_base > 0 else 0.0
    base_conf = coverage * agreement

    resonance = _compute_resonance(evidences)
    confidence = min(1.0, base_conf + resonance["bonus"])

    if abs(score) >= THRESHOLD_SCORE and confidence >= THRESHOLD_CONFIDENCE:
        direction = "long" if score > 0 else "short"
    else:
        direction = "none"

    return {
        "direction": direction,
        "score": round(score, 4),
        "confidence": round(confidence, 4),
        "agreement": round(agreement, 4),
        "coverage": round(coverage, 4),
        "resonance": resonance,
        "agents": {
            "indicator": {"score": indicator_summary.get("movement_score", 0) if indicator_summary else 0,
                          "confidence": indicator_summary.get("movement_confidence", 0) if indicator_summary else 0},
            "structure": {"score": structure_summary.get("movement_score", 0) if structure_summary else 0,
                          "confidence": structure_summary.get("movement_confidence", 0) if structure_summary else 0},
            "mechanics": {"score": mechanics_summary.get("movement_score", 0) if mechanics_summary else 0,
                          "confidence": mechanics_summary.get("movement_confidence", 0) if mechanics_summary else 0},
        },
    }
