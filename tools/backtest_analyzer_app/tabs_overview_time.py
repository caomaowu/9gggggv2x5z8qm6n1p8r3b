"""
回测分析工具 — Tab 1 (总览) 和 Tab 2 (时间分析)。

依赖：
- data_loader.safe_col  安全读取列
- plotly 用于所有图表
- streamlit 用于 UI 组件
"""

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .data_loader import safe_col


# ═══════════════════════════════════════════════════════════════════════
# 通用工具
# ═══════════════════════════════════════════════════════════════════════

_WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
_SESSION_LABELS = {
    "亚盘": (0, 8),
    "欧盘": (8, 16),
    "美盘": (16, 24),
}


def _fmt_pct(value: float) -> str:
    """格式化百分比，保留一位小数。"""
    if pd.isna(value):
        return "N/A"
    return f"{value:.1f}%"


def _fmt_pct2(value: float) -> str:
    """格式化百分比（两位小数，用于盈亏）。"""
    if pd.isna(value):
        return "N/A"
    return f"{value:.2f}%"


# ═══════════════════════════════════════════════════════════════════════
# Tab 1 — 总览
# ═══════════════════════════════════════════════════════════════════════

def render_tab1_overview(df: pd.DataFrame) -> None:
    """渲染 Tab 1：总览。

    包含：
    - 6 个指标卡片（总交易数、K1/K2 胜率、平均盈亏%、最大盈亏%）
    - 资金曲线折线图
    - K1/K2 滚动胜率曲线（窗口=20）
    """
    if df is None or df.empty:
        st.info("请先加载回测数据。")
        return

    st.subheader("📊 总览")

    # ── 指标卡片 ──────────────────────────────────────────────────────
    total_trades = len(df)

    # K1 胜率
    k1_col = safe_col(df, "is_correct_1", bool)
    k1_valid = k1_col.dropna()
    k1_wr = k1_valid.mean() * 100 if len(k1_valid) > 0 else 0.0

    # K2 胜率
    k2_col = safe_col(df, "is_correct_2", bool)
    k2_valid = k2_col.dropna()
    k2_wr = k2_valid.mean() * 100 if len(k2_valid) > 0 else 0.0

    # 平均盈亏%
    pnl_col = safe_col(df, "本次盈亏百分比", float)
    pnl_valid = pnl_col.dropna()
    avg_pnl = pnl_valid.mean() if len(pnl_valid) > 0 else 0.0

    # 最大单笔盈利 / 最大单笔亏损（取 profit_pct_1/2 的极值）
    p1 = safe_col(df, "profit_pct_1", float).dropna()
    p2 = safe_col(df, "profit_pct_2", float).dropna()
    combined = pd.concat([p1, p2])
    max_profit = float(combined.max()) if len(combined) > 0 else 0.0
    max_loss = float(combined.min()) if len(combined) > 0 else 0.0

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("总交易数", total_trades)
    col_b.metric("K1 胜率", _fmt_pct(k1_wr))
    col_c.metric("K2 胜率", _fmt_pct(k2_wr))

    col_d, col_e, col_f = st.columns(3)
    col_d.metric("平均盈亏%", _fmt_pct2(avg_pnl))
    col_e.metric("最大单笔盈利%", _fmt_pct2(max_profit))
    col_f.metric("最大单笔亏损%", _fmt_pct2(max_loss))

    st.markdown("---")

    # ── 资金曲线 ──────────────────────────────────────────────────────
    st.subheader("💰 资金曲线")
    capital = safe_col(df, "资金_当前", float)
    if capital.notna().sum() >= 2:
        x_vals = list(range(len(capital)))

        fig_cap = go.Figure()
        fig_cap.add_trace(
            go.Scatter(
                x=x_vals,
                y=capital.values,
                mode="lines",
                name="资金",
                line={"color": "#1f77b4", "width": 2},
                fill="tozeroy",
                fillcolor="rgba(31,119,180,0.08)",
            )
        )
        fig_cap.update_layout(
            xaxis_title="交易序号",
            yaxis_title="资金",
            height=400,
            margin={"l": 40, "r": 20, "t": 20, "b": 40},
        )
        st.plotly_chart(fig_cap, use_container_width=True)
    else:
        st.info("无资金曲线数据（资金_当前 列缺失或为空）")

    # ── 滚动胜率曲线 ──────────────────────────────────────────────────
    st.subheader("📈 K1 / K2 滚动胜率（窗口 = 20 笔）")
    window = 20

    if total_trades < window:
        st.info(f"交易数 {total_trades} 少于窗口 {window}，无法计算滚动胜率")
        return

    k1_float = safe_col(df, "is_correct_1", bool).map(
        {True: 1.0, False: 0.0}, na_action="ignore"
    ).fillna(0)
    k2_float = safe_col(df, "is_correct_2", bool).map(
        {True: 1.0, False: 0.0}, na_action="ignore"
    ).fillna(0)

    k1_rolling = k1_float.rolling(window=window, min_periods=1).mean() * 100
    k2_rolling = k2_float.rolling(window=window, min_periods=1).mean() * 100

    fig_roll = go.Figure()
    fig_roll.add_trace(
        go.Scatter(
            x=list(range(len(k1_rolling))),
            y=k1_rolling.values,
            mode="lines",
            name="K1 胜率",
            line={"color": "#2ca02c", "width": 2},
        )
    )
    fig_roll.add_trace(
        go.Scatter(
            x=list(range(len(k2_rolling))),
            y=k2_rolling.values,
            mode="lines",
            name="K2 胜率",
            line={"color": "#ff7f0e", "width": 2},
        )
    )
    fig_roll.add_hline(
        y=50,
        line_dash="dash",
        line_color="gray",
        annotation_text="50%",
        annotation_position="bottom right",
    )
    fig_roll.update_layout(
        xaxis_title="交易序号",
        yaxis_title="胜率 (%)",
        height=400,
        margin={"l": 40, "r": 20, "t": 20, "b": 40},
        legend={"orientation": "h", "yanchor": "top", "y": 1.1, "xanchor": "left", "x": 0},
    )
    st.plotly_chart(fig_roll, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════
# Tab 2 — 时间分析
# ═══════════════════════════════════════════════════════════════════════

def _parse_hour_from_end_time(end_time_series: pd.Series) -> pd.Series:
    """从 end_time 字符串（如 "07:59", "23:59"）提取小时（整数）。"""
    hours = end_time_series.astype(str).str.strip().str.extract(r"^(\d{1,2}):")
    return pd.to_numeric(hours[0], errors="coerce")


def _get_session(hour: float) -> Optional[str]:
    """根据小时返回交易时段名称。"""
    if pd.isna(hour):
        return None
    h = int(hour)
    if 0 <= h < 8:
        return "亚盘 (00-08)"
    elif 8 <= h < 16:
        return "欧盘 (08-16)"
    else:
        return "美盘 (16-24)"


def _build_session_stats(df: pd.DataFrame) -> pd.DataFrame:
    """按时段分组统计胜率、交易数、平均盈亏%。"""
    hour_series = _parse_hour_from_end_time(df["end_time"])
    session_series = hour_series.apply(_get_session)

    k1 = safe_col(df, "is_correct_1", bool).map(
        {True: 1.0, False: 0.0}, na_action="ignore"
    )
    pnl = safe_col(df, "本次盈亏百分比", float)

    combined = pd.DataFrame(
        {
            "session": session_series,
            "is_correct_1": k1.values,
            "pnl_pct": pnl.values,
        }
    )
    # 丢弃 end_time 无效的行
    combined = combined.dropna(subset=["session"])

    if combined.empty:
        return pd.DataFrame()

    grouped = combined.groupby("session", observed=True).agg(
        trade_count=("is_correct_1", "count"),
        win_rate=("is_correct_1", "mean"),
        avg_pnl=("pnl_pct", "mean"),
    )
    grouped["win_rate"] = grouped["win_rate"] * 100
    grouped = grouped.round({"win_rate": 1, "avg_pnl": 2})
    grouped = grouped.sort_index()
    return grouped


def _build_hourly_winrate(df: pd.DataFrame) -> pd.DataFrame:
    """按小时分组统计 K1 胜率（0-23 小时）。"""
    hour_series = _parse_hour_from_end_time(
        safe_col(df, "end_time", str)
    )
    k1 = safe_col(df, "is_correct_1", bool).map(
        {True: 1.0, False: 0.0}, na_action="ignore"
    )

    combined = pd.DataFrame({"hour": hour_series, "is_correct_1": k1.values})
    combined["hour"] = pd.to_numeric(combined["hour"], errors="coerce")
    combined = combined.dropna(subset=["hour"])
    combined["hour"] = combined["hour"].astype(int)

    if combined.empty:
        return pd.DataFrame()

    hourly = combined.groupby("hour").agg(
        trade_count=("is_correct_1", "count"),
        win_rate=("is_correct_1", "mean"),
    )
    hourly["win_rate"] = hourly["win_rate"] * 100
    hourly = hourly.reindex(range(24), fill_value=0)
    hourly = hourly.round({"win_rate": 1})
    return hourly


def _build_weekday_stats(df: pd.DataFrame) -> pd.DataFrame:
    """按星期分组统计 K1 胜率。"""
    date_col = safe_col(df, "end_date", object)
    k1 = safe_col(df, "is_correct_1", bool).map(
        {True: 1.0, False: 0.0}, na_action="ignore"
    )

    # end_date 可能已经是 datetime 或字符串
    if pd.api.types.is_datetime64_any_dtype(date_col):
        dow = date_col.dt.dayofweek  # 0=Mon ... 6=Sun
    else:
        dow = pd.to_datetime(date_col, errors="coerce").dt.dayofweek

    combined = pd.DataFrame({"dayofweek": dow, "is_correct_1": k1.values})
    combined = combined.dropna(subset=["dayofweek"])

    if combined.empty:
        return pd.DataFrame()

    grouped = combined.groupby("dayofweek").agg(
        trade_count=("is_correct_1", "count"),
        win_rate=("is_correct_1", "mean"),
    )
    grouped["win_rate"] = grouped["win_rate"] * 100
    grouped = grouped.reindex(range(7), fill_value=0)
    grouped.index = _WEEKDAY_NAMES
    grouped = grouped.round({"win_rate": 1})
    return grouped


def render_tab2_time(df: pd.DataFrame) -> None:
    """渲染 Tab 2：时间分析。

    包含：
    - 时段分组表格（亚盘/欧盘/美盘）
    - 24 小时胜率柱状图
    - 周一至周日胜率对比柱状图
    """
    if df is None or df.empty:
        st.info("请先加载回测数据。")
        return

    st.subheader("⏰ 时间分析")

    # ── 时段分组表 ────────────────────────────────────────────────────
    session_stats = _build_session_stats(df)

    if session_stats.empty:
        st.warning("无法解析 end_time 字段，请检查数据格式。")
    else:
        st.markdown("#### 交易时段对比")
        # 格式化显示
        display_table = session_stats.copy()
        display_table["win_rate"] = display_table["win_rate"].apply(
            lambda x: _fmt_pct(x) if pd.notna(x) else "-"
        )
        display_table["avg_pnl"] = display_table["avg_pnl"].apply(
            lambda x: _fmt_pct2(x) if pd.notna(x) else "-"
        )
        display_table.columns = ["交易数", "K1 胜率", "平均盈亏%"]
        st.dataframe(display_table, use_container_width=True)

    st.markdown("---")

    # ── 24 小时胜率柱状图 ─────────────────────────────────────────────
    st.markdown("#### 24 小时胜率分布")
    hourly_stats = _build_hourly_winrate(df)

    if hourly_stats.empty:
        st.warning("无法生成小时级统计。")
    else:
        colors = [
            "#d62728" if wr < 50 else "#2ca02c"
            for wr in hourly_stats["win_rate"]
        ]
        fig_hourly = go.Figure()
        fig_hourly.add_trace(
            go.Bar(
                x=hourly_stats.index,
                y=hourly_stats["win_rate"],
                marker_color=colors,
                text=hourly_stats["win_rate"].apply(
                    lambda v: _fmt_pct(v) if v > 0 else ""
                ),
                textposition="outside",
                textfont={"size": 10},
            )
        )
        fig_hourly.add_hline(
            y=50,
            line_dash="dash",
            line_color="gray",
            annotation_text="50%",
            annotation_position="bottom right",
        )
        fig_hourly.update_layout(
            xaxis={"title": "小时 (UTC)", "tickmode": "linear", "dtick": 1},
            yaxis={"title": "K1 胜率 (%)"},
            height=400,
            margin={"l": 40, "r": 20, "t": 20, "b": 40},
        )
        st.plotly_chart(fig_hourly, use_container_width=True)

    st.markdown("---")

    # ── 星期胜率柱状图 ────────────────────────────────────────────────
    st.markdown("#### 星期胜率对比")
    weekday_stats = _build_weekday_stats(df)

    if weekday_stats.empty:
        st.warning("无法生成星期统计（end_date 解析失败）。")
    else:
        wd_colors = [
            "#2ca02c" if wr >= 50 else "#d62728"
            for wr in weekday_stats["win_rate"]
        ]
        fig_wd = go.Figure()
        fig_wd.add_trace(
            go.Bar(
                x=weekday_stats.index,
                y=weekday_stats["win_rate"],
                marker_color=wd_colors,
                text=weekday_stats.apply(
                    lambda row: (
                        f"{_fmt_pct(row['win_rate'])}\n({int(row['trade_count'])}笔)"
                        if row["trade_count"] > 0
                        else ""
                    ),
                    axis=1,
                ),
                textposition="outside",
                textfont={"size": 10},
            )
        )
        fig_wd.add_hline(
            y=50,
            line_dash="dash",
            line_color="gray",
            annotation_text="50%",
            annotation_position="bottom right",
        )
        fig_wd.update_layout(
            xaxis_title="星期",
            yaxis_title="K1 胜率 (%)",
            height=400,
            margin={"l": 40, "r": 20, "t": 20, "b": 40},
        )
        st.plotly_chart(fig_wd, use_container_width=True)
