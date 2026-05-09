"""
test_brale_modules.py — Comprehensive tests for brale-core migration modules.

Covers:
    - indicator_compress  (all 10 indicators, snapshots, edge cases)
    - structure_compress  (fractal detection, dedup, pruning)
    - mechanics_compress  (derivative data aggregation)
    - fusion              (consensus weights, resonance, direction decision)
    - Agent JSON parsing & normalization (all 3 agents)
"""

import json
import math

import numpy as np
import pandas as pd
import pytest

# ======================================================================
# indicator_compress tests
# ======================================================================


@pytest.fixture
def sample_ohlcv_100():
    """Generate 100 realistic OHLCV bars."""
    np.random.seed(42)
    n = 100
    close = 50000.0 + np.cumsum(np.random.randn(n) * 200)
    high = close + np.abs(np.random.randn(n) * 150)
    low = close - np.abs(np.random.randn(n) * 150)
    open_ = np.roll(close, 1); open_[0] = close[0] - 50
    volume = np.abs(np.random.randn(n) * 100 + 500)
    dates = pd.date_range("2025-01-01", periods=n, freq="1h")
    df = pd.DataFrame({
        "Open": open_.round(2), "High": high.round(2),
        "Low": low.round(2), "Close": close.round(2), "Volume": volume.round(2),
    }, index=dates)
    return df


