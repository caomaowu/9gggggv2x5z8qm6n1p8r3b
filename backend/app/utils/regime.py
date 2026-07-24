"""
制度识别模块 (Market Regime Detection) - L1

完全确定性的市场状态分析，不依赖任何 LLM。
输入 OHLCV K 线数据，输出：
    - regime:            市场状态 (TREND_UP / TREND_DOWN / RANGE / HIGH_VOL / UNKNOWN)
    - recommended_bias:  建议打法 (FOLLOW_UP / FOLLOW_DOWN / FADE / ABSTAIN)
    - suggested_direction: 结合状态给出的方向暗示 (LONG / SHORT / NONE)
    - edge_score:        0~1 的优势打分，供决策端做规则化弃权 (L4)
    - features:          结构化数值特征字典，供决策端直接推理 (L2)
    - report:            供 LLM 阅读的结构化文本报告

设计要点：
    1. 纯规则、可解释、无状态 —— 满足"随时分析、每次独立"的核心约束。
    2. 震荡市默认给出"反手 (FADE)"建议，从根上消除"震荡市连续同向亏损"。
    3. 所有阈值集中为模块常量，便于后续在验证集上调参。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

try:
    import talib
    _HAS_TALIB = True
except Exception:  # pragma: no cover - talib 缺失时降级
    _HAS_TALIB = False


# ============================ 可调阈值常量 ============================
LOOKBACK = 100            # 参与制度判定的最大 K 线数
MIN_CANDLES = 35          # 最少需要的 K 线数（ADX(14)/MACD 需要足够样本）

ADX_TREND = 25.0          # ADX >= 该值视为趋势市
ADX_RANGE = 20.0          # ADX <= 该值视为非趋势（震荡）市
EMA_PERIOD = 20           # 判定趋势方向的 EMA 周期
EMA_SLOPE_MIN_PCT = 0.03  # EMA 每根斜率占价格百分比的最小趋势阈值(%)

ATR_PERIOD = 14
ATR_HIGH_PCT = 3.0        # ATR/价格 高于该百分比且无趋势 → 高波动无结构
BB_PERIOD = 20
BB_STD = 2.0

RANGE_NEAR_BOUNDARY = 0.30  # 距区间边界的相对阈值：>0.70 近阻力，<0.30 近支撑

RSI_PERIOD = 14
RSI_OB = 70.0             # 超买
RSI_OS = 30.0             # 超卖


# ============================ 数据预处理 ============================
def _to_dataframe(data: Any) -> Optional[pd.DataFrame]:
    """把 list[dict] 或 DataFrame 统一转成含 OHLCV 的 DataFrame，失败返回 None。"""
    if data is None:
        return None
    if isinstance(data, pd.DataFrame):
        df = data.copy()
    elif isinstance(data, list) and data:
        df = pd.DataFrame(data)
    else:
        return None

    if df.empty:
        return None

    # 兼容大小写字段
    rename_map = {}
    for col in list(df.columns):
        low = str(col).lower()
        if low == "open":
            rename_map[col] = "Open"
        elif low == "high":
            rename_map[col] = "High"
        elif low == "low":
            rename_map[col] = "Low"
        elif low == "close":
            rename_map[col] = "Close"
        elif low in ("volume", "vol"):
            rename_map[col] = "Volume"
    if rename_map:
        df = df.rename(columns=rename_map)

    required = {"High", "Low", "Close"}
    if not required.issubset(df.columns):
        return None

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["High", "Low", "Close"]).reset_index(drop=True)
    if df.empty:
        return None
    return df.tail(LOOKBACK).reset_index(drop=True)


def _is_multi_tf(kline_data: Any) -> bool:
    """判断是否为多时间框架结构 (dict[tf -> data])。"""
    if not isinstance(kline_data, dict):
        return False
    ohlc_keys = {"Open", "High", "Low", "Close", "Volume", "Datetime"}
    return not any(key in ohlc_keys for key in kline_data.keys())


# ============================ 特征计算 ============================
def _safe_last(series: Union[pd.Series, np.ndarray]) -> Optional[float]:
    try:
        arr = np.asarray(series, dtype=float)
        arr = arr[~np.isnan(arr)]
        if arr.size == 0:
            return None
        return float(arr[-1])
    except Exception:
        return None


def _ema_slope_pct(close: pd.Series, period: int) -> Optional[float]:
    """EMA 最近一段的平均每根斜率，表示为占当前价格的百分比。"""
    if len(close) < period + 2:
        return None
    if _HAS_TALIB:
        ema = talib.EMA(close.values.astype(float), timeperiod=period)
    else:
        ema = close.ewm(span=period, adjust=False).mean().values
    ema = ema[~np.isnan(ema)]
    if len(ema) < 5:
        return None
    span = min(5, len(ema) - 1)
    slope_per_bar = (ema[-1] - ema[-1 - span]) / span
    price = ema[-1] if ema[-1] != 0 else 1.0
    return float(slope_per_bar / price * 100.0)


def _atr_percentile(df: pd.DataFrame, period: int) -> Optional[float]:
    """当前 ATR 在历史窗口中的分位 (0~1)。"""
    if not _HAS_TALIB or len(df) < period + 5:
        return None
    atr = talib.ATR(df["High"].values.astype(float),
                    df["Low"].values.astype(float),
                    df["Close"].values.astype(float),
                    timeperiod=period)
    atr = atr[~np.isnan(atr)]
    if len(atr) < 5:
        return None
    cur = atr[-1]
    return float((atr <= cur).mean())


def _return_autocorr(close: pd.Series, lag: int = 1) -> Optional[float]:
    """收益率一阶自相关：>0 动量/趋势延续，<0 均值回归/震荡。"""
    rets = close.pct_change().dropna()
    if len(rets) < 20:
        return None
    try:
        ac = rets.autocorr(lag=lag)
        if ac is None or np.isnan(ac):
            return None
        return float(ac)
    except Exception:
        return None


def _support_resistance(df: pd.DataFrame) -> Dict[str, Optional[float]]:
    """用最近窗口线性拟合支撑/阻力，返回当前价所处区间位置与距离。"""
    close = df["Close"]
    n = len(close)
    if n < 10:
        return {"support": None, "resistance": None,
                "position_in_range": None,
                "dist_to_support_pct": None, "dist_to_resistance_pct": None}

    x = np.arange(n)
    # 用高低点的极值做稳健的水平/斜线区间估计
    win = min(n, 50)
    recent = df.tail(win)
    support = float(recent["Low"].min())
    resistance = float(recent["High"].max())
    price = float(close.iloc[-1])

    rng = resistance - support
    if rng <= 0:
        position = None
    else:
        position = float((price - support) / rng)
        position = max(0.0, min(1.0, position))

    dist_sup = float((price - support) / price * 100.0) if price else None
    dist_res = float((resistance - price) / price * 100.0) if price else None

    return {
        "support": round(support, 6),
        "resistance": round(resistance, 6),
        "position_in_range": None if position is None else round(position, 4),
        "dist_to_support_pct": None if dist_sup is None else round(dist_sup, 4),
        "dist_to_resistance_pct": None if dist_res is None else round(dist_res, 4),
    }


def _compute_features(df: pd.DataFrame) -> Dict[str, Any]:
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    price = float(close.iloc[-1])

    feats: Dict[str, Any] = {"price": round(price, 6), "candles": int(len(df))}

    # ADX / RSI / MACD / ATR (TA-Lib)
    adx = rsi = macd_hist = macd_hist_slope = atr = None
    if _HAS_TALIB:
        try:
            adx_arr = talib.ADX(high.values.astype(float), low.values.astype(float),
                                close.values.astype(float), timeperiod=14)
            adx = _safe_last(adx_arr)
        except Exception:
            adx = None
        try:
            rsi = _safe_last(talib.RSI(close.values.astype(float), timeperiod=RSI_PERIOD))
        except Exception:
            rsi = None
        try:
            _, _, hist = talib.MACD(close.values.astype(float),
                                    fastperiod=12, slowperiod=26, signalperiod=9)
            hist_clean = hist[~np.isnan(hist)]
            macd_hist = float(hist_clean[-1]) if len(hist_clean) else None
            if len(hist_clean) >= 4:
                macd_hist_slope = float(hist_clean[-1] - hist_clean[-4]) / 3.0
        except Exception:
            macd_hist = macd_hist_slope = None
        try:
            atr = _safe_last(talib.ATR(high.values.astype(float), low.values.astype(float),
                                       close.values.astype(float), timeperiod=ATR_PERIOD))
        except Exception:
            atr = None

    ema_slope = _ema_slope_pct(close, EMA_PERIOD)
    atr_pct = float(atr / price * 100.0) if (atr and price) else None
    atr_pctl = _atr_percentile(df, ATR_PERIOD)
    autocorr = _return_autocorr(close)

    # 布林带宽
    bb_width_pct = None
    if len(close) >= BB_PERIOD:
        mid = close.rolling(BB_PERIOD).mean()
        std = close.rolling(BB_PERIOD).std()
        upper = mid + BB_STD * std
        lower = mid - BB_STD * std
        if mid.iloc[-1] and not np.isnan(mid.iloc[-1]) and mid.iloc[-1] != 0:
            bb_width_pct = float((upper.iloc[-1] - lower.iloc[-1]) / mid.iloc[-1] * 100.0)

    sr = _support_resistance(df)

    feats.update({
        "adx": None if adx is None else round(adx, 2),
        "ema20_slope_pct": None if ema_slope is None else round(ema_slope, 4),
        "atr": None if atr is None else round(atr, 6),
        "atr_pct": None if atr_pct is None else round(atr_pct, 4),
        "atr_percentile": None if atr_pctl is None else round(atr_pctl, 3),
        "bb_width_pct": None if bb_width_pct is None else round(bb_width_pct, 4),
        "ret_autocorr_lag1": None if autocorr is None else round(autocorr, 4),
        "rsi": None if rsi is None else round(rsi, 2),
        "macd_hist": None if macd_hist is None else round(macd_hist, 6),
        "macd_hist_slope": None if macd_hist_slope is None else round(macd_hist_slope, 6),
    })
    feats.update(sr)
    return feats


# ============================ 制度分类与打分 ============================
def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _classify(feats: Dict[str, Any]) -> Dict[str, Any]:
    adx = feats.get("adx")
    ema_slope = feats.get("ema20_slope_pct")
    atr_pct = feats.get("atr_pct")
    autocorr = feats.get("ret_autocorr_lag1")
    rsi = feats.get("rsi")
    macd_hist = feats.get("macd_hist")
    pos = feats.get("position_in_range")

    # --- 判定趋势方向 ---
    trend_dir = 0
    if ema_slope is not None:
        if ema_slope >= EMA_SLOPE_MIN_PCT:
            trend_dir = 1
        elif ema_slope <= -EMA_SLOPE_MIN_PCT:
            trend_dir = -1

    is_trend = (adx is not None and adx >= ADX_TREND and trend_dir != 0)
    # 高波动无结构：ATR 占价百分比高且非趋势（不再要求斜率为 0，避免混沌市被当成区间）
    high_vol_no_structure = (
        atr_pct is not None and atr_pct >= ATR_HIGH_PCT
        and (adx is None or adx < ADX_TREND)
    )

    regime = "UNKNOWN"
    bias = "ABSTAIN"
    direction = "NONE"
    edge = 0.0

    if adx is None:
        regime, bias, direction, edge = "UNKNOWN", "ABSTAIN", "NONE", 0.0

    elif is_trend:
        regime = "TREND_UP" if trend_dir > 0 else "TREND_DOWN"
        bias = "FOLLOW_UP" if trend_dir > 0 else "FOLLOW_DOWN"
        direction = "LONG" if trend_dir > 0 else "SHORT"
        # edge: 趋势强度 + 动量一致 + 回调入场机会
        strength = _clamp((adx - ADX_TREND) / 25.0)
        mom_align = 0.0
        if macd_hist is not None:
            mom_align = 1.0 if (macd_hist > 0) == (trend_dir > 0) else 0.0
        pullback = 0.0
        if pos is not None:
            # 顺势时，价格回到区间下半部(多)/上半部(空)视为更好的入场
            pullback = (1.0 - pos) if trend_dir > 0 else pos
        # RSI 过度反向惩罚（追高/杀跌）
        rsi_pen = 0.0
        if rsi is not None:
            if trend_dir > 0 and rsi >= RSI_OB:
                rsi_pen = 0.3
            elif trend_dir < 0 and rsi <= RSI_OS:
                rsi_pen = 0.3
        edge = _clamp(0.45 * strength + 0.25 * mom_align + 0.30 * pullback - rsi_pen)

    elif high_vol_no_structure:
        regime, bias, direction, edge = "HIGH_VOL", "ABSTAIN", "NONE", 0.0

    else:
        # 兜底：非趋势、非混沌 → 区间震荡，默认反手 (FADE)。
        regime = "RANGE"
        bias = "FADE"
        # 区间反手：近阻力做空、近支撑做多、中间弃权
        range_clarity = _clamp((ADX_RANGE - (adx if adx is not None else ADX_RANGE)) / 15.0 + 0.3)
        mr_conf = 0.0
        if autocorr is not None and autocorr < 0:
            mr_conf = _clamp(-autocorr * 2.0)  # 负自相关越强，均值回归越可靠
        if pos is not None and pos >= (1.0 - RANGE_NEAR_BOUNDARY):
            direction = "SHORT"
            proximity = _clamp((pos - (1.0 - RANGE_NEAR_BOUNDARY)) / RANGE_NEAR_BOUNDARY)
            rsi_conf = 1.0 if (rsi is not None and rsi >= RSI_OB) else 0.0
            edge = _clamp(0.40 * range_clarity + 0.30 * proximity + 0.15 * mr_conf + 0.15 * rsi_conf)
        elif pos is not None and pos <= RANGE_NEAR_BOUNDARY:
            direction = "LONG"
            proximity = _clamp((RANGE_NEAR_BOUNDARY - pos) / RANGE_NEAR_BOUNDARY)
            rsi_conf = 1.0 if (rsi is not None and rsi <= RSI_OS) else 0.0
            edge = _clamp(0.40 * range_clarity + 0.30 * proximity + 0.15 * mr_conf + 0.15 * rsi_conf)
        else:
            # 处于区间中部：无优势，倾向弃权
            direction = "NONE"
            edge = _clamp(0.15 * range_clarity)

    return {
        "regime": regime,
        "recommended_bias": bias,
        "suggested_direction": direction,
        "edge_score": round(float(edge), 3),
    }


# ============================ 报告渲染 ============================
_REGIME_CN = {
    "TREND_UP": "上升趋势",
    "TREND_DOWN": "下降趋势",
    "RANGE": "区间震荡",
    "HIGH_VOL": "高波动无结构",
    "UNKNOWN": "数据不足/未知",
}
_BIAS_CN = {
    "FOLLOW_UP": "顺势做多 (Follow the uptrend)",
    "FOLLOW_DOWN": "顺势做空 (Follow the downtrend)",
    "FADE": "区间反手 (Fade extremes / mean-revert)",
    "ABSTAIN": "建议弃权 (No edge, abstain)",
}


def _fmt(v: Any, suffix: str = "") -> str:
    if v is None:
        return "N/A"
    if isinstance(v, float):
        return f"{v}{suffix}"
    return f"{v}{suffix}"


def _render_report(feats: Dict[str, Any], cls: Dict[str, Any], time_frame: str = "") -> str:
    regime = cls["regime"]
    tf = f" | Timeframe: {time_frame}" if time_frame else ""
    lines = [
        f"### Market Regime Analysis (deterministic){tf}",
        f"- Regime: **{regime}** ({_REGIME_CN.get(regime, regime)})",
        f"- Recommended playbook: **{_BIAS_CN.get(cls['recommended_bias'], cls['recommended_bias'])}**",
        f"- Suggested direction: **{cls['suggested_direction']}**",
        f"- Edge score (0-1): **{cls['edge_score']}**",
        "",
        "**Quantitative features:**",
        f"- Price: {_fmt(feats.get('price'))}",
        f"- ADX(14): {_fmt(feats.get('adx'))}  (>=25 trend, <=20 range)",
        f"- EMA20 slope: {_fmt(feats.get('ema20_slope_pct'), '%')} per bar",
        f"- ATR(14): {_fmt(feats.get('atr'))}  ({_fmt(feats.get('atr_pct'), '%')} of price, percentile {_fmt(feats.get('atr_percentile'))})",
        f"- Bollinger width: {_fmt(feats.get('bb_width_pct'), '%')}",
        f"- Return autocorr(lag1): {_fmt(feats.get('ret_autocorr_lag1'))}  (>0 momentum, <0 mean-reversion)",
        f"- RSI(14): {_fmt(feats.get('rsi'))}",
        f"- MACD hist: {_fmt(feats.get('macd_hist'))} (slope {_fmt(feats.get('macd_hist_slope'))})",
        f"- Support: {_fmt(feats.get('support'))} | Resistance: {_fmt(feats.get('resistance'))}",
        f"- Position in range: {_fmt(feats.get('position_in_range'))}  (0=at support, 1=at resistance)",
        f"- Distance to support: {_fmt(feats.get('dist_to_support_pct'), '%')} | to resistance: {_fmt(feats.get('dist_to_resistance_pct'), '%')}",
    ]
    return "\n".join(lines)


# ============================ 对外主入口 ============================
def analyze_single(kline_data: Any, time_frame: str = "") -> Dict[str, Any]:
    """对单一周期做制度分析。"""
    df = _to_dataframe(kline_data)
    if df is None or len(df) < MIN_CANDLES:
        cls = {"regime": "UNKNOWN", "recommended_bias": "ABSTAIN",
               "suggested_direction": "NONE", "edge_score": 0.0}
        feats = {"candles": 0 if df is None else int(len(df))}
        report = (
            "### Market Regime Analysis (deterministic)\n"
            f"- Regime: **UNKNOWN** (insufficient data, need >= {MIN_CANDLES} candles)\n"
            "- Recommended playbook: **ABSTAIN**\n"
            "- Edge score (0-1): **0.0**"
        )
        return {**cls, "features": feats, "report": report}

    feats = _compute_features(df)
    cls = _classify(feats)
    report = _render_report(feats, cls, time_frame)
    return {**cls, "features": feats, "report": report}


def analyze_regime(kline_data: Any, time_frame: str = "") -> Dict[str, Any]:
    """
    统一入口：自动兼容单周期(list[dict]/DataFrame)与多周期(dict[tf->data])。

    多周期时：逐周期计算，并给出汇总（以最长周期定方向、edge 取加权）。
    """
    if _is_multi_tf(kline_data):
        per_tf: Dict[str, Any] = {}
        for tf_name, tf_data in kline_data.items():
            per_tf[tf_name] = analyze_single(tf_data, tf_name)

        if not per_tf:
            return analyze_single(None)

        # 汇总：方向以 edge 最高的周期为准；报告拼接全部周期
        best_tf = max(per_tf.items(), key=lambda kv: kv[1].get("edge_score", 0.0))
        summary = {
            "regime": best_tf[1]["regime"],
            "recommended_bias": best_tf[1]["recommended_bias"],
            "suggested_direction": best_tf[1]["suggested_direction"],
            "edge_score": best_tf[1]["edge_score"],
        }
        report_parts = ["### Multi-Timeframe Regime Analysis (deterministic)",
                        f"- Dominant timeframe (highest edge): **{best_tf[0]}**", ""]
        for tf_name, res in per_tf.items():
            report_parts.append(f"--- [{tf_name}] ---")
            report_parts.append(res["report"])
            report_parts.append("")
        return {
            **summary,
            "features": {tf: res["features"] for tf, res in per_tf.items()},
            "per_timeframe": {tf: {k: res[k] for k in
                                   ("regime", "recommended_bias", "suggested_direction", "edge_score")}
                              for tf, res in per_tf.items()},
            "report": "\n".join(report_parts),
        }

    return analyze_single(kline_data, time_frame)
