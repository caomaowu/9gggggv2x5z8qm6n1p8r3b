"""
回测 CSV 分析工具 — Streamlit 主入口。

运行方式:
    streamlit run tools/backtest_analyzer.py

功能:
    - 自动扫描 tools/ 目录下的 .csv 文件
    - 10 个分析 Tab：总览、时间、币种、周期、分数、Agent、逆势、关联、交易模拟、自定义查询
"""
import os
import sys
from pathlib import Path

import streamlit as st

# 确保 tools/ 在 sys.path 中，支持子模块导入
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from backtest_analyzer_app.data_loader import load_csv_files, parse_backtest_csv
from backtest_analyzer_app.tabs_overview_time import render_tab1_overview, render_tab2_time
from backtest_analyzer_app.tabs_asset_timeframe_scores import (
    render_tab3_asset,
    render_tab4_timeframe,
    render_tab5_scores,
)
from backtest_analyzer_app.tabs_agent_contrarian_correlation import (
    render_tab6_agents,
    render_tab7_contrarian,
    render_tab8_correlation,
)
from backtest_analyzer_app.tabs_simulation_custom import (
    render_tab9_simulation,
    render_tab10_custom_query,
)


def _csv_display_name(filepath: str) -> str:
    """从绝对路径生成友好的显示名称。"""
    try:
        rel = os.path.relpath(filepath, TOOLS_DIR)
        return rel
    except ValueError:
        return os.path.basename(filepath)


def run_app() -> None:
    """Streamlit 主函数。"""
    st.set_page_config(
        page_title="回测分析工具",
        page_icon="📊",
        layout="wide",
    )

    st.markdown(
        """
        <style>
        html, body, [class*="css"] { font-size: 16px; }
        div[data-testid="stMetricValue"] { font-size: 24px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("📊 回测 CSV 分析工具")

    # ── 侧边栏：CSV 选择 ────────────────────────────────────────────
    st.sidebar.header("📁 数据源")

    # 扫描本地 CSV
    csv_files = load_csv_files()
    csv_options = {_csv_display_name(p): p for p in csv_files}

    # 上传选项
    uploaded_file = st.sidebar.file_uploader(
        "上传 CSV 文件",
        type=["csv"],
        help="支持从本地上传回测 CSV 文件",
    )

    selected_csv: str | None = None

    if uploaded_file is not None:
        # 保存上传文件到临时位置并加载
        temp_dir = Path(TOOLS_DIR) / ".temp"
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / f"_uploaded_{uploaded_file.name}"
        temp_path.write_bytes(uploaded_file.getvalue())
        selected_csv = str(temp_path)
        st.sidebar.success(f"已上传: {uploaded_file.name}")
    elif csv_options:
        display_name = st.sidebar.selectbox(
            "选择本地 CSV 文件",
            options=list(csv_options.keys()),
            index=0,
            help="自动扫描 tools/ 目录下的所有 CSV 文件",
        )
        selected_csv = csv_options[display_name]
    else:
        st.sidebar.warning("tools/ 目录下未找到 CSV 文件，请上传。")

    # 加载按钮
    if selected_csv:
        if st.sidebar.button("🔄 加载数据", type="primary", use_container_width=True):
            st.session_state["csv_path"] = selected_csv
            st.rerun()

    # ── 数据加载 ────────────────────────────────────────────────────
    csv_path = st.session_state.get("csv_path", None)

    if csv_path is None:
        st.info("👈 请在左侧选择或上传 CSV 文件，然后点击「加载数据」。")
        return

    st.sidebar.divider()
    st.sidebar.caption(f"当前文件: {os.path.basename(csv_path)}")

    df = parse_backtest_csv(csv_path)

    if df is None or df.empty:
        st.error("数据加载失败，请检查文件格式。")
        return

    st.sidebar.metric("数据行数", len(df))
    st.sidebar.metric("数据列数", len(df.columns))

    # ── Tab 导航 ────────────────────────────────────────────────────
    tab_labels = [
        "📊 总览",
        "🕐 时间分析",
        "🪙 币种分析",
        "⏱️ 周期分析",
        "🎯 分数分析",
        "🤖 Agent 表现",
        "📉 逆势波动",
        "🔗 关联分析",
        "💹 交易模拟",
        "🔍 自定义查询",
    ]

    tabs = st.tabs(tab_labels)

    with tabs[0]:
        render_tab1_overview(df)
    with tabs[1]:
        render_tab2_time(df)
    with tabs[2]:
        render_tab3_asset(df)
    with tabs[3]:
        render_tab4_timeframe(df)
    with tabs[4]:
        render_tab5_scores(df)
    with tabs[5]:
        render_tab6_agents(df)
    with tabs[6]:
        render_tab7_contrarian(df)
    with tabs[7]:
        render_tab8_correlation(df)
    with tabs[8]:
        render_tab9_simulation(df)
    with tabs[9]:
        render_tab10_custom_query(df)


if __name__ == "__main__":
    run_app()