class TestIndicatorCompress:
    def test_basic_compress(self, sample_ohlcv_100):
        from app.agents.preprocessing.indicator_compress import compress_indicator
        result = compress_indicator(sample_ohlcv_100, "1H", "BTC-USDT-SWAP")
        assert "_meta" in result
        assert result["_meta"]["version"] == "indicator_compress_v1"
        assert result["market"]["interval"] == "1H"
        assert result["market"]["current_price"] is not None
        data = result["data"]
        assert "ema_fast" in data
        assert "ema_mid" in data
        assert "ema_slow" in data
        assert "rsi" in data
        assert "atr" in data
        assert "obv" in data
        assert "stc" in data
        assert "bb" in data
        assert "chop" in data
        assert "stoch_rsi" in data
        assert "aroon" in data
        assert "td_sequential" in data

    def test_ema_values(self, sample_ohlcv_100):
        from app.agents.preprocessing.indicator_compress import compress_indicator, _ema
        closes = sample_ohlcv_100["Close"].values.astype(np.float64)
        ema = _ema(closes, 21)
        assert np.isfinite(ema[-1])
        assert ema[0] is np.nan or not np.isfinite(ema[0])  # first values are NaN

    def test_rsi_range(self, sample_ohlcv_100):
        from app.agents.preprocessing.indicator_compress import _rsi
        closes = sample_ohlcv_100["Close"].values.astype(np.float64)
        r = _rsi(closes, 14)
        valid = r[np.isfinite(r)]
        assert len(valid) > 0
        assert np.all((valid >= 0) & (valid <= 100))

    def test_atr_positive(self, sample_ohlcv_100):
        from app.agents.preprocessing.indicator_compress import _atr
        h = sample_ohlcv_100["High"].values.astype(np.float64)
        l = sample_ohlcv_100["Low"].values.astype(np.float64)
        c = sample_ohlcv_100["Close"].values.astype(np.float64)
        a = _atr(h, l, c, 14)
        valid = a[np.isfinite(a)]
        assert np.all(valid > 0)

    def test_stc_range(self, sample_ohlcv_100):
        from app.agents.preprocessing.indicator_compress import _compute_stc
        closes = sample_ohlcv_100["Close"].values.astype(np.float64)
        s = _compute_stc(closes, 23, 50, 10, 3)
        valid = s[np.isfinite(s)]
        assert len(valid) > 0
        assert np.all((valid >= 0) & (valid <= 100))

    def test_bb_bands_contain_price(self, sample_ohlcv_100):
        from app.agents.preprocessing.indicator_compress import _bollinger
        closes = sample_ohlcv_100["Close"].values.astype(np.float64)
        m, u, l = _bollinger(closes, 20, 2.0)
        valid_idx = np.isfinite(m) & np.isfinite(u) & np.isfinite(l)
        assert np.any(valid_idx)
        assert np.all(u[valid_idx] >= l[valid_idx])

    def test_obv_non_zero(self, sample_ohlcv_100):
        from app.agents.preprocessing.indicator_compress import _obv
        c = sample_ohlcv_100["Close"].values.astype(np.float64)
        v = sample_ohlcv_100["Volume"].values.astype(np.float64)
        o = _obv(c, v)
        assert np.isfinite(o[-1])

    def test_chop_state(self, sample_ohlcv_100):
        from app.agents.preprocessing.indicator_compress import _choppiness
        h = sample_ohlcv_100["High"].values.astype(np.float64)
        l = sample_ohlcv_100["Low"].values.astype(np.float64)
        c = sample_ohlcv_100["Close"].values.astype(np.float64)
        ch = _choppiness(h, l, c, 14)
        valid = ch[np.isfinite(ch)]
        assert len(valid) > 0

    def test_aroon_range(self, sample_ohlcv_100):
        from app.agents.preprocessing.indicator_compress import _aroon
        h = sample_ohlcv_100["High"].values.astype(np.float64)
        l = sample_ohlcv_100["Low"].values.astype(np.float64)
        up, down = _aroon(h, l, 25)
        valid_up = up[np.isfinite(up)]
        assert np.all((valid_up >= 0) & (valid_up <= 100))

    def test_slope_state_mapping(self):
        from app.agents.preprocessing.indicator_compress import _slope_state
        assert _slope_state(0.05) == "FLAT"
        assert _slope_state(0.2) == "MODERATE"
        assert _slope_state(0.5) == "STEEP"
        assert _slope_state(-0.05) == "FLAT"
        assert _slope_state(-0.3) == "MODERATE"
        assert _slope_state(-0.6) == "STEEP"
        assert _slope_state(None) == "FLAT"
        assert _slope_state(float("nan")) == "FLAT"

    def test_empty_data_handled(self):
        from app.agents.preprocessing.indicator_compress import _ema, _rsi
        empty = np.array([], dtype=np.float64)
        assert len(_ema(empty, 21)) == 0
        assert len(_rsi(empty, 14)) == 0

    def test_sanitize_filters_nan_inf(self):
        from app.agents.preprocessing.indicator_compress import _sanitize
        arr = np.array([1.0, np.nan, 3.0, np.inf, 5.0, -np.inf])
        clean = _sanitize(arr)
        assert list(clean) == [1.0, 3.0, 5.0]

    def test_clamp(self):
        from app.agents.preprocessing.indicator_compress import _clamp
        assert _clamp(1.5, -1.0, 1.0) == 1.0
        assert _clamp(-2.0, -1.0, 1.0) == -1.0
        assert _clamp(0.5, -1.0, 1.0) == 0.5

    def test_td_sequential(self, sample_ohlcv_100):
        from app.agents.preprocessing.indicator_compress import _td_sequential
        c = sample_ohlcv_100["Close"].values.astype(np.float64)
        td = _td_sequential(c)
        assert "current" in td
        assert "phase" in td
        assert td["phase"] in ("none", "setup", "countdown")


# ======================================================================
# structure_compress tests
# ======================================================================


