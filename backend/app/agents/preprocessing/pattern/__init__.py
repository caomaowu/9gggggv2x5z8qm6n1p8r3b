"""
pattern — Geometric + candle pattern detection package.

Ported from brale-core-master internal/pkg/pattern/
"""

from app.agents.preprocessing.pattern.geometry import detect as detect_geometry, Options as GeometryOptions
from app.agents.preprocessing.pattern.cdl import detect as detect_candle, Options as CandleOptions
from app.agents.preprocessing.pattern.evidence import combine, Options as EvidenceOptions

__all__ = ["detect_geometry", "GeometryOptions", "detect_candle", "CandleOptions", "combine", "EvidenceOptions"]
