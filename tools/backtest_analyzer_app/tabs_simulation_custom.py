"""
Tab 9 (交易模拟) and Tab 10 (自定义查询) render functions.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from .data_loader import safe_col


def render_tab9_simulation(df: pd.DataFrame) -> None:
    """Render Tab 9: 交易模拟 — capital curve, drawdown, performance metrics."""
    st.subheader("交易模拟")

    capital_current = safe_col(df, "资金_当前", float)
    capital_initial = safe_col(df, "资金_初始", float)
    pnl_pct = safe_col(df, "本次盈亏百分比", float)
    pnl_raw = safe_col(df, "本次盈亏", float)

    # Pre-check: if capital columns are all missing or zero, show warning
    if capital_current.isna().all() or (capital_current == 0).all():
        st.warning("交易引擎数据不可用，可能为普通回测模式")
        return

    if pnl_pct.isna().all():
        st.warning("盈亏百分比数据不可用")
        return

    # Drop rows where capital is NaN to work with valid data only
    valid_mask = capital_current.notna() & (capital_current != 0)
    if not valid_mask.any():
        st.warning("无有效资金数据")
        return

    capital = capital_current[valid_mask].values
    pnl_pct_valid = pnl_pct[valid_mask].values
    pnl_raw_valid = pnl_raw[valid_mask].values

    # ---- Metrics ----
    # 总收益率
    init_cap = capital_initial[valid_mask].iloc[0] if capital_initial.notna().any() else capital[0]
    final_cap = capital[-1]
    total_return = ((final_cap - init_cap) / init_cap) * 100 if init_cap > 0 else 0.0

    # 最大回撤 — track running peak of capital
    running_peak = np.maximum.accumulate(capital)
    drawdown_series = (capital - running_peak) / running_peak  # negative values
    max_drawdown = np.min(drawdown_series) * 100  # as negative percentage

    # 夏普比率 — annualized from trade returns
    returns = pnl_pct_valid / 100.0  # convert percentage to decimal
    mean_ret = np.mean(returns)
    std_ret = np.std(returns, ddof=1)
    if std_ret > 0 and len(returns) > 1:
        sharpe_ratio = (mean_ret / std_ret) * np.sqrt(252)
    else:
        sharpe_ratio = float("nan")

    # 盈亏比 — mean(winning) / abs(mean(losing))
    winning_mask = returns > 0
    losing_mask = returns < 0
    if winning_mask.any() and losing_mask.any():
        mean_win = np.mean(returns[winning_mask])
        mean_loss = np.abs(np.mean(returns[losing_mask]))
        profit_factor = mean_win / mean_loss if mean_loss > 0 else float("nan")
    else:
        profit_factor = float("nan")

    # Display metrics in a 4-column row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总收益率", f"{total_return:.2f}%")
    with col2:
        st.metric("最大回撤", f"{max_drawdown:.2f}%", delta=None)
    with col3:
        st.metric("夏普比率", f"{sharpe_ratio:.2f}" if not np.isnan(sharpe_ratio) else "N/A")
    with col4:
        st.metric("盈亏比", f"{profit_factor:.2f}" if not np.isnan(profit_factor) else "N/A")

    # ---- Chart 1: 资金曲线 (含回撤阴影) ----
    st.markdown("#### 资金曲线 (含回撤阴影)")
    trade_indices = list(range(len(capital)))

    fig_capital = go.Figure()

    # Capital curve line
    fig_capital.add_trace(
        go.Scatter(
            x=trade_indices,
            y=capital,
            mode="lines",
            name="资金曲线",
            line=dict(color="#1f77b4", width=2),
        )
    )

    # Drawdown filled area (negative values below zero)
    fig_capital.add_trace(
        go.Scatter(
            x=trade_indices,
            y=drawdown_series * 100,  # percentage scale
            mode="none",
            fill="tozeroy",
            name="回撤 (%)",
            fillcolor="rgba(214, 39, 40, 0.3)",
            line=dict(color="rgba(214, 39, 40, 0)"),
        )
    )

    fig_capital.update_layout(
        xaxis_title="交易序号",
        yaxis_title="资金 / 回撤",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="top", y=-0.15),
    )

    st.plotly_chart(fig_capital, use_container_width=True)

    # ---- Chart 2: 盈亏分布直方图 ----
    st.markdown("#### 盈亏分布直方图")
    # Separate positive and negative trades
    pos_pnl = pnl_pct_valid[pnl_pct_valid >= 0]
    neg_pnl = pnl_pct_valid[pnl_pct_valid < 0]

    fig_hist = go.Figure()

    if len(pos_pnl) > 0:
        fig_hist.add_trace(
            go.Histogram(
                x=pos_pnl,
                name="盈利",
                marker_color="green",
                opacity=0.7,
                xbins=dict(size=0.5),
            )
        )
    else:
        # Ensure trace exists for legend even if empty
        fig_hist.add_trace(
            go.Histogram(
                x=[],
                name="盈利 (无数据)",
                marker_color="green",
                opacity=0.7,
            )
        )

    if len(neg_pnl) > 0:
        fig_hist.add_trace(
            go.Histogram(
                x=neg_pnl,
                name="亏损",
                marker_color="red",
                opacity=0.7,
                xbins=dict(size=0.5),
            )
        )
    else:
        fig_hist.add_trace(
            go.Histogram(
                x=[],
                name="亏损 (无数据)",
                marker_color="red",
                opacity=0.7,
            )
        )

    fig_hist.update_layout(
        xaxis_title="盈亏百分比 (%)",
        yaxis_title="交易次数",
        barmode="overlay",
        legend=dict(orientation="h", yanchor="top", y=-0.15),
    )

    st.plotly_chart(fig_hist, use_container_width=True)

    # ---- Chart 3: 累计盈亏曲线 ----
    st.markdown("#### 累计盈亏曲线")

    # Use raw PnL if available and not all zero/NaN, otherwise compute from percentage
    if pnl_raw_valid is not None and not (np.isnan(pnl_raw_valid).all() or (pnl_raw_valid == 0).all()):
        cumulative_pnl = np.cumsum(pnl_raw_valid)
    else:
        # Estimate raw PnL from percentage: PnL% = PnL_raw / capital * 100 → PnL_raw ≈ PnL% * capital / 100
        estimated_pnl = (pnl_pct_valid / 100.0) * capital
        cumulative_pnl = np.cumsum(estimated_pnl)

    fig_cum = go.Figure()
    fig_cum.add_trace(
        go.Scatter(
            x=trade_indices,
            y=cumulative_pnl,
            mode="lines",
            name="累计盈亏",
            line=dict(color="#2ca02c", width=2),
        )
    )
    # Add zero reference line
    fig_cum.add_hline(
        y=0,
        line=dict(color="gray", dash="dash"),
        annotation_text="零线",
    )
    fig_cum.update_layout(
        xaxis_title="交易序号",
        yaxis_title="累计盈亏",
        hovermode="x unified",
    )

    st.plotly_chart(fig_cum, use_container_width=True)


def render_tab10_custom_query(df: pd.DataFrame) -> None:
    """Render Tab 10: 自定义查询 — filter, view, and export trade data."""
    st.subheader("自定义查询")

    # ---- Filters ----
    st.markdown("### 筛选条件")

    # 日期范围
    end_date = safe_col(df, "end_date", str)
    parsed_dates = pd.to_datetime(end_date, errors="coerce")
    valid_dates = parsed_dates.dropna()

    if not valid_dates.empty:
        min_date = valid_dates.min().date()
        max_date = valid_dates.max().date()
        date_range = st.date_input(
            "日期范围",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
    else:
        st.info("end_date 列不可用，日期过滤跳过")
        date_range = None

    # 币种多选
    asset_col = safe_col(df, "asset", str)
    unique_assets = sorted(asset_col.dropna().unique().tolist())
    selected_assets = st.multiselect("币种", options=unique_assets, default=[])

    # 周期多选
    timeframe_col = safe_col(df, "timeframe", str)
    unique_timeframes = sorted(timeframe_col.dropna().unique().tolist())
    selected_timeframes = st.multiselect("周期", options=unique_timeframes, default=[])

    # fusion_score 范围滑块 — only if column exists
    if "fusion_score" in df.columns:
        fusion_col = safe_col(df, "fusion_score", float)
        fusion_min = float(fusion_col.min()) if not fusion_col.isna().all() else 0.0
        fusion_max = float(fusion_col.max()) if not fusion_col.isna().all() else 1.0
        if fusion_max > fusion_min or (fusion_max == fusion_min and fusion_max > 0):
            fusion_range = st.slider(
                "fusion_score 范围",
                min_value=0.0,
                max_value=1.0,
                value=(fusion_min, fusion_max),
                step=0.05,
            )
        else:
            fusion_range = None
    else:
        fusion_range = None

    # 逆势_有偏离过滤 — only if column exists
    if "逆势_有偏离" in df.columns:
        deviation_options = ["全部", "是", "否"]
        deviation_filter = st.selectbox("逆势_有偏离", options=deviation_options, index=0)
    else:
        deviation_filter = None

    # ---- Apply Filters ----
    filtered_df = df.copy()

    # Date filter
    if date_range is not None and not valid_dates.empty:
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date_val = date_range
            date_mask = (valid_dates.dt.date >= start_date) & (valid_dates.dt.date <= end_date_val)
            filtered_df = filtered_df.loc[date_mask].copy()

    # Asset filter
    if selected_assets:
        asset_mask = asset_col.isin(selected_assets)
        filtered_df = filtered_df.loc[asset_mask].copy()

    # Timeframe filter
    if selected_timeframes:
        tf_mask = timeframe_col.isin(selected_timeframes)
        filtered_df = filtered_df.loc[tf_mask].copy()

    # Fusion score range filter
    if fusion_range is not None:
        fusion_col = safe_col(filtered_df, "fusion_score", float)
        low, high = fusion_range
        fs_mask = (fusion_col >= low) & (fusion_col <= high)
        filtered_df = filtered_df.loc[fs_mask].copy()

    # Deviation filter
    if deviation_filter is not None and deviation_filter != "全部":
        dev_col = safe_col(filtered_df, "逆势_有偏离", str)
        dev_mask = dev_col == deviation_filter
        filtered_df = filtered_df.loc[dev_mask].copy()

    # ---- Output ----
    st.markdown("---")
    st.markdown("### 筛选结果")

    total_count = len(df)
    filtered_count = len(filtered_df)

    # Compute summary stats
    is_correct_col = safe_col(filtered_df, "is_correct_1", float)
    pnl_pct_col = safe_col(filtered_df, "profit_pct_1", float)

    if filtered_count > 0:
        win_rate = is_correct_col.mean() if not is_correct_col.isna().all() else 0.0
        avg_pnl = pnl_pct_col.mean() if not pnl_pct_col.isna().all() else 0.0
    else:
        win_rate = 0.0
        avg_pnl = 0.0

    # 统计摘要
    summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
    with summary_col1:
        st.metric("筛选后数量", filtered_count, delta=f"{filtered_count - total_count}" if filtered_count != total_count else None)
    with summary_col2:
        st.metric("总交易数", total_count)
    with summary_col3:
        st.metric("胜率", f"{win_rate:.2%}" if filtered_count > 0 else "N/A")
    with summary_col4:
        st.metric("平均盈亏%", f"{avg_pnl:.2f}%" if filtered_count > 0 else "N/A")

    # 筛选后数据表格
    st.markdown("#### 筛选后数据")
    if filtered_count > 0:
        st.dataframe(filtered_df, use_container_width=True)
    else:
        st.info("筛选结果为空，请调整筛选条件。")

    # 导出CSV按钮
    st.markdown("#### 导出")
    if filtered_count > 0:
        csv_data = filtered_df.to_csv(index=False)
        st.download_button(
            label=f"导出筛选结果 CSV ({filtered_count} 条)",
            data=csv_data,
            file_name="backtest_filtered.csv",
            mime="text/csv",
        )
    else:
        st.download_button(
            label="导出筛选结果 CSV",
            data="",
            file_name="backtest_filtered.csv",
            mime="text/csv",
            disabled=True,
        )