class TestStructureCompress:
    def test_basic_compress(self, sample_ohlcv_100):
        from app.agents.preprocessing.structure_compress import compress_structure
        result = compress_structure(sample_ohlcv_100, "1H", "BTC-USDT-SWAP")
        assert "_meta" in result
        data = result["data"]
        assert "fractal_points" in data
        assert "candidates" in data
        assert "supports" in data
        assert "resistances" in data
        assert "pattern_hint" in data

    def test_fractal_detection(self, sample_ohlcv_100):
        from app.agents.preprocessing.structure_compress import (
            _is_fractal_high, _is_fractal_low,
            _select_structure_points,
        )
        h = sample_ohlcv_100["High"].values.astype(np.float64)
        l = sample_ohlcv_100["Low"].values.astype(np.float64)
        points = _select_structure_points(h, l, span=5, max_points=12)
        assert isinstance(points, list)
        for p in points:
            assert p["type"] in ("high", "low")
            assert "price" in p
            assert "idx" in p

    def test_lin_reg_slope(self):
        from app.agents.preprocessing.structure_compress import _lin_reg_slope
        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        assert _lin_reg_slope(arr) == pytest.approx(1.0)
        horizontal = np.array([2.0, 2.0, 2.0, 2.0])
        assert _lin_reg_slope(horizontal) == pytest.approx(0.0)

    def test_volume_ratio(self):
        from app.agents.preprocessing.structure_compress import _volume_ratio
        vols = np.array([100.0, 100.0, 100.0, 200.0])
        ratio = _volume_ratio(vols, 3)
        assert ratio == pytest.approx(2.0)

    def test_dedup_candidates(self, sample_ohlcv_100):
        from app.agents.preprocessing.structure_compress import (
            StructureCompressOptions, _dedup_candidates,
        )
        atr = np.full(100, 100.0)
        opts = StructureCompressOptions()
        candidates = [
            {"type": "ema", "price": 50000.0, "age_candles": 0, "source": "ema_20"},
            {"type": "ema", "price": 50001.0, "age_candles": 0, "source": "ema_20"},  # near dup
            {"type": "support", "price": 48000.0, "age_candles": 5, "source": "fractal_low"},
        ]
        result = _dedup_candidates(candidates, atr, opts)
        assert len(result) <= len(candidates)

    def test_prune_candidates(self):
        from app.agents.preprocessing.structure_compress import _prune_candidates
        candidates = [
            {"type": "support", "price": 48000.0, "age_candles": 0},
            {"type": "support", "price": 49000.0, "age_candles": 0},
            {"type": "support", "price": 47000.0, "age_candles": 0},
            {"type": "resistance", "price": 51000.0, "age_candles": 0},
            {"type": "resistance", "price": 52000.0, "age_candles": 0},
            {"type": "resistance", "price": 53000.0, "age_candles": 0},
            {"type": "resistance", "price": 54000.0, "age_candles": 0},
        ]
        result = _prune_candidates(candidates, 50000.0, per_side=2)
        assert len(result) <= 4
        support_prices = [c["price"] for c in result if c["price"] < 50000.0]
        resistance_prices = [c["price"] for c in result if c["price"] > 50000.0]
        assert len(support_prices) <= 2
        assert len(resistance_prices) <= 2


# ======================================================================
# mechanics_compress tests
# ======================================================================


class TestMechanicsCompress:
    def test_basic_compress_no_data(self):
        from app.agents.preprocessing.mechanics_compress import compress_mechanics
        result = compress_mechanics(symbol="BTC-USDT-SWAP", interval="1H")
        assert "symbol" in result
        assert "oi" in result
        assert result["oi"]["missing"] is True
        assert result["funding"]["missing"] is True

    def test_compress_with_oi_and_funding(self, sample_ohlcv_100):
        from app.agents.preprocessing.mechanics_compress import compress_mechanics
        oi_snap = {"oi": 5000000, "ts": "2025-01-01T00:00:00Z"}
        funding = [{"fundingRate": 0.0001, "fundingTime": "2025-01-01T00:00:00Z",
                     "realizedRate": 0.0001, "ts": "1234567890"}]
        long_short = [{"longRatio": 0.6, "shortRatio": 0.4, "longShortRatio": 1.5,
                        "ts": "2025-01-01T00:00:00Z"}]
        result = compress_mechanics(
            ohlcv_data=sample_ohlcv_100,
            oi_snapshot=oi_snap,
            funding_history=funding,
            long_short_history=long_short,
            symbol="BTC-USDT-SWAP",
            interval="1H",
        )
        assert result["oi"]["missing"] is False
        assert result["oi"]["value"] == 5000000
        assert result["funding"]["missing"] is False
        assert result["funding"]["rate"] == 0.0001
        assert result["long_short_by_interval"]["1H"]["missing"] is False

    def test_compress_with_liquidations(self, sample_ohlcv_100):
        from app.agents.preprocessing.mechanics_compress import compress_mechanics
        liq = [
            {"side": "buy", "posSide": "long", "sz": 10.0, "ts": ""},
            {"side": "sell", "posSide": "short", "sz": 5.0, "ts": ""},
        ]
        opts = __import__("app.agents.preprocessing.mechanics_compress",
                           fromlist=["MechanicsCompressOptions"]).MechanicsCompressOptions(
            require_liquidations=True)
        result = compress_mechanics(
            ohlcv_data=sample_ohlcv_100,
            liquidation_orders=liq,
            symbol="BTC-USDT-SWAP",
            interval="1H",
            opts=opts,
        )
        assert result["liquidations"]["missing"] is False
        assert result["liquidations"]["count"] == 2

    def test_compress_missing_flags(self):
        from app.agents.preprocessing.mechanics_compress import compress_mechanics
        opts = __import__("app.agents.preprocessing.mechanics_compress",
                           fromlist=["MechanicsCompressOptions"]).MechanicsCompressOptions(
            require_oi=False, require_funding=False, require_long_short=False,
            require_cvd=False)
        result = compress_mechanics(opts=opts, symbol="BTC", interval="1H")
        assert result["oi"]["missing"] is True
        assert result["funding"]["missing"] is True


