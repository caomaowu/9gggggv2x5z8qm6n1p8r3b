"""
mechanics_compress.py — Derivatives-market mechanics compression.

Replicates brale-core-master internal/decision/features/mechanics_compress.go.

Aggregates:
    - Open Interest (snapshot + history change)
    - Funding Rate
    - Long/Short account ratio
    - Taker volume ratio (buy/sell)
    - CVD (Cumulative Volume Delta, estimated from taker data)
    - Fear & Greed (placeholder via external API)
    - Liquidation orders (recent window)

Key constraint: rubik endpoints do NOT support `after` pagination.
Missing data is explicitly marked.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

_log = logging.getLogger(__name__)


# ======================================================================
# Fear & Greed — Alternative.me API (free, no auth)
# ======================================================================

_FNG_API = "https://api.alternative.me/fng/?limit=5"


def _fetch_fear_greed() -> dict[str, Any] | None:
    """Fetch latest Fear & Greed index from Alternative.me.

    Returns dict with {value, timestamp, classification, history, next_update_sec}
    or None on failure.
    """
    import urllib.request
    import json as _json

    try:
        req = urllib.request.Request(_FNG_API, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = _json.loads(resp.read().decode())
    except Exception:
        _log.debug("fear_greed fetch failed")
        return None

    try:
        data_list = payload.get("data", [])
        if not data_list:
            return None

        latest = data_list[0]
        val = int(str(latest.get("value", "0")).strip())
        ts_val = str(latest.get("timestamp", "0")).strip()
        ts_sec = int(ts_val) if ts_val.isdigit() else 0
        timestamp = pd.Timestamp(ts_sec, unit="s", tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ") if ts_sec else ""

        next_update_sec = 0
        until = str(latest.get("time_until_update", "0")).strip()
        if until.isdigit():
            next_update_sec = int(until)

        history = []
        for pt in data_list:
            h_ts = str(pt.get("timestamp", "0")).strip()
            h_sec = int(h_ts) if h_ts.isdigit() else 0
            if not h_sec:
                continue
            history.append({
                "value": int(str(pt.get("value", "0")).strip()),
                "classification": str(pt.get("value_classification", "")).strip(),
                "timestamp": pd.Timestamp(h_sec, unit="s", tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
            })

        return {
            "value": float(val),
            "classification": str(latest.get("value_classification", "")).strip(),
            "timestamp": timestamp,
            "history": history,
            "next_update_sec": next_update_sec,
        }
    except Exception:
        _log.debug("fear_greed parse failed")
        return None


@dataclass
class MechanicsCompressOptions:
    require_oi: bool = True
    require_funding: bool = True
    require_long_short: bool = True
    require_fear_greed: bool = True
    require_liquidations: bool = False
    require_cvd: bool = True
    require_futures_sentiment: bool = True


DEFAULT_MECHANICS_OPTIONS = MechanicsCompressOptions()


# ======================================================================
# Helper: parse timeframe strings like "5m", "1H", "4H" for window sizes
# ======================================================================

_TIMEFRAME_MINUTES: dict[str, int] = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "4h": 240, "1d": 1440, "1w": 10080,
}


def _tf_minutes(tf: str) -> int:
    """Parse timeframe string to minutes, case-insensitive."""
    return _TIMEFRAME_MINUTES.get(tf.lower(), 60)


# ======================================================================
# Helper: filter rubik data to K-line time window
# ======================================================================

def _filter_rubik_to_kline_window(
    rubik_data: list[dict] | None,
    kline_df: pd.DataFrame | None,
    ts_field: str = "ts",
    interval: str = "1H",
) -> list[dict]:
    """
    Slice rubik data to the backtest K-line time window.

    Buffer is the analysis interval's duration, so the last incomplete
    rubik period (e.g. 15:00–16:00 for a 16:00 candle) is included.

    Returns an empty list when the rubik data does NOT overlap the K-line
    window at all — the caller must mark the derivative as missing.
    """
    if not rubik_data:
        return []
    if kline_df is None or kline_df.empty:
        return rubik_data

    kline_start = kline_df.index[0]
    kline_end = kline_df.index[-1]
    # Ensure tz-aware UTC for comparison with rubik ts
    if kline_start.tz is None:
        kline_start = kline_start.tz_localize('UTC')
    if kline_end.tz is None:
        kline_end = kline_end.tz_localize('UTC')
    buffer_mins = max(60, _tf_minutes(interval))
    buffer = pd.Timedelta(minutes=buffer_mins)

    window_start = kline_start - buffer
    window_end = kline_end + buffer

    filtered: list[dict] = []
    for r in rubik_data:
        ts_str = str(r.get(ts_field, ""))
        if not ts_str:
            filtered.append(r)
            continue

        try:
            ts_int = int(ts_str)
            if ts_int > 1e12:
                ts = pd.Timestamp(ts_int, unit='ms', tz='UTC')
            else:
                ts = pd.Timestamp(ts_int, unit='s', tz='UTC')
        except (ValueError, TypeError):
            try:
                ts = pd.Timestamp(ts_str)
                if ts.tz is None:
                    ts = ts.tz_localize('UTC')
            except Exception:
                filtered.append(r)
                continue

        if window_start <= ts <= window_end:
            filtered.append(r)

    if not filtered:
        return []   # no overlap → caller marks missing

    try:
        filtered.sort(key=lambda x: int(str(x.get(ts_field, "0"))))
    except Exception:
        pass

    return filtered


def _bucket_liquidation_windows(orders: list[dict], bucket_sec: int = 300) -> list[list[dict]]:
    """Bucket liquidation orders into time windows for ZScore computation.

    Each bucket spans bucket_sec seconds. Returns list of buckets (newest last).
    If orders span < 2 buckets, returns empty list (insufficient for stats).
    """
    if not orders or len(orders) < 2:
        return []

    # Parse timestamps (handle both string and int formats)
    parsed = []
    for r in orders:
        ts_raw = r.get("ts", "")
        try:
            ts_val = int(str(ts_raw))
        except (ValueError, TypeError):
            continue
        # Normalize ms → seconds
        if ts_val > 1_000_000_000_000:
            ts_val //= 1000
        parsed.append((ts_val, r))

    if not parsed:
        return []

    parsed.sort(key=lambda x: x[0])
    start_time = parsed[0][0]
    end_time = parsed[-1][0]

    if end_time - start_time < bucket_sec:
        return []  # all orders in same bucket, no stats possible

    # Bucket
    buckets: list[list[dict]] = []
    current_start = start_time
    current_bucket: list[dict] = []
    for ts_val, r in parsed:
        if ts_val >= current_start + bucket_sec:
            if current_bucket:
                buckets.append(current_bucket)
            current_start = ts_val
            current_bucket = [r]
        else:
            current_bucket.append(r)
    if current_bucket:
        buckets.append(current_bucket)

    return buckets if len(buckets) >= 2 else []


# ======================================================================
# Main compress
# ======================================================================


def compress_mechanics(
    ohlcv_data: pd.DataFrame | None = None,
    oi_snapshot: dict | None = None,
    oi_history: list[dict] | None = None,
    funding_history: list[dict] | None = None,
    long_short_history: list[dict] | None = None,
    taker_volume_history: list[dict] | None = None,
    liquidation_orders: list[dict] | None = None,
    symbol: str = "",
    interval: str = "1H",
    opts: MechanicsCompressOptions | None = None,
) -> dict[str, Any]:
    if opts is None:
        opts = DEFAULT_MECHANICS_OPTIONS

    now_ts = int(time.time() * 1000)
    out: dict[str, Any] = {"symbol": symbol, "timestamp": pd.Timestamp.now(tz="UTC").isoformat()}

    current_price = None
    price_ts = ""
    if ohlcv_data is not None and len(ohlcv_data) > 0:
        closes = ohlcv_data["Close"].values.astype(np.float64)
        current_price = float(closes[-1]) if len(closes) else None
        if isinstance(ohlcv_data.index, pd.DatetimeIndex):
            price_ts = str(ohlcv_data.index[-1])

    # --- OI snapshot ---
    if opts.require_oi:
        oi_val = None
        oi_ts = ""
        if oi_snapshot:
            oi_val = oi_snapshot.get("oi")
            oi_ts = oi_snapshot.get("ts", "")
        out["oi"] = {
            "value": oi_val,
            "timestamp": oi_ts,
            "price": current_price,
            "price_timestamp": price_ts,
            "missing": oi_snapshot is None,
        }
    else:
        out["oi"] = {"value": None, "timestamp": "", "price": current_price,
                      "price_timestamp": price_ts, "missing": True}

    # --- OI history (change over multiple lookback windows, brale-style multi-period) ---
    oi_filtered = _filter_rubik_to_kline_window(
        oi_history, ohlcv_data, ts_field="ts", interval=interval
    )
    oi_by_interval: dict[str, Any] = {}
    if opts.require_oi and oi_filtered:
        oi_vals = [r.get("oi", 0) for r in oi_filtered if r.get("oi") is not None]
        latest_oi = oi_vals[-1] if oi_vals else None

        def _oi_change(vals: list[float], lookback_frac: float) -> dict:
            """Compute OI change_pct + price_change_pct over a fractional lookback window."""
            n = len(vals)
            if n < 2:
                return {"change_pct": 0.0, "price_change_pct": 0.0, "value": latest_oi}
            idx = max(1, int(n * (1 - lookback_frac)))
            segment = vals[idx:]
            first_oi = segment[0] if segment else vals[0]
            last_oi = segment[-1] if segment else vals[-1]
            cp = round(((last_oi - first_oi) / abs(first_oi)) * 100, 4) if abs(first_oi) > 1e-12 else 0.0
            # Price change over same segment
            pp = 0.0
            if ohlcv_data is not None and len(ohlcv_data) >= 2:
                all_closes = ohlcv_data["Close"].values.astype(np.float64)
                close_idx = max(1, int(len(all_closes) * (1 - lookback_frac)))
                fc = float(all_closes[close_idx])
                lc = float(all_closes[-1])
                if abs(fc) > 1e-12:
                    pp = round(((lc - fc) / abs(fc)) * 100, 4)
            return {"change_pct": cp, "price_change_pct": pp, "value": last_oi}

        # Short window (~recent 25%), mid (~50%), full
        oi_by_interval["short"] = _oi_change(oi_vals, 0.25)
        oi_by_interval["mid"] = _oi_change(oi_vals, 0.50)
        oi_by_interval["full"] = _oi_change(oi_vals, 1.0)
        # Mark data as present if we have values
        for k in oi_by_interval:
            oi_by_interval[k]["missing"] = False
    else:
        oi_by_interval[interval] = {"value": None, "change_pct": 0.0, "price": current_price,
                                     "price_change_pct": 0.0, "missing": True}
    out["oi_history"] = oi_by_interval

    # 回测检测：OI 历史明确提供但无法覆盖 K 线时间窗口 → 远期回测
    _is_backtest = opts.require_oi and oi_history is not None and len(oi_history) > 0 \
                   and oi_by_interval.get("full", {}).get("missing", False)
    if _is_backtest:
        out["oi"]["missing"] = True

    # --- Funding rate ---
    funding_filtered = _filter_rubik_to_kline_window(
        funding_history, ohlcv_data, ts_field="ts", interval=interval
    )
    if opts.require_funding:
        rate = None
        rate_ts = ""
        if funding_filtered:
            rate = funding_filtered[0].get("fundingRate", funding_filtered[0].get("rate"))
            rate_ts = funding_filtered[0].get("fundingTime", "")
        out["funding"] = {
            "rate": rate,
            "timestamp": rate_ts,
            "missing": not bool(funding_filtered),
        }
    else:
        out["funding"] = {"rate": None, "timestamp": "", "missing": True}

    # --- Long/Short ratio ---
    ls_filtered = _filter_rubik_to_kline_window(
        long_short_history, ohlcv_data, ts_field="ts", interval=interval
    )
    ls_by_interval: dict[str, Any] = {}
    if opts.require_long_short:
        if ls_filtered and len(ls_filtered) > 0:
            latest = ls_filtered[-1]
            rs = latest.get("longShortRatio") or latest.get("ls_ratio")
            ls_by_interval[interval] = {
                "ratio": rs,
                "long_ratio": latest.get("longRatio"),
                "short_ratio": latest.get("shortRatio"),
                "timestamp": latest.get("ts", ""),
                "missing": False,
            }
        else:
            ls_by_interval[interval] = {"ratio": None, "timestamp": "", "missing": True}
    else:
        ls_by_interval[interval] = {"ratio": None, "timestamp": "", "missing": True}
    out["long_short_by_interval"] = ls_by_interval

    # --- CVD (estimated from taker volume ratio) ---
    # brale: builds CVD series per-bar from taker buy/sell, then detects divergence + peak_flip.
    taker_filtered = _filter_rubik_to_kline_window(
        taker_volume_history, ohlcv_data, ts_field="ts", interval=interval
    )
    cvd_by_interval: dict[str, Any] = {}
    buy_cum = 0.0
    sell_cum = 0.0  # reused by futures sentiment below
    if opts.require_cvd:
        if taker_filtered and len(taker_filtered) > 0:
            # Build cumulative CVD series (one point per taker record)
            cvd_series: list[float] = []
            c_sum = 0.0
            for r in taker_filtered:
                buy_cum += r.get("buyVol", 0)
                sell_cum += r.get("sellVol", 0)
                c_sum = buy_cum - sell_cum
                cvd_series.append(c_sum)
            cvd_val = round(c_sum, 4)
            total_vol = buy_cum + sell_cum
            normalized = round(cvd_val / total_vol, 4) if total_vol > 1e-12 else 0.0

            # -- momentum: last minus 6th-from-last (brale: momentum = cvd[-1] - cvd[-6])
            momentum = 0.0
            if len(cvd_series) > 6:
                momentum = round(cvd_series[-1] - cvd_series[-6], 4)

            # -- divergence: compare price direction vs CVD direction over ~6 bars (brale: no thresholds, directional only)
            divergence = "neutral"
            if ohlcv_data is not None and len(ohlcv_data) >= 6 and len(cvd_series) >= 6:
                closes = ohlcv_data["Close"].values.astype(np.float64)
                price_now = float(closes[-1])
                price_prev = float(closes[-6])
                cvd_now = cvd_series[-1]
                cvd_prev = cvd_series[-6]
                if price_now > price_prev and cvd_now < cvd_prev:
                    divergence = "down"   # price up but CVD down → bearish divergence
                elif price_now < price_prev and cvd_now > cvd_prev:
                    divergence = "up"     # price down but CVD up → bullish divergence

            # -- peak_flip: last 3 CVD values pattern (brale: a<b>c→local_top, a>b<c→local_bottom)
            peak_flip = "none"
            if len(cvd_series) >= 3:
                a, b, c_val = cvd_series[-1], cvd_series[-2], cvd_series[-3]
                if a < b and b > c_val:
                    peak_flip = "local_top"
                elif a > b and b < c_val:
                    peak_flip = "local_bottom"

            cvd_by_interval[interval] = {
                "value": cvd_val,
                "momentum": momentum,
                "normalized": normalized,
                "divergence": divergence,
                "peak_flip": peak_flip,
                "timestamp": taker_filtered[-1].get("ts", ""),
                "missing": False,
            }
        else:
            cvd_by_interval[interval] = {"value": None, "momentum": 0.0,
                                          "normalized": 0.0, "divergence": "neutral",
                                          "peak_flip": "none", "timestamp": "", "missing": True}
    else:
        cvd_by_interval[interval] = {"value": None, "momentum": 0.0,
                                      "normalized": 0.0, "divergence": "neutral",
                                      "peak_flip": "none", "timestamp": "", "missing": True}
    out["cvd_by_interval"] = cvd_by_interval

    # --- Fear & Greed (Alternative.me API, real-time only) ---
    if opts.require_fear_greed and not _is_backtest:
        fg = _fetch_fear_greed()
        if fg:
            out["fear_greed"] = {
                "value": fg["value"],
                "timestamp": fg["timestamp"],
                "missing": False,
            }
            out["fear_greed_history"] = fg.get("history", [])
            out["fear_greed_next_update_sec"] = fg.get("next_update_sec", 0)
        else:
            out["fear_greed"] = {"value": None, "timestamp": "", "missing": True}
            out["fear_greed_history"] = []
            out["fear_greed_next_update_sec"] = 0
    else:
        out["fear_greed"] = {"value": None, "timestamp": "", "missing": True}
        out["fear_greed_history"] = []
        out["fear_greed_next_update_sec"] = 0

    # --- Liquidations (multi-window: 5m / 1h / 4h, brale-style) ---
    # brale uses 3 fixed windows. Status and source metadata track data quality.
    _LIQ_WINDOWS: list[tuple[str, int]] = [("5m", 300), ("1h", 3600), ("4h", 14400)]
    liq_now_ts = int(time.time())
    if opts.require_liquidations and not _is_backtest:
        if liquidation_orders and len(liquidation_orders) > 0:
            # Parse + sort orders
            parsed: list[tuple[int, dict]] = []
            for r in liquidation_orders:
                ts_raw = r.get("ts", "")
                try:
                    ts_val = int(str(ts_raw))
                    if ts_val > 1_000_000_000_000:
                        ts_val //= 1000
                except (ValueError, TypeError):
                    continue
                parsed.append((ts_val, r))
            parsed.sort(key=lambda x: x[0])

            # Global aggregate
            long_liq = sum(r.get("sz", 0) for _, r in parsed if r.get("posSide") == "long")
            short_liq = sum(r.get("sz", 0) for _, r in parsed if r.get("posSide") == "short")
            total_liq = long_liq + short_liq
            imbalance = round((long_liq - short_liq) / total_liq, 4) if total_liq > 1e-12 else 0.0

            min_ts = parsed[0][0]
            max_ts = parsed[-1][0]
            coverage_sec_total = max_ts - min_ts

            out["liquidations"] = {
                "volume": round(total_liq, 4),
                "long_vol": round(long_liq, 4),
                "short_vol": round(short_liq, 4),
                "imbalance": imbalance,
                "sample_count": len(parsed),
                "coverage_sec": coverage_sec_total,
                "last_event_age_sec": liq_now_ts - max_ts,
                "timestamp": str(parsed[-1][1].get("ts", "")),
                "missing": False,
            }

            # --- Per-window aggregation (brale: classifyLiquidationState picks highest stress) ---
            oi_val = out.get("oi", {}).get("value")
            liq_by_window: dict[str, Any] = {}
            for win_name, win_sec in _LIQ_WINDOWS:
                cutoff = max_ts - win_sec
                win_orders = [(ts, r) for ts, r in parsed if ts >= cutoff]
                if not win_orders:
                    liq_by_window[win_name] = {
                        "total_vol": 0.0, "long_vol": 0.0, "short_vol": 0.0,
                        "imbalance": 0.0, "sample_count": 0,
                        "coverage_sec": 0, "status": "unavailable", "complete": False,
                    }
                    continue

                w_long = sum(r.get("sz", 0) for _, r in win_orders if r.get("posSide") == "long")
                w_short = sum(r.get("sz", 0) for _, r in win_orders if r.get("posSide") == "short")
                w_total = w_long + w_short
                w_imbalance = round((w_long - w_short) / w_total, 4) if w_total > 1e-12 else 0.0
                w_coverage = max_ts - win_orders[0][0]

                # Window status (brale: warming_up if coverage < window duration)
                win_complete = w_coverage >= win_sec
                if win_complete:
                    win_status = "ok"
                elif w_coverage > 0:
                    win_status = "warming_up"
                else:
                    win_status = "unavailable"

                # Rel metrics
                vol_over_oi = round(w_total / oi_val, 6) if oi_val and oi_val > 1e-12 else 0.0
                vol_over_volume = 0.0
                if ohlcv_data is not None and len(ohlcv_data) >= 2 and w_total > 1e-12:
                    # Sum candle volume within the window's time range
                    if isinstance(ohlcv_data.index, pd.DatetimeIndex):
                        win_end = pd.Timestamp(max_ts, unit='s', tz='UTC')
                        win_start = win_end - pd.Timedelta(seconds=win_sec)
                        mask = (ohlcv_data.index >= win_start) & (ohlcv_data.index <= win_end)
                        candle_vol = float(ohlcv_data.loc[mask, "Volume"].sum()) if mask.any() else 0.0
                        if candle_vol > 1e-12:
                            vol_over_volume = round(w_total / candle_vol, 6)

                # Z-score: simple over available windows (not rolling history — single analysis)
                z_score_val = 0.0
                if w_total > 1e-12 and len(liq_by_window) >= 1:
                    prev_vols = [v["total_vol"] for v in liq_by_window.values()
                                 if v.get("total_vol", 0) > 1e-12]
                    all_vols = prev_vols + [w_total]
                    if len(all_vols) >= 2:
                        mean_v = sum(all_vols) / len(all_vols)
                        std_v = (sum((v - mean_v) ** 2 for v in all_vols) / len(all_vols)) ** 0.5
                        if std_v > 1e-12:
                            z_score_val = round((w_total - mean_v) / std_v, 4)

                liq_by_window[win_name] = {
                    "long_vol": round(w_long, 4),
                    "short_vol": round(w_short, 4),
                    "total_vol": round(w_total, 4),
                    "imbalance": w_imbalance,
                    "sample_count": len(win_orders),
                    "coverage_sec": w_coverage,
                    "status": win_status,
                    "complete": win_complete,
                    "rel": {
                        "vol_over_oi": vol_over_oi,
                        "vol_over_volume": vol_over_volume,
                        "zscore": z_score_val,
                        "spike": z_score_val >= 2.0,  # brale: spike threshold is 2.0
                    },
                }

            out["liquidations_by_window"] = liq_by_window

            # Liquidation source metadata (brale: LiqSource struct)
            source_status = "ok"
            if coverage_sec_total < 300:
                source_status = "warming_up"
            last_event_age = liq_now_ts - max_ts
            if last_event_age > 3600:
                source_status = "stale"
            out["liquidation_source"] = {
                "source": "rubik_order_book",
                "coverage": "order_book_snapshot",
                "status": source_status,
                "stream_connected": False,
                "coverage_sec": coverage_sec_total,
                "sample_count": len(parsed),
                "last_event_age_sec": last_event_age,
                "complete": coverage_sec_total >= 300,
            }
        else:
            out["liquidations"] = {"volume": None, "timestamp": "", "missing": True}
            out["liquidations_by_window"] = {}
            out["liquidation_source"] = {
                "source": "", "coverage": "", "status": "unavailable",
                "stream_connected": False, "coverage_sec": 0,
                "sample_count": 0, "last_event_age_sec": 0, "complete": False,
            }
    else:
        out["liquidations"] = {"volume": None, "timestamp": "", "missing": True}
        out["liquidations_by_window"] = {}
        out["liquidation_source"] = {
            "source": "", "coverage": "", "status": "disabled",
            "stream_connected": False, "coverage_sec": 0,
            "sample_count": 0, "last_event_age_sec": 0, "complete": False,
        }

    # --- Futures sentiment (computed from available data) ---
    fs: dict[str, Any] = {
        "top_trader_lsr": None, "ls_ratio": None,
        "taker_long_short_vol_ratio": None, "timestamp": "",
        "missing": True,
    }
    if opts.require_futures_sentiment:
        # LSRatio from latest long/short data
        if long_short_history and len(long_short_history) > 0:
            latest_ls = long_short_history[0]
            ls_ratio = latest_ls.get("longShortRatio") or latest_ls.get("ratio")
            if ls_ratio is not None:
                fs["ls_ratio"] = round(float(ls_ratio), 4)
                fs["top_trader_lsr"] = round(float(ls_ratio), 4)
                fs["timestamp"] = str(latest_ls.get("ts", ""))
                fs["missing"] = False

        # Taker volume ratio from taker data
        # Compute if not already done by CVD section above
        if buy_cum == 0.0 and sell_cum == 0.0 and taker_filtered and len(taker_filtered) > 0:
            for r in taker_filtered:
                buy_cum += r.get("buyVol", 0)
                sell_cum += r.get("sellVol", 0)
        if sell_cum > 1e-12:
            fs["taker_long_short_vol_ratio"] = round(buy_cum / sell_cum, 4)
            fs["missing"] = False  # at least one field has data
    out["futures_sentiment"] = fs

    # --- Metadata ---
    out["_meta"] = {
        "version": "mechanics_compress_v1",
        "timestamp_now_ts": now_ts,
    }

    # Check has_data
    has_any = False
    for key in ["oi", "funding", "long_short_by_interval", "cvd_by_interval", "liquidations", "fear_greed"]:
        v = out.get(key, {})
        if isinstance(v, dict) and not v.get("missing", True):
            has_any = True
            break
    out["_meta"]["has_any_data"] = has_any

    return out
