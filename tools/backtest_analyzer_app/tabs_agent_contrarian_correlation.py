"""
Tab 6 (Agent表现), Tab 7 (逆势波动), Tab 8 (关联分析) render functions
for the Streamlit backtest analyzer.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .data_loader import safe_col


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_match_values(series: pd.Series) -> dict:
    """Count 是/否/空 for an agent match column and compute hit rate."""
    yes = int((series == "是").sum())
    no = int((series == "否").sum())
    empty = int(series.isna().sum() + (series == "").sum())
    total_yes_no = yes + no
    hit_rate = yes / total_yes_no if total_yes_no > 0 else 0.0
    return {
        "是": yes,
        "否": no,
        "空": empty,
        "命中率": round(hit_rate * 100, 2),
    }


# ---------------------------------------------------------------------------
# Tab 6 – Agent 表现
# ---------------------------------------------------------------------------

def render_tab6_agents(df: pd.DataFrame) -> None:
    """Tab 6: Agent表现 — match rates, score distributions, consistency analysis."""
    st.header("🤖 Agent 表现")

    agent_names = [
        ("indicator", "指标 Agent"),
        ("structure", "结构 Agent"),
        ("mechanics", "力学 Agent"),
        ("fusion", "融合 Agent"),
    ]

    match_cols = [f"{key}_匹配" for key, _ in agent_names]
    score_cols = [f"{key}_score" for key, _ in agent_names]

    has_any_match = any(col in df.columns for col in match_cols)
    has_any_score = any(col in df.columns for col in score_cols)

    if not has_any_match and not has_any_score:
        st.info("Agent 匹配数据不可用 — CSV 中缺少所有 Agent 匹配列和分数列。")
        return

    # ------------------------------------------------------------------
    # Agent Match Metrics Table
    # ------------------------------------------------------------------
    if has_any_match:
        st.subheader("Agent 匹配命中率")

        rows = []
        for key, label in agent_names:
            col = f"{key}_匹配"
            if col in df.columns:
                s = safe_col(df, col, default_dtype=str)
                stats = _count_match_values(s)
                rows.append({
                    "Agent": label,
                    "是": stats["是"],
                    "否": stats["否"],
                    "空": stats["空"],
                    "命中率 (%)": stats["命中率"],
                })
            else:
                rows.append({
                    "Agent": label,
                    "是": "—",
                    "否": "—",
                    "空": "—",
                    "命中率 (%)": "—",
                })

        metrics_df = pd.DataFrame(rows)
        st.dataframe(metrics_df, use_container_width=True, hide_index=True)

        # --------------------------------------------------------------
        # Consistency Analysis
        # --------------------------------------------------------------
        st.subheader("一致性分析")

        match_series = {}
        for key, _ in agent_names:
            col = f"{key}_匹配"
            if col in df.columns:
                s = safe_col(df, col, default_dtype=str)
                match_series[key] = (s == "是").astype(int)
            else:
                match_series[key] = pd.Series(0, index=df.index)

        consistency = (
            match_series["indicator"]
            + match_series["structure"]
            + match_series["mechanics"]
            + match_series["fusion"]
        )

        def _consistency_label(c: int) -> str:
            if c == 4:
                return "4/4 一致"
            elif c == 3:
                return "3/4 一致"
            elif c == 2:
                return "2/4 一致"
            else:
                return "≤1/4 一致"

        group_order = ["4/4 一致", "3/4 一致", "2/4 一致", "≤1/4 一致"]

        if "is_correct_1" in df.columns:
            correct = pd.to_numeric(df["is_correct_1"], errors="coerce")
            analysis_rows = []
            for label in group_order:
                mask = consistency.apply(lambda x: _consistency_label(x)) == label
                count = int(mask.sum())
                win_rate = correct[mask].mean() if count > 0 else 0.0
                analysis_rows.append({
                    "一致性": label,
                    "交易数": count,
                    "胜率": round(win_rate * 100, 2),
                })

            analysis_df = pd.DataFrame(analysis_rows)
            analysis_df["排序"] = analysis_df["一致性"].apply(
                lambda x: group_order.index(x)
            )
            analysis_df = analysis_df.sort_values("排序").drop(columns=["排序"])

            col_table, col_chart = st.columns(2)
            with col_table:
                st.dataframe(analysis_df, use_container_width=True, hide_index=True)

            with col_chart:
                fig_consistency = px.bar(
                    analysis_df,
                    x="一致性",
                    y="胜率",
                    text="交易数",
                    title="一致性 vs 胜率",
                    labels={"胜率": "胜率 (%)"},
                    color="一致性",
                    category_orders={"一致性": group_order},
                )
                fig_consistency.update_traces(textposition="outside")
                st.plotly_chart(fig_consistency, use_container_width=True)
        else:
            st.warning("缺少 `is_correct_1` 列，无法计算一致性胜率。")
    else:
        st.info("Agent 匹配数据不可用 — CSV 中缺少 Agent 匹配列。")

    # ------------------------------------------------------------------
    # Score Distribution Histograms
    # ------------------------------------------------------------------
    if has_any_score:
        st.subheader("Agent 分数分布")

        available_scores = [
            (key, label)
            for key, label in agent_names
            if f"{key}_score" in df.columns
        ]

        if available_scores:
            n = len(available_scores)
            if n <= 2:
                rows_cnt, cols_cnt = 1, n
            elif n == 3:
                rows_cnt, cols_cnt = 2, 2
            else:
                rows_cnt, cols_cnt = 2, 2

            subplot_titles = [label for _, label in available_scores]
            # Pad titles if using 2×2 but fewer than 4
            while len(subplot_titles) < rows_cnt * cols_cnt:
                subplot_titles.append("")

            fig_scores = make_subplots(
                rows=rows_cnt,
                cols=cols_cnt,
                subplot_titles=subplot_titles,
                shared_xaxes=True,
            )

            for idx, (key, label) in enumerate(available_scores):
                col = f"{key}_score"
                s = safe_col(df, col, default_dtype=float)
                valid = s.dropna()

                row = (idx // cols_cnt) + 1
                col_pos = (idx % cols_cnt) + 1

                if len(valid) > 0:
                    fig_scores.add_trace(
                        go.Histogram(
                            x=valid,
                            name=label,
                            nbinsx=30,
                            showlegend=False,
                        ),
                        row=row,
                        col=col_pos,
                    )

            fig_scores.update_layout(
                height=500,
                title_text="Agent 分数分布直方图",
                showlegend=False,
            )
            st.plotly_chart(fig_scores, use_container_width=True)
        else:
            st.info("没有可用的 Agent 分数列。")
    else:
        st.info("Agent 分数据不可用 — CSV 中缺少所有 Agent 分数列。")


# ---------------------------------------------------------------------------
# Tab 7 – 逆势波动
# ---------------------------------------------------------------------------

def render_tab7_contrarian(df: pd.DataFrame) -> None:
    """Tab 7: 逆势波动 — deviation analysis: win rate, histogram, scatter."""
    st.header("📉 逆势波动")

    col_has_dev = "逆势_有偏离"
    col_dev_count = "逆势_偏离次数"
    col_dev_max = "逆势_最大偏离%"

    if col_has_dev not in df.columns:
        st.info("逆势波动数据不可用 — CSV 中缺少 `逆势_有偏离` 列。")
        return

    # ------------------------------------------------------------------
    # Deviation vs Clean Win Rate Comparison
    # ------------------------------------------------------------------
    st.subheader("偏离 vs 干净组胜率对比")

    dev_series = safe_col(df, col_has_dev, default_dtype=str)

    if "is_correct_1" in df.columns:
        correct = pd.to_numeric(df["is_correct_1"], errors="coerce")

        dev_mask = dev_series == "是"
        clean_mask = dev_series == "否"

        dev_win_rate = correct[dev_mask].mean() if dev_mask.sum() > 0 else 0.0
        clean_win_rate = correct[clean_mask].mean() if clean_mask.sum() > 0 else 0.0
        dev_count = int(dev_mask.sum())
        clean_count = int(clean_mask.sum())

        compare_data = pd.DataFrame([
            {"组别": "有偏离", "胜率": round(dev_win_rate * 100, 2), "交易数": dev_count},
            {"组别": "干净组", "胜率": round(clean_win_rate * 100, 2), "交易数": clean_count},
        ])

        fig_bar = px.bar(
            compare_data,
            x="组别",
            y="胜率",
            text="交易数",
            title="偏离 vs 干净组胜率",
            labels={"胜率": "胜率 (%)"},
            color="组别",
        )
        fig_bar.update_traces(textposition="outside")
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.warning("缺少 `is_correct_1` 列，无法计算胜率。")

    # ------------------------------------------------------------------
    # Deviation Count Histogram
    # ------------------------------------------------------------------
    st.subheader("偏离次数分布")

    if col_dev_count in df.columns:
        count_series = safe_col(df, col_dev_count, default_dtype=float)
        count_valid = count_series.dropna()

        if len(count_valid) > 0:
            fig_hist = px.histogram(
                count_valid,
                nbins=20,
                title="逆势偏离次数分布",
                labels={"value": "偏离次数", "count": "频数"},
            )
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("`逆势_偏离次数` 列无有效数据。")
    else:
        st.info("缺少 `逆势_偏离次数` 列。")

    # ------------------------------------------------------------------
    # Deviation Magnitude vs PnL Scatter
    # ------------------------------------------------------------------
    st.subheader("偏离幅度 vs 盈亏")

    has_max = col_dev_max in df.columns
    has_profit = "profit_pct_1" in df.columns
    has_correct = "is_correct_1" in df.columns

    if has_max and has_profit:
        max_series = safe_col(df, col_dev_max, default_dtype=float)
        profit_series = safe_col(df, "profit_pct_1", default_dtype=float)

        valid_mask = max_series.notna() & profit_series.notna()

        if valid_mask.sum() > 0:
            scatter_df = pd.DataFrame({
                "逆势_最大偏离%": max_series[valid_mask],
                "profit_pct_1": profit_series[valid_mask],
            })

            if has_correct:
                correct_vals = pd.to_numeric(df["is_correct_1"], errors="coerce")
                scatter_df["is_correct_1"] = (
                    correct_vals[valid_mask]
                    .map({1: "正确", 0: "错误"})
                    .fillna("未知")
                )
                color_col = "is_correct_1"
            else:
                color_col = None

            fig_scatter = px.scatter(
                scatter_df,
                x="逆势_最大偏离%",
                y="profit_pct_1",
                color=color_col,
                title="偏离幅度 vs 盈亏百分比",
                labels={
                    "逆势_最大偏离%": "最大偏离 (%)",
                    "profit_pct_1": "盈亏 (%)",
                },
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.info("`逆势_最大偏离%` 与 `profit_pct_1` 无有效交集数据。")
    else:
        missing = []
        if not has_max:
            missing.append(col_dev_max)
        if not has_profit:
            missing.append("profit_pct_1")
        st.info(f"缺少列: {', '.join(missing)}，跳过散点图。")


# ---------------------------------------------------------------------------
# Tab 8 – 关联分析
# ---------------------------------------------------------------------------

def render_tab8_correlation(df: pd.DataFrame) -> None:
    """Tab 8: 关联分析 — scatter plots, box plot, correlation heatmap."""
    st.header("🔗 关联分析")

    has_fusion = "fusion_score" in df.columns
    has_profit = "profit_pct_1" in df.columns
    has_correct = "is_correct_1" in df.columns
    has_confidence = "fusion_confidence" in df.columns
    has_indicator = "indicator_score" in df.columns

    # ------------------------------------------------------------------
    # Scatter: fusion_score vs profit_pct_1
    # ------------------------------------------------------------------
    st.subheader("融合分数 vs 盈亏")

    if has_fusion and has_profit:
        fusion_vals = safe_col(df, "fusion_score", default_dtype=float)
        profit_vals = safe_col(df, "profit_pct_1", default_dtype=float)
        valid = fusion_vals.notna() & profit_vals.notna()

        if valid.sum() > 0:
            scatter_df = pd.DataFrame({
                "fusion_score": fusion_vals[valid],
                "profit_pct_1": profit_vals[valid],
            })
            if has_correct:
                correct_vals = pd.to_numeric(df["is_correct_1"], errors="coerce")
                scatter_df["is_correct_1"] = (
                    correct_vals[valid]
                    .map({1: "正确", 0: "错误"})
                    .fillna("未知")
                )

            fig_fusion_pnl = px.scatter(
                scatter_df,
                x="fusion_score",
                y="profit_pct_1",
                color="is_correct_1" if has_correct else None,
                title="Fusion Score vs 盈亏",
                labels={
                    "fusion_score": "融合分数",
                    "profit_pct_1": "盈亏 (%)",
                },
            )
            st.plotly_chart(fig_fusion_pnl, use_container_width=True)
        else:
            st.info("`fusion_score` 与 `profit_pct_1` 无有效交集数据。")
    else:
        missing = []
        if not has_fusion:
            missing.append("fusion_score")
        if not has_profit:
            missing.append("profit_pct_1")
        st.info(f"缺少列: {', '.join(missing)}，跳过散点图。")

    # ------------------------------------------------------------------
    # Box Plot: fusion_confidence vs is_correct_1
    # ------------------------------------------------------------------
    st.subheader("置信度 vs 结果")

    if has_confidence and has_correct:
        conf_vals = safe_col(df, "fusion_confidence", default_dtype=float)
        correct_vals = pd.to_numeric(df["is_correct_1"], errors="coerce")
        valid = conf_vals.notna() & correct_vals.notna()

        if valid.sum() > 0:
            box_df = pd.DataFrame({
                "fusion_confidence": conf_vals[valid],
                "结果": (
                    correct_vals[valid]
                    .map({1: "正确", 0: "错误"})
                    .fillna("未知")
                ),
            })
            fig_box = px.box(
                box_df,
                x="结果",
                y="fusion_confidence",
                title="置信度 vs 预测结果",
                labels={
                    "fusion_confidence": "融合置信度",
                    "结果": "预测结果",
                },
            )
            st.plotly_chart(fig_box, use_container_width=True)
        else:
            st.info("`fusion_confidence` 与 `is_correct_1` 无有效交集数据。")
    else:
        missing = []
        if not has_confidence:
            missing.append("fusion_confidence")
        if not has_correct:
            missing.append("is_correct_1")
        st.info(f"缺少列: {', '.join(missing)}，跳过箱线图。")

    # ------------------------------------------------------------------
    # Scatter: indicator_score vs fusion_score
    # ------------------------------------------------------------------
    st.subheader("指标分数 vs 融合分数")

    if has_indicator and has_fusion:
        ind_vals = safe_col(df, "indicator_score", default_dtype=float)
        fusion_vals_2 = safe_col(df, "fusion_score", default_dtype=float)
        valid = ind_vals.notna() & fusion_vals_2.notna()

        if valid.sum() > 0:
            comp_df = pd.DataFrame({
                "indicator_score": ind_vals[valid],
                "fusion_score": fusion_vals_2[valid],
            })
            fig_comp = px.scatter(
                comp_df,
                x="indicator_score",
                y="fusion_score",
                title="指标分数 vs 融合分数",
                labels={
                    "indicator_score": "指标分数",
                    "fusion_score": "融合分数",
                },
            )
            st.plotly_chart(fig_comp, use_container_width=True)
        else:
            st.info("`indicator_score` 与 `fusion_score` 无有效交集数据。")
    else:
        missing = []
        if not has_indicator:
            missing.append("indicator_score")
        if not has_fusion:
            missing.append("fusion_score")
        st.info(f"缺少列: {', '.join(missing)}，跳过散点图。")

    # ------------------------------------------------------------------
    # Correlation Heatmap
    # ------------------------------------------------------------------
    st.subheader("相关性热力图")

    numeric_df = df.select_dtypes(include=[np.number]).copy()

    # Ensure is_correct_1/2 are numeric even if stored as bool/object
    for col in ["is_correct_1", "is_correct_2"]:
        if col in df.columns and col not in numeric_df.columns:
            numeric_df[col] = pd.to_numeric(df[col], errors="coerce")

    if len(numeric_df.columns) >= 2:
        corr_matrix = numeric_df.corr()

        fig_heat = px.imshow(
            corr_matrix,
            text_auto=".2f",
            aspect="auto",
            title="数值列相关性热力图",
            color_continuous_scale="RdBu_r",
            zmin=-1,
            zmax=1,
        )
        fig_heat.update_layout(height=700)
        st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.info("数值列不足（需要至少 2 列），无法生成相关性热力图。")