# ======================================================================
# fusion tests
# ======================================================================


class TestFusion:
    def test_consensus_all_long(self):
        from app.agents.preprocessing.fusion import compute_consensus
        result = compute_consensus(
            indicator_summary={"movement_score": 0.7, "movement_confidence": 0.8},
            structure_summary={"movement_score": 0.6, "movement_confidence": 0.7},
            mechanics_summary={"movement_score": 0.5, "movement_confidence": 0.6},
        )
        assert result["direction"] == "long"
        assert result["score"] > 0

    def test_consensus_all_short(self):
        from app.agents.preprocessing.fusion import compute_consensus
        result = compute_consensus(
            indicator_summary={"movement_score": -0.7, "movement_confidence": 0.8},
            structure_summary={"movement_score": -0.6, "movement_confidence": 0.7},
            mechanics_summary={"movement_score": -0.5, "movement_confidence": 0.6},
        )
        assert result["direction"] == "short"
        assert result["score"] < 0

    def test_consensus_balanced_none(self):
        from app.agents.preprocessing.fusion import compute_consensus
        result = compute_consensus(
            indicator_summary={"movement_score": 0.2, "movement_confidence": 0.3},
            structure_summary={"movement_score": -0.1, "movement_confidence": 0.3},
            mechanics_summary={"movement_score": 0.0, "movement_confidence": 0.1},
        )
        assert result["direction"] == "none"

    def test_consensus_empty(self):
        from app.agents.preprocessing.fusion import compute_consensus
        result = compute_consensus()
        assert result["direction"] == "none"
        assert result["score"] == 0.0
        assert result["confidence"] == 0.0

    def test_resonance_activates(self):
        from app.agents.preprocessing.fusion import compute_consensus
        result = compute_consensus(
            indicator_summary={"movement_score": 0.5, "movement_confidence": 0.7},
            structure_summary={"movement_score": 0.6, "movement_confidence": 0.8},
            mechanics_summary={"movement_score": 0.4, "movement_confidence": 0.4},
        )
        assert result["resonance"]["active"] is True
        assert result["resonance"]["bonus"] > 0.0

    def test_weights(self):
        from app.agents.preprocessing.fusion import _base_weight, compute_consensus
        assert _base_weight("structure") == 1.0
        assert _base_weight("indicator") == 0.7
        assert _base_weight("mechanics") == 0.5

    def test_score_clamped(self):
        from app.agents.preprocessing.fusion import compute_consensus
        result = compute_consensus(
            indicator_summary={"movement_score": 5.0, "movement_confidence": 1.0},
            structure_summary={"movement_score": 5.0, "movement_confidence": 1.0},
            mechanics_summary={"movement_score": 5.0, "movement_confidence": 1.0},
        )
        assert -1.0 <= result["score"] <= 1.0
        assert 0.0 <= result["confidence"] <= 1.0


