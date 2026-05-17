"""
Tab 3 (币种分析), Tab 4 (周期分析), Tab 5 (分数分析) render functions.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .data_loader import safe_col


def render_tab3_asset(df: pd.DataFrame) -> None:
    """Render Tab 3: 币种分析 — win rate, trade volume, PnL by asset."""
    st.subheader("币种分析")

    asset = safe_col(df, "asset", str)
    is_correct = safe_col(df, "is_correct_1", float)
    profit_pct = safe_col(df, "profit_pct_1", float)

    # Build grouping DataFrame
    group_df = pd.DataFrame({
        "asset": asset,
        "is_correct_1": is_correct,
        "profit_pct_1": profit_pct,
    })

    grouped = group_df.groupby("asset").agg(
        win_rate=("is_correct_1", "mean"),
        trade_count=("is_correct_1", "count"),
        avg_pnl_pct=("profit_pct_1", "mean"),
    ).reset_index()

    grouped = grouped.sort_values("win_rate", ascending=False)
    grouped["win_rate"] = grouped["win_rate"].round(4)
    grouped["avg_pnl_pct"] = grouped["avg_pnl_pct"].round(4)

    # Table
    st.markdown("#### 币种汇总表")
    st.dataframe(
        grouped.rename(columns={
            "asset": "币种",
            "win_rate": "胜率",
            "trade_count": "交易次数",
            "avg_pnl_pct": "平均盈亏%",
        }),
        use_container_width=True,
        hide_index=True,
    )

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### 胜率柱状图 (Top 20)")
        top20 = grouped.head(20)
        fig_bar = px.bar(
            top20,
            x="asset",
            y="win_rate",
            color="win_rate",
            color_continuous_scale="Blues",
            labels={"asset": "币种", "win_rate": "胜率"},
        )
        fig_bar.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_right:
        st.markdown("#### 交易量分布")
        trade_counts = asset.value_counts().reset_index()
        trade_counts.columns = ["asset", "count"]
        fig_pie = px.pie(
            trade_counts,
            names="asset",
            values="count",
            labels={"asset": "币种", "count": "交易次数"},
        )
        st.plotly_chart(fig_pie, use_container_width=True)


def render_tab4_timeframe(df: pd.DataFrame) -> None:
    """Render Tab 4: 周期分析 — win rate and trade count by timeframe."""
    st.subheader("周期分析")

    timeframe = safe_col(df, "timeframe", str)
    is_correct = safe_col(df, "is_correct_1", float)

    group_df = pd.DataFrame({
        "timeframe": timeframe,
        "is_correct_1": is_correct,
    })

    grouped = group_df.groupby("timeframe").agg(
        win_rate=("is_correct_1", "mean"),
        trade_count=("is_correct_1", "count"),
    ).reset_index()

    grouped["win_rate"] = grouped["win_rate"].round(4)

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### 各周期胜率")
        fig_winrate = px.bar(
            grouped,
            x="timeframe",
            y="win_rate",
            color="win_rate",
            color_continuous_scale="Greens",
            labels={"timeframe": "周期", "win_rate": "胜率"},
        )
        st.plotly_chart(fig_winrate, use_container_width=True)

    with col_right:
        st.markdown("#### 交易次数分布")
        fig_count = px.bar(
            grouped,
            x="timeframe",
            y="trade_count",
            color="trade_count",
            color_continuous_scale="Oranges",
            labels={"timeframe": "周期", "trade_count": "交易次数"},
        )
        st.plotly_chart(fig_count, use_container_width=True)

    st.markdown("#### 周期统计表")
    st.dataframe(
        grouped.rename(columns={
            "timeframe": "周期",
            "win_rate": "胜率",
            "trade_count": "交易次数",
        }),
        use_container_width=True,
        hide_index=True,
    )


def _bin_scores(series: pd.Series, bucket: float = 0.05) -> pd.Series:
    """Round scores to nearest bucket interval."""
    return (series / bucket).round() * bucket


_SCORE_COLUMNS = [
    "fusion_score",
    "indicator_score",
    "structure_score",
    "mechanics_score",
]

_SCORE_LABELS = {
    "fusion_score": "融合评分",
    "indicator_score": "指标评分",
    "structure_score": "结构评分",
    "mechanics_score": "机械评分",
}

_SCORE_COLORS = {
    "fusion_score": "#1f77b4",
    "indicator_score": "#ff7f0e",
    "structure_score": "#2ca02c",
    "mechanics_score": "#d62728",
}


def render_tab5_scores(df: pd.DataFrame) -> None:
    """Render Tab 5: 分数分析 — win rate by score bins for 4 score types."""
    st.subheader("分数分析")

    is_correct = safe_col(df, "is_correct_1", float)
    has_data = False

    fig = go.Figure()

    for col in _SCORE_COLUMNS:
        if col not in df.columns:
            continue

        scores = safe_col(df, col, float)
        if scores.isna().all() or (scores == 0).all():
            continue

        binned = _bin_scores(scores)
        win_rate_by_bin = (
            pd.DataFrame({"bin": binned, "is_correct": is_correct})
            .groupby("bin")["is_correct"]
            .mean()
            .reset_index()
        )
        win_rate_by_bin.columns = ["score_bin", "win_rate"]

        fig.add_trace(
            go.Scatter(
                x=win_rate_by_bin["score_bin"],
                y=win_rate_by_bin["win_rate"],
                mode="lines+markers",
                name=_SCORE_LABELS.get(col, col),
                line=dict(color=_SCORE_COLORS.get(col, "#333333")),
            )
        )
        has_data = True

    if not has_data:
        st.info("没有可用的评分列数据。")
        return

    fig.update_layout(
        xaxis_title="评分区间 (0.05 分档)",
        yaxis_title="胜率",
        legend_title="评分类型",
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)