# ======================================================================
# Agent JSON parsing & normalization tests
# ======================================================================


class TestIndicatorAgentOutput:
    @pytest.fixture
    def module(self):
        import app.agents.brale_indicator_agent as mod
        return mod

    def test_extract_json_direct(self, module):
        text = '{"expansion":"expanding","alignment":"aligned","noise":"low","momentum_detail":"test","conflict_detail":"none","movement_score":0.8,"movement_confidence":0.9,"next_focus":"test"}'
        parsed = module._extract_json(text)
        assert parsed["expansion"] == "expanding"
        assert parsed["movement_score"] == 0.8

    def test_extract_json_markdown(self, module):
        text = '```json\n{"expansion":"expanding","alignment":"aligned"}\n```'
        parsed = module._extract_json(text)
        assert parsed["expansion"] == "expanding"

    def test_normalize_output_valid(self, module):
        raw = {"expansion": "EXPANDING", "alignment": "aligned", "noise": "low",
               "movement_score": 0.6, "movement_confidence": 0.7}
        out = module._normalize_output(raw)
        assert out["expansion"] == "expanding"
        assert out["alignment"] == "aligned"
        assert out["movement_score"] == 0.6

    def test_normalize_clamps_score(self, module):
        raw = {"movement_score": 2.5, "movement_confidence": -0.5}
        out = module._normalize_output(raw)
        assert out["movement_score"] == 1.0
        assert out["movement_confidence"] == 0.0

    def test_normalize_default_fields(self, module):
        out = module._normalize_output({})
        assert out["expansion"] == "unknown"
        assert out["alignment"] == "unknown"
        assert out["noise"] == "unknown"
        assert out["movement_score"] == 0.0


class TestStructureAgentOutput:
    @pytest.fixture
    def module(self):
        import app.agents.brale_structure_agent as mod
        return mod

    def test_normalize_valid(self, module):
        raw = {"regime": "TREND_UP", "last_break": "bos_up", "quality": "clean",
               "pattern": "double_top", "movement_score": 0.7, "movement_confidence": 0.8}
        out = module._normalize_output(raw)
        assert out["regime"] == "trend_up"
        assert out["pattern"] == "double_top"

    def test_normalize_invalid_enum_defaults(self, module):
        raw = {"regime": "INVALID", "last_break": "INVALID", "quality": "INVALID",
               "pattern": "INVALID"}
        out = module._normalize_output(raw)
        assert out["regime"] == "unclear"
        assert out["last_break"] == "unknown"
        assert out["quality"] == "unclear"
        assert out["pattern"] == "none"

    def test_pattern_enum_values(self, module):
        for pattern in ["double_top", "double_bottom", "head_shoulders", "inv_head_shoulders",
                         "triangle_sym", "triangle_asc", "triangle_desc", "wedge_rising",
                         "wedge_falling", "flag", "pennant", "channel_up", "channel_down",
                         "none", "unknown"]:
            raw = {"pattern": pattern, "movement_score": 0, "movement_confidence": 0}
            out = module._normalize_output(raw)
            assert out["pattern"] == pattern


class TestMechanicsAgentOutput:
    @pytest.fixture
    def module(self):
        import app.agents.brale_mechanics_agent as mod
        return mod

    def test_normalize_valid(self, module):
        raw = {"leverage_state": "increasing", "crowding": "long_crowded",
               "risk_level": "high", "movement_score": -0.5, "movement_confidence": 0.6}
        out = module._normalize_output(raw)
        assert out["leverage_state"] == "increasing"
        assert out["crowding"] == "long_crowded"
        assert out["risk_level"] == "high"

    def test_normalize_invalid_defaults(self, module):
        out = module._normalize_output({"leverage_state": "INVALID", "crowding": "INVALID",
                                         "risk_level": "INVALID"})
        assert out["leverage_state"] == "unknown"
        assert out["crowding"] == "unknown"
        assert out["risk_level"] == "unknown"
